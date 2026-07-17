import copy
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import admin_service


def approved_question(question_id, version=1):
    return {
        "question_id": question_id,
        "question_type": "MULTIPLE_CHOICE_SINGLE",
        "category": "안전",
        "question": f"{question_id} 본문",
        "option_a": "A 보기",
        "option_b": "B 보기",
        "option_c": "C 보기",
        "option_d": "D 보기",
        "answer": "A",
        "explanation": f"{question_id} 해설",
        "difficulty_init": "중",
        "difficulty_ai": "중",
        "admin_override": "중",
        "status": "approved",
        "version": version,
    }


class FakeQuestions:
    def __init__(self):
        self.questions = {
            "Q1": approved_question("Q1", 2),
            "Q2": approved_question("Q2"),
            "Q3": approved_question("Q3"),
        }

    def get_question(self, question_id):
        question = self.questions.get(question_id)
        return copy.deepcopy(question) if question else None


class FakeExamSets:
    def __init__(self, events):
        self.events = events
        self.rows = []
        self.fail_create = False
        self.fail_update = False

    def list_exam_sets(self):
        return self.rows

    def get_exam(self, exam_id):
        return next((row for row in self.rows if row["exam_id"] == exam_id), None)

    def create_exam_set(self, data):
        self.events.append("legacy")
        if self.fail_create:
            raise RuntimeError("legacy create failed")
        stored = copy.deepcopy(data)
        stored.setdefault("assigned_users", [])
        self.rows.append(stored)
        return stored

    def update_exam_set(self, exam_id, fields):
        self.events.append("legacy_metadata")
        if self.fail_update:
            raise RuntimeError("legacy metadata failed")
        row = self.get_exam(exam_id)
        if not row:
            return False
        row.update(copy.deepcopy(fields))
        return True


class FakeExamV2:
    def __init__(self, events):
        self.events = events
        self.versions = []
        self.items = []
        self.fail_save = False

    def save_frozen_exam(self, version, items):
        self.events.append("v2")
        if self.fail_save:
            raise RuntimeError("normalized save failed")
        if not any(
            existing["exam_version_id"] == version["exam_version_id"]
            for existing in self.versions
        ):
            self.versions.append(copy.deepcopy(version))
        known = {item["exam_set_item_id"] for item in self.items}
        self.items.extend(
            copy.deepcopy(item)
            for item in items
            if item["exam_set_item_id"] not in known
        )

    def find_current_version(self, exam_set_id):
        matches = [
            version
            for version in self.versions
            if version["exam_set_id"] == exam_set_id
        ]
        return max(matches, key=lambda row: int(row["version_no"])) if matches else None


class ExamCreationDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.questions = FakeQuestions()
        self.legacy = FakeExamSets(self.events)
        self.v2 = FakeExamV2(self.events)
        self.repo_patches = [
            patch("repositories.question_repo", self.questions),
            patch("repositories.exam_set_repo", self.legacy),
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

    def test_legacy_defaults_never_call_v2(self):
        with self.flags(mode="legacy", frozen="false"):
            result = admin_service.create_exam_set(
                "시험", "T1", ["Q1"], created_by="admin-1"
            )
        self.assertEqual(self.events, ["legacy"])
        self.assertEqual(result["question_ids"], ["Q1"])
        self.assertEqual(result["evaluation_type"], "official")
        self.assertEqual(result["total_score"], 100)
        self.assertEqual(result["exam_version_id"], "")

    def test_default_scores_are_34_33_33(self):
        with self.flags():
            admin_service.create_exam_set(
                "시험", "T1", ["Q1", "Q2", "Q3"], created_by="admin-1"
            )
        self.assertEqual([item["score"] for item in self.v2.items], [34, 33, 33])

    def test_custom_scores_and_full_snapshots_are_saved_in_order(self):
        with self.flags():
            result = admin_service.create_exam_set(
                "시험",
                "T1",
                ["Q2", "Q1"],
                created_by="admin-1",
                question_scores={"Q1": 40, "Q2": 60},
                evaluation_type="practice",
            )
        self.assertEqual(self.events, ["v2", "legacy", "legacy_metadata"])
        self.assertEqual([item["question_id"] for item in self.v2.items], ["Q2", "Q1"])
        self.assertEqual([item["score"] for item in self.v2.items], [60, 40])
        self.assertEqual(result["evaluation_type"], "practice")
        self.assertTrue(result["exam_version_id"].startswith("examver-"))
        snapshot = self.v2.items[0]["question_snapshot_json"]
        self.assertIn('"question":"Q2 본문"', snapshot)
        self.assertIn('"option_d":"D 보기"', snapshot)
        self.assertIn('"answer":"A"', snapshot)
        self.assertIn('"explanation":"Q2 해설"', snapshot)

    def test_invalid_scores_fail_before_any_write(self):
        with self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set(
                    "시험",
                    "T1",
                    ["Q1", "Q2"],
                    question_scores={"Q1": 100},
                )
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(self.events, [])

    def test_normalized_failure_prevents_legacy_create(self):
        self.v2.fail_save = True
        with self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set("시험", "T1", ["Q1"])
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.events, ["v2"])
        self.assertEqual(self.legacy.rows, [])

    def test_legacy_failure_after_normalized_write_returns_503(self):
        self.legacy.fail_create = True
        with self.flags():
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set("시험", "T1", ["Q1"])
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.events, ["v2", "legacy"])
        self.assertEqual(len(self.v2.versions), 1)

    def test_same_idempotency_key_reuses_legacy_and_v2_ids(self):
        with self.flags():
            first = admin_service.create_exam_set(
                "시험", "T1", ["Q1"], idempotency_key="request-1"
            )
            second = admin_service.create_exam_set(
                "시험", "T1", ["Q1"], idempotency_key="request-1"
            )
        self.assertEqual(first["exam_id"], second["exam_id"])
        self.assertEqual(first["exam_set_id"], second["exam_set_id"])
        self.assertEqual(first["exam_version_id"], second["exam_version_id"])
        self.assertEqual(len(self.legacy.rows), 1)
        self.assertEqual(len(self.v2.versions), 1)
        self.assertEqual(len(self.v2.items), 1)

    def test_same_idempotency_key_with_different_questions_is_409(self):
        with self.flags():
            admin_service.create_exam_set(
                "시험", "T1", ["Q1"], idempotency_key="request-1"
            )
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set(
                    "시험", "T1", ["Q2"], idempotency_key="request-1"
                )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(len(self.legacy.rows), 1)

    def test_duplicate_name_is_rejected_before_normalized_write(self):
        self.legacy.rows.append({
            "exam_set_id": "existing-set",
            "exam_id": "existing-exam",
            "name": "중복 시험",
            "team_code": "T1",
            "question_ids": ["Q1"],
        })
        with self.flags(), self.assertRaises(HTTPException) as raised:
            admin_service.create_exam_set(
                "중복 시험", "T1", ["Q2"], idempotency_key="new-request"
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.events, [])
        self.assertEqual(self.v2.versions, [])

    def test_from_paper_reuses_current_version_and_scores(self):
        with self.flags():
            created = admin_service.create_exam_set(
                "원본",
                "T1",
                ["Q1", "Q2"],
                question_scores={"Q1": 70, "Q2": 30},
                evaluation_type="official",
            )
            self.events.clear()
            round_result = admin_service.create_exam_round_from_paper(
                created["exam_set_id"],
                name="연습 회차",
                created_by="admin-2",
                evaluation_type="practice",
            )
        self.assertEqual(self.events, ["legacy", "legacy_metadata"])
        self.assertEqual(round_result["exam_version_id"], created["exam_version_id"])
        self.assertEqual(round_result["evaluation_type"], "practice")
        self.assertEqual(len(self.v2.versions), 1)
        self.assertEqual(len(self.v2.items), 2)

    def test_from_paper_persists_schedule_score_and_duration(self):
        with self.flags():
            created = admin_service.create_exam_set(
                "원본", "T1", ["Q1"], idempotency_key="paper-1"
            )
            self.events.clear()
            round_result = admin_service.create_exam_round_from_paper(
                created["exam_set_id"],
                name="예약 회차",
                idempotency_key="round-1",
                exam_datetime="2026-07-20T09:00",
                pass_score=80,
                duration_min=90,
            )
        self.assertEqual(self.events, ["legacy", "legacy_metadata"])
        self.assertEqual(round_result["exam_datetime"], "2026-07-20T09:00")
        self.assertEqual(round_result["pass_score"], 80)
        self.assertEqual(round_result["duration_min"], 90)

    def test_from_paper_without_v2_version_freezes_once(self):
        self.legacy.rows.append({
            "exam_set_id": "set-old",
            "exam_id": "exam-old",
            "name": "기존 시험지",
            "team_code": "T1",
            "question_ids": ["Q1", "Q2"],
            "evaluation_type": "official",
            "assigned_users": [],
        })
        with self.flags():
            result = admin_service.create_exam_round_from_paper(
                "set-old", created_by="admin-1"
            )
        self.assertEqual(self.events, ["v2", "legacy", "legacy_metadata"])
        self.assertEqual(result["exam_version_id"], self.v2.versions[0]["exam_version_id"])
        self.assertEqual(len(self.v2.versions), 1)


if __name__ == "__main__":
    unittest.main()
