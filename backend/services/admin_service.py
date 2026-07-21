import logging
import os
import time
import uuid
import json
from datetime import datetime, timezone

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


def _record_audit(actor: dict | None, action_type: str, target_type: str, target_id: str,
                   before: dict | None = None, after: dict | None = None, reason: str = "") -> None:
    """감사 로그 기록은 최선 노력으로만 수행한다 — 실패해도 실제 작업(승인/반려 등)을 막지 않는다."""
    from repositories import audit_repo
    if audit_repo is None:
        return
    try:
        audit_repo.record(
            actor_id=(actor or {}).get("sub", ""),
            actor_role=(actor or {}).get("role", ""),
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            reason=reason,
        )
    except Exception:
        logging.exception("audit log write failed for %s %s", action_type, target_id)


def fetch_audit_logs() -> dict:
    """audit_logs 탭에서 실제 감사 기록을 조회한다. OJT_USE_AUDIT_LOG가 꺼져 있으면
    빈 목록과 enabled=False를 반환한다(가짜 데이터를 만들지 않는다)."""
    from repositories import audit_repo
    if audit_repo is None:
        return {"logs": [], "enabled": False}
    return {"logs": audit_repo.list_logs(), "enabled": True}


_VALID_GATE_MODES = {"legacy", "strict"}


def _get_gate_mode() -> str:
    """OJT_GATE_MODE 환경변수(legacy 기본값)로 강화된 7-Gate 사용 여부를 결정한다.
    잘못된 값은 legacy로 조용히 되돌리지 않고 요청 시 명시적으로 오류를 낸다."""
    raw = os.getenv("OJT_GATE_MODE", "legacy").strip().lower()
    if raw not in _VALID_GATE_MODES:
        raise HTTPException(status_code=500, detail=f"잘못된 OJT_GATE_MODE 설정입니다: {raw!r}")
    return raw


def _gate_response_fields(q: dict) -> dict:
    """strict 모드에서만 존재하는 gate_snapshot을 API 응답에 additive 필드로 얹는다.
    legacy 문제는 gate_snapshot이 없으므로 그대로 빈 dict를 반환해 기존 응답 스키마를 보존한다."""
    snapshot = (q.get("flags") or {}).get("gate_snapshot")
    if not snapshot:
        return {}
    return {
        "overall_gate_status": snapshot["overall_status"],
        "gates": snapshot["gates"],
    }


def _generate_ai_questions_strict(
    questions: list,
    q_repo,
    pool_key: str,
    category_label: str,
    team_code: str,
    material_text: str,
    flagged_question_ids: frozenset,
    persist_legacy: bool = True,
) -> tuple:
    """OJT_GATE_MODE=strict 전용 경로. PASS 여부와 관계없이 모든 Candidate를 정확히 한 번 저장하고,
    Gate 전체 판정을 기존 flags JSON 안의 gate_snapshot에 보존한다."""
    from ai_engine.router import get_semantic_gate_verifier
    from services.generation.gate_service import GateContext, evaluate_candidate

    verifier = get_semantic_gate_verifier()
    try:
        approved_questions = [
            existing for pool in q_repo.get_all_questions().values() for existing in pool
            if existing.get("status") == "approved"
        ]
    except Exception:
        approved_questions = []

    passed, failed_list = [], []
    for q in questions:
        context = GateContext(
            material_text=material_text,
            team_code=team_code,
            pool_key=pool_key,
            category_label=category_label,
            approved_questions=tuple(approved_questions),
            flagged_question_ids=flagged_question_ids,
        )
        gate_result = evaluate_candidate(q, context, verifier, mode="strict")

        q["flags"] = {
            "warning": gate_result["flags"]["warning"],
            "security_hold": gate_result["flags"]["security_hold"],
            "gate_snapshot": gate_result,
        }
        q["gate_errors"] = gate_result["failed"]
        q["status"] = "reviewing" if gate_result["pass"] else "draft"

        if persist_legacy:
            q_repo.add_question(pool_key, q)
        approved_questions.append(q)  # 같은 배치의 다음 Candidate와도 V06 중복 비교 대상이 된다.

        (passed if gate_result["pass"] else failed_list).append(q)

    return passed, failed_list


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


def fetch_generation_jobs() -> dict:
    """생성_jobs 목록을 실제 Sheets(generation_jobs 탭)에서 조회한다.
    OJT_USE_CANDIDATE_TAB이 꺼져 있어 저장소가 구성되지 않았으면 빈 목록과 enabled=False를 반환한다."""
    from repositories import generation_v2_repo
    if generation_v2_repo is None:
        return {"jobs": [], "enabled": False}
    return {"jobs": generation_v2_repo.list_jobs(), "enabled": True}


