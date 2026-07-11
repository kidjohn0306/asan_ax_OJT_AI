"""V01~V07 결정론적 Gate 판정 규칙 테스트 — 순수 함수, 외부 I/O 없음."""
import unittest

from services.generation.gates import run_gates

VALID_QUESTION = {
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


if __name__ == "__main__":
    unittest.main()
