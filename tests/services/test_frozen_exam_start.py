import copy
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import exam_service


CURRENT_QUESTION = {
    "question_id": "Q1",
    "category": "현재 카테고리",
    "question": "변경된 문제은행 문항",
    "answer": "D",
    "explanation": "변경된 해설",
    "difficulty_init": "하",
    "option_a": "현재 A",
    "option_b": "현재 B",
    "option_c": "현재 C",
    "option_d": "현재 D",
    "version": 99,
    "status": "approved",
}


def frozen_item(item_id, question_id, order_no, question):
    return {
        "exam_set_item_id": item_id,
        "exam_set_id": "set-1",
        "paper_version": "1",
        "order_no": str(order_no),
        "question_id": question_id,
        "question_version": "2",
        "score": "50",
        "question_snapshot_json": json.dumps({
            "question_id": question_id,
            "category": "동결 카테고리",
            "question": question,
            "answer": "A",
            "explanation": "동결 해설",
            "difficulty_init": "상",
            "option_a": f"{question_id} 동결 A",
            "option_b": f"{question_id} 동결 B",
            "option_c": f"{question_id} 동결 C",
            "option_d": f"{question_id} 동결 D",
            "version": 2,
        }, ensure_ascii=False),
    }


class FakeQuestionRepo:
    def get_all_questions(self):
        return {"team1": [copy.deepcopy(CURRENT_QUESTION)]}


class FakeSnapshotRepo:
    def __init__(self, events):
        self.events = events
        self.rows = {}

    def save_snapshot(self, result_id, snapshot):
        self.events.append(f"snapshot:{result_id}")
        self.rows[result_id] = copy.deepcopy(snapshot)

    def get_snapshot(self, result_id):
        return self.rows.get(result_id)


class FakeExamSets:
    def __init__(self, assigned=True):
        self.row = {
            "exam_id": "exam-1",
            "exam_set_id": "set-1",
            "name": "동결 시험",
            "team_code": "T1",
            "question_ids": ["Q1"],
            "assigned_users": ["E1"] if assigned else [],
            "status": "active",
            "pass_score": 70,
        }

    def list_exam_sets(self):
        return [self.row]


class FakeExamV2:
    def __init__(self):
        self.assignment = {
            "assignment_id": "assignment-1",
            "exam_id": "exam-1",
            "exam_version_id": "version-1",
            "employee_id": "E1",
            "status": "assigned",
            "max_attempts": "1",
            "attempts_used": "0",
        }
        self.version = {
            "exam_version_id": "version-1",
            "exam_set_id": "set-1",
            "version_no": "1",
            "total_score": "100",
        }
        self.items = [
            frozen_item("item-2", "Q2", 2, "두 번째 동결 문항"),
            frozen_item("item-1", "Q1", 1, "첫 번째 동결 문항"),
        ]
        self.calls = []

    def find_assignment(self, exam_id, employee_id):
        self.calls.append(("find_assignment", exam_id, employee_id))
        if (
            self.assignment["exam_id"] == exam_id
            and self.assignment["employee_id"] == employee_id
        ):
            return copy.deepcopy(self.assignment)
        return None

    def find_version(self, exam_version_id):
        self.calls.append(("find_version", exam_version_id))
        return copy.deepcopy(self.version) if exam_version_id == "version-1" else None

    def list_version_items(self, exam_set_id, paper_version):
        self.calls.append(("list_version_items", exam_set_id, paper_version))
        return copy.deepcopy(sorted(self.items, key=lambda row: int(row["order_no"])))


class FakeResultV2:
    def __init__(self, events):
        self.events = events
        self.attempts = {}
        self.fail_upsert = False
        self.calls = 0

    def find_attempt_for_assignment(self, assignment_id, employee_id, statuses=None):
        self.calls += 1
        return next((
            copy.deepcopy(row)
            for row in self.attempts.values()
            if row["assignment_id"] == assignment_id
            and row["employee_id"] == employee_id
            and (statuses is None or row["status"] in statuses)
        ), None)

    def upsert_attempt(self, row):
        self.calls += 1
        self.events.append(f"attempt:{row['attempt_id']}")
        if self.fail_upsert:
            raise RuntimeError("attempt write failed")
        self.attempts[row["attempt_id"]] = copy.deepcopy(row)