def fetch_generation_job_detail(job_id: str) -> dict:
    """생성 작업 하나의 상세 — 후보 문제 목록을 포함한다.
    Candidate 탭이 비활성화됐거나 Job을 찾을 수 없으면 enabled=False를 반환한다."""
    from repositories import generation_v2_repo
    if generation_v2_repo is None:
        return {"job": None, "candidates": [], "enabled": False}
    job = next((j for j in generation_v2_repo.list_jobs() if j.get("generation_job_id") == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="생성 작업을 찾을 수 없습니다.")
    candidates = generation_v2_repo.list_candidates_by_job(job_id)
    return {"job": job, "candidates": candidates, "enabled": True}


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
            "pass_score": meta.get("pass_score", 70),
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
            "category_accuracy": {},
            "exams": [],
            "insights": [],
        }

    count = len(all_results)
    avg_score = round(sum(r.get("score", 0) for r in all_results) / count, 1)
    pass_count = sum(1 for r in all_results if r.get("pass"))

    from services.generation.gates import VALID_CATEGORIES

    total_correct = total_answered = 0
    diff_totals = {"상": {"correct": 0, "total": 0}, "중": {"correct": 0, "total": 0}, "하": {"correct": 0, "total": 0}}
    cat_totals = {c: {"correct": 0, "total": 0} for c in VALID_CATEGORIES}
    for r in all_results:
        for q in r.get("results", []):
            total_answered += 1
            is_correct = bool(q.get("correct"))
            if is_correct:
                total_correct += 1
            d = q.get("difficulty")
            if d in diff_totals:
                diff_totals[d]["total"] += 1
                if is_correct:
                    diff_totals[d]["correct"] += 1
            c = q.get("category")
            if c in cat_totals:
                cat_totals[c]["total"] += 1
                if is_correct:
                    cat_totals[c]["correct"] += 1
    accuracy_pct = round(total_correct / total_answered * 100, 1) if total_answered else 0

    difficulty_accuracy = {
        d: {**v, "pct": round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0}
        for d, v in diff_totals.items()
    }
    category_accuracy = {
        c: {**v, "pct": round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0}
        for c, v in cat_totals.items()
    }

    team_results: dict = {}
    for r in all_results:
        team_results.setdefault(r.get("team_code", "-"), []).append(r)
    team_averages = sorted(
        [
            {
                "team_code": code,
                "team_name": team_names.get(code, code),
                "avg_score": round(sum(r.get("score", 0) for r in recs) / len(recs), 1),
                "count": len(recs),
                "pass_count": sum(1 for r in recs if r.get("pass")),
                "pass_pct": round(sum(1 for r in recs if r.get("pass")) / len(recs) * 100, 1),
            }
            for code, recs in team_results.items()
        ],
        key=lambda x: x["avg_score"],
    )

    insights = []
    if team_averages:
        weakest_team = team_averages[0]
        insights.append(f"{weakest_team['team_name']} 평균 점수가 {weakest_team['avg_score']}점으로 가장 낮습니다.")
        weakest_pass_team = min(team_averages, key=lambda t: t["pass_pct"])
        insights.append(f"{weakest_pass_team['team_name']} 합격률이 {weakest_pass_team['pass_pct']}%로 가장 낮습니다.")
    scored_diffs = {d: v for d, v in difficulty_accuracy.items() if v["total"] > 0}
    if scored_diffs:
        weakest_diff = min(scored_diffs.items(), key=lambda kv: kv[1]["pct"])
        insights.append(f"난이도 '{weakest_diff[0]}' 문항의 정답률이 {weakest_diff[1]['pct']}%로 가장 낮습니다.")
    scored_cats = {c: v for c, v in category_accuracy.items() if v["total"] > 0}
    if scored_cats:
        weakest_cat = min(scored_cats.items(), key=lambda kv: kv[1]["pct"])
        insights.append(f"'{weakest_cat[0]}' 영역 문항의 정답률이 {weakest_cat[1]['pct']}%로 가장 낮습니다.")
    ranked_exams = [e for e in exams if e["taker_count"] >= 2]
    if ranked_exams:
        weakest_exam = min(ranked_exams, key=lambda e: e["avg_score"])
        insights.append(f"'{weakest_exam['name']}' 시험 평균 점수가 {weakest_exam['avg_score']}점으로 가장 낮습니다.")
    insights.append(
        f"전체 정답률은 {accuracy_pct}%, 합격률은 {round(pass_count / count * 100, 1)}%입니다."
    )

    return {
        "summary": {"count": count, "avg_score": avg_score, "accuracy_pct": accuracy_pct, "pass_count": pass_count},
        "team_averages": team_averages,
        "difficulty_accuracy": difficulty_accuracy,
        "category_accuracy": category_accuracy,
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

    data = q_repo.get_all_questions()
    if team:
        team_key = TEAM_KEY_MAP.get(team, team)
        questions = data.get(team_key, [])
    else:
        questions = [q for pool in data.values() for q in pool]

    if status:
        questions = [q for q in questions if q.get("status") == status]

    if category:
        questions = [q for q in questions if q.get("category") == category]

    return {"questions": questions}


def override_difficulty(question_id: str, new_difficulty: str, reason_code: str = "") -> dict:
    q_repo, _, fb_repo = _get_repos()

    q = q_repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")

    ai_difficulty = q.get("difficulty_ai") or q.get("difficulty_init", "중")
    # 직전 판정 이력 2건을 실제로 불러와 이번 건과 합쳐 3연속 스트릭을 이어간다.
    # (예전에는 매번 빈 리스트를 새로 넘겨 auto_confirmed가 절대 True가 될 수 없었음)
    recent_feedback = fb_repo.list_recent_feedback(limit=2)  # newest-first
    log = [r["ai_difficulty"] != r["admin_difficulty"] for r in reversed(recent_feedback)]
    result = update_difficulty_from_feedback(question_id, ai_difficulty, new_difficulty, log)

    q_repo.update_question(question_id, {"admin_override": new_difficulty})

    fb_repo.append_feedback({
        "question_id": question_id,
        "question_text": q.get("question", ""),
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


def generate_ai_questions(
    team_code: str,
    material_text: str,
    count: int,
    difficulty_hint: str,
    requested_by: str = "",
    idempotency_key: str = "",
    material_ids: list | None = None,
) -> dict:
    from ai_engine.router import generate_questions_from_material
    from services.generation.gates import run_gates
    from services.generation.dual_write import (
        assign_candidate_ids,
        build_candidate_row,
        build_gate_rows,
        get_generation_write_policy,
        link_candidate_to_legacy,
    )
    from services.material_service import get_material_text_for_team

    from repositories import question_stats_repo

    category = TEAM_KEY_MAP.get(team_code, team_code)  # pool_key — 문제 저장 위치(add_question)에 사용
    category_label = _category_label_for_pool(category)  # 공통/팀별/환경안전/일반상식 — 문제의 category 필드·게이트 검증·프론트 필터에 사용
    q_repo, _, fb_repo = _get_repos()
    policy = get_generation_write_policy()
    provider = os.getenv("AI_PROVIDER", "mock")
    now = datetime.now(timezone.utc).isoformat()
    generation_job_id = ""
    generation_v2_repo = None

    if policy.candidates:
        from repositories import generation_v2_repo
        if generation_v2_repo is None:
            raise HTTPException(
                status_code=503,
                detail="정규화 문제 저장소가 구성되지 않았습니다.",
            )
        if idempotency_key:
            generation_job_id = "gen-" + uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"ojt:generation:{idempotency_key}",
            ).hex
        else:
            generation_job_id = "gen-" + uuid.uuid4().hex
        job = {
            "generation_job_id": generation_job_id,
            "requested_by": requested_by,
            "evaluation_type": "OJT",
            "team_code": team_code,
            "category_counts_json": {},
            "difficulty_counts_json": {difficulty_hint: count},
            "knowledge_unit_ids_json": [],
            "requested_count": count,
            "candidate_multiplier": 1,
            "provider": provider,
            "model_name": os.getenv("AI_MODEL", ""),
            "prompt_version": os.getenv("OJT_PROMPT_VERSION", ""),
            "status": "RUNNING",
            "started_at": now,
            "row_version": 1,
            "work_name": f"{team_code} AI 문제 생성",
            "progress_percent": 0,
            "completed_count": 0,
            "review_required_count": 0,
            "failed_count": 0,
        }
        try:
            generation_v2_repo.create_job(job)
        except Exception as exc:
            logging.exception("generation job 생성 실패: %s", exc)
            raise HTTPException(status_code=503, detail="문제 생성 작업 저장에 실패했습니다.")

    # Drive에서 스캔해둔 교육자료(공통+팀별)를 기본 자료로 사용하고,
    # 관리자가 직접 붙여넣은 텍스트는 이번 출제에 한해 보충하는 내용으로 뒤에 덧붙인다.
    # (수동 입력으로 자동 스캔 자료가 사라지지 않도록 둘 다 살리는 방식)
    selected_ids = set(material_ids) if material_ids is not None else None
    try:
        drive_material = get_material_text_for_team(team_code, selected_ids)
    except Exception:
        drive_material = ""
    material_text = "\n\n".join(t for t in (drive_material, material_text) if t)
    rejected = q_repo.list_by_status("rejected")
    rejected_examples = [q for q in rejected if q.get("reject_reason")]

    overused_questions = []
    flagged_ids = set()
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

    # 관리자가 AI 난이도 판정을 재조정한 최근 이력을 프롬프트에 보정 예시로 전달해
    # 다음 생성부터 난이도 판정 정확도가 점차 개선되도록 한다.
    difficulty_corrections = []
    try:
        recent_feedback = fb_repo.list_recent_feedback(limit=10)
        difficulty_corrections = [
            {
                "question_text": r["question_text"],
                "ai_difficulty": r["ai_difficulty"],
                "admin_difficulty": r["admin_difficulty"],
            }
            for r in recent_feedback
            if r.get("question_text") and r.get("ai_difficulty") != r.get("admin_difficulty")
        ]
    except Exception:
        pass  # 피드백 조회 실패는 문제 생성 자체를 막지 않음

    try:
        questions = generate_questions_from_material(
            material_text, category_label, count, difficulty_hint,
            rejected_examples, overused_questions, difficulty_corrections,
        )
    except Exception as e:
        if generation_v2_repo is not None:
            try:
                generation_v2_repo.update_job(generation_job_id, {
                    "status": "FAILED",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": str(e),
                    "failed_count": count,
                })
            except Exception:
                logging.exception("generation job 실패 상태 저장 실패")
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

    if policy.candidates:
        questions = assign_candidate_ids(questions, generation_job_id)

    gate_mode = _get_gate_mode()
    if gate_mode == "strict":
        passed, failed_list = _generate_ai_questions_strict(
            questions, q_repo, category, category_label, team_code,
            material_text, frozenset(flagged_ids),
            persist_legacy=not policy.candidates,
        )
    else:
        passed, failed_list = [], []
        for q in questions:
            gate_result = run_gates(q)
            if gate_result["pass"]:
                q["status"] = "reviewing"
                q["flags"] = gate_result["flags"]
                if not policy.candidates:
                    q_repo.add_question(category, q)
                passed.append(q)
            else:
                q["status"] = "draft"
                q["gate_errors"] = gate_result["failed"]
                failed_list.append(q)

    if generation_v2_repo is not None:
        completed_at = datetime.now(timezone.utc).isoformat()
        candidates = passed + failed_list
        candidate_rows = [
            build_candidate_row(
                question,
                generation_job_id=generation_job_id,
                team_code=team_code,
                provider=provider,
                generated_at=completed_at,
                model_name=os.getenv("AI_MODEL", ""),
                prompt_version=os.getenv("OJT_PROMPT_VERSION", ""),
            )
            for question in candidates
        ]
        gate_rows = [
            row
            for question in candidates
            for row in build_gate_rows(question, completed_at)
        ] if policy.gates else []
        try:
            generation_v2_repo.save_candidates(candidate_rows)
            if gate_rows:
                generation_v2_repo.save_gate_results(gate_rows)
        except Exception as exc:
            try:
                generation_v2_repo.update_job(generation_job_id, {
                    "status": "FAILED",
                    "completed_at": completed_at,
                    "error_message": str(exc),
                    "failed_count": len(candidates),
                })
            except Exception:
                logging.exception("generation job 실패 상태 저장 실패")
            raise HTTPException(status_code=503, detail="정규화 문제 데이터 저장에 실패했습니다.")

        try:
            legacy_questions = candidates if gate_mode == "strict" else passed
            for question in legacy_questions:
                linked = link_candidate_to_legacy(
                    question,
                    question.get("candidate_id", ""),
                )
                q_repo.add_question(category, linked)
        except Exception as exc:
            try:
                generation_v2_repo.update_job(generation_job_id, {
                    "status": "PARTIAL_FAILED",
                    "completed_at": completed_at,
                    "error_message": str(exc),
                })
            except Exception:
                logging.exception("generation job 부분 실패 상태 저장 실패")
            raise HTTPException(status_code=503, detail="Legacy 문제은행 저장에 실패했습니다.")

        try:
            generation_v2_repo.update_job(generation_job_id, {
                "status": "COMPLETED",
                "completed_at": completed_at,
                "progress_percent": 100,
                "completed_count": len(passed),
                "review_required_count": sum(
                    1 for question in candidates
                    if question.get("status") == "reviewing"
                ),
                "failed_count": len(failed_list),
            })
        except Exception:
            logging.exception("generation job 완료 상태 저장 실패")
            raise HTTPException(status_code=503, detail="문제 생성 완료 상태 저장에 실패했습니다.")

    return {
        "team_code": team_code,
        "provider": provider,
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
                **_gate_response_fields(q),
            }
            for q in passed + failed_list
        ],
        **({"generation_job_id": generation_job_id} if generation_job_id else {}),
    }


