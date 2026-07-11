import logging
import os
import time

from fastapi import HTTPException
from services.difficulty import update_difficulty_from_feedback

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}

# pool_key(문제 저장 위치: common/team1/team2/.../safety/general) -> 문제의 category 필드에 쓰이는
# 한글 분류 라벨. 문제은행 시드 데이터·gates.py의 VALID_CATEGORIES·프론트 카테고리 필터가 모두 이 한글
# 라벨을 기준으로 하므로, AI 문제 생성 시에도 pool_key가 아니라 이 라벨을 category로 사용해야 한다.
_POOL_KEY_TO_CATEGORY_LABEL = {"common": "공통", "safety": "환경안전", "general": "일반상식"}


def _category_label_for_pool(pool_key: str) -> str:
    return _POOL_KEY_TO_CATEGORY_LABEL.get(pool_key, "팀별")


def _get_repos():
    from repositories import question_repo, result_repo, feedback_repo
    return question_repo, result_repo, feedback_repo


def fetch_users() -> dict:
    from repositories import user_repo
    return {"users": user_repo.list_users()}


def delete_user(employee_id: str) -> dict:
    from repositories import user_repo
    if not user_repo.delete_user(employee_id):
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {"deleted": True, "employee_id": employee_id}


def reset_user_password(employee_id: str) -> dict:
    """관리자가 사용자 비밀번호를 임시 비밀번호로 초기화. 실제 발급된 비밀번호는
    이메일 연동이 없어 응답으로 반환 — 관리자가 직접 사용자에게 전달해야 함."""
    import secrets
    import string
    from repositories import user_repo
    from repositories.local_json import update_local_admin_password
    from services.auth_service import pwd_context

    alphabet = string.ascii_uppercase + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(10))
    password_hash = pwd_context.hash(temp_password)

    if not (user_repo.update_user(employee_id, {"password_hash": password_hash})
            or update_local_admin_password(employee_id, password_hash)):
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    return {"employee_id": employee_id, "temp_password": temp_password}


def fetch_exam_count() -> dict:
    _, r_repo, _ = _get_repos()
    return {"count": r_repo.count()}


def fetch_user_count() -> dict:
    from repositories import user_repo
    return {"count": len(user_repo.list_users())}


def fetch_team_headcounts() -> dict:
    """팀별 실제 소속(승인된) 인원수 — 팀 관리 화면에서 정원과 대조하기 위한 실제 값."""
    from repositories import user_repo
    counts: dict = {}
    for u in user_repo.list_users():
        team = u.get("team") or "미배정"
        counts[team] = counts.get(team, 0) + 1
    return {"headcounts": counts}


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
        log = {
            "name": r.get("name", r.get("team_code", "-")),
            "team": r.get("team_code", "-"),
            "date": r.get("submitted_at", "")[:10],
            "score": r.get("score", 0),
            "pass": r.get("pass", False),
            "difficulty_dist": _calc_diff_dist(r.get("results", [])),
        }
        logs.append(log)

    if team:
        logs = [l for l in logs if l["team"] == team]
    if date_from:
        logs = [l for l in logs if l["date"] >= date_from]
    if date_to:
        logs = [l for l in logs if l["date"] <= date_to]
    return {"logs": logs}


