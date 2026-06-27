"""
Claude API 기반 문제 생성 모듈 (프로덕션용)
AI_PROVIDER=claude 일 때 router.py에서 호출
"""
import os

def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""다음 OJT 교육자료를 바탕으로 {category} 분야 객관식 문제 {count}개를 생성하세요.
난이도는 '{difficulty_hint}'을 기준으로 합니다.

[교육자료]
{material_text}

각 문제는 아래 JSON 배열 형식으로만 출력하세요 (설명 없이 순수 JSON):
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

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    import json, re
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    questions_raw = json.loads(raw)

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
