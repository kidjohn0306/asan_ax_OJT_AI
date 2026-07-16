import json
import math
import unittest

from schema.sheets_v2 import SHEET_HEADERS
from services.results.dual_write import (
    SubmissionValidationError,
    build_attempt_id,
    build_attempt_record,
    build_frozen_grading_records,
    get_result_write_policy,
    normalize_submission,
)


def frozen_item(
    item_id: str,
    question_id: str,
    order_no: int,
    score: int,
    answer: str,
    difficulty: str = "중",
) -> dict:
    return {
        "exam_set_item_id": item_id,
        "exam_set_id": "set-1",
        "paper_version": 1,
        "order_no": order_no,
        "question_id": question_id,
        "question_version": 3,
        "score": score,
        "question_snapshot_json": json.dumps({
            "question_id": question_id,
            "question": f"문항 {question_id}",
            "answer": answer,
            "difficulty_init": difficulty,
            "option_a": "보기 A",
            "option_b": "보기 B",
            "option_c": "보기 C",
            "option_d": "보기 D",
            "version": 3,
        }, ensure_ascii=False),
        "created_at": "2026-07-15T00:00:00+00:00",
        "checksum": f"checksum-{question_id}",
    }


ITEMS = [
    frozen_item("item-2", "Q2", 2, 40, "B", "하"),
    frozen_item("item-1", "Q1", 1, 60, "A", "상"),
]


class ResultWritePolicyTests(unittest.TestCase):
    def test_defaults_are_legacy_only(self):
        policy = get_result_write_policy({})
        self.assertEqual(policy.mode, "legacy")
        self.assertFalse(policy.frozen_exams)
        self.assertFalse(policy.assignments)
        self.assertFalse(policy.result_answers)

    def test_result_answers_requires_every_prerequisite(self):
        complete = {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
            "OJT_USE_ASSIGNMENTS_TAB": "true",
            "OJT_USE_RESULT_ANSWERS": "true",
        }
        policy = get_result_write_policy(complete)
        self.assertTrue(policy.frozen_exams)
        self.assertTrue(policy.assignments)
        self.assertTrue(policy.result_answers)

        for missing in (
            "OJT_USE_FROZEN_EXAM",
            "OJT_USE_ASSIGNMENTS_TAB",
            "OJT_USE_RESULT_ANSWERS",
        ):
            with self.subTest(missing=missing):
                env = dict(complete)
                env[missing] = "false"
                self.assertFalse(get_result_write_policy(env).result_answers)

    def test_attempt_id_is_stable_per_assignment_and_number(self):
        self.assertEqual(
            build_attempt_id("assignment-1", 1),
            build_attempt_id("assignment-1", 1),
        )
        self.assertNotEqual(
            build_attempt_id("assignment-1", 1),
            build_attempt_id("assignment-1", 2),
        )


class SubmissionNormalizationTests(unittest.TestCase):
    def assert_code(self, expected_code, answers, response_times):
        with self.assertRaises(SubmissionValidationError) as raised:
            normalize_submission(ITEMS, answers, response_times)
        self.assertEqual(raised.exception.code, expected_code)

    def test_orders_items_and_fills_unanswered_values(self):
        answers, times = normalize_submission(
            ITEMS,
            {"Q1": "a"},
            {"Q1": 12.5},
        )
        self.assertEqual(list(answers), ["Q1", "Q2"])
        self.assertEqual(answers, {"Q1": "A", "Q2": None})
        self.assertEqual(times, {"Q1": 12.5, "Q2": 0.0})

    def test_unknown_answer_or_time_question_is_rejected(self):
        self.assert_code(
            "SUBMISSION_UNKNOWN_QUESTION",
            {"Q3": "A"},
            {},
        )
        self.assert_code(
            "SUBMISSION_UNKNOWN_QUESTION",
            {},
            {"Q3": 1},
        )

    def test_invalid_choice_is_rejected(self):
        for value in ("E", "", 1, True, None):
            with self.subTest(value=value):
                self.assert_code(
                    "SUBMISSION_INVALID_CHOICE",
                    {"Q1": value},
                    {},
                )

    def test_invalid_response_time_is_rejected(self):
        invalid = (-1, "1", True, math.inf, -math.inf, math.nan)
        for value in invalid:
            with self.subTest(value=value):
                self.assert_code(
                    "SUBMISSION_INVALID_RESPONSE_TIME",
                    {},
                    {"Q1": value},
                )


class FrozenGradingMapperTests(unittest.TestCase):
    def test_grades_every_item_with_custom_scores_and_unanswered(self):
        rows, summary = build_frozen_grading_records(
            result_id="result-1",
            items=ITEMS,
            answers={"Q1": "a"},
            response_times={"Q1": 12.5},
            created_at="2026-07-15T01:00:00+00:00",
        )
        self.assertEqual([row["question_id"] for row in rows], ["Q1", "Q2"])
        self.assertEqual(summary["score"], 60)
        self.assertEqual(summary["total_questions"], 2)
        self.assertEqual(summary["correct_count"], 1)
        self.assertEqual(summary["response_time_total_seconds"], 12.5)
        self.assertEqual(rows[1]["selected_choice"], None)
        self.assertFalse(rows[1]["is_correct"])
        self.assertEqual(rows[1]["score"], 0)
        self.assertEqual(
            summary["difficulty_summary"],
            {
                "상": {"correct": 1, "incorrect": 0},
                "중": {"correct": 0, "incorrect": 0},
                "하": {"correct": 0, "incorrect": 1},
            },
        )
        self.assertTrue(all(
            set(row) <= set(SHEET_HEADERS["result_answers"])
            for row in rows
        ))

    def test_answer_ids_are_stable_for_retry(self):
        first, _ = build_frozen_grading_records(
            "result-1", ITEMS, {"Q1": "A"}, {}, "time-1"
        )
        second, _ = build_frozen_grading_records(
            "result-1", ITEMS, {"Q1": "A"}, {}, "time-2"
        )
        self.assertEqual(
            [row["result_answer_id"] for row in first],
            [row["result_answer_id"] for row in second],
        )

    def test_attempt_record_is_canonical_and_increments_version(self):
        first = build_attempt_record(
            attempt_id="attempt-1",
            assignment_id="assignment-1",
            exam_id="exam-1",
            exam_version_id="version-1",
            employee_id="E1",
            status="started",
            occurred_at="2026-07-15T01:00:00+00:00",
        )
        second = build_attempt_record(
            attempt_id="attempt-1",
            assignment_id="assignment-1",
            exam_id="exam-1",
            exam_version_id="version-1",
            employee_id="E1",
            status="submitting",
            occurred_at="2026-07-15T01:05:00+00:00",
            current=first,
            submission_idempotency_key="submit-1",
        )
        self.assertLessEqual(set(second), set(SHEET_HEADERS["exam_attempts"]))
        self.assertEqual(first["row_version"], 1)
        self.assertEqual(second["row_version"], 2)
        self.assertEqual(second["started_at"], first["started_at"])
        self.assertEqual(second["submission_idempotency_key"], "submit-1")


if __name__ == "__main__":
    unittest.main()
