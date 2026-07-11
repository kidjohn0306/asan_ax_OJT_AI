"""V01~V07 결정론적 Gate 판정 규칙 테스트 — 순수 함수, 외부 I/O 없음."""
import unittest

from services.generation.gates import (
    overall_status,
    question_fingerprint,
    run_deterministic_gates,
    run_gates,
)

VALID_QUESTION = {
    "question_type": "MULTIPLE_CHOICE_SINGLE",
    "question_id": "team2-test-001",
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
    "status": "draft",
}


class LegacyGateContractTests(unittest.TestCase):
    """강화 이전부터 다른 코드가 의존해온 run_gates() 응답 계약을 고정한다."""

    def test_legacy_result_keeps_required_fields(self):
        result = run_gates(dict(VALID_QUESTION))
        self.assertIn("pass", result)
        self.assertIn("failed", result)
        self.assertIn("flags", result)
        self.assertIn("warning", result["flags"])
        self.assertIn("security_hold", result["flags"])


class V01SchemaGateTests(unittest.TestCase):
    def test_valid_question_passes(self):
        result = run_deterministic_gates(dict(VALID_QUESTION))
        self.assertEqual(result["gates"]["V01"]["status"], "PASS")

    def test_unsupported_question_type_is_hard_fail(self):
        question = {**VALID_QUESTION, "question_type": "SHORT_ANSWER"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V01"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V01"]["code"], "V01_UNSUPPORTED_QUESTION_TYPE")

    def test_empty_question_is_hard_fail(self):
        question = {**VALID_QUESTION, "question": "   "}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V01"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V01"]["code"], "V01_FIELD_EMPTY")

    def test_empty_option_is_hard_fail(self):
        question = {**VALID_QUESTION, "option_c": ""}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V01"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V01"]["code"], "V01_FIELD_EMPTY")

    def test_nfkc_duplicate_options_is_hard_fail(self):
        # "1２명"(전각 숫자)은 NFKC 정규화 후 "12명"이 되어 "12명"과 중복된다.
        question = {**VALID_QUESTION, "option_a": "12명", "option_b": "1２명",
                    "option_c": "3명", "option_d": "4명"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V01"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V01"]["code"], "V01_DUPLICATE_OPTIONS")

    def test_answer_out_of_range_is_hard_fail(self):
        question = {**VALID_QUESTION, "answer": "E"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V01"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V01"]["code"], "V01_ANSWER_OUT_OF_RANGE")


class V04DistractorQualityGateTests(unittest.TestCase):
    def test_forbidden_phrase_is_review_required(self):
        question = {**VALID_QUESTION, "option_c": "위 보기 모두 맞다"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V04"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V04"]["code"], "V04_FORBIDDEN_DISTRACTOR_PHRASE")

    def test_answer_length_outlier_is_warning(self):
        question = {
            **VALID_QUESTION,
            "option_b": "2명이 함께 2인 1조로 상호 확인하며 작업해야 안전하다",
        }
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V04"]["status"], "WARNING")
        self.assertEqual(result["gates"]["V04"]["code"], "V04_ANSWER_LENGTH_OUTLIER")