_GATE_REQUIRED_PASS_KEYS = ("V01", "V02", "V03", "V07")
_GATE_WARNING_ELIGIBLE_KEYS = ("V04", "V05", "V06")
_MIN_OVERRIDE_REASON_LENGTH = 10


def _gate_error(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


def _write_normalized_question_review(
    question: dict,
    updated_fields: dict,
    action: str,
    actor: dict | None,
    reason: str,
) -> bool:
    from repositories import generation_v2_repo
    from services.generation.dual_write import (
        build_review_records,
        get_generation_write_policy,
    )

    if not get_generation_write_policy().candidates:
        return False
    if generation_v2_repo is None:
        raise HTTPException(
            status_code=503,
            detail="정규화 문제 저장소를 사용할 수 없습니다.",
        )

    before = dict(question)
    after = {**question, **updated_fields}
    reviewed_at = datetime.now(timezone.utc).isoformat()
    actor_id = (actor or {}).get("sub", "")
    review, history = build_review_records(
        before,
        after,
        action=action,
        actor_id=actor_id,
        reason=reason,
        reviewed_at=reviewed_at,
    )
    candidate_id = review["candidate_id"]
    if not candidate_id:
        existing = generation_v2_repo.find_candidate_by_question_id(
            question.get("question_id", "")
        )
        candidate_id = (existing or {}).get("candidate_id", "")
        review["candidate_id"] = candidate_id

    candidate_fields = {
        "status": updated_fields["status"],
        "review_status": updated_fields["status"],
        "reviewed_by": actor_id,
        "reviewed_at": reviewed_at,
        "last_saved_at": reviewed_at,
    }
    if action == "APPROVE":
        candidate_fields["approved_question_id"] = question.get("question_id", "")
    else:
        candidate_fields["rejection_reason"] = reason

    try:
        generation_v2_repo.record_review(review, history)
        if candidate_id:
            generation_v2_repo.update_candidate(candidate_id, candidate_fields)
    except Exception as exc:
        logging.exception("normalized question review write failed")
        raise HTTPException(
            status_code=503,
            detail="정규화 승인·반려 기록 저장에 실패했습니다.",
        ) from exc
    return True


def approve_question(question_id: str, actor: dict = None, override_reason: str = "") -> dict:
    """strict 모드에서는 Gate Snapshot·fingerprint·필수 Gate PASS·관리자 난이도 확정을 모두 확인한 뒤에만
    승인한다. legacy 모드는 기존 상태 검증을 유지하되, security_hold(V07 미통과)는 모드와 무관하게 차단한다."""
    from services.generation.gates import VALID_DIFFICULTIES, question_fingerprint
    from services.generation.gate_service import GATE_VERSION

    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")

    if (q.get("flags") or {}).get("security_hold"):
        raise _gate_error("GATE_SECURITY_HOLD", "보안 검토가 필요한 문제는 승인할 수 없습니다.")

    gate_mode = _get_gate_mode()
    snapshot = (q.get("flags") or {}).get("gate_snapshot")

    if gate_mode == "strict":
        if q.get("status") != "reviewing":
            raise _gate_error("GATE_STATUS_INVALID", f"승인 불가 상태: {q.get('status')}")
        if not snapshot:
            raise _gate_error("GATE_SNAPSHOT_MISSING", "Gate 검증 결과가 없습니다.")
        if snapshot.get("gate_version") != GATE_VERSION:
            raise _gate_error("GATE_VERSION_UNSUPPORTED",
                               f"지원하지 않는 Gate 버전입니다: {snapshot.get('gate_version')!r}")

        current_fingerprint = question_fingerprint(q)
        if current_fingerprint != snapshot.get("question_fingerprint"):
            raise _gate_error("GATE_RESULT_STALE", "Gate 검증 이후 문제 내용이 변경되었습니다.")

        overall = snapshot.get("overall_status")
        if overall == "HARD_FAIL":
            raise _gate_error("GATE_HARD_FAIL", "Hard Fail 상태의 문제는 승인할 수 없습니다.")
        if overall == "REVIEW_REQUIRED":
            raise _gate_error("GATE_REVIEW_REQUIRED", "검토가 필요한 문제는 승인할 수 없습니다.")

        gates = snapshot.get("gates", {})
        for key in _GATE_REQUIRED_PASS_KEYS:
            if gates.get(key, {}).get("status") != "PASS":
                raise _gate_error("GATE_REQUIRED_PASS_MISSING", f"{key} Gate가 PASS 상태가 아닙니다.")

        if (q.get("admin_override") or "").strip() not in VALID_DIFFICULTIES:
            raise _gate_error("GATE_ADMIN_DIFFICULTY_REQUIRED", "관리자 난이도 확정이 필요합니다.")

        has_warning = any(gates.get(key, {}).get("status") == "WARNING" for key in _GATE_WARNING_ELIGIBLE_KEYS)
        if has_warning and len(override_reason.strip()) < _MIN_OVERRIDE_REASON_LENGTH:
            raise _gate_error("GATE_WARNING_OVERRIDE_REQUIRED",
                               f"WARNING Gate 승인에는 {_MIN_OVERRIDE_REASON_LENGTH}자 이상의 사유가 필요합니다.")
    else:
        if q.get("status") not in ("reviewing", "draft", "rejected"):
            raise HTTPException(status_code=400, detail=f"승인 불가 상태: {q.get('status')}")

    updated_fields = {"status": "approved"}
    if snapshot:
        updated_flags = dict(q.get("flags") or {})
        updated_flags["gate_approval"] = {
            "approved_by": (actor or {}).get("sub", ""),
            "override_reason": override_reason.strip(),
            "gate_version": snapshot.get("gate_version", ""),
            "question_fingerprint": snapshot.get("question_fingerprint", ""),
        }
        updated_fields["flags"] = updated_flags

    used_normalized_repo = _write_normalized_question_review(
        q,
        updated_fields,
        action="APPROVE",
        actor=actor,
        reason=override_reason.strip(),
    )
    try:
        q_repo.update_question(question_id, updated_fields)
    except Exception as exc:
        if not used_normalized_repo:
            raise
        logging.exception("legacy question approval update failed after normalized write")
        raise HTTPException(
            status_code=503,
            detail="기존 문제 승인 저장에 실패했습니다.",
        ) from exc
    _record_audit(actor, "APPROVE_QUESTION", "question", question_id,
                  before={"status": q.get("status")}, after=updated_fields, reason=override_reason.strip())
    from services.activity_log import record_activity
    record_activity("question_review", actor_name=(actor or {}).get("name", ""),
                     target=question_id, detail="승인 완료", team_code=q.get("team_code", ""))
    return {"approved": True, "question_id": question_id}


def reject_question(question_id: str, reason: str, actor: dict = None) -> dict:
    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    updated_fields = {
        "status": "rejected",
        "flags": {**q.get("flags", {}), "needs_edit": True},
        "reject_reason": reason,
    }
    used_normalized_repo = _write_normalized_question_review(
        q,
        updated_fields,
        action="REJECT",
        actor=actor,
        reason=reason,
    )
    try:
        q_repo.update_question(question_id, updated_fields)
    except Exception as exc:
        if not used_normalized_repo:
            raise
        logging.exception("legacy question rejection update failed after normalized write")
        raise HTTPException(
            status_code=503,
            detail="기존 문제 반려 저장에 실패했습니다.",
        ) from exc
    _record_audit(actor, "REJECT_QUESTION", "question", question_id,
                  before={"status": q.get("status")}, after=updated_fields, reason=reason)
    from services.activity_log import record_activity
    record_activity("question_reject", actor_name=(actor or {}).get("name", ""),
                     target=question_id, detail=reason, team_code=q.get("team_code", ""))
    return {"rejected": True, "question_id": question_id, "reason": reason}


_EDITABLE_QUESTION_FIELDS = (
    "question", "option_a", "option_b", "option_c", "option_d",
    "answer", "explanation",
)


def edit_question(question_id: str, fields: dict, actor: dict = None) -> dict:
    """검수 대기·승인된 문제의 본문·보기·정답·해설을 수정한다.
    확정 시험은 Snapshot을 그대로 쓰므로 이 수정은 문제은행 원본에만 반영되고
    이미 생성된 시험지의 Snapshot에는 영향을 주지 않는다."""
    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    if q.get("status") == "archived":
        raise HTTPException(status_code=400, detail="보관된 문제는 수정할 수 없습니다.")
    updated_fields = {key: value for key, value in fields.items() if key in _EDITABLE_QUESTION_FIELDS}
    if not updated_fields:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")
    before = {key: q.get(key) for key in updated_fields}
    q_repo.update_question(question_id, updated_fields)
    _record_audit(actor, "EDIT_QUESTION", "question", question_id, before=before, after=updated_fields)
    return {"updated": True, "question_id": question_id, "fields": updated_fields}


def bulk_approve_questions(question_ids: list[str], actor: dict = None) -> dict:
    results = []
    for question_id in question_ids:
        try:
            approve_question(question_id, actor=actor)
            results.append({"question_id": question_id, "ok": True})
        except HTTPException as exc:
            results.append({"question_id": question_id, "ok": False, "error": exc.detail})
    return {"results": results, "succeeded": sum(1 for r in results if r["ok"]), "failed": sum(1 for r in results if not r["ok"])}


def bulk_reject_questions(question_ids: list[str], reason: str, actor: dict = None) -> dict:
    results = []
    for question_id in question_ids:
        try:
            reject_question(question_id, reason, actor=actor)
            results.append({"question_id": question_id, "ok": True})
        except HTTPException as exc:
            results.append({"question_id": question_id, "ok": False, "error": exc.detail})
    return {"results": results, "succeeded": sum(1 for r in results if r["ok"]), "failed": sum(1 for r in results if not r["ok"])}


_DIRECT_SET_STATUSES = ("reviewing", "archived")


def set_question_status(question_id: str, status: str, reason: str = "", actor: dict = None) -> dict:
    """문제은행·검수 화면에서 상태를 직접 변경한다.
    승인·반려는 Gate 검증·정규화 이중 기록을 그대로 타도록 approve_question/reject_question에 위임하고,
    검수 대기·보관으로 되돌리는 것만 직접 반영한다(감사 필요성이 낮은 안전한 되돌리기이므로)."""
    if status == "approved":
        return approve_question(question_id, actor=actor)
    if status == "rejected":
        return reject_question(question_id, reason or "관리자 상태 변경", actor=actor)
    if status not in _DIRECT_SET_STATUSES:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 상태입니다: {status!r}")
    q_repo, _, _ = _get_repos()
    q = q_repo.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다.")
    before_status = q.get("status")
    q_repo.update_question(question_id, {"status": status})
    _record_audit(actor, "SET_QUESTION_STATUS", "question", question_id,
                  before={"status": before_status}, after={"status": status}, reason=reason)
    return {"updated": True, "question_id": question_id, "status": status}


def approve_new_user(employee_id: str, name: str, team: str, approved_by_name: str = "") -> dict:
    from repositories import user_repo
    from repositories.local_json import load_local_admins
    from datetime import datetime

    all_ids = {u["employee_id"] for u in user_repo.list_users()} | {a["employee_id"] for a in load_local_admins()}
    if employee_id in all_ids:
        raise HTTPException(status_code=409, detail="이미 등록된 사원번호입니다.")

    approved_date = datetime.now().isoformat()
    new_user = {
        "employee_id": employee_id,
        "password_hash": "mock_hash",
        "name": name,
        "team": team,
        "role": "examinee",
        "approved": True,
        "approved_date": approved_date,
    }
    user_repo.add_user(new_user)

    from services.activity_log import record_activity
    record_activity("user_register", actor_name=approved_by_name or "관리자",
                     target=name, detail="", team_code=team)

    return {"approved": True, "employee_id": employee_id, "name": name, "team": team, "approved_date": approved_date}


def list_exam_sets() -> list:
    from repositories import exam_set_repo
    return exam_set_repo.list_exam_sets()


def _load_approved_exam_questions(question_repo, question_ids: list[str]) -> list[dict]:
    approved = []
    rejected = []
    for question_id in dict.fromkeys(question_ids):
        question = question_repo.get_question(question_id)
        if not question or question.get("status") != "approved":
            rejected.append(question_id)
        else:
            approved.append(question)
    if rejected:
        raise HTTPException(status_code=409, detail={
            "code": "EXAM_QUESTION_NOT_APPROVED",
            "message": "승인된 문제만 시험에 사용할 수 있습니다.",
            "question_ids": rejected,
        })
    if not approved:
        raise HTTPException(
            status_code=400,
            detail="시험에는 승인 문제 한 개 이상이 필요합니다.",
        )
    return approved


def _validate_exam_question_ids(question_repo, question_ids: list[str]) -> list[str]:
    return [
        question["question_id"]
        for question in _load_approved_exam_questions(question_repo, question_ids)
    ]


def _exam_input_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": code, "message": message},
    )