def fetch_results_analysis() -> dict:
    """결과 분석 화면용 실제 응시 결과 집계 — 시험 회차(exam_id) 단위로 그룹화한다.
    같은 시험지(exam_set_id)를 여러 회차가 공유할 수 있으므로 회차 단위로 묶어야 한다.
    데이터가 없으면 빈 요약을 반환한다(목업으로 채우지 않음)."""
    from repositories import team_repo, exam_set_repo
    _, r_repo, _ = _get_repos()
    all_results = list(r_repo.get_all_results().values())

    team_names = {t["team_code"]: t["team_name"] for t in team_repo.list_teams()}
    exam_meta = {s["exam_id"]: s for s in exam_set_repo.list_exam_sets()}

    groups: dict = {}
    for r in all_results:
        groups.setdefault(r.get("exam_id") or "legacy", []).append(r)

    exams = []
    for exam_id, group in groups.items():
        meta = exam_meta.get(exam_id, {})
        team_code = meta.get("team_code") or group[0].get("team_code", "-")
        takers = sorted(
            [
                {
                    "employee_id": r.get("employee_id", "-"),
                    "name": r.get("name") or "-",
                    "score": r.get("score", 0),
                    "pass": r.get("pass", False),
                    "date": r.get("submitted_at", "")[:10],
                    "results": r.get("results", []),
                }
                for r in group
            ],
            key=lambda x: x["date"],
            reverse=True,
        )
        g_count = len(group)
        g_correct = sum(1 for r in group for q in r.get("results", []) if q.get("correct"))
        g_answered = sum(len(r.get("results", [])) for r in group)
        exams.append({
            "exam_id": exam_id,
            "exam_set_id": meta.get("exam_set_id", exam_id),
            "name": meta.get("name") or "미배정 시험(레거시)",
            "team_code": team_code,
            "team_name": team_names.get(team_code, team_code),
            "exam_datetime": meta.get("exam_datetime") or meta.get("created_at", ""),
            "taker_count": g_count,
            "avg_score": round(sum(r.get("score", 0) for r in group) / g_count, 1),
            "pass_count": sum(1 for r in group if r.get("pass")),
            "accuracy_pct": round(g_correct / g_answered * 100, 1) if g_answered else 0,
            "takers": takers,
        })
    exams.sort(key=lambda x: (x["exam_datetime"] or "", x["takers"][0]["date"] if x["takers"] else ""), reverse=True)

    if not all_results:
        return {
            "summary": {"count": 0, "avg_score": 0, "accuracy_pct": 0, "pass_count": 0},
            "team_averages": [],
            "difficulty_accuracy": {},
            "exams": [],
            "insights": [],
        }

    count = len(all_results)
    avg_score = round(sum(r.get("score", 0) for r in all_results) / count, 1)
    pass_count = sum(1 for r in all_results if r.get("pass"))

    total_correct = total_answered = 0
    diff_totals = {"상": {"correct": 0, "total": 0}, "중": {"correct": 0, "total": 0}, "하": {"correct": 0, "total": 0}}
    for r in all_results:
        for q in r.get("results", []):
            total_answered += 1
            if q.get("correct"):
                total_correct += 1
            d = q.get("difficulty")
            if d in diff_totals:
                diff_totals[d]["total"] += 1
                if q.get("correct"):
                    diff_totals[d]["correct"] += 1
    accuracy_pct = round(total_correct / total_answered * 100, 1) if total_answered else 0

    difficulty_accuracy = {
        d: {**v, "pct": round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0}
        for d, v in diff_totals.items()
    }

    team_scores: dict = {}
    for r in all_results:
        team_scores.setdefault(r.get("team_code", "-"), []).append(r.get("score", 0))
    team_averages = sorted(
        [
            {
                "team_code": code,
                "team_name": team_names.get(code, code),
                "avg_score": round(sum(scores) / len(scores), 1),
                "count": len(scores),
            }
            for code, scores in team_scores.items()
        ],
        key=lambda x: x["avg_score"],
    )

    insights = []
    if team_averages:
        weakest_team = team_averages[0]
        insights.append(f"{weakest_team['team_name']} 평균 점수가 {weakest_team['avg_score']}점으로 가장 낮습니다.")
    scored_diffs = {d: v for d, v in difficulty_accuracy.items() if v["total"] > 0}
    if scored_diffs:
        weakest_diff = min(scored_diffs.items(), key=lambda kv: kv[1]["pct"])
        insights.append(f"난이도 '{weakest_diff[0]}' 문항의 정답률이 {weakest_diff[1]['pct']}%로 가장 낮습니다.")
    insights.append(
        f"전체 정답률은 {accuracy_pct}%, 합격률은 {round(pass_count / count * 100, 1)}%입니다."
    )

    return {
        "summary": {"count": count, "avg_score": avg_score, "accuracy_pct": accuracy_pct, "pass_count": pass_count},
        "team_averages": team_averages,
        "difficulty_accuracy": difficulty_accuracy,
        "exams": exams,
        "insights": insights,
    }


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
            team_key = TEAM_KEY_MAP.get(team, team)
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
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")

    ai_difficulty = q.get("difficulty_ai") or q.get("difficulty_init", "중")
    log = []
    result = update_difficulty_from_feedback(question_id, ai_difficulty, new_difficulty, log)

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
    from services.generation.gates import run_gates
    from services.material_service import get_material_text_for_team

    from repositories import question_stats_repo

    category = TEAM_KEY_MAP.get(team_code, team_code)  # pool_key — 문제 저장 위치(add_question)에 사용
    category_label = _category_label_for_pool(category)  # 공통/팀별/환경안전/일반상식 — 문제의 category 필드·게이트 검증·프론트 필터에 사용
    q_repo, _, _ = _get_repos()

    # Drive에서 스캔해둔 교육자료(공통+팀별)를 기본 자료로 사용하고,
    # 관리자가 직접 붙여넣은 텍스트는 이번 출제에 한해 보충하는 내용으로 뒤에 덧붙인다.
    # (수동 입력으로 자동 스캔 자료가 사라지지 않도록 둘 다 살리는 방식)
    try:
        drive_material = get_material_text_for_team(team_code)
    except Exception:
        drive_material = ""
    material_text = "\n\n".join(t for t in (drive_material, material_text) if t)
    rejected = q_repo.list_by_status("rejected")
    rejected_examples = [q for q in rejected if q.get("reject_reason")]

    overused_questions = []
    try:
        flagged_ids = {stat["question_id"] for stat in question_stats_repo.list_flagged()}
        if flagged_ids:
            # get_question()을 건마다 호출하면 매번 전체 문제은행을 다시 읽으므로(N+1),
            # 문제은행을 한 번만 불러와 조회한다.
            all_pools = q_repo.get_all_questions().values()
            overused_questions = [
                q["question"] for pool in all_pools for q in pool
                if q.get("question_id") in flagged_ids and q.get("question")
            ]
    except Exception:
        pass  # 통계 조회 실패는 문제 생성 자체를 막지 않음

    try:
        questions = generate_questions_from_material(
            material_text, category_label, count, difficulty_hint, rejected_examples, overused_questions
        )
    except Exception as e:
        provider = os.getenv("AI_PROVIDER", "mock")
        logging.exception(f"AI 문제 생성 실패 (provider={provider}): {e}")
        raise HTTPException(status_code=502, detail="AI 문제 생성에 실패했습니다. 잠시 후 다시 시도해주세요.")

    # 생성기가 자체 부여한 question_id(예: "팀-CLAUDE-001")는 category_label의 첫 글자만 써서
    # team1/team2/team3처럼 category_label이 같은(둘 다 "팀별") 다른 팀끼리 ID가 충돌한다.
    # get_question()은 ID만으로 전체 풀을 검색하므로, 충돌 시 엉뚱한 팀의(이미 승인/반려된) 문제가
    # 대신 조회되어 승인·반려·난이도 조정이 잘못된 문제에 적용되는 심각한 버그로 이어진다.
    # pool_key(팀별로 고유) + 생성 시각(배치별로 고유)을 넣어 전역 유일성을 보장한다.
    batch_stamp = int(time.time() * 1000)
    for i, q in enumerate(questions):
        q["question_id"] = f"{category}-{batch_stamp}-{i+1:03d}"

    passed, failed_list = [], []
    for q in questions:
        gate_result = run_gates(q)
        if gate_result["pass"]:
            q["status"] = "reviewing"
            q["flags"] = gate_result["flags"]
            q_repo.add_question(category, q)
            passed.append(q)
        else:
            q["status"] = "draft"
            q["gate_errors"] = gate_result["failed"]
            failed_list.append(q)

    return {
        "team_code": team_code,
        "provider": os.getenv("AI_PROVIDER", "mock"),
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
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    if q.get("status") not in ("reviewing", "draft"):
        raise HTTPException(status_code=400, detail=f"승인 불가 상태: {q.get('status')}")
    q_repo.update_question(question_id, {"status": "approved"})
    return {"approved": True, "question_id": question_id}


def reject_question(question_id: str, reason: str) -> dict:
    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    q_repo.update_question(question_id, {
        "status": "rejected",
        "flags": {**q.get("flags", {}), "needs_edit": True},
        "reject_reason": reason,
    })
    return {"rejected": True, "question_id": question_id, "reason": reason}


def approve_new_user(employee_id: str, name: str, team: str, exam_date: str) -> dict:
    from repositories import user_repo
    from repositories.local_json import load_local_admins

    all_ids = {u["employee_id"] for u in user_repo.list_users()} | {a["employee_id"] for a in load_local_admins()}
    if employee_id in all_ids:
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
    user_repo.add_user(new_user)

    return {"approved": True, "employee_id": employee_id, "name": name, "team": team, "exam_date": exam_date}


def list_exam_sets() -> list:
    from repositories import exam_set_repo
    return exam_set_repo.list_exam_sets()


def create_exam_set(name: str, team_code: str, question_ids: list, created_by: str = "") -> dict:
    import uuid
    from repositories import exam_set_repo
    data = {
        "exam_set_id": f"set-{str(uuid.uuid4())[:8]}",
        "exam_id": f"exam-{str(uuid.uuid4())[:8]}",
        "name": name,
        "team_code": team_code,
        "question_ids": question_ids,
        "created_by": created_by,
        "status": "active",
    }
    return exam_set_repo.create_exam_set(data)


def list_question_papers() -> list:
    """시험지(문제 구성) 목록 — 같은 exam_set_id를 쓰는 여러 회차 중 대표 1건씩만 반환."""
    from repositories import exam_set_repo
    papers = {}
    for s in exam_set_repo.list_exam_sets():
        key = s.get("exam_set_id")
        if key and key not in papers:
            papers[key] = {
                "exam_set_id": key,
                "name": s.get("name"),
                "team_code": s.get("team_code"),
                "question_count": len(s.get("question_ids", [])),
                "created_at": s.get("created_at"),
            }
    return sorted(papers.values(), key=lambda p: p.get("created_at") or "", reverse=True)


def create_exam_round_from_paper(exam_set_id: str, name: str = None, created_by: str = "") -> dict:
    """기존 시험지(exam_set_id)의 문제 구성을 재사용해 새 시험 회차를 만든다.
    배정 대상·일시·커트라인은 새로 시작(빈 배정, 미정 일시, 기본 커트라인 70점)."""
    import uuid
    from repositories import exam_set_repo
    source = next((s for s in exam_set_repo.list_exam_sets() if s.get("exam_set_id") == exam_set_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="시험지를 찾을 수 없습니다.")
    data = {
        "exam_set_id": exam_set_id,
        "exam_id": f"exam-{str(uuid.uuid4())[:8]}",
        "name": name or source.get("name"),
        "team_code": source.get("team_code"),
        "question_ids": source.get("question_ids", []),
        "created_by": created_by,
        "status": "active",
    }
    return exam_set_repo.create_exam_set(data)


def assign_user_to_exam_set(employee_id: str, exam_id: str) -> dict:
    from repositories import exam_set_repo

    # 한 응시자는 동시에 하나의 시험(회차)에만 배정되어야 한다. 그렇지 않으면 이전에
    # 배정된 회차가 그대로 남아있어, 새 회차로 재배정해도 실제 출제 시 어느 회차를 써야
    # 할지 모호해지고 이전 문제가 그대로 나오는 버그로 이어진다.
    for s in exam_set_repo.list_exam_sets():
        other_id = s.get("exam_id")
        if other_id and other_id != exam_id and employee_id in s.get("assigned_users", []):
            exam_set_repo.unassign_user(other_id, employee_id)

    if not exam_set_repo.assign_user(exam_id, employee_id):
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"success": True, "employee_id": employee_id, "exam_id": exam_id}


def unassign_user_from_exam_set(employee_id: str, exam_id: str) -> dict:
    from repositories import exam_set_repo
    if not exam_set_repo.unassign_user(exam_id, employee_id):
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"success": True, "employee_id": employee_id, "exam_id": exam_id}


