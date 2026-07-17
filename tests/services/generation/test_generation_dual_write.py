import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from services import admin_service


QUESTION = {
    "category": "팀별",
    "question": "안전 확인 방법은?",
    "option_a": "A 방법",
    "option_b": "B 방법",
    "option_c": "C 방법",
    "option_d": "D 방법",
    "answer": "A",
    "explanation": "A가 기준이다.",
    "difficulty_init": "하",
    "difficulty_ai": "하",
    "admin_override": "하",
}


class FakeQuestions:
    def __init__(self, fail_add=False):
        self.items = {}
        self.fail_add = fail_add

    def list_by_status(self, status):
        return []

    def get_all_questions(self):
        return {}

    def add_question(self, pool_key, question):
        if self.fail_add:
            raise RuntimeError("legacy write failed")
        self.items[question["question_id"]] = (pool_key, question)


class FakeStats:
    def list_flagged(self):
        return []


class FakeV2:
    def __init__(self, fail_candidates=False):
        self.jobs = []
        self.updates = []
        self.candidates = []
        self.gates = []
        self.fail_candidates = fail_candidates

    def create_job(self, job):
        self.jobs.append(dict(job))

    def update_job(self, job_id, fields):
        self.updates.append((job_id, dict(fields)))

    def save_candidates(self, rows):
        if self.fail_candidates:
            raise RuntimeError("candidate write failed")
        self.candidates.extend(dict(row) for row in rows)

    def save_gate_results(self, rows):
        self.gates.extend(dict(row) for row in rows)


class FakeVerifier:
    provider = "fake"

    def verify(self, question, context):
        return {
            "grounding": "SUPPORTED",
            "grounding_reason": "supported",
            "single_answer": "PASS",
            "single_answer_reason": "single",
            "distractor_status": "PASS",
            "distractor_reason": "valid",
            "scope_status": "PASS",
            "scope_reason": "valid",
        }


class GenerationDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.questions = FakeQuestions()
        self.stats = FakeStats()
        self.v2 = FakeV2()
        patchers = [
            patch("repositories.question_repo", self.questions),
            patch("repositories.question_stats_repo", self.stats),
            patch("repositories.generation_v2_repo", self.v2),
            patch("services.material_service.get_material_text_for_team", return_value="자료"),
            patch("ai_engine.router.generate_questions_from_material", return_value=[dict(QUESTION)]),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def dual_env(self, gates=False):
        values = {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_CANDIDATE_TAB": "true",
            "OJT_USE_GATE_RESULTS_TAB": "true" if gates else "false",
            "OJT_GATE_MODE": "strict" if gates else "legacy",
        }
        return patch.dict("os.environ", values, clear=False)

    def test_default_legacy_mode_never_calls_v2_repository(self):
        with patch.dict("os.environ", {
            "OJT_SHEETS_SCHEMA_MODE": "legacy",
            "OJT_USE_CANDIDATE_TAB": "false",
            "OJT_USE_GATE_RESULTS_TAB": "false",
            "OJT_GATE_MODE": "legacy",
        }, clear=False):
            result = admin_service.generate_ai_questions("T2", "", 1, "하")
        self.assertEqual(result["count"], 1)
        self.assertEqual(self.v2.jobs, [])
        self.assertEqual(self.v2.candidates, [])

    def test_dual_strict_records_job_candidate_and_seven_gates(self):
        with self.dual_env(gates=True), patch(
            "ai_engine.router.get_semantic_gate_verifier",
            return_value=FakeVerifier(),
        ):
            result = admin_service.generate_ai_questions(
                "T2", "", 1, "하", requested_by="admin-1", idempotency_key="req-1"
            )
        self.assertEqual(len(self.v2.jobs), 1)
        self.assertEqual(self.v2.jobs[0]["status"], "RUNNING")
        self.assertEqual(len(self.v2.candidates), 1)
        self.assertEqual(len(self.v2.gates), 7)
        self.assertEqual(self.v2.updates[-1][1]["status"], "COMPLETED")
        stored = next(iter(self.questions.items.values()))[1]
        self.assertEqual(stored["flags"]["candidate_id"], self.v2.candidates[0]["candidate_id"])
        self.assertIn("generation_job_id", result)

    def test_dual_legacy_preserves_failed_candidate_only_in_v2(self):
        with self.dual_env(gates=False), patch(
            "ai_engine.router.generate_questions_from_material",
            return_value=[{**QUESTION, "explanation": ""}],
        ):
            result = admin_service.generate_ai_questions("T2", "", 1, "하")
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(self.questions.items, {})
        self.assertEqual(len(self.v2.candidates), 1)
        self.assertEqual(self.v2.candidates[0]["status"], "draft")

    def test_normalized_failure_prevents_legacy_write(self):
        self.v2.fail_candidates = True
        with self.dual_env(gates=False):
            with self.assertRaises(HTTPException) as raised:
                admin_service.generate_ai_questions("T2", "", 1, "하")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.items, {})
        self.assertEqual(self.v2.updates[-1][1]["status"], "FAILED")

    def test_legacy_failure_after_v2_is_partial_failed(self):
        self.questions.fail_add = True
        with self.dual_env(gates=False):
            with self.assertRaises(HTTPException) as raised:
                admin_service.generate_ai_questions("T2", "", 1, "하")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(len(self.v2.candidates), 1)
        self.assertEqual(self.v2.updates[-1][1]["status"], "PARTIAL_FAILED")

    def test_provider_failure_updates_job_and_keeps_502(self):
        with self.dual_env(gates=False), patch(
            "ai_engine.router.generate_questions_from_material",
            side_effect=RuntimeError("provider failed"),
        ):
            with self.assertRaises(HTTPException) as raised:
                admin_service.generate_ai_questions("T2", "", 1, "하")
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(self.v2.updates[-1][1]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
