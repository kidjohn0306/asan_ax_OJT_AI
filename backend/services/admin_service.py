import json
from pathlib import Path

MOCK_DIR = Path(__file__).parent.parent / "mock_data"

# 메모리 내 난이도 수정 이력 (실서비스에서는 Drive difficulty_log.xlsx에 저장)
_difficulty_overrides: dict = {}
_auto_confirmed: set = set()  # 3회 연속 오류 없는 문항 ID


def fetch_logs(team=None, date_from=None, date_to=None) -> dict:
    # TODO: Google Drive 결과로그에서 조회
    return {
        "logs": [
            {"name": "홍길동", "team": "T1", "date": "2026-06-14", "score": 92, "pass": True, "difficulty_dist": {"상": 2, "중": 5, "하": 3}},
            {"name": "김철수", "team": "T2", "date": "2026-06-14", "score": 64, "pass": False, "difficulty_dist": {"상": 3, "중": 4, "하": 3}},
        ]
    }


def fetch_questions(team=None, category=None) -> dict:
    with open(MOCK_DIR / "questions.json", encoding="utf-8") as f:
        data = json.load(f)

    all_questions = []
    for key, pool in data.items():
        all_questions.extend(pool)

    if category:
        all_questions = [q for q in all_questions if q.get("category") == category]

    return {"questions": all_questions}


def override_difficulty(question_id: str, new_difficulty: str) -> dict:
    _difficulty_overrides[question_id] = new_difficulty
    # TODO: Drive difficulty_log.xlsx에 기록 + AI 재학습 트리거
    # 3회 연속 오류 없으면 자동 확정 처리 (실제 로직은 ai_engine에서)
    return {
        "updated": True,
        "question_id": question_id,
        "new_difficulty": new_difficulty,
        "ai_retrain_triggered": True,
        "auto_confirmed": question_id in _auto_confirmed,
    }


def approve_new_user(employee_id: str, name: str, team: str, exam_date: str) -> dict:
    # TODO: Drive 또는 사내 DB에 저장
    return {
        "approved": True,
        "employee_id": employee_id,
        "name": name,
        "team": team,
        "exam_date": exam_date,
    }