def set_exam_datetime(exam_id: str, exam_datetime: str) -> dict:
    from repositories import exam_set_repo
    success = exam_set_repo.update_exam_set(exam_id, {"exam_datetime": exam_datetime})
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"success": True, "exam_id": exam_id, "exam_datetime": exam_datetime}


def set_pass_score(exam_id: str, pass_score: int) -> dict:
    from repositories import exam_set_repo
    success = exam_set_repo.update_exam_set(exam_id, {"pass_score": pass_score})
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"success": True, "exam_id": exam_id, "pass_score": pass_score}


def delete_exam_set(exam_id: str) -> dict:
    from repositories import exam_set_repo
    if not exam_set_repo.delete_exam_set(exam_id):
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"deleted": True, "exam_id": exam_id}


def seed_mock_data() -> dict:
    from repositories import user_repo
    from repositories.local_json import load_local_admins

    existing_ids = {u["employee_id"] for u in user_repo.list_users()} | {a["employee_id"] for a in load_local_admins()}
    seed_users = [
        {"employee_id": "2024001", "password_hash": "mock_hash", "name": "김테스트", "team": "T1", "role": "examinee", "exam_date": "2026-07-10", "approved": True},
        {"employee_id": "2024002", "password_hash": "mock_hash", "name": "이테스트", "team": "T2", "role": "examinee", "exam_date": "2026-07-10", "approved": True},
        {"employee_id": "2024003", "password_hash": "mock_hash", "name": "박테스트", "team": "T3", "role": "examinee", "exam_date": "2026-07-11", "approved": True},
    ]
    added = 0
    for u in seed_users:
        if u["employee_id"] not in existing_ids:
            user_repo.add_user(u)
            existing_ids.add(u["employee_id"])
            added += 1
    return {"seeded_users": added, "message": f"더미 사용자 {added}명 추가 완료 (기존 계정 skip)"}


