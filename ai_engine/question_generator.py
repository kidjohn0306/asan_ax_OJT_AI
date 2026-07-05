"""
Claude API 기반 문제 생성 모듈
AI_PROVIDER=claude 일 때 router.py에서 호출
"""
import os
import json
import re

CLAUDE_MODEL = "claude-sonnet-5"
_MAX_REJECTED_EXAMPLES = 5
_MAX_OVERUSED_EXAMPLES = 5
_MAX_MATERIAL_CHARS = 4000  # 토큰 절약을 위한 자료 절단 한도 (gemini_generator.py와 동일 정책)


def _truncate_material(text: str) -> str:
    if len(text) <= _MAX_MATERIAL_CHARS:
        return text
    truncated = text[:_MAX_MATERIAL_CHARS]
    last_period = max(truncated.rfind('。'), truncated.rfind('.'), truncated.rfind('\n'))
    if last_period > _MAX_MATERIAL_CHARS * 0.7:
        truncated = truncated[:last_period + 1]
    return truncated + "\n[이하 생략 — 토큰 절약을 위해 요약 처리됨]"


def _build_prompt(
    material_text: str, category: str, count: int, difficulty_hint: str,
    rejected_examples: list, overused_questions: list = None,
) -> str:
    rejection_block = ""
    if rejected_examples:
        lines = "\n".join(
            f'  - 문제: "{q["question"]}" → 반려 사유: {q.get("reject_reason", "미기재")}'
            for q in rejected_examples[:_MAX_REJECTED_EXAMPLES]
        )
        rejection_block = f"\n[반드시 피해야 할 문제 유형 (과거 반려 사례)]\n{lines}\n위 사례와 유사한 문제는 절대 생성하지 마세요.\n"

    overused_block = ""
    if overused_questions:
        lines = "\n".join(f'  - "{q}"' for q in overused_questions[:_MAX_OVERUSED_EXAMPLES])
        overused_block = f"\n[이미 자주 출제되어 새로운 문제가 필요한 항목 (과다 출제됨)]\n{lines}\n위 문제들과 동일하거나 매우 유사한 문제는 생성하지 마세요.\n"

    return f"""다음 OJT 교육자료를 바탕으로 {category} 분야 객관식 문제 {count}개를 생성하세요.
난이도는 '{difficulty_hint}'을 기준으로 합니다.
{rejection_block}{overused_block}
[교육자료]
{material_text}

반드시 아래 JSON 배열 형식으로만 출력하고, 설명이나 마크다운 없이 순수 JSON만 반환하세요:
[
  {{
    "question": "문제 내용",
    "option_a": "보기 A",
    "option_b": "보기 B",
    "option_c": "보기 C",
    "option_d": "보기 D",
    "answer": "A",
    "difficulty_init": "{difficulty_hint}"
  }}
]"""


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


def _parse_response(raw: str) -> list:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    # 모델이 지시를 무시하고 JSON 앞뒤에 설명 텍스트를 덧붙이는 경우를 대비해
    # 첫 '['부터 마지막 ']'까지만 잘라서 파싱한다
    start, end = raw.find('['), raw.rfind(']')
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 응답 JSON 파싱 실패: {e}")


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
    rejected_examples: list[dict] = None,
    overused_questions: list[str] = None,
) -> list[dict]:
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("CLAUDE_API_KEY 환경변수가 설정되지 않았습니다.")

    prompt = _build_prompt(
        _truncate_material(material_text), category, count, difficulty_hint,
        rejected_examples or [], overused_questions or [],
    )
    raw = _call_api(prompt, api_key)
    questions_raw = _parse_response(raw)

    return [
        {
            "question_id": f"{category[:1].upper()}-CLAUDE-{i+1:03d}",
            "category": category,
            "question": q.get("question", ""),
            "option_a": q.get("option_a", ""),
            "option_b": q.get("option_b", ""),
            "option_c": q.get("option_c", ""),
            "option_d": q.get("option_d", ""),
            "answer": q.get("answer", "A").upper(),
            "difficulty_init": q.get("difficulty_init", difficulty_hint),
            "difficulty_ai": q.get("difficulty_init", difficulty_hint),
            "admin_override": "",
        }
        for i, q in enumerate(questions_raw[:count])
    ]


def _mock_generate(category: str, count: int) -> list[dict]:
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
            "difficulty_init": "중",
            "difficulty_ai": "중",
            "admin_override": "",
        }
        for i in range(count)
    ]