class V05ScopeDifficultyGateTests(unittest.TestCase):
    def test_category_invalid_is_hard_fail(self):
        question = {**VALID_QUESTION, "category": "잡학"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V05"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V05"]["code"], "V05_CATEGORY_INVALID")

    def test_difficulty_invalid_is_hard_fail(self):
        question = {**VALID_QUESTION, "difficulty_init": "", "difficulty_ai": "최상"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V05"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V05"]["code"], "V05_DIFFICULTY_INVALID")

    def test_team_pool_mismatch_is_hard_fail(self):
        result = run_deterministic_gates(dict(VALID_QUESTION), pool_key="team1", team_code="T2")
        self.assertEqual(result["gates"]["V05"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V05"]["code"], "V05_TEAM_POOL_MISMATCH")

    def test_admin_override_missing_is_warning(self):
        result = run_deterministic_gates(dict(VALID_QUESTION))
        self.assertEqual(result["gates"]["V05"]["status"], "WARNING")
        self.assertEqual(result["gates"]["V05"]["code"], "V05_ADMIN_DIFFICULTY_PENDING")

    def test_admin_override_present_passes(self):
        question = {**VALID_QUESTION, "admin_override": "하"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V05"]["status"], "PASS")


class V06DuplicateExposureGateTests(unittest.TestCase):
    def test_exact_duplicate_is_hard_fail(self):
        approved = ({"question_id": "team2-old-001", "question": VALID_QUESTION["question"]},)
        result = run_deterministic_gates(dict(VALID_QUESTION), approved_questions=approved)
        self.assertEqual(result["gates"]["V06"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V06"]["code"], "V06_EXACT_DUPLICATE")

    def test_high_similarity_is_review_required(self):
        approved = ({
            "question_id": "team2-old-002",
            "question": "Baffle 분리 작업의 최소 작업 인원은 총 몇 명인가?",
        },)
        result = run_deterministic_gates(dict(VALID_QUESTION), approved_questions=approved)
        self.assertEqual(result["gates"]["V06"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["gates"]["V06"]["code"], "V06_HIGH_SIMILARITY")

    def test_duplicate_id_is_hard_fail(self):
        approved = ({"question_id": VALID_QUESTION["question_id"], "question": "다른 문제"},)
        result = run_deterministic_gates(dict(VALID_QUESTION), approved_questions=approved)
        self.assertEqual(result["gates"]["V06"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V06"]["code"], "V06_DUPLICATE_ID")

    def test_flagged_question_id_is_warning(self):
        result = run_deterministic_gates(
            dict(VALID_QUESTION),
            flagged_question_ids=frozenset({VALID_QUESTION["question_id"]}),
        )
        self.assertEqual(result["gates"]["V06"]["status"], "WARNING")
        self.assertEqual(result["gates"]["V06"]["code"], "V06_FREQUENTLY_ISSUED")


class V07SecurityMediaGateTests(unittest.TestCase):
    def test_phone_is_hard_fail(self):
        question = {**VALID_QUESTION, "explanation": "문의 010-1234-5678"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V07"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V07"]["code"], "V07_PHONE_DETECTED")

    def test_email_is_hard_fail(self):
        question = {**VALID_QUESTION, "explanation": "문의 ojt@example.com"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V07"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V07"]["code"], "V07_EMAIL_DETECTED")

    def test_url_is_hard_fail(self):
        question = {**VALID_QUESTION, "explanation": "참고 https://internal.example.com/doc"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V07"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V07"]["code"], "V07_URL_DETECTED")

    def test_security_keyword_is_hard_fail(self):
        question = {**VALID_QUESTION, "explanation": "관리자계정 정보는 별도 문서 참고"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V07"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V07"]["code"], "V07_SECURITY_KEYWORD_DETECTED")

    def test_unapproved_media_is_hard_fail(self):
        result = run_deterministic_gates(dict(VALID_QUESTION), media={"present": True, "approved": False})
        self.assertEqual(result["gates"]["V07"]["status"], "HARD_FAIL")
        self.assertEqual(result["gates"]["V07"]["code"], "V07_MEDIA_NOT_APPROVED")

    def test_equipment_identifier_only_is_warning(self):
        question = {**VALID_QUESTION, "explanation": "설비번호 EQ-4821 점검 기록 참고"}
        result = run_deterministic_gates(question)
        self.assertEqual(result["gates"]["V07"]["status"], "WARNING")
        self.assertEqual(result["gates"]["V07"]["code"], "V07_EQUIPMENT_IDENTIFIER_DETECTED")


class OverallStatusTests(unittest.TestCase):
    def test_overall_status_uses_highest_severity(self):
        self.assertEqual(overall_status(["PASS", "WARNING"]), "WARNING")
        self.assertEqual(overall_status(["WARNING", "REVIEW_REQUIRED"]), "REVIEW_REQUIRED")
        self.assertEqual(overall_status(["PASS", "HARD_FAIL"]), "HARD_FAIL")
        self.assertEqual(overall_status([]), "PASS")


class QuestionFingerprintTests(unittest.TestCase):
    def test_fingerprint_changes_when_content_changes(self):
        original = question_fingerprint(dict(VALID_QUESTION))
        changed = question_fingerprint({**VALID_QUESTION, "question": "변경된 질문"})
        self.assertNotEqual(original, changed)

    def test_fingerprint_stable_for_unchanged_content(self):
        first = question_fingerprint(dict(VALID_QUESTION))
        second = question_fingerprint(dict(VALID_QUESTION))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