def list_teams() -> list:
    from repositories import team_repo
    return team_repo.list_teams()


def create_team(team_id: str, team_name: str, team_code: str) -> dict:
    from repositories import team_repo
    existing = team_repo.list_teams()
    if any(t["team_id"] == team_id or t["team_code"] == team_code for t in existing):
        raise HTTPException(status_code=409, detail="이미 존재하는 팀 ID 또는 코드입니다.")
    return team_repo.create_team({"team_id": team_id, "team_name": team_name, "team_code": team_code})


def update_team(team_id: str, team_name: str) -> dict:
    from repositories import team_repo
    updated = team_repo.update_team(team_id, {"team_name": team_name})
    if not updated:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    return updated


def delete_team(team_id: str) -> dict:
    from repositories import team_repo
    if not team_repo.delete_team(team_id):
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    return {"deleted": True, "team_id": team_id}


def fetch_system_status() -> dict:
    """관리자 화면(대시보드/설정)의 '운영 모드'·'Claude API' 표시용 실제 설정값.
    Claude/Gemini는 실제 API 호출 없이 키 설정 여부만 확인한다 (Google Drive 상태는
    /api/drive/status가 이미 실제 연결을 확인하므로 여기서 중복 확인하지 않음)."""
    return {
        "ai_provider": os.getenv("AI_PROVIDER", "mock"),
        "storage_backend": os.getenv("STORAGE_BACKEND", "local"),
        "claude_key_configured": bool(os.getenv("CLAUDE_API_KEY")),
        "gemini_key_configured": bool(os.getenv("GEMINI_API_KEY")),
    }


