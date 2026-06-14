"""
C팀 담당: Claude API 기반 문제 생성 모듈
USE_MOCK_DATA=true 이면 mock_data/questions.json 반환
USE_MOCK_DATA=false 이면 Claude API 호출
"""
import os

USE_MOCK = os.getenv("USE_MOCK_DATA", "true").lower() == "true"


def generate_questions_from_material(
    material_text: str,
    category: str,
    count: int = 10,
    difficulty_hint: str = "중",
) -> list[dict]:
    """
    OJT 교육자료 텍스트 → Claude API로 문항 생성
    material_text: Google Drive에서 읽어온 Excel/Doc 내용
    """
    if USE_MOCK:
        return _mock_generate(category, count)

    # TODO: Claude API 연동
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""
다음 OJT 교육자료를 바탕으로 {category} 분야 객관식 문제 {count}개를 생성하세요.
난이도는 '{difficulty_hint}'을 기준으로 합니다.

[교육자료]
{material_text}

각 문제는 JSON 형식으로 출력하세요:
{{
  "question": "문제 내용",
  "option_a": "보기 A",
  "option_b": "보기 B",
  "option_c": "보기 C",
  "option_d": "보기 D",
  "answer": "A|B|C|D",
  "difficulty_init": "상|중|하"
}}
"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    # TODO: JSON 파싱 및 검증
    return []


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
