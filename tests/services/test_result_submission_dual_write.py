import copy
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from repositories.result_v2 import ImmutableResultAnswerConflict
from services import exam_service
from services.results.dual_write import build_attempt_record


def item(item_id, question_id, order_no, score, answer, difficulty):
    return {
        "exam_set_item_id": item_id,
        "exam_set_id": "set-1",
        "paper_version": "1",
        "order_no": str(order_no),
        "question_id": question_id,
        "question_version": "2",
        "score": str(score),
        "question_snapshot_json": json.dumps({
            "question": f"동결 {question_id}",
            "category": "동결",
            "answer": answer,
            "explanation": f"해설 {question_id}",
            "difficulty_init": difficulty,
            "option_a": "A 보기",
            "option_b": "B 보기",
            "option_c": "C 보기",
            "option_d": "D 보기",
        }, ensure_ascii=False),
    }


ITEMS = [
    item("item-1", "Q1", 1, 60, "A", "상"),
    item("item-2", "Q2", 2, 40, "B", "하"),
]


def snapshot(employee_id="E1"):
    row = {}
    for frozen in ITEMS:
        data = json.loads(frozen["question_snapshot_json"])
        row[frozen["question_id"]] = {
            **data,
            "version": int(frozen["question_version"]),
            "difficulty": data["difficulty_init"],
        }
    row["_meta"] = {
        "team_code": "T1",
        "exam_id": "exam-1",
        "name": "동결 시험",
        "pass_score": 70,
        "created_at": "2026-07-15T00:00:00+00:00",
        "employee_id": employee_id,
        "assignment_id": "assignment-1",
        "exam_version_id": "version-1",
        "attempt_id": "attempt-1",
        "attempt_no": 1,
        "grading_mode": "frozen_v2",
    }
    return row


class FakeSnapshots:
    def __init__(self):
        self.rows = {"attempt-1": snapshot()}

    def get_snapshot(self, result_id):
        return copy.deepcopy(self.rows.get(result_id))


class FakeResults:
    def __init__(self, events):
        self.events = events
        self.rows = {}
        self.fail_append = False

    def get_result(self, result_id):
        return copy.deepcopy(self.rows.get(result_id))

    def append_result(self, row):
        self.events.append("legacy-result")
        if self.fail_append:
            raise RuntimeError("legacy result failed")
        self.rows[row["result_id"]] = copy.deepcopy(row)


class FakeExamV2:
    def __init__(self, events):
        self.events = events
        self.assignment = {
            "assignment_id": "assignment-1",
            "exam_id": "exam-1",
            "exam_version_id": "version-1",
            "employee_id": "E1",
            "status": "assigned",
            "max_attempts": "1",
            "attempts_used": "0",
            "row_version": "1",
        }
        self.version = {
            "exam_version_id": "version-1",
            "exam_set_id": "set-1",
            "version_no": "1",
            "total_score": "100",
        }
        self.fail_assignment = False

    def find_assignment(self, exam_id, employee_id):
        if exam_id == "exam-1" and employee_id == "E1":
            return copy.deepcopy(self.assignment)
        return None

    def find_version(self, exam_version_id):
        return copy.deepcopy(self.version) if exam_version_id == "version-1" else None

    def list_version_items(self, exam_set_id, paper_version):
        return copy.deepcopy(ITEMS)

    def upsert_assignment(self, row):
        self.events.append("v2-assignment-usage")
        if self.fail_assignment:
            raise RuntimeError("assignment update failed")
        self.assignment = copy.deepcopy(row)


