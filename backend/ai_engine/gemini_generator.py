"""
Gemini API 기반 문제 생성 모듈 (테스트용 — 무료 티어)
AI_PROVIDER=gemini 일 때 router.py에서 호출
"""
import os
import json
import re

import google.generativeai as genai


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""다음 OJT 교육자료를 바탕으로 {category} 분야 객관식 문제 {count}개를 생성하세요.
난이도는 '{difficulty_hint}'을 기준으로 합니다.

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

    response = model.generate_content(prompt)
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    questions_raw = json.loads(raw)

    return [
        {
            "question_id": f"{category[:1].upper()}-GEMINI-{i+1:03d}",
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
