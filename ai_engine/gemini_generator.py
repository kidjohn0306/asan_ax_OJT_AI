"""
Gemini API 기반 문제 생성 모듈 (테스트용 — 무료 티어)
google-generativeai gRPC 충돌 방지를 위해 REST API 직접 호출
AI_PROVIDER=gemini 일 때 router.py에서 호출
"""
import os

import requests

from ai_engine._shared import truncate_material, build_prompt, parse_response

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def _call_api(prompt: str, api_key: str) -> str:
    response = requests.post(
        f"{GEMINI_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    response.raise_for_status()
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise ValueError(f"Gemini API 응답 형식 오류: {e}")


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
    rejected_examples: list[dict] = None,
    overused_questions: list[str] = None,
    difficulty_corrections: list[dict] = None,
) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    prompt = build_prompt(
        truncate_material(material_text), category, count, difficulty_hint,
        rejected_examples or [], overused_questions or [], difficulty_corrections or [],
    )
    raw = _call_api(prompt, api_key)
    questions_raw = parse_response(raw, "Gemini")

    return [
        {
            "question_id": f"{category[:1].upper()}-GEMINI-{i+1:03d}",
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
