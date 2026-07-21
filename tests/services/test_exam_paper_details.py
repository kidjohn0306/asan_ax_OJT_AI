import copy
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import admin_service


class FakeExamSets:
    def __init__(self, rows=None):
        self.rows = rows or []

    def list_exam_sets(self):
        return copy.deepcopy(self.rows)

    def get_exam(self, exam_id):
        return copy.deepcopy(next(
            (row for row in self.rows if row.get("exam_id") == exam_id),
            None,
        ))


class FakeQuestions:
    def __init__(self):
        self.get_all_calls = 0
        self.get_question_calls = 0
        self.questions = {
            "common": [{
                "question_id": "Q1",
                "category": "현재 분류",
                "question": "현재 문제은행 문제",
                "option_a": "현재 A",
                "option_b": "현재 B",
                "option_c": "현재 C",
                "option_d": "현재 D",
                "answer": "D",
                "explanation": "현재 해설",
                "difficulty_init": "상",
                "version": 99,
            }],
        }

    def get_all_questions(self):
        self.get_all_calls += 1
        return copy.deepcopy(self.questions)

    def get_question(self, question_id):
        self.get_question_calls += 1
        return None


class FakeExamV2:
    def __init__(self, version=None, items=None):
        self.version = version
        self.items = items or []
        self.find_calls = []
        self.list_calls = []
        self.fail_find = False
        self.fail_list = False

    def find_current_version(self, exam_set_id):
        self.find_calls.append(exam_set_id)
        if self.fail_find:
            raise RuntimeError("v2 lookup failed")
        return copy.deepcopy(self.version)

    def list_version_items(self, exam_set_id, version_no):
        self.list_calls.append((exam_set_id, version_no))
        if self.fail_list:
            raise RuntimeError("v2 items failed")
        return copy.deepcopy(self.items)


def frozen_snapshot(question_id, question, version):
    return {
        "question_id": question_id,
        "category": "동결 분류",
        "question": question,
        "option_a": "동결 A",
        "option_b": "동결 B",
        "option_c": "동결 C",
        "option_d": "동결 D",
        "answer": "B",
        "explanation": "동결 해설",
        "difficulty_init": "하",
        "version": version,
    }


