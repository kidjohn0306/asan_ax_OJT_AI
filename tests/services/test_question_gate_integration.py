"""admin_service.generate_ai_questions()의 legacy/strict Gate 분기 통합 테스트.
실제 AI Provider·Drive·Sheets를 호출하지 않도록 관련 의존성을 모두 Fake/Mock으로 대체한다."""
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

import services.material_service  # noqa: F401 — 아래 patch()가 속성으로 참조하기 전에 서브모듈을 로드해둔다.
from services import admin_service


@contextmanager
def _gate_mode(value):
    original = os.environ.get("OJT_GATE_MODE")
    if value is None:
        os.environ.pop("OJT_GATE_MODE", None)
    else:
        os.environ["OJT_GATE_MODE"] = value
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("OJT_GATE_MODE", None)
        else:
            os.environ["OJT_GATE_MODE"] = original


class FakeQuestionRepository:
    """QuestionRepository 계약을 만족하는 인메모리 테스트 대역."""

    def __init__(self):
        self._questions = {}  # question_id -> (pool_key, question dict)

    def get_all_questions(self) -> dict:
        pools = {}
        for pool_key, q in self._questions.values():
            pools.setdefault(pool_key, []).append(q)
        return pools

    def get_approved_questions(self, team_key=None, category=None) -> list:
        return [q for _, q in self._questions.values() if q.get("status") == "approved"]

    def list_by_status(self, status: str) -> list:
        return [q for _, q in self._questions.values() if q.get("status") == status]

    def get_question(self, question_id: str):
        entry = self._questions.get(question_id)
        return entry[1] if entry else None

    def add_question(self, pool_key: str, question: dict) -> None:
        self._questions[question["question_id"]] = (pool_key, question)

    def update_question(self, question_id: str, fields: dict) -> None:
        entry = self._questions.get(question_id)
        if entry:
            entry[1].update(fields)

    def count_by_status(self, status: str) -> int:
        return len(self.list_by_status(status))


class FakeQuestionStatsRepo:
    def list_flagged(self) -> list:
        return []

    def increment_batch(self, question_ids) -> None:
        pass


class FakeSemanticVerifier:
    """실제 AI 호출 없이 미리 정해둔 의미 검증 결과(혹은 예외)를 반환한다."""

    def __init__(self, response=None, exception=None):
        self.provider = "fake"
        self.response = response or _semantic_response()
        self.exception = exception
        self.call_count = 0

    def verify(self, question, context):
        self.call_count += 1
        if self.exception is not None:
            raise self.exception
        return self.response


def _semantic_response(**overrides) -> dict:
    base = {
        "grounding": "SUPPORTED",
        "grounding_reason": "자료와 일치합니다.",
        "single_answer": "PASS",
        "single_answer_reason": "정답은 하나입니다.",
        "distractor_status": "PASS",
        "distractor_reason": "보기 품질이 적절합니다.",
        "scope_status": "PASS",
        "scope_reason": "범위가 일치합니다.",
    }
    base.update(overrides)
    return base


def _generated_question(**overrides) -> dict:
    base = {
        "category": "팀별",
        "question": "Baffle 분리 작업의 최소 작업 인원은 몇 명인가?",
        "option_a": "1명",
        "option_b": "2명",
        "option_c": "3명",
        "option_d": "4명",
        "answer": "B",
        "explanation": "Baffle 분리 작업은 2인이 수행한다.",
        "difficulty_init": "하",
        "difficulty_ai": "하",
        "admin_override": "",
    }
    base.update(overrides)
    return base


class GenerateAIQuestionsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fake_repo = FakeQuestionRepository()
        self.fake_stats = FakeQuestionStatsRepo()
        patchers = [
            patch("repositories.question_repo", self.fake_repo),
            patch("repositories.question_stats_repo", self.fake_stats),
            patch("services.material_service.get_material_text_for_team",
                  return_value="Baffle 분리 작업은 2인이 수행하며 최소 인원은 2명이다."),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def _generate(self, questions, verifier=None):
        with patch("ai_engine.router.generate_questions_from_material", return_value=questions):
            if verifier is not None:
                with patch("ai_engine.router.get_semantic_gate_verifier", return_value=verifier):
                    return admin_service.generate_ai_questions("T2", "", 1, "하")
            return admin_service.generate_ai_questions("T2", "", 1, "하")

    # --- legacy 분기 -----------------------------------------------------

    def test_gate_mode_unset_defaults_to_legacy(self):
        with _gate_mode(None):
            result = self._generate([_generated_question(admin_override="하")])
        self.assertEqual(result["count"], 1)
        stored = list(self.fake_repo._questions.values())
        self.assertEqual(len(stored), 1)
        _, stored_question = stored[0]
        self.assertEqual(stored_question["status"], "reviewing")
        self.assertNotIn("gate_snapshot", stored_question["flags"])
        self.assertNotIn("overall_gate_status", result["questions"][0])

    def test_legacy_mode_keeps_existing_pass_behavior(self):
        with _gate_mode("legacy"):
            result = self._generate([_generated_question(admin_override="하")])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["failed_count"], 0)

    def test_legacy_mode_failed_candidate_is_not_persisted(self):
        with _gate_mode("legacy"):
            # 팀별 카테고리인데 해설이 비어 있으면 legacy V-04(내부자료 기반 근거)에서 실패한다.
            result = self._generate([_generated_question(explanation="")])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(len(self.fake_repo._questions), 0)
        self.assertTrue(result["questions"][0]["gate_errors"])

    # --- strict 분기 -------------------------------------------------------

    def test_strict_pass_sets_reviewing(self):
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            result = self._generate([_generated_question(admin_override="하")], verifier=verifier)
        self.assertEqual(result["count"], 1)
        stored = list(self.fake_repo._questions.values())[0][1]
        self.assertEqual(stored["status"], "reviewing")
        self.assertEqual(stored["flags"]["gate_snapshot"]["overall_status"], "PASS")

    def test_strict_warning_with_required_gates_pass_sets_reviewing(self):
        # admin_override가 비어 있으면 V05가 WARNING이지만 V01·V02·V03·V07은 여전히 PASS다.
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            result = self._generate([_generated_question(admin_override="")], verifier=verifier)
        self.assertEqual(result["count"], 1)
        stored = list(self.fake_repo._questions.values())[0][1]
        self.assertEqual(stored["status"], "reviewing")
        self.assertEqual(stored["flags"]["gate_snapshot"]["overall_status"], "WARNING")

    def test_strict_review_required_sets_draft(self):
        verifier = FakeSemanticVerifier(_semantic_response(single_answer="UNCERTAIN"))
        with _gate_mode("strict"):
            result = self._generate([_generated_question(admin_override="하")], verifier=verifier)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["failed_count"], 1)
        stored = list(self.fake_repo._questions.values())[0][1]
        self.assertEqual(stored["status"], "draft")
        self.assertEqual(stored["flags"]["gate_snapshot"]["overall_status"], "REVIEW_REQUIRED")

    def test_strict_hard_fail_sets_draft_without_calling_verifier(self):
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            result = self._generate([_generated_question(answer="E")], verifier=verifier)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["failed_count"], 1)
        stored = list(self.fake_repo._questions.values())[0][1]
        self.assertEqual(stored["status"], "draft")
        self.assertEqual(stored["flags"]["gate_snapshot"]["overall_status"], "HARD_FAIL")
        self.assertEqual(verifier.call_count, 0)

    def test_strict_draft_candidate_is_persisted_exactly_once(self):
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            self._generate([_generated_question(answer="E")], verifier=verifier)
        self.assertEqual(len(self.fake_repo._questions), 1)

    def test_strict_gate_snapshot_and_stable_error_codes_present(self):
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            result = self._generate([_generated_question(answer="E")], verifier=verifier)
        stored = list(self.fake_repo._questions.values())[0][1]
        self.assertIn("gate_snapshot", stored["flags"])
        self.assertIn("V01_ANSWER_OUT_OF_RANGE", stored["gate_errors"])
        self.assertIn("overall_gate_status", result["questions"][0])
        self.assertIn("gates", result["questions"][0])

    def test_strict_verifier_error_does_not_become_pass(self):
        verifier = FakeSemanticVerifier(exception=TimeoutError("timed out"))
        with _gate_mode("strict"):
            result = self._generate([_generated_question(admin_override="하")], verifier=verifier)
        self.assertEqual(result["count"], 0)
        stored = list(self.fake_repo._questions.values())[0][1]
        self.assertEqual(stored["status"], "draft")
        self.assertNotEqual(stored["flags"]["gate_snapshot"]["overall_status"], "PASS")

    def test_strict_batch_duplicate_candidates_are_flagged(self):
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            result = self._generate(
                [_generated_question(admin_override="하"), _generated_question(admin_override="하")],
                verifier=verifier,
            )
        self.assertEqual(len(self.fake_repo._questions), 2)
        statuses = [q["status"] for _, q in self.fake_repo._questions.values()]
        self.assertIn("reviewing", statuses)
        self.assertIn("draft", statuses)  # 두 번째는 첫 번째와 완전 중복이라 V06 HARD_FAIL


