"""
Claude API 기반 문제 생성 모듈
AI_PROVIDER=claude 일 때 router.py에서 호출
"""
import os

from ai_engine._shared import truncate_material, build_prompt, parse_response

CLAUDE_MODEL = "claude-sonnet-5"


def _call_api(prompt: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
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

    prompt = build_prompt(
        truncate_material(material_text), category, count, difficulty_hint,
        rejected_examples or [], overused_questions or [], difficulty_corrections or [],
    )
    raw = _call_api(prompt, api_key)
    questions_raw = parse_response(raw, "Claude")

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
