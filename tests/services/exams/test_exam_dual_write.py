import json
import unittest

from schema.sheets_v2 import SHEET_HEADERS
from services.exams.dual_write import (
    build_assignment_record,
    build_exam_ids,
    build_frozen_exam_records,
    get_exam_write_policy,
    resolve_question_scores,
)


APPROVED_Q1 = {
    "question_id": "Q1",
    "question_type": "MULTIPLE_CHOICE_SINGLE",
    "category": "안전",
    "question": "보호구 착용 시점은?",
    "option_a": "작업 전",
    "option_b": "작업 후",
    "option_c": "휴식 중",
    "option_d": "퇴근 후",
    "answer": "A",
    "explanation": "작업 전에 착용한다.",
    "difficulty_init": "하",
    "difficulty_ai": "중",
    "admin_override": "중",
    "status": "approved",
    "version": 2,
}

APPROVED_Q2 = {
    **APPROVED_Q1,
    "question_id": "Q2",
    "question": "작업 전 확인 사항은?",
    "answer": "B",
    "version": 1,
}


class ExamWritePolicyTests(unittest.TestCase):
    def test_defaults_are_legacy_only(self):
        policy = get_exam_write_policy({})
        self.assertEqual(policy.mode, "legacy")
        self.assertFalse(policy.frozen_exams)
        self.assertFalse(policy.assignments)

    def test_frozen_flag_enables_versions_only(self):
        policy = get_exam_write_policy({
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
            "OJT_USE_ASSIGNMENTS_TAB": "false",
        })
        self.assertTrue(policy.frozen_exams)
        self.assertFalse(policy.assignments)

    def test_assignments_require_frozen_exam_flag(self):
        policy = get_exam_write_policy({
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "false",
            "OJT_USE_ASSIGNMENTS_TAB": "true",
        })
        self.assertFalse(policy.frozen_exams)
        self.assertFalse(policy.assignments)

    def test_assignments_enable_when_both_flags_are_on(self):
        policy = get_exam_write_policy({
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
            "OJT_USE_ASSIGNMENTS_TAB": "true",
        })
        self.assertTrue(policy.frozen_exams)
        self.assertTrue(policy.assignments)


