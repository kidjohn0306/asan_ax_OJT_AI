import json
from pathlib import Path
from datetime import datetime, timezone
from services.difficulty import update_difficulty_from_feedback

MOCK_DIR = Path(__file__).parent.parent / "mock_data"
TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}


def _get_repos():
    from repositories import question_repo, result_repo, feedback_repo
    return question_repo, result_repo, feedback_repo


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
    _, r_repo, _ = _get_repos()
    return {"count": r_repo.count()}


def fetch_user_count() -> dict:
    data = _load_users()
    return {"count": len(data["approved_users"])}


def fetch_approved_question_count() -> dict:
    q_repo, _, _ = _get_repos()
    return {"count": q_repo.count_by_status("approved")}


def fetch_reviewing_question_count() -> dict:
    q_repo, _, _ = _get_repos()
    return {"count": q_repo.count_by_status("reviewing")}


def fetch_logs(team=None, date_from=None, date_to=None) -> dict:
    _, r_repo, _ = _get_repos()
    all_results = r_repo.get_all_results()

    logs = []
    for r in all_results.values():
        # results.jsonl에 name 필드가 없으면 team_code로 대체
        log = {
            "name": r.get("name", r.get("team_code", "-")),
            "team": r.get("team_code", "-"),
            "date": r.get("submitted_at", "")[:10],
            "score": r.get("score", 0),
            "pass": r.get("pass", False),
            "difficulty_dist": _calc_diff_dist(r.get("results", [])),
        }
        logs.append(log)

    # 데이터 없으면 더미 반환 (초기 상태 호환)
    if not logs:
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


def _calc_diff_dist(results: list) -> dict:
    dist = {"상": 0, "중": 0, "하": 0}
    for r in results:
        d = r.get("difficulty", "중")
        if d in dist:
            dist[d] += 1
    return dist


def fetch_questions(team=None, category=None, status=None) -> dict:
    q_repo, _, _ = _get_repos()

    if status:
        questions = q_repo.list_by_status(status)
    else:
        data = q_repo.get_all_questions()
        if team:
            team_key = TEAM_KEY_MAP.get(team)
            questions = data.get(team_key, [])
        else:
            questions = [q for pool in data.values() for q in pool]

    if category:
        questions = [q for q in questions if q.get("category") == category]

    return {"questions": questions}


def override_difficulty(question_id: str, new_difficulty: str, reason_code: str = "") -> dict:
    q_repo, _, fb_repo = _get_repos()

    q = q_repo.get_question(question_id)
    if not q:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")

    # 설계 §7.1: difficulty_ai(AI 판정값) vs 관리자 확정값 비교 (버그 수정)
    ai_difficulty = q.get("difficulty_ai") or q.get("difficulty_init", "중")
    log = []
    result = update_difficulty_from_feedback(question_id, ai_difficulty, new_difficulty, log)

    # admin_override 필드에 영속화 (인메모리 제거)
    q_repo.update_question(question_id, {"admin_override": new_difficulty})

    fb_repo.append_feedback({
        "question_id": question_id,
        "ai_difficulty": ai_difficulty,
        "admin_difficulty": new_difficulty,
        "reason_code": reason_code,
        "auto_confirmed": result["auto_confirmed"],
    })

    return {
        "updated": True,
        "question_id": question_id,
        "new_difficulty": new_difficulty,
        "ai_retrain_triggered": True,
        "auto_confirmed": result["auto_confirmed"],
    }


def generate_ai_questions(team_code: str, material_text: str, count: int, difficulty_hint: str) -> dict:
    from ai_engine.router import generate_questions_from_material
    category = TEAM_KEY_MAP.get(team_code, "team1")

    q_repo, _, _ = _get_repos()
    rejected = q_repo.list_by_status("rejected")
    rejected_examples = [q for q in rejected if q.get("reject_reason")]

    questions = generate_questions_from_material(material_text, category, count, difficulty_hint, rejected_examples)

    from services.generation.gates import run_gates

    passed, failed_list = [], []
    for q in questions:
        gate_result = run_gates(q)
        if gate_result["pass"]:
            q["status"] = "reviewing"
            q["flags"] = gate_result["flags"]
            q_repo.update_question(q["question_id"], q)
            passed.append(q)
        else:
            q["status"] = "draft"
            q["gate_errors"] = gate_result["failed"]
            failed_list.append(q)

    return {
        "team_code": team_code,
        "provider": __import__("os").getenv("AI_PROVIDER", "mock"),
        "count": len(passed),
        "failed_count": len(failed_list),
        "questions": [
            {
                "id": q.get("question_id", ""),
                "category": q.get("category", ""),
                "question": q.get("question", ""),
                "options": {
                    "A": q.get("option_a", ""),
                    "B": q.get("option_b", ""),
                    "C": q.get("option_c", ""),
                    "D": q.get("option_d", ""),
                },
                "difficulty": q.get("difficulty_ai") or q.get("difficulty_init", "중"),
                "gate_errors": q.get("gate_errors", []),
            }
            for q in passed + failed_list
        ],
    }


def approve_question(question_id: str) -> dict:
    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    if q.get("status") not in ("reviewing", "draft"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"승인 불가 상태: {q.get('status')}")
    q_repo.update_question(question_id, {"status": "approved"})
    return {"approved": True, "question_id": question_id}


def reject_question(question_id: str, reason: str) -> dict:
    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    q_repo.update_question(question_id, {
        "status": "rejected",
        "flags": {**q.get("flags", {}), "needs_edit": True},
        "reject_reason": reason,
    })
    return {"rejected": True, "question_id": question_id, "reason": reason}


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

    return {"approved": True, "employee_id": employee_id, "name": name, "team": team, "exam_date": exam_date}


def get_difficulty_overrides() -> dict:
    # 인메모리 제거 → questions.json의 admin_override 필드가 진실의 원본
    q_repo, _, _ = _get_repos()
    data = q_repo.get_all_questions()
    overrides = {}
    for pool in data.values():
        for q in pool:
            if q.get("admin_override"):
                overrides[q["question_id"]] = q["admin_override"]
    return overrides