def _validate_evaluation_type(evaluation_type: str) -> str:
    if evaluation_type not in {"official", "practice"}:
        raise _exam_input_error(
            "EXAM_EVALUATION_TYPE_INVALID",
            "evaluation_type must be official or practice",
        )
    return evaluation_type


def _validate_exam_category(exam_category: str) -> str:
    if exam_category not in {"exam_study", "exam_test"}:
        raise _exam_input_error(
            "EXAM_CATEGORY_INVALID",
            "exam_category must be exam_study or exam_test",
        )
    return exam_category


def _resolve_exam_scores(question_ids, question_scores):
    from services.exams.dual_write import resolve_question_scores

    try:
        return resolve_question_scores(question_ids, question_scores)
    except ValueError as exc:
        raise _exam_input_error("EXAM_SCORE_INVALID", str(exc)) from exc


def _frozen_exam_metadata(
    version: dict,
    scores: dict[str, int],
    evaluation_type: str,
    idempotency_key: str,
) -> dict:
    return {
        "evaluation_type": evaluation_type,
        "blueprint_json": {"question_scores": scores},
        "frozen_at": version.get("confirmed_at", ""),
        "frozen_by": version.get("confirmed_by", ""),
        "paper_version": version.get("version_no", 1),
        "snapshot_checksum": version.get("question_hash", ""),
        "row_version": 1,
        "confirmed_by": version.get("confirmed_by", ""),
        "confirmed_at": version.get("confirmed_at", ""),
        "current_exam_version_id": version.get("exam_version_id", ""),
        "idempotency_key": idempotency_key,
    }


