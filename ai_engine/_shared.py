"""
gemini_generator.py / question_generator.py 공통 로직 (자료 절단, 프롬프트 생성, 응답 파싱).
두 모듈이 byte-for-byte 동일하게 구현하고 있던 부분을 통합했다.
"""
import json
import re

MAX_REJECTED_EXAMPLES = 5
MAX_OVERUSED_EXAMPLES = 5
MAX_DIFFICULTY_EXAMPLES = 5
MAX_MATERIAL_CHARS = 4000  # 약 1000 토큰 — 토큰 절약을 위한 자료 절단 한도


def truncate_material(text: str) -> str:
    if len(text) <= MAX_MATERIAL_CHARS:
        return text
    # 문장 경계에서 자름
    truncated = text[:MAX_MATERIAL_CHARS]
    last_period = max(truncated.rfind('。'), truncated.rfind('.'), truncated.rfind('\n'))
    if last_period > MAX_MATERIAL_CHARS * 0.7:
        truncated = truncated[:last_period + 1]
    return truncated + "\n[이하 생략 — 토큰 절약을 위해 요약 처리됨]"


def build_prompt(
    material_text: str, category: str, count: int, difficulty_hint: str,
    rejected_examples: list, overused_questions: list = None,
    difficulty_corrections: list = None,
) -> str:
    rejection_block = ""
    if rejected_examples:
        lines = "\n".join(
            f'  - 문제: "{q["question"]}" → 반려 사유: {q.get("reject_reason", "미기재")}'
            for q in rejected_examples[:MAX_REJECTED_EXAMPLES]
        )
        rejection_block = f"\n[반드시 피해야 할 문제 유형 (과거 반려 사례)]\n{lines}\n위 사례와 유사한 문제는 절대 생성하지 마세요.\n"

    overused_block = ""
    if overused_questions:
        # 전체 문제은행이 아닌 자주 출제된 문항 몇 개만 전달해 토큰을 아끼면서 중복 출제를 회피
        lines = "\n".join(f'  - "{q}"' for q in overused_questions[:MAX_OVERUSED_EXAMPLES])
        overused_block = f"\n[이미 자주 출제되어 새로운 문제가 필요한 항목 (과다 출제됨)]\n{lines}\n위 문제들과 동일하거나 매우 유사한 문제는 생성하지 마세요.\n"

    difficulty_block = ""
    if difficulty_corrections:
        lines = "\n".join(
            f'  - 문제: "{c["question_text"]}" → AI 예측: {c["ai_difficulty"]}, 관리자 확정: {c["admin_difficulty"]}'
            for c in difficulty_corrections[:MAX_DIFFICULTY_EXAMPLES]
        )
        difficulty_block = f"\n[난이도 판정 보정 이력 (관리자가 재조정한 최근 사례)]\n{lines}\n위 사례를 참고하여 이번 문제들의 난이도 판정을 더 정확히 하세요.\n"

    return f"""다음 OJT 교육자료를 바탕으로 {category} 분야 객관식 문제 {count}개를 생성하세요.
난이도는 '{difficulty_hint}'을 기준으로 합니다.
{rejection_block}{overused_block}{difficulty_block}
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
    "explanation": "정답 근거 (교육자료 기준 해설)",
    "difficulty_init": "{difficulty_hint}"
  }}
]"""


def parse_response(raw: str, provider_label: str) -> list:
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
        raise ValueError(f"{provider_label} 응답 JSON 파싱 실패: {e}")
