"""
Gemini API 기반 문제 생성 모듈 (테스트용 — 무료 티어)
google-generativeai gRPC 충돌 방지를 위해 REST API 직접 호출
AI_PROVIDER=gemini 일 때 router.py에서 호출
"""
import os
import json
import re

import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
_MAX_REJECTED_EXAMPLES = 5
_MAX_OVERUSED_EXAMPLES = 5
_MAX_MATERIAL_CHARS = 4000  # 약 1000 토큰 — 무료 티어 토큰 절약


def _truncate_material(text: str) -> str:
    if len(text) <= _MAX_MATERIAL_CHARS:
        return text
    # 문장 경계에서 자름
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
        # 전체 문제은행이 아닌 자주 출제된 문항 몇 개만 전달해 토큰을 아끼면서 중복 출제를 회피
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


def _parse_response(raw: str) -> list:
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini 응답 JSON 파싱 실패: {e}")


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
    rejected_examples: list[dict] = None,
    overused_questions: list[str] = None,
) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    prompt = _build_prompt(
        _truncate_material(material_text), category, count, difficulty_hint,
        rejected_examples or [], overused_questions or [],
    )
    raw = _call_api(prompt, api_key)
    questions_raw = _parse_response(raw)

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