def _existing_exam_retry(exam_set_repo, exam_id: str, idempotency_key: str):
    return next((
        row
        for row in exam_set_repo.list_exam_sets()
        if row.get("exam_id") == exam_id
        or (
            idempotency_key
            and row.get("idempotency_key") == idempotency_key
        )
    ), None)


def _assert_same_idempotent_exam(existing: dict, data: dict) -> None:
    immutable_fields = (
        "exam_set_id",
        "name",
        "team_code",
        "question_ids",
        "evaluation_type",
        "exam_category",
    )
    if any(existing.get(field) != data.get(field) for field in immutable_fields):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "EXAM_IDEMPOTENCY_CONFLICT",
                "message": "idempotency_key was already used with different exam data",
            },
        )


def _persist_legacy_exam(
    exam_set_repo,
    data: dict,
    normalized_used: bool,
    metadata: dict | None,
) -> dict:
    existing = _existing_exam_retry(
        exam_set_repo,
        data["exam_id"],
        data.get("idempotency_key", ""),
    )
    if existing:
        _assert_same_idempotent_exam(existing, data)
    try:
        stored = existing or exam_set_repo.create_exam_set(data)
        if metadata is not None:
            if not exam_set_repo.update_exam_set(data["exam_id"], metadata):
                raise RuntimeError("legacy exam metadata target was not found")
            stored.update(metadata)
        return stored
    except HTTPException:
        raise
    except Exception as exc:
        if not normalized_used:
            raise
        logging.exception("legacy exam write failed after normalized persistence")
        raise HTTPException(
            status_code=503,
            detail="기존 시험 저장에 실패했습니다.",
        ) from exc


def create_exam_set(
    name: str,
    team_code: str,
    question_ids: list,
    created_by: str = "",
    question_scores: dict[str, int] | None = None,
    evaluation_type: str = "official",
    exam_category: str = "exam_study",
    idempotency_key: str = "",
    created_by_name: str = "",
) -> dict:
    from repositories import exam_set_repo, question_repo, exam_v2_repo
    from repositories.exam_v2 import ImmutableExamConflict
    from services.exams.dual_write import (
        build_exam_ids,
        build_frozen_exam_records,
        get_exam_write_policy,
    )

    evaluation_type = _validate_evaluation_type(evaluation_type)
    exam_category = _validate_exam_category(exam_category)
    approved_questions = _load_approved_exam_questions(
        question_repo, question_ids
    )
    valid_ids = [question["question_id"] for question in approved_questions]
    scores = _resolve_exam_scores(question_ids, question_scores)
    exam_set_id, exam_id = build_exam_ids(idempotency_key)
    policy = get_exam_write_policy()
    confirmed_at = datetime.now(timezone.utc).isoformat()
    version = None
    metadata = None

    # 같은 멱등키 재시도는 같은 exam_id를 재사용한다. 그 외 시험 중 이름 또는
    # 문제 구성이 같으면 어떤 V2/Legacy 행도 쓰기 전에 차단한다.
    existing = exam_set_repo.list_exam_sets()
    other_exams = [
        row for row in existing if str(row.get("exam_id", "")) != exam_id
    ]
    name_key = name.strip()
    question_set = set(valid_ids)
    if any(row.get("name", "").strip() == name_key for row in other_exams):
        raise HTTPException(status_code=409, detail="이미 동일한 이름의 시험지가 있습니다.")
    if any(set(row.get("question_ids", [])) == question_set for row in other_exams):
        raise HTTPException(status_code=409, detail="이미 동일한 문제 구성의 시험지가 있습니다.")

    if policy.frozen_exams:
        if exam_v2_repo is None:
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 저장소를 사용할 수 없습니다.",
            )
        version, items = build_frozen_exam_records(
            exam_set_id=exam_set_id,
            questions=approved_questions,
            scores=scores,
            confirmed_by=created_by,
            confirmed_at=confirmed_at,
            version_no=1,
        )
        try:
            exam_v2_repo.save_frozen_exam(version, items)
        except ImmutableExamConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "EXAM_IMMUTABLE_CONFLICT",
                    "message": str(exc),
                },
            ) from exc
        except Exception as exc:
            logging.exception("normalized frozen exam write failed")
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 저장에 실패했습니다.",
            ) from exc
        metadata = _frozen_exam_metadata(
            version, scores, evaluation_type, idempotency_key
        )

    # exam_category는 Phase4 dual-write 플래그와 무관하게 항상 확장 컬럼에 기록한다.
    metadata = {"exam_category": exam_category, **(metadata or {})}

    data = {
        "exam_set_id": exam_set_id,
        "exam_id": exam_id,
        "name": name,
        "team_code": team_code,
        "question_ids": valid_ids,
        "question_scores": scores,
        "evaluation_type": evaluation_type,
        "exam_category": exam_category,
        "total_score": 100,
        "exam_version_id": (
            version["exam_version_id"] if version is not None else ""
        ),
        "idempotency_key": idempotency_key,
        "created_by": created_by,
        "status": "active",
    }
    stored = _persist_legacy_exam(
        exam_set_repo,
        data,
        normalized_used=policy.frozen_exams,
        metadata=metadata,
    )
    from services.activity_log import record_activity
    record_activity("exam_create", actor_name=created_by_name or "관리자",
                     target=stored.get("name", name), detail="미정" if not stored.get("exam_datetime") else "",
                     team_code=stored.get("team_code", ""))
    return {
        **stored,
        "exam_category": exam_category,
        "evaluation_type": evaluation_type,
        "total_score": 100,
        "exam_version_id": (
            version["exam_version_id"] if version is not None else ""
        ),
    }


