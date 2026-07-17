import unittest

from schema.sheets_v2 import SHEET_HEADERS
from services.generation.dual_write import (
    GATE_CODES,
    assign_candidate_ids,
    build_candidate_row,
    build_gate_rows,
    build_review_records,
    get_generation_write_policy,
    link_candidate_to_legacy,
)


class GenerationWritePolicyTests(unittest.TestCase):
    def test_defaults_to_legacy_only(self):
        policy = get_generation_write_policy({})
        self.assertEqual(policy.mode, "legacy")
        self.assertFalse(policy.candidates)
        self.assertFalse(policy.gates)

    def test_dual_candidate_flag_enables_candidate_writes(self):
        policy = get_generation_write_policy({
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_CANDIDATE_TAB": "true",
        })
        self.assertTrue(policy.candidates)
        self.assertFalse(policy.gates)

    def test_gate_rows_require_candidate_and_gate_flags(self):
        gate_only = get_generation_write_policy({
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_GATE_RESULTS_TAB": "true",
        })
        both = get_generation_write_policy({
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_CANDIDATE_TAB": "true",
            "OJT_USE_GATE_RESULTS_TAB": "true",
        })
        self.assertFalse(gate_only.gates)
        self.assertTrue(both.gates)


class NormalizedQuestionMapperTests(unittest.TestCase):
    def setUp(self):
        self.question = {
            "question_id": "team2-1",
            "category": "팀별",
            "question": "안전 확인 방법은?",
            "option_a": "A 방법",
            "option_b": "B 방법",
            "option_c": "C 방법",
            "option_d": "D 방법",
            "answer": "A",
            "explanation": "A가 기준이다.",
            "difficulty_init": "하",
            "difficulty_ai": "중",
            "status": "reviewing",
            "flags": {
                "warning": False,
                "gate_snapshot": {
                    "overall_status": "PASS",
                    "gates": {
                        code: {
                            "status": "PASS",
                            "reason": f"{code} passed",
                            "confidence": 1.0,
                        }
                        for code in GATE_CODES
                    },
                },
            },
        }

    def test_candidate_ids_are_stable_and_unique(self):
        first = assign_candidate_ids(
            [dict(self.question), dict(self.question)],
            "job-1",
        )
        second = assign_candidate_ids(
            [dict(self.question), dict(self.question)],
            "job-1",
        )
        self.assertEqual(
            [q["candidate_id"] for q in first],
            [q["candidate_id"] for q in second],
        )
        self.assertEqual(len({q["candidate_id"] for q in first}), 2)

    def test_candidate_row_uses_only_canonical_headers(self):
        question = assign_candidate_ids([self.question], "job-1")[0]
        row = build_candidate_row(
            question,
            generation_job_id="job-1",
            team_code="T2",
            provider="mock",
            generated_at="2026-07-15T00:00:00+00:00",
        )
        self.assertLessEqual(set(row), set(SHEET_HEADERS["question_candidates"]))
        self.assertEqual(row["question_text"], self.question["question"])
        self.assertEqual(row["correct_answer"], "A")
        self.assertEqual(row["overall_gate_status"], "PASS")

    def test_gate_snapshot_maps_to_exactly_seven_stable_rows(self):
        question = assign_candidate_ids([self.question], "job-1")[0]
        first = build_gate_rows(question, "2026-07-15T00:00:00+00:00")
        second = build_gate_rows(question, "2026-07-15T00:00:00+00:00")
        self.assertEqual(len(first), 7)
        self.assertEqual([row["gate_code"] for row in first], list(GATE_CODES))
        self.assertEqual(
            [row["gate_result_id"] for row in first],
            [row["gate_result_id"] for row in second],
        )
        self.assertTrue(all(
            set(row) <= set(SHEET_HEADERS["gate_results"])
            for row in first
        ))

    def test_legacy_flags_keep_candidate_link_and_gate_snapshot(self):
        linked = link_candidate_to_legacy(self.question, "cand-1")
        self.assertEqual(linked["candidate_id"], "cand-1")
        self.assertEqual(linked["flags"]["candidate_id"], "cand-1")
        self.assertIn("gate_snapshot", linked["flags"])
        self.assertNotIn("candidate_id", self.question["flags"])

    def test_review_and_history_ids_are_stable_and_canonical(self):
        before = link_candidate_to_legacy(self.question, "cand-1")
        before["question_id"] = "Q1"
        after = {**before, "status": "approved"}
        first = build_review_records(
            before,
            after,
            action="APPROVE",
            actor_id="admin-1",
            reason="검수 완료",
            reviewed_at="2026-07-15T00:00:00+00:00",
        )
        second = build_review_records(
            before,
            after,
            action="APPROVE",
            actor_id="admin-1",
            reason="검수 완료",
            reviewed_at="2026-07-15T00:00:00+00:00",
        )
        self.assertEqual(first[0]["review_id"], second[0]["review_id"])
        self.assertEqual(first[1]["history_id"], second[1]["history_id"])
        self.assertLessEqual(set(first[0]), set(SHEET_HEADERS["question_reviews"]))
        self.assertLessEqual(set(first[1]), set(SHEET_HEADERS["question_history"]))


if __name__ == "__main__":
    unittest.main()
