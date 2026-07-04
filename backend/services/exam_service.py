import random
import uuid
from datetime import datetime, timezone

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}


def _calc_dist(total: int) -> dict:
    upper = round(total * 0.28)
    mid   = round(total * 0.40)
    low   = total - upper - mid
    return {"상": upper, "중": mid, "하": low}


DEFAULT_EXAM_NAME = "OJT 기초고사"


def _get_repos():
    from repositories import question_repo, result_repo, snapshot_repo
    return question_repo, result_repo, snapshot_repo


def _find_assigned_exam_set(employee_id: str) -> dict | None:
    if not employee_id:
        return None
    from repositories import exam_set_repo
    candidates = [
        s for s in exam_set_repo.list_exam_sets()
        if employee_id in s.get("assigned_users", []) and s.get("status", "active") == "active"
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return candidates[0]


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


def get_assigned_exam_name(employee_id: str) -> str:
    assigned_set = _find_assigned_exam_set(employee_id)
    if not assigned_set:
        return DEFAULT_EXAM_NAME
    return assigned_set.get("name") or DEFAULT_EXAM_NAME


def generate_exam_questions(team_code: str, preview: bool = False, config: dict = None,
                            total_count: int = 25, manual_dist: dict = None,
                            employee_id: str = "") -> dict:
    q_repo, r_repo, s_repo = _get_repos()

    assigned_set = None if preview else _find_assigned_exam_set(employee_id)

    if assigned_set:
        exam_name = assigned_set.get("name") or DEFAULT_EXAM_NAME
        exam_set_id = assigned_set.get("exam_set_id", "")
        team_code = assigned_set.get("team_code", team_code)
        questions = [q_repo.get_question(qid) for qid in assigned_set.get("question_ids", [])]
        questions = [q for q in questions if q]
    else:
        exam_name = DEFAULT_EXAM_NAME
        exam_set_id = ""
        team_key = TEAM_KEY_MAP.get(team_code, "team1")

        data = q_repo.get_all_questions()
        # preview 모드는 approved+reviewing 포함, 실제 시험은 approved만
        allowed = {"approved", "reviewing"} if preview else {"approved"}
        pool = (
            [q for q in data.get("common",  []) if q.get("status") in allowed]
            + [q for q in data.get(team_key, []) if q.get("status") in allowed]
            + [q for q in data.get("safety",  []) if q.get("status") in allowed]
            + [q for q in data.get("general", []) if q.get("status") in allowed]
        )

        dist = manual_dist if manual_dist else _calc_dist(total_count)
        questions = _pick_by_difficulty(pool, dist)
        # 난이도별 부족 시 나머지 풀에서 보충
        if len(questions) < total_count:
            picked_ids = {q.get("question_id") for q in questions}
            remaining = [q for q in pool if q.get("question_id") not in picked_ids]
            random.shuffle(remaining)
            questions += remaining[:total_count - len(questions)]
        random.shuffle(questions)

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
        snapshot["_meta"] = {
            "team_code": team_code,
            "exam_set_id": exam_set_id,
            "name": exam_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        s_repo.save_snapshot(exam_id, snapshot)

    return {
        "exam_id": exam_id,
        "team_code": team_code,
        "name": exam_name,
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
                # admin preview에서는 난이도 포함, 응시자 화면에서는 제외 (설계 §9.4)
                **({ "difficulty": q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init", "중") } if preview else {}),
            }
            for q in questions
        ],
    }


def score_and_save(exam_id: str, answers: dict, response_times: dict, employee_id: str = "", name: str = "", skip_save: bool = False) -> dict:
    q_repo, r_repo, s_repo = _get_repos()

    snapshot = s_repo.get_snapshot(exam_id)
    if not snapshot:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=410,
            detail="시험 세션이 만료됐습니다. 시험을 다시 시작해주세요.",
        )

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
        "employee_id": employee_id,
        "exam_set_id": meta.get("exam_set_id") or "legacy",
        "name": name,
        "score": score,
        "pass": score >= 70,
        "difficulty_summary": difficulty_summary,
        "results": results,
        "team_code": meta.get("team_code", ""),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    if not skip_save:
        r_repo.append_result(result_data)
    return result_data


def get_exam_result(exam_id: str) -> dict:
    _, r_repo, _ = _get_repos()
    result = r_repo.get_result(exam_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    return result