def list_question_papers() -> list:
    """시험지(문제 구성) 목록 — 같은 exam_set_id를 쓰는 여러 회차 중 대표 1건씩만 반환."""
    from repositories import exam_set_repo

    def rank(row):
        try:
            paper_version = int(row.get("paper_version") or 0)
        except (TypeError, ValueError):
            paper_version = 0
        return paper_version, str(row.get("created_at") or "")

    grouped = {}
    for row in exam_set_repo.list_exam_sets():
        exam_set_id = row.get("exam_set_id")
        if exam_set_id:
            grouped.setdefault(exam_set_id, []).append(row)

    papers = {}
    for exam_set_id, rows in grouped.items():
        representative = max(rows, key=rank)
        paper_version = rank(representative)[0]
        papers[exam_set_id] = {
            "exam_id": str(representative.get("exam_id") or ""),
            "exam_set_id": str(exam_set_id),
            "name": str(representative.get("name") or ""),
            "team_code": str(representative.get("team_code") or ""),
            "paper_version": paper_version,
            "question_count": len(representative.get("question_ids") or []),
            "used_by_exam_count": len(rows),
            "created_at": str(representative.get("created_at") or ""),
            "exam_category": str(representative.get("exam_category") or "exam_study"),
        }
    return sorted(papers.values(), key=lambda p: p.get("created_at") or "", reverse=True)


def _scores_from_exam_version(version: dict) -> dict[str, int]:
    blueprint = version.get("blueprint_json") or "[]"
    if isinstance(blueprint, str):
        try:
            blueprint = json.loads(blueprint)
        except json.JSONDecodeError:
            blueprint = []
    if not isinstance(blueprint, list):
        return {}
    scores = {}
    for item in blueprint:
        try:
            score = int(item.get("score", 0))
        except (AttributeError, TypeError, ValueError):
            continue
        question_id = str(item.get("question_id", ""))
        if question_id and score > 0:
            scores[question_id] = score
    return scores


def create_exam_round_from_paper(
    exam_set_id: str,
    name: str = None,
    created_by: str = "",
    evaluation_type: str | None = None,
    idempotency_key: str = "",
    exam_datetime: str = None,
    pass_score: int = None,
    duration_min: int = None,
    created_by_name: str = "",
) -> dict:
    """기존 시험지(exam_set_id)의 문제 구성을 재사용해 새 시험 회차를 만든다.
    배정 대상은 새로 시작(빈 배정). 일시·커트라인·시험 시간은 주어지면 생성 시점에 바로 반영하고,
    없으면 기존처럼 미정 일시·기본 커트라인 70점·기본 시험 시간 60분으로 시작한다."""
    from repositories import exam_set_repo, question_repo, exam_v2_repo
    from repositories.exam_v2 import ImmutableExamConflict
    from services.exams.dual_write import (
        build_exam_ids,
        build_frozen_exam_records,
        get_exam_write_policy,
    )
    source = next((s for s in exam_set_repo.list_exam_sets() if s.get("exam_set_id") == exam_set_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="시험지를 찾을 수 없습니다.")
    evaluation_type = _validate_evaluation_type(
        evaluation_type or source.get("evaluation_type") or "official"
    )
    # 시험 유형(기초고사/업무능력평가)은 시험지 생성 단계에서만 선택하며, 회차 생성은
    # 원본 시험지의 값을 그대로 물려받고 여기서 다시 선택하지 않는다.
    exam_category = source.get("exam_category") or "exam_study"
    policy = get_exam_write_policy()
    version = None
    scores = {}
    metadata = None

    if policy.frozen_exams:
        if exam_v2_repo is None:
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 저장소를 사용할 수 없습니다.",
            )
        try:
            version = exam_v2_repo.find_current_version(exam_set_id)
        except Exception as exc:
            logging.exception("normalized exam version lookup failed")
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 버전 조회에 실패했습니다.",
            ) from exc
        if version is not None:
            scores = _scores_from_exam_version(version)

    if version is None:
        current_questions = _load_approved_exam_questions(
            question_repo,
            source.get("question_ids", []),
        )
        valid_ids = [question["question_id"] for question in current_questions]
        scores = _resolve_exam_scores(
            valid_ids,
            source.get("question_scores"),
        )
        if policy.frozen_exams:
            confirmed_at = datetime.now(timezone.utc).isoformat()
            version, items = build_frozen_exam_records(
                exam_set_id=exam_set_id,
                questions=current_questions,
                scores=scores,
                confirmed_by=created_by,
                confirmed_at=confirmed_at,
                version_no=1,
            )
            try:
                exam_v2_repo.save_frozen_exam(version, items)
            except ImmutableExamConflict as exc:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "EXAM_IMMUTABLE_CONFLICT",
                        "message": str(exc),
                    },
                ) from exc
            except Exception as exc:
                logging.exception("normalized frozen exam write failed")
                raise HTTPException(
                    status_code=503,
                    detail="정규화 시험 저장에 실패했습니다.",
                ) from exc
    else:
        valid_ids = list(source.get("question_ids", []))
        if set(scores) != set(valid_ids):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "EXAM_VERSION_BLUEPRINT_INVALID",
                    "message": "확정 시험 버전의 문항 배점이 일치하지 않습니다.",
                },
            )

    if version is not None:
        metadata = _frozen_exam_metadata(
            version, scores, evaluation_type, idempotency_key
        )
    # exam_category는 Phase4 dual-write 플래그와 무관하게 항상 확장 컬럼에 기록한다.
    metadata = {"exam_category": exam_category, **(metadata or {})}
    _, exam_id = build_exam_ids(idempotency_key)
    data = {
        "exam_set_id": exam_set_id,
        "exam_id": exam_id,
        "name": name or source.get("name"),
        "team_code": source.get("team_code"),
        "question_ids": valid_ids,
        "question_scores": scores,
        "evaluation_type": evaluation_type,
        "exam_category": exam_category,
        "total_score": 100,
        "exam_version_id": (
            version["exam_version_id"] if version is not None else ""
        ),
        "idempotency_key": idempotency_key,
        "created_by": created_by,
        "status": "active",
        "exam_datetime": exam_datetime or "",
        "pass_score": 70 if pass_score is None else pass_score,
        "duration_min": 60 if duration_min is None else duration_min,
    }
    update_fields = {
        key: value
        for key, value in {
            "exam_datetime": exam_datetime,
            "pass_score": pass_score,
            "duration_min": duration_min,
        }.items()
        if value is not None
    }
    if update_fields:
        metadata = {**metadata, **update_fields}
    stored = _persist_legacy_exam(
        exam_set_repo,
        data,
        normalized_used=policy.frozen_exams,
        metadata=metadata,
    )
    from services.activity_log import record_activity
    record_activity("exam_create", actor_name=created_by_name or "관리자",
                     target=stored.get("name") or name or "", detail=stored.get("exam_datetime") or "미정",
                     team_code=stored.get("team_code", ""))
    return {
        **stored,
        "evaluation_type": evaluation_type,
        "exam_category": exam_category,
        "total_score": 100,
        "exam_version_id": (
            version["exam_version_id"] if version is not None else ""
        ),
    }
