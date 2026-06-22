import json
import random
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path

USE_MOCK = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
MOCK_DIR = Path(__file__).parent.parent / "mock_data"
RESULTS_FILE = MOCK_DIR / "results.json"

DIFFICULTY_DIST = {
    "common":  {"상": 1, "중": 2, "하": 2},
    "team":    {"상": 3, "중": 4, "하": 3},
    "safety":  {"상": 2, "중": 2, "하": 1},
    "general": {"상": 1, "중": 2, "하": 2},
}

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}

_exam_sessions: dict = {}


def _load_questions() -> dict:
    with open(MOCK_DIR / "questions.json", encoding="utf-8") as f:
        data = json.load(f)
    from services.admin_service import get_difficulty_overrides
    overrides = get_difficulty_overrides()
    if overrides:
        for pool in data.values():
            for q in pool:
                qid = q.get("question_id")
                if qid in overrides:
                    q["difficulty_ai"] = overrides[qid]
    return data


def _load_results() -> dict:
    if not RESULTS_FILE.exists():
        return {}
    with open(RESULTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_results(results: dict):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _pick_by_difficulty(pool: list, dist: dict) -> list:
    by_diff: dict = {"상": [], "중": [], "하": []}
    for q in pool:
        d = q.get("difficulty_ai") or q.get("difficulty_init", "중")
        if d in by_diff:
            by_diff[d].append(q)
    result = []
    for diff, count in dist.items():
        result.extend(random.sample(by_diff[diff], min(count, len(by_diff[diff]))))
    return result


def generate_exam_questions(team_code: str, preview: bool = False, config: dict = None) -> dict:
    data = _load_questions()
    team_key = TEAM_KEY_MAP.get(team_code, "team1")

    questions = (
        _pick_by_difficulty(data.get("common", []), DIFFICULTY_DIST["common"])
        + _pick_by_difficulty(data.get(team_key, []), DIFFICULTY_DIST["team"])
        + _pick_by_difficulty(data.get("safety", []), DIFFICULTY_DIST["safety"])
        + _pick_by_difficulty(data.get("general", []), DIFFICULTY_DIST["general"])
    )

    exam_id = str(uuid.uuid4())
    if not preview:
        _exam_sessions[exam_id] = {
            "team_code": team_code,
            "questions": {q["question_id"]: q for q in questions},
        }

    return {
        "exam_id": exam_id,
        "team_code": team_code,
        "preview": preview,
        "questions": [
            {
                "id": q["question_id"],
                "category": q["category"],
                "question": q["question"],
                "options": {
                    "A": q["option_a"],
                    "B": q["option_b"],
                    "C": q["option_c"],
                    "D": q["option_d"],
                },
                "difficulty": q.get("difficulty_ai") or q.get("difficulty_init"),
            }
            for q in questions
        ],
    }


def score_and_save(exam_id: str, answers: dict, response_times: dict) -> dict:
    session = _exam_sessions.get(exam_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="시험 세션을 찾을 수 없습니다.")

    questions = session["questions"]
    results = []
    score = 0

    for qid, user_ans in answers.items():
        q = questions.get(qid)
        if not q:
            continue
        correct = isinstance(user_ans, str) and q["answer"] == user_ans.upper()
        if correct:
            score += 4  # 25문항 × 4점 = 100점 만점
        results.append({
            "q_id": qid,
            "correct": correct,
            "answer": q["answer"],
            "user_answer": user_ans,
            "difficulty": q.get("difficulty_ai") or q.get("difficulty_init"),
            "response_time": response_times.get(qid, 0),
        })

    result_data = {
        "exam_id": exam_id,
        "score": score,
        "pass": score >= 70,
        "results": results,
        "team_code": session["team_code"],
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    if USE_MOCK:
        all_results = _load_results()
        all_results[exam_id] = result_data
        _save_results(all_results)
    # else: TODO Google Drive 저장

    del _exam_sessions[exam_id]
    return result_data


def get_exam_result(exam_id: str) -> dict:
    all_results = _load_results()
    result = all_results.get(exam_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다. Drive 연동 후 전체 조회 가능.")
    return result