class ExamPaperDetailsTests(unittest.TestCase):
    def setUp(self):
        self.legacy = FakeExamSets([{
            "exam_id": "exam-1",
            "exam_set_id": "set-1",
            "name": "확정 시험",
            "team_code": "T1",
            "question_ids": ["Q1", "Q2"],
            "created_at": "2026-07-15T09:00:00+00:00",
        }])
        self.questions = FakeQuestions()
        self.version = {
            "exam_version_id": "ver-2",
            "exam_set_id": "set-1",
            "version_no": "2",
        }
        self.items = [
            {
                "order_no": "2",
                "question_id": "Q2",
                "question_version": "4",
                "score": "40",
                "question_snapshot_json": json.dumps(
                    frozen_snapshot("Q2", "두 번째 동결 문제", 4),
                    ensure_ascii=False,
                ),
            },
            {
                "order_no": "1",
                "question_id": "Q1",
                "question_version": "3",
                "score": "60",
                "question_snapshot_json": frozen_snapshot(
                    "Q1", "동결된 문제", 3
                ),
            },
        ]
        self.v2 = FakeExamV2(self.version, self.items)
        self.repo_patches = [
            patch("repositories.exam_set_repo", self.legacy),
            patch("repositories.question_repo", self.questions),
            patch("repositories.exam_v2_repo", self.v2),
        ]
        for repo_patch in self.repo_patches:
            repo_patch.start()
            self.addCleanup(repo_patch.stop)

    def flags(self, mode="dual", frozen="true"):
        return patch.dict("os.environ", {
            "OJT_SHEETS_SCHEMA_MODE": mode,
            "OJT_USE_FROZEN_EXAM": frozen,
            "OJT_USE_ASSIGNMENTS_TAB": "false",
        }, clear=False)

    def test_frozen_details_use_snapshot_scores_versions_and_order(self):
        with self.flags():
            result = admin_service.get_exam_set_questions("exam-1")

        self.assertEqual(
            [question["question_id"] for question in result["questions"]],
            ["Q1", "Q2"],
        )
        self.assertEqual(result["questions"][0]["question"], "동결된 문제")
        self.assertEqual(result["questions"][0]["options"]["A"], "동결 A")
        self.assertEqual(result["questions"][0]["answer"], "B")
        self.assertEqual(result["questions"][0]["explanation"], "동결 해설")
        self.assertEqual(result["questions"][0]["difficulty"], "하")
        self.assertEqual(
            [question["score"] for question in result["questions"]],
            [60, 40],
        )
        self.assertEqual(
            [question["question_version"] for question in result["questions"]],
            [3, 4],
        )
        self.assertEqual(result["exam_set"]["exam_version_id"], "ver-2")
        self.assertEqual(result["exam_set"]["paper_version"], 2)
        self.assertEqual(
            result["exam_set"]["question_scores"], {"Q1": 60, "Q2": 40}
        )
        self.assertTrue(result["exam_set"]["immutable"])
        self.assertEqual(self.v2.find_calls, ["set-1"])
        self.assertEqual(self.v2.list_calls, [("set-1", 2)])
        self.assertEqual(self.questions.get_all_calls, 0)
        self.assertEqual(self.questions.get_question_calls, 0)

    def test_normalized_lookup_error_is_503_without_legacy_fallback(self):
        self.v2.fail_find = True
        with self.flags():
            with self.assertLogs(level="ERROR"):
                with self.assertRaises(HTTPException) as raised:
                    admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.get_all_calls, 0)

    def test_missing_normalized_repository_is_503_without_legacy_fallback(self):
        with patch("repositories.exam_v2_repo", None), self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.get_all_calls, 0)

    def test_normalized_items_error_is_503_without_legacy_fallback(self):
        self.v2.fail_list = True
        with self.flags():
            with self.assertLogs(level="ERROR"):
                with self.assertRaises(HTTPException) as raised:
                    admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.get_all_calls, 0)

    def test_invalid_frozen_snapshot_is_503_without_legacy_fallback(self):
        self.v2.items[0]["question_snapshot_json"] = "not-json"
        with self.flags():
            with self.assertLogs(level="ERROR"):
                with self.assertRaises(HTTPException) as raised:
                    admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.get_all_calls, 0)

    def test_incomplete_frozen_snapshot_is_503_without_legacy_fallback(self):
        self.v2.items[0]["question_snapshot_json"] = {}
        with self.flags():
            with self.assertLogs(level="ERROR"):
                with self.assertRaises(HTTPException) as raised:
                    admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.get_all_calls, 0)

    def test_mismatched_frozen_snapshot_id_is_503_without_legacy_fallback(self):
        self.v2.items[0]["question_snapshot_json"] = frozen_snapshot(
            "OTHER", "다른 문항의 Snapshot", 4
        )
        with self.flags():
            with self.assertLogs(level="ERROR"):
                with self.assertRaises(HTTPException) as raised:
                    admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.get_all_calls, 0)

    def test_feature_off_uses_single_bulk_question_lookup(self):
        with self.flags(mode="legacy", frozen="false"):
            result = admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(self.questions.get_all_calls, 1)
        self.assertEqual(self.v2.find_calls, [])
        self.assertEqual(result["questions"][0]["question"], "현재 문제은행 문제")
        self.assertFalse(result["exam_set"]["immutable"])

    def test_legacy_fallback_restores_scores_from_serialized_blueprint(self):
        self.legacy.rows[0]["question_scores"] = {}
        self.legacy.rows[0]["blueprint_json"] = json.dumps({
            "question_scores": {"Q1": 60, "Q2": 40},
        })
        with self.flags(mode="legacy", frozen="false"):
            result = admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(
            result["exam_set"]["question_scores"], {"Q1": 60, "Q2": 40}
        )
        self.assertEqual(result["questions"][0]["score"], 60)

    def test_missing_current_version_uses_single_bulk_question_lookup(self):
        self.v2.version = None
        with self.flags():
            result = admin_service.get_exam_set_questions("exam-1")
        self.assertEqual(self.v2.find_calls, ["set-1"])
        self.assertEqual(self.v2.list_calls, [])
        self.assertEqual(self.questions.get_all_calls, 1)
        self.assertFalse(result["exam_set"]["immutable"])

    def test_list_papers_selects_latest_version_and_counts_all_rounds(self):
        self.legacy.rows = [
            {
                "exam_id": "exam-old",
                "exam_set_id": "set-shared",
                "name": "구 버전",
                "team_code": "T1",
                "paper_version": 1,
                "question_ids": ["Q1"],
                "created_at": "2026-07-10T09:00:00+00:00",
            },
            {
                "exam_id": "exam-v2-older",
                "exam_set_id": "set-shared",
                "name": "버전 2 이전 회차",
                "team_code": "T1",
                "paper_version": 2,
                "question_ids": ["Q1", "Q2"],
                "created_at": "2026-07-11T09:00:00+00:00",
            },
            {
                "exam_id": "exam-v2-newer",
                "exam_set_id": "set-shared",
                "name": "버전 2 최신 회차",
                "team_code": "T2",
                "paper_version": 2,
                "question_ids": ["Q1", "Q2"],
                "created_at": "2026-07-12T09:00:00+00:00",
            },
        ]

        result = admin_service.list_question_papers()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {
            "exam_id": "exam-v2-newer",
            "exam_set_id": "set-shared",
            "name": "버전 2 최신 회차",
            "team_code": "T2",
            "paper_version": 2,
            "question_count": 2,
            "used_by_exam_count": 3,
            "created_at": "2026-07-12T09:00:00+00:00",
            "exam_category": "exam_study",
        })


if __name__ == "__main__":
    unittest.main()