def _is_approved_exam_user(user: dict | None) -> bool:
    if not user:
        return False
    approved = user.get("approved", False)
    return approved is True or str(approved).strip().lower() == "true"

def _exam_evaluation_type(exam: dict | None) -> str:
    value = str((exam or {}).get("evaluation_type") or "official").strip().lower()
    return value if value in {"official", "practice"} else "official"


def _assignment_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message},
    )


def assign_user_to_exam_set(
    employee_id: str,
    exam_id: str,
    actor: dict | None = None,
) -> dict:
    from repositories import exam_set_repo, user_repo, exam_v2_repo
    from services.exams.dual_write import (
        build_assignment_record,
        get_exam_write_policy,
    )

    target = exam_set_repo.get_exam(exam_id)
    if target is None:
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")

    user = user_repo.find_user(employee_id)
    if (
        user
        and target.get("team_code")
        and user.get("team")
        and user.get("team") != target.get("team_code")
    ):
        raise HTTPException(
            status_code=400,
            detail="시험지 대상 팀과 응시자 소속 팀이 다릅니다.",
        )

    if not _is_approved_exam_user(user):
        raise _assignment_error(
            "EXAM_ASSIGNEE_NOT_APPROVED",
            "승인된 응시자만 시험에 배정할 수 있습니다.",
        )

    actor_id = str((actor or {}).get("sub") or "")
    assigned_at = datetime.now(timezone.utc).isoformat()
    policy = get_exam_write_policy()
    all_exams = exam_set_repo.list_exam_sets()
    exams_by_id = {
        row.get("exam_id"): row
        for row in all_exams
        if row.get("exam_id")
    }

    # 정식 시험은 사용자당 하나만 유지한다. 연습 시험은 기존 정식/연습 배정을
    # 모두 보존하므로 학습용 시험을 여러 개 동시에 제공할 수 있다.
    legacy_conflicts = []
    if _exam_evaluation_type(target) == "official":
        legacy_conflicts = [
            row
            for row in all_exams
            if row.get("exam_id") != exam_id
            and employee_id in row.get("assigned_users", [])
            and _exam_evaluation_type(row) == "official"
        ]

    normalized_written = False
    if policy.assignments:
        if exam_v2_repo is None:
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 배정 저장소를 사용할 수 없습니다.",
            )
        try:
            version = exam_v2_repo.find_current_version(target.get("exam_set_id", ""))
            if version is None:
                raise _assignment_error(
                    "EXAM_VERSION_NOT_CONFIRMED",
                    "확정된 시험 버전이 있어야 응시자를 배정할 수 있습니다.",
                )

            conflict_ids = [row["exam_id"] for row in legacy_conflicts]
            if _exam_evaluation_type(target) == "official":
                for active in exam_v2_repo.list_active_assignments(employee_id):
                    other_id = active.get("exam_id")
                    if (
                        other_id
                        and other_id != exam_id
                        and _exam_evaluation_type(exams_by_id.get(other_id)) == "official"
                        and other_id not in conflict_ids
                    ):
                        conflict_ids.append(other_id)

            for conflict_id in conflict_ids:
                current = exam_v2_repo.find_assignment(conflict_id, employee_id)
                if current is None:
                    continue
                cancelled = build_assignment_record(
                    conflict_id,
                    current.get("exam_version_id", ""),
                    employee_id,
                    actor_id,
                    assigned_at,
                    current=current,
                    status="cancelled",
                )
                exam_v2_repo.upsert_assignment(cancelled)

            current = exam_v2_repo.find_assignment(exam_id, employee_id)
            assigned = build_assignment_record(
                exam_id,
                version["exam_version_id"],
                employee_id,
                actor_id,
                assigned_at,
                current=current,
                status="assigned",
            )
            if current and current.get("status") == "cancelled":
                assigned["assigned_by"] = actor_id
                assigned["assigned_at"] = assigned_at
            if target.get("exam_datetime") and not assigned.get("available_from"):
                assigned["available_from"] = target["exam_datetime"]
            exam_v2_repo.upsert_assignment(assigned)
            normalized_written = True
        except HTTPException:
            raise
        except Exception as exc:
            logging.exception("normalized exam assignment write failed")
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 배정 저장에 실패했습니다.",
            ) from exc

    try:
        for conflict in legacy_conflicts:
            exam_set_repo.unassign_user(conflict["exam_id"], employee_id)
        if not exam_set_repo.assign_user(exam_id, employee_id):
            if normalized_written:
                raise RuntimeError("legacy exam assignment target disappeared")
            raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as exc:
        if not normalized_written:
            raise
        logging.exception("legacy exam assignment write failed after normalized write")
        raise HTTPException(
            status_code=503,
            detail="기존 시험 배정 저장에 실패했습니다.",
        ) from exc

    return {"success": True, "employee_id": employee_id, "exam_id": exam_id}


def unassign_user_from_exam_set(
    employee_id: str,
    exam_id: str,
    actor: dict | None = None,
) -> dict:
    from repositories import exam_set_repo, exam_v2_repo
    from services.exams.dual_write import (
        build_assignment_record,
        get_exam_write_policy,
    )

    target = exam_set_repo.get_exam(exam_id)
    if target is None:
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")

    actor_id = str((actor or {}).get("sub") or "")
    cancelled_at = datetime.now(timezone.utc).isoformat()
    policy = get_exam_write_policy()
    normalized_written = False
    if policy.assignments:
        if exam_v2_repo is None:
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 배정 저장소를 사용할 수 없습니다.",
            )
        try:
            current = exam_v2_repo.find_assignment(exam_id, employee_id)
            if current is not None:
                cancelled = build_assignment_record(
                    exam_id,
                    current.get("exam_version_id", ""),
                    employee_id,
                    actor_id,
                    cancelled_at,
                    current=current,
                    status="cancelled",
                )
                exam_v2_repo.upsert_assignment(cancelled)
                normalized_written = True
        except Exception as exc:
            logging.exception("normalized exam assignment cancellation failed")
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 배정 취소 저장에 실패했습니다.",
            ) from exc

    try:
        if not exam_set_repo.unassign_user(exam_id, employee_id):
            if normalized_written:
                raise RuntimeError("legacy exam assignment target disappeared")
            raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as exc:
        if not normalized_written:
            raise
        logging.exception("legacy exam assignment cancellation failed after normalized write")
        raise HTTPException(
            status_code=503,
            detail="기존 시험 배정 취소 저장에 실패했습니다.",
        ) from exc

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