class ApproveQuestionGuardTests(unittest.TestCase):
    """approve_question()의 strict 승인 Guard와 legacy security_hold 공통 차단을 검증한다."""

    def setUp(self):
        self.fake_repo = FakeQuestionRepository()
        self.fake_stats = FakeQuestionStatsRepo()
        patchers = [
            patch("repositories.question_repo", self.fake_repo),
            patch("repositories.question_stats_repo", self.fake_stats),
            patch("services.material_service.get_material_text_for_team",
                  return_value="Baffle 분리 작업은 2인이 수행하며 최소 인원은 2명이다."),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        self.admin_actor = {"sub": "admin001", "role": "admin"}

    def _seed_strict_question(self, **overrides) -> str:
        verifier = FakeSemanticVerifier(_semantic_response())
        with _gate_mode("strict"):
            with patch("ai_engine.router.generate_questions_from_material",
                       return_value=[_generated_question(**overrides)]):
                with patch("ai_engine.router.get_semantic_gate_verifier", return_value=verifier):
                    admin_service.generate_ai_questions("T2", "", 1, "하")
        return list(self.fake_repo._questions.keys())[0]

    def test_missing_question_is_404(self):
        with _gate_mode("strict"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question("no-such-id", actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 404)

    def test_strict_draft_status_is_409(self):
        qid = self._seed_strict_question(answer="E")  # V01 HARD_FAIL → draft
        with _gate_mode("strict"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "GATE_STATUS_INVALID")

    def test_strict_missing_admin_override_is_409(self):
        qid = self._seed_strict_question(admin_override="")  # V05 WARNING, 나머지 PASS → reviewing
        with _gate_mode("strict"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "GATE_ADMIN_DIFFICULTY_REQUIRED")

    def test_strict_warning_without_reason_is_409(self):
        # 정답 보기만 지나치게 길면 V04가 WARNING(V04_ANSWER_LENGTH_OUTLIER)이 된다 — V07과
        # 무관한 WARNING-eligible Gate라 관리자 사유만 있으면 승인 가능해야 한다.
        qid = self._seed_strict_question(
            admin_override="하", option_b="2명이 함께 2인 1조로 상호 확인하며 작업해야 안전하다",
        )
        with _gate_mode("strict"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "GATE_WARNING_OVERRIDE_REQUIRED")

    def test_strict_warning_with_reason_succeeds(self):
        qid = self._seed_strict_question(
            admin_override="하", option_b="2명이 함께 2인 1조로 상호 확인하며 작업해야 안전하다",
        )
        with _gate_mode("strict"):
            result = admin_service.approve_question(
                qid, actor=self.admin_actor, override_reason="현장 확인 후 승인함",
            )
        self.assertTrue(result["approved"])
        _, stored = list(self.fake_repo._questions.values())[0]
        self.assertEqual(stored["status"], "approved")

    def test_strict_all_pass_succeeds_without_reason(self):
        qid = self._seed_strict_question(admin_override="하")
        with _gate_mode("strict"):
            result = admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertTrue(result["approved"])

    def test_strict_stale_fingerprint_is_409(self):
        qid = self._seed_strict_question(admin_override="하")
        _, stored = list(self.fake_repo._questions.values())[0]
        stored["question"] = "Gate 이후 수정된 문제"
        with _gate_mode("strict"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "GATE_RESULT_STALE")

    def test_strict_security_hold_blocks_approval(self):
        qid = self._seed_strict_question(admin_override="하", explanation="문의 010-1234-5678")
        with _gate_mode("strict"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "GATE_SECURITY_HOLD")

    def test_legacy_security_hold_blocks_approval(self):
        # legacy 모드는 V07을 pass 판정에 반영하지 않아 그대로 통과·저장되지만,
        # 승인 시점에는 security_hold를 legacy에서도 공통으로 차단해야 한다.
        with _gate_mode("legacy"):
            result = self._generate([_generated_question(explanation="관리자계정 비밀번호 문의")])
        self.assertEqual(result["count"], 1)
        qid = list(self.fake_repo._questions.keys())[0]
        with _gate_mode("legacy"):
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question(qid, actor=self.admin_actor)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "GATE_SECURITY_HOLD")

    def _generate(self, questions):
        with patch("ai_engine.router.generate_questions_from_material", return_value=questions):
            return admin_service.generate_ai_questions("T2", "", 1, "하")


if __name__ == "__main__":
    unittest.main()
