"""
AI 난이도 판정 알고리즘
정답률(50%) + 응답시간(30%) + 평균점수 대비(20%) 가중치

현재는 규칙 기반(rule-based)으로 구현.
실제 Claude API 연동 후 AI 판정으로 교체 예정.
"""


def classify_difficulty(
    correct_rate: float,    # 0.0 ~ 1.0
    avg_response_time: float,  # 초
    score_percentile: float,   # 0.0 ~ 1.0 (응시자 집단 내 상대 위치)
) -> str:
    """
    Returns: "상" | "중" | "하"
    """
    # 정답률 점수 (0~50)
    if correct_rate >= 0.8:
        rate_score = 0      # 쉬움 → 하 방향
    elif correct_rate >= 0.5:
        rate_score = 25
    else:
        rate_score = 50     # 어려움 → 상 방향

    # 응답시간 점수 (0~30)
    if avg_response_time <= 10:
        time_score = 0
    elif avg_response_time <= 30:
        time_score = 15
    else:
        time_score = 30

    # 상대 점수 점수 (0~20)
    if score_percentile >= 0.7:
        percentile_score = 0
    elif score_percentile >= 0.4:
        percentile_score = 10
    else:
        percentile_score = 20

    total = rate_score + time_score + percentile_score  # 0~100

    if total >= 60:
        return "상"
    elif total >= 30:
        return "중"
    else:
        return "하"


def update_difficulty_from_feedback(
    question_id: str,
    ai_difficulty: str,
    admin_difficulty: str,
    error_log: list,  # 최근 판정 오류 이력
) -> dict:
    """
    관리자 재조정 후 AI 학습 루프 처리.
    오류 0회 × 3회 연속이면 auto_confirmed=True 반환.
    """
    is_error = ai_difficulty != admin_difficulty
    error_log.append(is_error)

    recent = error_log[-3:] if len(error_log) >= 3 else error_log
    auto_confirmed = len(recent) == 3 and not any(recent)

    return {
        "question_id": question_id,
        "new_difficulty": admin_difficulty,
        "auto_confirmed": auto_confirmed,
        "error_log_length": len(error_log),
    }