def set_exam_duration(exam_id: str, duration_min: int) -> dict:
    from repositories import exam_set_repo
    success = exam_set_repo.update_exam_set(exam_id, {"duration_min": duration_min})
    if not success:
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"success": True, "exam_id": exam_id, "duration_min": duration_min}


def delete_exam_set(exam_id: str) -> dict:
    from repositories import exam_set_repo
    if not exam_set_repo.delete_exam_set(exam_id):
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")
    return {"deleted": True, "exam_id": exam_id}


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
    from repositories import question_repo, exam_set_repo, user_repo
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


def bulk_upload_users(csv_text: str, approved_by_name: str = "") -> dict:
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
    from datetime import datetime

    all_ids = {u["employee_id"] for u in user_repo.list_users()} | {a["employee_id"] for a in load_local_admins()}
    success, skipped, errors = 0, 0, 0
    for row in rows:
        try:
            eid = (row.get("employee_id") or "").strip()
            name = (row.get("name") or "").strip()
            team = (row.get("team_code") or row.get("team") or "").strip()
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
                "approved_date": datetime.now().isoformat(),
                "approved": True,
            })
            all_ids.add(eid)
            success += 1
        except Exception:
            errors += 1
    if success > 0:
        from services.activity_log import record_activity
        record_activity("user_register", actor_name=approved_by_name or "관리자",
                         target=f"{success}명", detail="")
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
    from repositories import exam_set_repo, question_repo, exam_v2_repo
    from services.exams.dual_write import get_exam_write_policy

    exam_set = exam_set_repo.get_exam(exam_id)
    if not exam_set:
        raise HTTPException(status_code=404, detail="시험을 찾을 수 없습니다.")

    def base_exam_set(**extensions):
        return {
            "exam_id": exam_set.get("exam_id"),
            "exam_set_id": exam_set.get("exam_set_id"),
            "name": exam_set.get("name"),
            "team_code": exam_set.get("team_code"),
            "created_at": exam_set.get("created_at"),
            "exam_category": exam_set.get("exam_category") or "exam_study",
            **extensions,
        }

    def snapshot_question(item):
        value = item.get("question_snapshot_json")
        if isinstance(value, dict):
            snapshot = value
        elif isinstance(value, str):
            snapshot = json.loads(value)
        else:
            raise ValueError("question snapshot must be an object or JSON string")
        if not isinstance(snapshot, dict):
            raise ValueError("question snapshot must be an object")
        required_keys = {
            "question_id", "category", "question",
            "option_a", "option_b", "option_c", "option_d",
            "answer", "explanation",
        }
        if not required_keys.issubset(snapshot) or not any(
            key in snapshot
            for key in (
                "admin_override", "difficulty_ai", "difficulty_init", "difficulty"
            )
        ):
            raise ValueError("question snapshot is incomplete")
        item_question_id = str(item.get("question_id") or "")
        snapshot_question_id = str(snapshot.get("question_id") or "")
        if not item_question_id or item_question_id != snapshot_question_id:
            raise ValueError("question snapshot id does not match item")
        return {
            "question_id": item_question_id,
            "category": snapshot.get("category", ""),
            "question": snapshot.get("question", ""),
            "options": {
                "A": snapshot.get("option_a", ""),
                "B": snapshot.get("option_b", ""),
                "C": snapshot.get("option_c", ""),
                "D": snapshot.get("option_d", ""),
            },
            "answer": snapshot.get("answer"),
            "explanation": snapshot.get("explanation", ""),
            "difficulty": (
                snapshot.get("admin_override")
                or snapshot.get("difficulty_ai")
                or snapshot.get("difficulty_init")
                or snapshot.get("difficulty")
                or "중"
            ),
            "question_version": int(item.get("question_version")),
            "score": int(item.get("score")),
        }

    def legacy_question_scores():
        scores = exam_set.get("question_scores") or {}
        if not scores:
            blueprint = exam_set.get("blueprint_json") or {}
            if isinstance(blueprint, str):
                try:
                    blueprint = json.loads(blueprint)
                except json.JSONDecodeError:
                    blueprint = {}
            if isinstance(blueprint, dict):
                scores = blueprint.get("question_scores") or {}
        if not isinstance(scores, dict):
            return {}
        normalized = {}
        for question_id, score in scores.items():
            try:
                normalized[str(question_id)] = int(score)
            except (TypeError, ValueError):
                continue
        return normalized

    policy = get_exam_write_policy()
    if policy.frozen_exams and exam_v2_repo is None:
        raise HTTPException(
            status_code=503,
            detail="정규화 시험 저장소를 사용할 수 없습니다.",
        )
    if policy.frozen_exams:
        try:
            version = exam_v2_repo.find_current_version(
                exam_set.get("exam_set_id", "")
            )
            if version is not None:
                paper_version = int(version.get("version_no") or 0)
                items = exam_v2_repo.list_version_items(
                    exam_set.get("exam_set_id", ""), paper_version
                )
                if not items:
                    raise ValueError("frozen exam version has no items")
                ordered_items = sorted(
                    items, key=lambda item: int(item.get("order_no") or 0)
                )
                questions = [snapshot_question(item) for item in ordered_items]
                question_scores = {
                    question["question_id"]: int(question["score"])
                    for question in questions
                }
                return {
                    "exam_set": base_exam_set(
                        exam_version_id=version.get("exam_version_id", ""),
                        paper_version=paper_version,
                        question_scores=question_scores,
                        immutable=True,
                    ),
                    "questions": questions,
                }
        except Exception as exc:
            logging.exception("normalized frozen exam detail lookup failed")
            raise HTTPException(
                status_code=503,
                detail="정규화 시험 상세 조회에 실패했습니다.",
            ) from exc

    # question_id 하나마다 개별 get_question() 호출을 하면 문항 수만큼 Sheets 왕복이 발생해
    # 분당 요청 한도(quota)를 쉽게 넘긴다. exam_service.generate_exam_questions와 동일하게
    # 전체를 한 번에 불러와 id로 조회한다.
    all_by_id = {q["question_id"]: q for pool in question_repo.get_all_questions().values() for q in pool}
    question_scores = legacy_question_scores()

    questions = []
    for qid in exam_set.get("question_ids", []):
        q = all_by_id.get(qid)
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
            "explanation": q.get("explanation", ""),
            "difficulty": q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init", "중"),
            "question_version": q.get("version", 1),
            "score": question_scores.get(qid, 0),
        })

    return {
        "exam_set": base_exam_set(
            exam_version_id=(
                exam_set.get("current_exam_version_id")
                or exam_set.get("exam_version_id")
                or ""
            ),
            paper_version=int(exam_set.get("paper_version") or 0),
            question_scores=question_scores,
            immutable=False,
        ),
        "questions": questions,
    }
