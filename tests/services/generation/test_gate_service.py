"""V02 Grounding·V03 Single Answer 의미 검증과 evaluate_candidate() 조립 테스트.
실제 AI Provider를 호출하지 않고 FakeVerifier로 gate_service의 오류 폐쇄 정책을 검증한다."""
import unittest

from services.generation.gate_service import GateContext, evaluate_candidate
from tests.services.generation.test_gate_rules import VALID_QUESTION

CONTEXT = GateContext(
    material_text="Baffle 분리 작업은 2인이 수행하며 최소 작업 인원은 2명이다.",
    team_code="T2",
    pool_key="team2",
    category_label="팀별",
)


class FakeVerifier:
    """실제 AI 호출 없이 evaluate_candidate()의 분기를 검증하기 위한 테스트 대역."""

    def __init__(self, result=None, exception=None):
        self.result = result
        self.exception = exception
        self.call_count = 0

    def verify(self, question, context):
        self.call_count += 1
        if self.exception is not None:
            raise self.exception
        return self.result


def _semantic_response(**overrides) -> dict:
    base = {
        "grounding": "SUPPORTED",
        "grounding_reason": "자료의 작업 인원 설명과 정답이 일치합니다.",
        "single_answer": "PASS",
        "single_answer_reason": "정답만 자료와 일치합니다.",
        "distractor_status": "PASS",
        "distractor_reason": "보기 품질이 적절합니다.",
        "scope_status": "PASS",
        "scope_reason": "T2 팀별 범위와 일치합니다.",
    }
    base.update(overrides)
    return base


class V02GroundingTests(unittest.TestCase):
    def test_supported_is_pass(self):
        verifier = FakeVerifier(_semantic_response(grounding="SUPPORTED"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V02"]["status"], "PASS")

    def test_partial_is_review_required(self):
        verifier = FakeVerifier(_semantic_response(grounding="PARTIAL"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V02"]["status"], "REVIEW_REQUIRED")

    def test_unsupported_is_hard_fail(self):
        verifier = FakeVerifier(_semantic_response(grounding="UNSUPPORTED"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V02"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V02"]["code"], "V02_GROUNDING_UNSUPPORTED")


class V03SingleAnswerTests(unittest.TestCase):
    def test_pass(self):
        verifier = FakeVerifier(_semantic_response(single_answer="PASS"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V03"]["status"], "PASS")

    def test_fail_is_hard_fail(self):
        verifier = FakeVerifier(_semantic_response(single_answer="FAIL"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V03"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V03"]["code"], "V03_SINGLE_ANSWER_FAIL")

    def test_uncertain_is_review_required(self):
        verifier = FakeVerifier(_semantic_response(single_answer="UNCERTAIN"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V03"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V03"]["code"], "V03_SINGLE_ANSWER_UNCERTAIN")


class VerifierFailureClosedTests(unittest.TestCase):
    """검증기 오류·불명확 응답이 PASS로 둔갑하지 않는지 확인한다 (strict 모드 실패 폐쇄 정책)."""

    def test_timeout_is_review_required(self):
        verifier = FakeVerifier(exception=TimeoutError("timed out"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V02"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V03"]["status"], "REVIEW_REQUIRED")

    def test_non_json_response_is_review_required(self):
        verifier = FakeVerifier(result="이것은 JSON 오브젝트가 아닌 문자열입니다")
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V02"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V02"]["code"], "SEMANTIC_VERIFIER_INVALID_RESPONSE")

    def test_missing_required_key_is_review_required(self):
        incomplete = _semantic_response()
        del incomplete["single_answer"]
        verifier = FakeVerifier(result=incomplete)
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V03"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V03"]["code"], "SEMANTIC_VERIFIER_INVALID_RESPONSE")

    def test_unknown_enum_value_is_review_required(self):
        verifier = FakeVerifier(result=_semantic_response(grounding="MAYBE"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertEqual(result["gates"]["V02"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V02"]["code"], "SEMANTIC_VERIFIER_INVALID_RESPONSE")

    def test_v01_hard_fail_skips_verifier_call(self):
        question = {**VALID_QUESTION, "answer": "E"}
        verifier = FakeVerifier(_semantic_response())
        result = evaluate_candidate(question, CONTEXT, verifier, mode="strict")
        self.assertEqual(verifier.call_count, 0)
        self.assertEqual(result["gates"]["V02"]["code"], "V02_NOT_EVALUATED")
        self.assertEqual(result["gates"]["V03"]["code"], "V03_NOT_EVALUATED")

    def test_missing_material_skips_verifier_and_hard_fails_v02(self):
        empty_context = GateContext(
            material_text="", team_code="T2", pool_key="team2", category_label="팀별",
        )
        verifier = FakeVerifier(_semantic_response())
        result = evaluate_candidate(dict(VALID_QUESTION), empty_context, verifier, mode="strict")
        self.assertEqual(verifier.call_count, 0)
        self.assertEqual(result["gates"]["V02"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V02"]["code"], "V02_SOURCE_MISSING")


class OverallAssemblyTests(unittest.TestCase):
    def test_all_pass_yields_legacy_pass_true(self):
        question = {**VALID_QUESTION, "admin_override": "하"}
        verifier = FakeVerifier(_semantic_response())
        result = evaluate_candidate(question, CONTEXT, verifier, mode="strict")
        self.assertTrue(result["pass"])
        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(result["gate_version"], "mcq-7gate-v1")
        self.assertIn("question_fingerprint", result)
        self.assertIn("source_digest", result)
        self.assertFalse(result["flags"]["security_hold"])

    def test_semantic_hard_fail_overrides_legacy_pass(self):
        verifier = FakeVerifier(_semantic_response(single_answer="FAIL"))
        result = evaluate_candidate(dict(VALID_QUESTION), CONTEXT, verifier, mode="strict")
        self.assertFalse(result["pass"])
        self.assertEqual(result["overall_status"], "HARD_FAIL")
        self.assertIn("V03_SINGLE_ANSWER_FAIL", result["failed"])


if __name__ == "__main__":
    unittest.main()
