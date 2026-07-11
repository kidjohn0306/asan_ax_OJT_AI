"""
AI 문제 생성 라우터
AI_PROVIDER 환경변수로 백엔드 선택:
  mock   (기본값) — mock_data/questions.json 반환
  gemini           — Gemini API 무료 티어 (테스트용)
  claude           — Claude API (프로덕션)
"""
import os

AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").lower()


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
    rejected_examples: list = None,
    overused_questions: list = None,
) -> list[dict]:
    if AI_PROVIDER == "gemini":
        from ai_engine.gemini_generator import generate_questions_from_material as _gen
        return _gen(material_text, category, count, difficulty_hint, rejected_examples, overused_questions)

    if AI_PROVIDER == "claude":
        from ai_engine.question_generator import generate_questions_from_material as _gen
        return _gen(material_text, category, count, difficulty_hint, rejected_examples, overused_questions)

    # mock (기본값)
    from ai_engine.question_generator import _mock_generate
    return _mock_generate(category, count, difficulty_hint)
