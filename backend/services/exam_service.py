import json
import random
import uuid
import os
from pathlib import Path

USE_MOCK = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
MOCK_DIR = Path(__file__).parent.parent / "mock_data"

# 난이도 배분 기준 (분야별)
DIFFICULTY_DIST = {
    "common":  {"상": 1, "중": 2, "하": 2},   # 5문항
    "team":    {"상": 3, "중": 4, "하": 3},   # 10문항
    "safety":  {"상": 2, "중": 2, "하": 1},   # 5문항
    "general": {"상": 1, "중": 2, "하": 2},   # 5문항
}

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}

# 메모리 내 시험 세션 저장 (실서비스에서는 Redis/DB 사용)
_exam_sessions: dict = {}


def _load_questions() -> dict:
    with open(MOCK_DIR / "questions.json", encoding="utf-8") as f:
        return json.load(f)


def _pick_by_difficulty(pool: list, dist: dict) -> list:
    """난이도 배분에 맞춰 랜덤 추출. 부족하면 채울 수 있는 만큼만."""
    result = []
    by_diff = {"상": [], "중": [], "하": []}
    for q in pool:
        d = q.get("difficulty_ai") or q.get("difficulty_init", "중")
        if d in by_diff:
            by_diff[d].append(q)
    for diff, count in dist.items():
        sample = random.sample(by_diff[diff], min(count, len(by_diff[diff])))
        result.extend(sample)
    return result


def generate_exam_questions(team_code: str, preview: bool = False, config: dict = None) -> dict:
    data = _load_questions()
    team_key = TEAM_KEY_MAP.get(team_code, "team1")

    questions = (
        _pick_by_difficulty(data["common"], DIFFICULTY_DIST["common"])
        + _pick_by_difficulty(data.get(team_key, []), DIFFICULTY_DIST["team"])
        + _pick_by_difficulty(data["safety"], DIFFICULTY_DIST["safety"])
        + _pick_by_difficulty(data["general"], DIFFICULTY_DIST["general"])
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
        correct = q["answer"] == user_ans.upper()
        if correct:
            score += 4  # 25문항 * 4점 = 100점 만점
        results.append({
            "q_id": qid,
            "correct": correct,
            "answer": q["answer"],
            "user_answer": user_ans,
            "difficulty": q.get("difficulty_ai") or q.get("difficulty_init"),
            "response_time": response_times.get(qid, 0),
        })

    # TODO: USE_MOCK=false 이면 Google Drive 결과로그에 저장
    del _exam_sessions[exam_id]  # 세션 제거 (데이터 휘발성)

    return {
        "exam_id": exam_id,
        "score": score,
        "pass": score >= 70,
        "results": results,
    }


def get_exam_result(exam_id: str) -> dict:
    # TODO: Drive 결과로그에서 조회
    return {"exam_id": exam_id, "message": "결과 조회 — Drive 연동 후 구현"}