class FakeStats:
    def increment_batch(self, question_ids):
        pass


class FrozenExamStartTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.questions = FakeQuestionRepo()
        self.snapshots = FakeSnapshotRepo(self.events)
        self.exam_sets = FakeExamSets()
        self.exam_v2 = FakeExamV2()
        self.result_v2 = FakeResultV2(self.events)
        self.repo_patches = [
            patch("repositories.question_repo", self.questions),
            patch("repositories.result_repo", object()),
            patch("repositories.snapshot_repo", self.snapshots),
            patch("repositories.exam_set_repo", self.exam_sets),
            patch("repositories.exam_v2_repo", self.exam_v2),
            patch("repositories.result_v2_repo", self.result_v2),
            patch("repositories.question_stats_repo", FakeStats()),
        ]
        for repo_patch in self.repo_patches:
            repo_patch.start()
            self.addCleanup(repo_patch.stop)

    def flags(self, enabled=True):
        values = {
            "OJT_SHEETS_SCHEMA_MODE": "dual" if enabled else "legacy",
            "OJT_USE_FROZEN_EXAM": "true" if enabled else "false",
            "OJT_USE_ASSIGNMENTS_TAB": "true" if enabled else "false",
            "OJT_USE_RESULT_ANSWERS": "true" if enabled else "false",
        }
        return patch.dict("os.environ", values, clear=False)

    def test_confirmed_exam_renders_frozen_items_in_order(self):
        with self.flags():
            response = exam_service.generate_exam_questions("T1", employee_id="E1")
        self.assertEqual(
            [question["question"] for question in response["questions"]],
            ["첫 번째 동결 문항", "두 번째 동결 문항"],
        )
        self.assertEqual(response["questions"][0]["options"]["A"], "Q1 동결 A")
        self.assertNotEqual(
            response["questions"][0]["question"], CURRENT_QUESTION["question"]
        )
        self.assertEqual(self.events[0].split(":")[0], "attempt")
        self.assertEqual(self.events[1].split(":")[0], "snapshot")
        self.assertEqual(response["result_id"], next(iter(self.result_v2.attempts)))
        meta = self.snapshots.rows[response["result_id"]]["_meta"]
        self.assertEqual(meta["employee_id"], "E1")
        self.assertEqual(meta["assignment_id"], "assignment-1")
        self.assertEqual(meta["exam_version_id"], "version-1")
        self.assertEqual(meta["attempt_id"], response["result_id"])
        self.assertEqual(meta["attempt_no"], 1)
        self.assertEqual(meta["grading_mode"], "frozen_v2")

    def test_repeated_generate_reuses_started_attempt(self):
        with self.flags():
            first = exam_service.generate_exam_questions("T1", employee_id="E1")
            second = exam_service.generate_exam_questions("T1", employee_id="E1")
        self.assertEqual(first["result_id"], second["result_id"])
        self.assertEqual(len(self.result_v2.attempts), 1)

    def test_attempt_limit_is_409(self):
        self.exam_v2.assignment["attempts_used"] = "1"
        with self.flags(), self.assertRaises(HTTPException) as raised:
            exam_service.generate_exam_questions("T1", employee_id="E1")
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"], "EXAM_ATTEMPT_LIMIT_REACHED"
        )
        self.assertEqual(self.snapshots.rows, {})

    def test_attempt_write_failure_prevents_snapshot(self):
        self.result_v2.fail_upsert = True
        with self.flags(), self.assertRaises(HTTPException) as raised:
            exam_service.generate_exam_questions("T1", employee_id="E1")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.snapshots.rows, {})

    def test_flag_off_uses_current_legacy_question_and_skips_v2(self):
        with self.flags(enabled=False):
            response = exam_service.generate_exam_questions("T1", employee_id="E1")
        self.assertEqual(response["questions"][0]["question"], CURRENT_QUESTION["question"])
        self.assertEqual(self.result_v2.calls, 0)
        meta = self.snapshots.rows[response["result_id"]]["_meta"]
        self.assertNotIn("attempt_id", meta)


if __name__ == "__main__":
    unittest.main()
