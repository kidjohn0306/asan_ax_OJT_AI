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


def fetch_results_summary() -> dict:
    """응시 결과 전체 집계 — 결과 분석 화면의 통계 카드·부서별 평균 점수용."""
    _, r_repo, _ = _get_repos()
    all_results = list(r_repo.get_all_results().values())

    count = len(all_results)
    avg_score = round(sum(r.get("score", 0) for r in all_results) / count, 1) if count else 0
    pass_count = sum(1 for r in all_results if r.get("pass"))

    correct = sum(1 for r in all_results for item in r.get("results", []) if item.get("correct"))
    total_answers = sum(len(r.get("results", [])) for r in all_results)
    accuracy = round(correct / total_answers * 100, 1) if total_answers else 0

    team_scores: dict = {}
    for r in all_results:
        team = r.get("team_code") or "미배정"
        team_scores.setdefault(team, []).append(r.get("score", 0))
    team_avg_score = {team: round(sum(scores) / len(scores), 1) for team, scores in team_scores.items()}

    return {
        "count": count,
        "avg_score": avg_score,
        "accuracy": accuracy,
        "pass_count": pass_count,
        "team_avg_score": team_avg_score,
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


def generate_ai_questions(team_code: str, material_text: str, count: int, difficulty_hint: str) -> dict:
    from ai_engine.router import generate_questions_from_material
    from services.generation.gates import run_gates
    from services.material_service import get_material_text_for_team

    from repositories import question_stats_repo

    category = TEAM_KEY_MAP.get(team_code, team_code)  # pool_key — 문제 저장 위치(add_question)에 사용
    category_label = _category_label_for_pool(category)  # 공통/팀별/환경안전/일반상식 — 문제의 category 필드·게이트 검증·프론트 필터에 사용
    q_repo, _, fb_repo = _get_repos()

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

    gate_mode = _get_gate_mode()
    if gate_mode == "strict":
        passed, failed_list = _generate_ai_questions_strict(
            questions, q_repo, category, category_label, team_code,
            material_text, frozenset(flagged_ids),
        )
    else:
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
                **_gate_response_fields(q),
            }
            for q in passed + failed_list
        ],
    }


_GATE_REQUIRED_PASS_KEYS = ("V01", "V02", "V03", "V07")
_GATE_WARNING_ELIGIBLE_KEYS = ("V04", "V05", "V06")
_MIN_OVERRIDE_REASON_LENGTH = 10


def _gate_error(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


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
        if q.get("status") not in ("reviewing", "draft"):
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

    q_repo.update_question(question_id, updated_fields)
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
        "name": name,
        "team_code": team_code,
        "question_ids": question_ids,
        "created_by": created_by,
        "status": "active",
    }
    return exam_set_repo.create_exam_set(data)


def assign_user_to_exam_set(employee_id: str, exam_set_id: str) -> dict:
    from repositories import exam_set_repo

    # 한 응시자는 동시에 하나의 시험 세트에만 배정되어야 한다. 그렇지 않으면 이전에
    # 배정된 세트가 그대로 남아있어, 새 세트로 재배정해도 실제 출제 시 어느 세트를 써야
    # 할지 모호해지고 이전 문제가 그대로 나오는 버그로 이어진다.
    for s in exam_set_repo.list_exam_sets():
        other_id = s.get("exam_set_id")
        if other_id and other_id != exam_set_id and employee_id in s.get("assigned_users", []):
            exam_set_repo.unassign_user(other_id, employee_id)

    if not exam_set_repo.assign_user(exam_set_id, employee_id):
        raise HTTPException(status_code=404, detail="시험세트를 찾을 수 없습니다.")
    return {"success": True, "employee_id": employee_id, "exam_set_id": exam_set_id}


def unassign_user_from_exam_set(employee_id: str, exam_set_id: str) -> dict:
    from repositories import exam_set_repo
    if not exam_set_repo.unassign_user(exam_set_id, employee_id):
        raise HTTPException(status_code=404, detail="시험세트를 찾을 수 없습니다.")
    return {"success": True, "employee_id": employee_id, "exam_set_id": exam_set_id}


def delete_exam_set(exam_set_id: str) -> dict:
    from repositories import exam_set_repo
    if not exam_set_repo.delete_exam_set(exam_set_id):
        raise HTTPException(status_code=404, detail="시험세트를 찾을 수 없습니다.")
    return {"deleted": True, "exam_set_id": exam_set_id}


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


def get_exam_set_assignees(exam_set_id: str) -> list:
    from repositories import exam_set_repo
    exam_set = exam_set_repo.get_exam_set(exam_set_id)
    if not exam_set:
        raise HTTPException(status_code=404, detail="시험세트를 찾을 수 없습니다.")
    assigned_ids = exam_set.get("assigned_users", [])
    all_users = fetch_users().get("users", [])
    return [u for u in all_users if u.get("employee_id") in assigned_ids]