def fetch_dashboard_stats() -> dict:
    from repositories import question_repo, result_repo, exam_set_repo, user_repo
    total_users = len(user_repo.list_users())
    sets = exam_set_repo.list_exam_sets()
    active_sets = [s for s in sets if s.get("status") == "active"]
    assigned_count = sum(len(s.get("assigned_users", [])) for s in active_sets)
    return {
        "question_count": question_repo.count_by_status("approved"),
        "exam_set_count": len(active_sets),
        "assigned_count": assigned_count,
        "user_count": total_users,
    }


def bulk_upload_users(csv_text: str) -> dict:
    import csv
    import io

    if not csv_text or not csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV 파일이 비어 있습니다.")

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV 형식을 읽을 수 없습니다: {e}")

    required_cols = {"employee_id", "name"}
    if not required_cols.issubset(set(fieldnames)):
        raise HTTPException(status_code=400, detail=f"CSV에 필수 컬럼이 없습니다: {', '.join(sorted(required_cols))}")

    from repositories import user_repo
    from repositories.local_json import load_local_admins

    all_ids = {u["employee_id"] for u in user_repo.list_users()} | {a["employee_id"] for a in load_local_admins()}
    success, skipped, errors = 0, 0, 0
    for row in rows:
        try:
            eid = (row.get("employee_id") or "").strip()
            name = (row.get("name") or "").strip()
            team = (row.get("team_code") or "").strip()
            exam_date = (row.get("exam_date") or "").strip()
            if not eid or not name:
                errors += 1
                continue
            if eid in all_ids:
                skipped += 1
                continue
            user_repo.add_user({
                "employee_id": eid,
                "password_hash": "mock_hash",
                "name": name,
                "team": team,
                "role": "examinee",
                "exam_date": exam_date,
                "approved": True,
            })
            all_ids.add(eid)
            success += 1
        except Exception:
            errors += 1
    return {"success": success, "skipped": skipped, "errors": errors, "total": success + skipped + errors}


