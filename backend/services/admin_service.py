import json
from pathlib import Path
from services.difficulty import update_difficulty_from_feedback

MOCK_DIR = Path(__file__).parent.parent / "mock_data"
TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}

_difficulty_overrides: dict = {}
_difficulty_error_logs: dict[str, list] = {}


def _load_users() -> dict:
    with open(MOCK_DIR / "users.json", encoding="utf-8") as f:
        return json.load(f)


def _save_users(data: dict):
    with open(MOCK_DIR / "users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_users() -> dict:
    data = _load_users()
    return {"users": data["approved_users"]}


def delete_user(employee_id: str) -> dict:
    data = _load_users()
    before = len(data["approved_users"])
    data["approved_users"] = [u for u in data["approved_users"] if u["employee_id"] != employee_id]
    if len(data["approved_users"]) == before:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    _save_users(data)
    return {"deleted": True, "employee_id": employee_id}


def fetch_exam_count() -> dict:
    results_file = MOCK_DIR / "results.json"
    if not results_file.exists():
        return {"count": 0}
    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)
    return {"count": len(data)}


def fetch_user_count() -> dict:
    data = _load_users()
    return {"count": len(data["approved_users"])}


def get_difficulty_overrides() -> dict:
    return _difficulty_overrides


def fetch_logs(team=None, date_from=None, date_to=None) -> dict:
    # TODO: Google Drive 결과로그에서 조회
    logs = [
        {"name": "홍길동", "team": "T1", "date": "2026-06-14", "score": 92, "pass": True,  "difficulty_dist": {"상": 2, "중": 5, "하": 3}},
        {"name": "김철수", "team": "T2", "date": "2026-06-14", "score": 64, "pass": False, "difficulty_dist": {"상": 3, "중": 4, "하": 3}},
        {"name": "박영희", "team": "T1", "date": "2026-06-13", "score": 88, "pass": True,  "difficulty_dist": {"상": 2, "중": 5, "하": 3}},
        {"name": "이민수", "team": "T3", "date": "2026-06-13", "score": 65, "pass": False, "difficulty_dist": {"상": 3, "중": 4, "하": 3}},
        {"name": "최지훈", "team": "T2", "date": "2026-06-12", "score": 95, "pass": True,  "difficulty_dist": {"상": 2, "중": 6, "하": 2}},
    ]
    if team:
        logs = [l for l in logs if l["team"] == team]
    if date_from:
        logs = [l for l in logs if l["date"] >= date_from]
    if date_to:
        logs = [l for l in logs if l["date"] <= date_to]
    return {"logs": logs}


def fetch_questions(team=None, category=None) -> dict:
    with open(MOCK_DIR / "questions.json", encoding="utf-8") as f:
        data = json.load(f)

    all_questions = []
    if team:
        team_key = TEAM_KEY_MAP.get(team)
        all_questions.extend(data.get(team_key, []))
    else:
        for pool in data.values():
            all_questions.extend(pool)

    if category:
        all_questions = [q for q in all_questions if q.get("category") == category]

    # Apply in-memory admin overrides so the UI reflects changes immediately
    for q in all_questions:
        qid = q.get("question_id")
        if qid in _difficulty_overrides:
            q["difficulty_ai"] = _difficulty_overrides[qid]

    return {"questions": all_questions}


def override_difficulty(question_id: str, new_difficulty: str) -> dict:
    prev = _difficulty_overrides.get(question_id, new_difficulty)
    log = _difficulty_error_logs.setdefault(question_id, [])
    result = update_difficulty_from_feedback(question_id, prev, new_difficulty, log)
    _difficulty_overrides[question_id] = new_difficulty
    # TODO: Drive difficulty_log.xlsx 기록 + AI 재학습 트리거
    return {
        "updated": True,
        "question_id": question_id,
        "new_difficulty": new_difficulty,
        "ai_retrain_triggered": True,
        "auto_confirmed": result["auto_confirmed"],
    }


def approve_new_user(employee_id: str, name: str, team: str, exam_date: str) -> dict:
    data = _load_users()
    all_users = data["approved_users"] + data["admins"]

    if any(u["employee_id"] == employee_id for u in all_users):
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="이미 등록된 사원번호입니다.")

    new_user = {
        "employee_id": employee_id,
        "password_hash": "mock_hash",
        "name": name,
        "team": team,
        "role": "examinee",
        "exam_date": exam_date,
        "approved": True,
    }
    data["approved_users"].append(new_user)
    _save_users(data)

    return {
        "approved": True,
        "employee_id": employee_id,
        "name": name,
        "team": team,
        "exam_date": exam_date,
    }
