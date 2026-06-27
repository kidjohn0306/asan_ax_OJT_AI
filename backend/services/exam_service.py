import random
import uuid
import os
from datetime import datetime, timezone

USE_MOCK = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

DIFFICULTY_DIST = {
    "common":  {"상": 1, "중": 2, "하": 2},
    "team":    {"상": 3, "중": 4, "하": 3},
    "safety":  {"상": 2, "중": 2, "하": 1},
    "general": {"상": 1, "중": 2, "하": 2},
}

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}


def _get_repos():
    from repositories import question_repo, result_repo, snapshot_repo
    return question_repo, result_repo, snapshot_repo


def _pick_by_difficulty(pool: list, dist: dict) -> list:
    # admin_override 우선 → difficulty_ai → difficulty_init
    def effective_diff(q):
        return q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init", "중")

    by_diff: dict = {"상": [], "중": [], "하": []}
    for q in pool:
        d = effective_diff(q)
        if d in by_diff:
            by_diff[d].append(q)
    result = []
    for diff, count in dist.items():
        result.extend(random.sample(by_diff[diff], min(count, len(by_diff[diff]))))
    return result


def generate_exam_questions(team_code: str, preview: bool = False, config: dict = None) -> dict:
    q_repo, r_repo, s_repo = _get_repos()
    team_key = TEAM_KEY_MAP.get(team_code, "team1")

    # 카테고리별로 approved 문제 직접 분리 (pool 키 기반)
    data = q_repo.get_all_questions()
    common  = [q for q in data.get("common",  []) if q.get("status") == "approved"]
    team_qs = [q for q in data.get(team_key,  []) if q.get("status") == "approved"]
    safety  = [q for q in data.get("safety",  []) if q.get("status") == "approved"]
    general = [q for q in data.get("general", []) if q.get("status") == "approved"]

    questions = (
        _pick_by_difficulty(common,  DIFFICULTY_DIST["common"])
        + _pick_by_difficulty(team_qs, DIFFICULTY_DIST["team"])
        + _pick_by_difficulty(safety,  DIFFICULTY_DIST["safety"])
        + _pick_by_difficulty(general, DIFFICULTY_DIST["general"])
    )

    exam_id = str(uuid.uuid4())

    if not preview:
        # 스냅샷 저장 (approved 문제 정보 + 정답 고정)
        snapshot = {
            q["question_id"]: {
                "question":   q["question"],
                "answer":     q["answer"],
                "difficulty": q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init"),
                "option_a":   q["option_a"],
                "option_b":   q["option_b"],
                "option_c":   q["option_c"],
                "option_d":   q["option_d"],
                "version":    q.get("version", 1),
            }
            for q in questions
        }
        snapshot["_meta"] = {"team_code": team_code, "created_at": datetime.now(timezone.utc).isoformat()}
        s_repo.save_snapshot(exam_id, snapshot)

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
                # 응시자 화면에는 난이도 숨김 (설계 §9.4)
            }
            for q in questions
        ],
    }


def score_and_save(exam_id: str, answers: dict, response_times: dict) -> dict:
    q_repo, r_repo, s_repo = _get_repos()

    # 스냅샷 기준으로 채점 (라이브 문제 아님)
    snapshot = s_repo.get_snapshot(exam_id)
    if not snapshot:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="시험 세션을 찾을 수 없습니다.")

    meta = snapshot.get("_meta", {})
    results = []
    score = 0
    difficulty_summary = {
        "상": {"correct": 0, "incorrect": 0},
        "중": {"correct": 0, "incorrect": 0},
        "하": {"correct": 0, "incorrect": 0},
    }

    for qid, user_ans in answers.items():
        q_snap = snapshot.get(qid)
        if not q_snap:
            continue
        correct = isinstance(user_ans, str) and q_snap["answer"] == user_ans.upper()
        if correct:
            score += 4  # 25문항 × 4점 = 100점 만점
        difficulty = q_snap.get("difficulty", "중")
        if difficulty in difficulty_summary:
            key = "correct" if correct else "incorrect"
            difficulty_summary[difficulty][key] += 1
        results.append({
            "q_id": qid,
            "correct": correct,
            "answer": q_snap["answer"],
            "user_answer": user_ans,
            "difficulty": difficulty,
            "response_time": response_times.get(qid, 0),
        })

    result_data = {
        "exam_id": exam_id,
        "score": score,
        "pass": score >= 70,
        "difficulty_summary": difficulty_summary,
        "results": results,
        "team_code": meta.get("team_code", ""),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    r_repo.append_result(result_data)
    return result_data


def get_exam_result(exam_id: str) -> dict:
    _, r_repo, _ = _get_repos()
    result = r_repo.get_result(exam_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    return result