def get_exam_set_assignees(exam_id: str) -> list:
    from repositories import exam_set_repo
    exam_set = exam_set_repo.get_exam(exam_id)
    if not exam_set:
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    assigned_ids = exam_set.get("assigned_users", [])
    all_users = fetch_users().get("users", [])
    return [u for u in all_users if u.get("employee_id") in assigned_ids]


def get_exam_set_questions(exam_id: str) -> dict:
    from repositories import exam_set_repo, question_repo

    exam_set = exam_set_repo.get_exam(exam_id)
    if not exam_set:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")

    questions = []
    for qid in exam_set.get("question_ids", []):
        q = question_repo.get_question(qid)
        if not q:
            continue
        questions.append({
            "question_id": q["question_id"],
            "category": q["category"],
            "question": q["question"],
            "options": {
                "A": q["option_a"], "B": q["option_b"],
                "C": q["option_c"], "D": q["option_d"],
            },
            "answer": q.get("answer"),
            "difficulty": q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init", "중"),
        })

    return {
        "exam_set": {
            "exam_id": exam_set.get("exam_id"),
            "exam_set_id": exam_set.get("exam_set_id"),
            "name": exam_set.get("name"),
            "team_code": exam_set.get("team_code"),
            "created_at": exam_set.get("created_at"),
        },
        "questions": questions,
    }
