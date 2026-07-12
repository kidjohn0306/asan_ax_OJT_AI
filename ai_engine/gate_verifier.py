"""교육자료 기반 Gate 의미 검증기 — Gemini/Claude Provider에게 문제의 근거(Grounding)와
정답 단일성(Single Answer)을 직접 채점하지 않고 판정 가능한 JSON 계약으로만 응답하게 한다.
mock Provider는 임의 PASS를 만들지 않고 SemanticVerifierUnavailable을 발생시켜
gate_service.evaluate_candidate()가 V02·V03을 REVIEW_REQUIRED로 처리하게 한다."""
import json


class SemanticVerifierUnavailable(Exception):
    """의미 검증을 실제로 수행할 수 없을 때(Mock Provider, 자격 증명 누락, API 실패) 발생시킨다."""


_VERIFY_PROMPT_RULES = """제공된 교육자료만 사용한다.
외부 지식으로 정답을 보완하지 않는다.
정답 선택지가 자료로 직접 또는 명확히 증명되는지 확인한다.
오답 세 개가 모두 명확히 틀리는지 확인한다.
응답은 지정된 JSON Object 하나만 반환한다.
판단이 불가능하면 PASS 대신 PARTIAL 또는 UNCERTAIN을 반환한다."""

_RESPONSE_SCHEMA_HINT = """다음 JSON 형식으로만 응답하라. 다른 텍스트나 마크다운은 포함하지 마라:
{"grounding": "SUPPORTED|PARTIAL|UNSUPPORTED", "grounding_reason": "300자 이하 근거 설명",
 "single_answer": "PASS|FAIL|UNCERTAIN", "single_answer_reason": "300자 이하 설명",
 "distractor_status": "PASS|WARNING|REVIEW_REQUIRED|HARD_FAIL", "distractor_reason": "300자 이하 설명",
 "scope_status": "PASS|WARNING|REVIEW_REQUIRED|HARD_FAIL", "scope_reason": "300자 이하 설명"}"""

_MAX_MATERIAL_CHARS_FOR_VERIFY = 8000


def _build_prompt(question: dict, context) -> str:
    options = "\n".join(
        f"{label}. {question.get(f'option_{label.lower()}', '')}"
        for label in ("A", "B", "C", "D")
    )
    material = (context.material_text or "")[:_MAX_MATERIAL_CHARS_FOR_VERIFY]
    return f"""다음 규칙을 반드시 따른다.
{_VERIFY_PROMPT_RULES}

[교육자료]
{material}

[문제]
{question.get('question', '')}
{options}
[정답] {question.get('answer', '')}
[해설] {question.get('explanation', '')}

{_RESPONSE_SCHEMA_HINT}"""


def _parse_response(raw_text: str) -> dict:
    try:
        data = json.loads(raw_text)
    except (TypeError, ValueError) as exc:
        raise SemanticVerifierUnavailable(f"의미 검증기 응답 JSON 파싱 실패: {exc}") from exc
    if not isinstance(data, dict):
        raise SemanticVerifierUnavailable("의미 검증기 응답이 JSON Object가 아닙니다.")
    return data


class ProviderSemanticGateVerifier:
    """AI_PROVIDER(gemini/claude/mock)에 맞는 의미 검증을 수행한다."""

    def __init__(self, provider: str):
        self.provider = provider

    def verify(self, question: dict, context) -> dict:
        if self.provider == "gemini":
            from ai_engine.gemini_generator import _call_api
            import os
            api_key = os.getenv("GEMINI_API_KEY")
            key_name = "GEMINI_API_KEY"
        elif self.provider == "claude":
            from ai_engine.question_generator import _call_api
            import os
            api_key = os.getenv("CLAUDE_API_KEY")
            key_name = "CLAUDE_API_KEY"
        else:
            # provider="mock"을 포함해 알 수 없는 값은 모두 의미 검증 불가로 처리한다.
            # Mock 결과를 근거가 확인된 문제처럼 PASS시키지 않는다.
            raise SemanticVerifierUnavailable(f"{self.provider} Provider는 의미 검증을 수행할 수 없습니다.")

        if not api_key:
            raise SemanticVerifierUnavailable(f"{key_name} 환경변수가 설정되지 않았습니다.")

        prompt = _build_prompt(question, context)
        try:
            raw_text = _call_api(prompt, api_key)
        except Exception as exc:
            raise SemanticVerifierUnavailable(f"{self.provider} 의미 검증 API 호출 실패: {exc}") from exc

        return _parse_response(raw_text)