class FakeResultV2:
    def __init__(self, events):
        self.events = events
        self.answers = {}
        self.attempt = build_attempt_record(
            attempt_id="attempt-1",
            assignment_id="assignment-1",
            exam_id="exam-1",
            exam_version_id="version-1",
            employee_id="E1",
            status="started",
            occurred_at="2026-07-15T00:00:00+00:00",
        )
        self.fail_answers = False
        self.fail_attempt_status = None

    def find_attempt(self, attempt_id):
        return copy.deepcopy(self.attempt) if attempt_id == "attempt-1" else None

    def list_result_answers(self, result_id):
        return [
            copy.deepcopy(row)
            for row in self.answers.values()
            if row["result_id"] == result_id
        ]

    def save_result_answers(self, rows):
        if self.fail_answers:
            raise RuntimeError("answer write failed")
        changed = False
        for row in rows:
            current = self.answers.get(row["result_answer_id"])
            if current is not None:
                comparable_current = {
                    key: value for key, value in current.items() if key != "created_at"
                }
                comparable_incoming = {
                    key: value for key, value in row.items() if key != "created_at"
                }
                if comparable_current != comparable_incoming:
                    raise ImmutableResultAnswerConflict("different answer")
                continue
            self.answers[row["result_answer_id"]] = copy.deepcopy(row)
            changed = True
        if changed:
            self.events.append("v2-answers")

    def upsert_attempt(self, row):
        self.events.append(f"v2-attempt-{row['status']}")
        if self.fail_attempt_status == row["status"]:
            raise RuntimeError(f"attempt {row['status']} failed")
        self.attempt = copy.deepcopy(row)


class ResultSubmissionDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.snapshots = FakeSnapshots()
        self.results = FakeResults(self.events)
        self.exam_v2 = FakeExamV2(self.events)
        self.result_v2 = FakeResultV2(self.events)
        self.repo_patches = [
            patch("repositories.question_repo", object()),
            patch("repositories.snapshot_repo", self.snapshots),
            patch("repositories.result_repo", self.results),
            patch("repositories.exam_v2_repo", self.exam_v2),
            patch("repositories.result_v2_repo", self.result_v2),
        ]
        for repo_patch in self.repo_patches:
            repo_patch.start()
            self.addCleanup(repo_patch.stop)

    def flags(self):
        return patch.dict("os.environ", {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
            "OJT_USE_ASSIGNMENTS_TAB": "true",
            "OJT_USE_RESULT_ANSWERS": "true",
        }, clear=False)

    def submit(self, answers=None, key="submit-1", skip_save=False):
        return exam_service.score_and_save(
            "attempt-1",
            answers if answers is not None else {"Q1": "A"},
            {"Q1": 12.5},
            employee_id="E1",
            name="홍길동",
            skip_save=skip_save,
            submission_idempotency_key=key,
        )

    def test_grades_all_items_and_writes_in_safe_order(self):
        with self.flags():
            result = self.submit()
        self.assertEqual(result["score"], 60)
        self.assertFalse(result["pass"])
        self.assertEqual(result["total_questions"], 2)
        self.assertEqual(result["correct_count"], 1)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][1]["user_answer"], None)
        answers = list(self.result_v2.answers.values())
        self.assertEqual(len(answers), 2)
        self.assertEqual(answers[1]["selected_choice"], None)
        self.assertEqual(answers[1]["score"], 0)
        self.assertEqual(self.events, [
            "v2-answers",
            "v2-attempt-submitting",
            "legacy-result",
            "v2-attempt-submitted",
            "v2-assignment-usage",
        ])
        self.assertEqual(self.exam_v2.assignment["attempts_used"], 1)
        self.assertEqual(self.result_v2.attempt["status"], "submitted")

    def test_snapshot_employee_mismatch_is_403(self):
        self.snapshots.rows["attempt-1"] = snapshot(employee_id="E2")
        with self.flags(), self.assertRaises(HTTPException) as raised:
            self.submit()
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(self.events, [])

    def test_invalid_payload_returns_stable_400_codes(self):
        cases = (
            ({"Q3": "A"}, {"Q1": 1}, "SUBMISSION_UNKNOWN_QUESTION"),
            ({"Q1": "E"}, {"Q1": 1}, "SUBMISSION_INVALID_CHOICE"),
            ({"Q1": "A"}, {"Q1": -1}, "SUBMISSION_INVALID_RESPONSE_TIME"),
        )
        for answers, times, code in cases:
            with self.subTest(code=code), self.flags():
                with self.assertRaises(HTTPException) as raised:
                    exam_service.score_and_save(
                        "attempt-1",
                        answers,
                        times,
                        employee_id="E1",
                        submission_idempotency_key="submit-1",
                    )
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(raised.exception.detail["code"], code)
        self.assertEqual(self.events, [])

    def test_missing_key_uses_result_id(self):
        with self.flags():
            self.submit(key="")
        self.assertEqual(
            self.result_v2.attempt["submission_idempotency_key"],
            "attempt-1",
        )

    def test_same_retry_returns_existing_without_writes(self):
        with self.flags():
            first = self.submit()
            self.events.clear()
            second = self.submit()
        self.assertEqual(second, first)
        self.assertEqual(self.events, [])

    def test_same_key_with_different_answers_is_409(self):
        with self.flags():
            self.submit()
            self.events.clear()
            with self.assertRaises(HTTPException) as raised:
                self.submit(answers={"Q1": "B"})
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"],
            "SUBMISSION_IDEMPOTENCY_CONFLICT",
        )
        self.assertEqual(self.events, [])

    def test_completed_attempt_with_different_key_is_409(self):
        with self.flags():
            self.submit()
            self.events.clear()
            with self.assertRaises(HTTPException) as raised:
                self.submit(key="submit-2")
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "RESULT_ALREADY_SUBMITTED")
        self.assertEqual(self.events, [])

    def test_normalized_answer_failure_prevents_legacy_result(self):
        self.result_v2.fail_answers = True
        with self.flags(), self.assertRaises(HTTPException) as raised:
            self.submit()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.results.rows, {})
        self.assertEqual(self.result_v2.attempt["status"], "started")

    def test_legacy_failure_resumes_without_duplicate_answers(self):
        self.results.fail_append = True
        with self.flags(), self.assertRaises(HTTPException) as raised:
            self.submit()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.result_v2.attempt["status"], "submitting")
        self.results.fail_append = False
        self.events.clear()
        with self.flags():
            recovered = self.submit()
        self.assertEqual(recovered["score"], 60)
        self.assertEqual(self.events, [
            "legacy-result",
            "v2-attempt-submitted",
            "v2-assignment-usage",
        ])

    def test_final_attempt_failure_recovers_without_rewriting_result(self):
        self.result_v2.fail_attempt_status = "submitted"
        with self.flags(), self.assertRaises(HTTPException) as raised:
            self.submit()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("attempt-1", self.results.rows)
        self.assertEqual(self.result_v2.attempt["status"], "submitting")
        self.result_v2.fail_attempt_status = None
        self.events.clear()
        with self.flags():
            recovered = self.submit()
        self.assertEqual(recovered["score"], 60)
        self.assertEqual(self.events, [
            "v2-attempt-submitted",
            "v2-assignment-usage",
        ])

    def test_assignment_failure_recovers_usage_only(self):
        self.exam_v2.fail_assignment = True
        with self.flags(), self.assertRaises(HTTPException) as raised:
            self.submit()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.result_v2.attempt["status"], "submitted")
        self.exam_v2.fail_assignment = False
        self.events.clear()
        with self.flags():
            recovered = self.submit()
        self.assertEqual(recovered["score"], 60)
        self.assertEqual(self.events, ["v2-assignment-usage"])

    def test_skip_save_grades_without_any_write(self):
        with self.flags():
            result = self.submit(skip_save=True)
        self.assertEqual(result["score"], 60)
        self.assertEqual(self.events, [])
        self.assertEqual(self.results.rows, {})
        self.assertEqual(self.result_v2.answers, {})


if __name__ == "__main__":
    unittest.main()
