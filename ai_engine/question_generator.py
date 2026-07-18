"""
Claude API 기반 문제 생성 모듈
AI_PROVIDER=claude 일 때 router.py에서 호출
"""
import os

from ai_engine._shared import (
    truncate_material, build_prompt, parse_response, generate_in_batches, shuffle_answer_position,
)

CLAUDE_MODEL = "claude-sonnet-5"

# 고정 max_tokens(4096)로는 한 배치(최대 MAX_QUESTIONS_PER_CALL문항)의 해설이 길 때도
# JSON 응답이 도중에 잘려("Unterminated string") 파싱이 실패했다 — 배치 문항 수에 비례해
# 여유 있게 늘리되 베타 헤더 없이 안전한 상한(8192) 안에서 맞춘다.
_BASE_OUTPUT_TOKENS = 500
_TOKENS_PER_QUESTION = 500
_MAX_OUTPUT_TOKENS = 8192


def _call_api(prompt: str, api_key: str, count: int = 10) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    max_tokens = min(_MAX_OUTPUT_TOKENS, _BASE_OUTPUT_TOKENS + _TOKENS_PER_QUESTION * count)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    # content[0]이 항상 텍스트 블록이라고 단정할 수 없음 — thinking 등 다른 블록이 먼저 올 수 있어
    # 텍스트가 있는 첫 블록을 찾는다
    for block in message.content:
        text = getattr(block, "text", None)
        if text:
            return text.strip()
    raise ValueError("Claude API 응답에 텍스트 콘텐츠가 없습니다.")


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
    rejected_examples: list[dict] = None,
    overused_questions: list[str] = None,
    difficulty_corrections: list[dict] = None,
) -> list[dict]:
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("CLAUDE_API_KEY 환경변수가 설정되지 않았습니다.")

    truncated_material = truncate_material(material_text)

    def _generate_batch(batch_count: int) -> list[dict]:
        prompt = build_prompt(
            truncated_material, category, batch_count, difficulty_hint,
            rejected_examples or [], overused_questions or [], difficulty_corrections or [],
        )
        raw = _call_api(prompt, api_key, batch_count)
        return parse_response(raw, "Claude")

    questions_raw = [shuffle_answer_position(q) for q in generate_in_batches(count, _generate_batch)]

    return [
        {
            "question_id": f"{category[:1].upper()}-CLAUDE-{i+1:03d}",
            "category": category,
            "question": q.get("question", ""),
            "option_a": q.get("option_a", ""),
            "option_b": q.get("option_b", ""),
            "option_c": q.get("option_c", ""),
            "option_d": q.get("option_d", ""),
            "answer": str(q.get("answer", "A")).strip().upper(),
            "explanation": q.get("explanation", ""),
            "difficulty_init": q.get("difficulty_init", difficulty_hint),
            "difficulty_ai": q.get("difficulty_init", difficulty_hint),
            "admin_override": "",
        }
        for i, q in enumerate(questions_raw[:count])
    ]


def _mock_generate(category: str, count: int, difficulty_hint: str = "중") -> list[dict]:
    return [
        {
            "question_id": f"{category[:1].upper()}-MOCK-{i+1:03d}",
            "category": category,
            "question": f"[Mock] {category} 관련 문제 {i+1}번",
            "option_a": "보기 A",
            "option_b": "보기 B",
            "option_c": "보기 C",
            "option_d": "보기 D",
            "answer": "A",
            "explanation": f"[Mock] {category} 문제 {i+1}번 해설",
            "difficulty_init": difficulty_hint,
            "difficulty_ai": difficulty_hint,
            "admin_override": "",
        }
        for i in range(count)
    ]