class QuestionScoreTests(unittest.TestCase):
    def test_scores_default_to_positive_integer_total_100(self):
        self.assertEqual(
            resolve_question_scores(["Q1", "Q2", "Q3"]),
            {"Q1": 34, "Q2": 33, "Q3": 33},
        )

    def test_explicit_scores_are_kept_in_question_order(self):
        self.assertEqual(
            resolve_question_scores(
                ["Q1", "Q2"], {"Q2": 40, "Q1": 60}
            ),
            {"Q1": 60, "Q2": 40},
        )

    def test_score_ids_must_match_question_ids(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            resolve_question_scores(["Q1", "Q2"], {"Q1": 100})
        with self.assertRaisesRegex(ValueError, "unknown"):
            resolve_question_scores(
                ["Q1", "Q2"], {"Q1": 50, "Q2": 40, "Q3": 10}
            )

    def test_scores_must_be_positive_integers_totaling_100(self):
        for scores in (
            {"Q1": 100, "Q2": 0},
            {"Q1": 50, "Q2": 50.0},
            {"Q1": 50, "Q2": True},
        ):
            with self.subTest(scores=scores):
                with self.assertRaisesRegex(ValueError, "positive integers"):
                    resolve_question_scores(["Q1", "Q2"], scores)
        with self.assertRaisesRegex(ValueError, "total"):
            resolve_question_scores(["Q1", "Q2"], {"Q1": 50, "Q2": 49})

    def test_duplicate_empty_and_more_than_100_questions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            resolve_question_scores([])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            resolve_question_scores(["Q1", "Q1"])
        with self.assertRaisesRegex(ValueError, "at most 100"):
            resolve_question_scores([f"Q{i}" for i in range(101)])


class FrozenExamMapperTests(unittest.TestCase):
    def test_idempotency_key_produces_stable_exam_ids(self):
        self.assertEqual(build_exam_ids("request-1"), build_exam_ids("request-1"))
        self.assertNotEqual(build_exam_ids("request-1"), build_exam_ids("request-2"))

    def test_missing_idempotency_key_produces_new_ids(self):
        self.assertNotEqual(build_exam_ids(), build_exam_ids())

    def test_frozen_records_are_canonical_and_snapshot_question(self):
        version, items = build_frozen_exam_records(
            exam_set_id="set-1",
            questions=[APPROVED_Q1, APPROVED_Q2],
            scores={"Q1": 60, "Q2": 40},
            confirmed_by="admin-1",
            confirmed_at="2026-07-15T00:00:00+00:00",
            version_no=1,
        )
        self.assertEqual(version["total_score"], 100)
        self.assertEqual(version["question_count"], 2)
        self.assertEqual([item["score"] for item in items], [60, 40])
        self.assertEqual([item["order_no"] for item in items], [1, 2])
        snapshot = json.loads(items[0]["question_snapshot_json"])
        self.assertEqual(snapshot["question"], APPROVED_Q1["question"])
        self.assertEqual(snapshot["option_d"], APPROVED_Q1["option_d"])
        self.assertEqual(snapshot["answer"], "A")
        self.assertEqual(snapshot["explanation"], APPROVED_Q1["explanation"])
        self.assertEqual(snapshot["version"], 2)
        self.assertLessEqual(set(version), set(SHEET_HEADERS["exam_versions"]))
        self.assertTrue(all(
            set(item) <= set(SHEET_HEADERS["exam_set_items"])
            for item in items
        ))

    def test_frozen_record_ids_and_hashes_are_stable(self):
        kwargs = {
            "exam_set_id": "set-1",
            "questions": [APPROVED_Q1],
            "scores": {"Q1": 100},
            "confirmed_by": "admin-1",
            "confirmed_at": "2026-07-15T00:00:00+00:00",
            "version_no": 1,
        }
        first = build_frozen_exam_records(**kwargs)
        second = build_frozen_exam_records(**kwargs)
        self.assertEqual(first, second)
        self.assertTrue(first[0]["exam_version_id"].startswith("examver-"))
        self.assertTrue(first[1][0]["exam_set_item_id"].startswith("examitem-"))

    def test_assignment_id_is_stable_per_exam_and_employee(self):
        first = build_assignment_record(
            exam_id="exam-1",
            exam_version_id="ver-1",
            employee_id="E1",
            actor_id="admin-1",
            assigned_at="2026-07-15T00:00:00+00:00",
        )
        second = build_assignment_record(
            exam_id="exam-1",
            exam_version_id="ver-1",
            employee_id="E1",
            actor_id="admin-1",
            assigned_at="2026-07-15T00:00:00+00:00",
        )
        self.assertEqual(first["assignment_id"], second["assignment_id"])
        self.assertEqual(first["status"], "assigned")
        self.assertEqual(first["row_version"], 1)
        self.assertFalse(first["reentry_allowed"])
        self.assertLessEqual(set(first), set(SHEET_HEADERS["assignments"]))

    def test_assignment_update_increments_row_version(self):
        updated = build_assignment_record(
            exam_id="exam-1",
            exam_version_id="ver-1",
            employee_id="E1",
            actor_id="admin-2",
            assigned_at="2026-07-16T00:00:00+00:00",
            current={"assignment_id": "assignment-existing", "row_version": "2"},
            status="cancelled",
        )
        self.assertEqual(updated["assignment_id"], "assignment-existing")
        self.assertEqual(updated["row_version"], 3)
        self.assertEqual(updated["status"], "cancelled")
        self.assertEqual(updated["cancelled_by"], "admin-2")


if __name__ == "__main__":
    unittest.main()
