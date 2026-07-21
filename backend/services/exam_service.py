import random
import uuid
import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}

PASS_SCORE = 70
DEFAULT_DURATION_MIN = 60
SCORE_PER_QUESTION = 4
_UPPER_RATIO = 0.28
_MID_RATIO = 0.40


def _calc_dist(total: int) -> dict:
    upper = round(total * _UPPER_RATIO)
    mid   = round(total * _MID_RATIO)
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


def _filter_by_exam_count(pool: list, max_exam_count: int | None) -> list:
    if not max_exam_count:
        return pool
    try:
        from repositories import question_stats_repo
        stats = question_stats_repo.list_all_stats()
    except Exception:
        return pool
    filtered = [q for q in pool if stats.get(q.get("question_id"), {}).get("exam_count", 0) < max_exam_count]
    # 필터링으로 풀이 텅 비면 배분이 아예 불가능해지므로, 그럴 땐 제한을 적용하지 않고 원래 풀을 반환
    return filtered if filtered else pool


def _exam_session_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message},
    )


def _positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _frozen_question(item: dict) -> dict:
    value = item.get("question_snapshot_json", {})
    if isinstance(value, dict):
        snapshot = dict(value)
    else:
        try:
            snapshot = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise _exam_session_error(
                "EXAM_FROZEN_ITEMS_MISSING",
                "확정 시험 문항 Snapshot을 읽을 수 없습니다.",
            ) from exc
    if not isinstance(snapshot, dict):
        raise _exam_session_error(
            "EXAM_FROZEN_ITEMS_MISSING",
            "확정 시험 문항 Snapshot 형식이 올바르지 않습니다.",
        )
    return {
        "question_id": item.get("question_id") or snapshot.get("question_id", ""),
        "category": snapshot.get("category", ""),
        "question": snapshot.get("question", ""),
        "answer": snapshot.get("answer", ""),
        "explanation": snapshot.get("explanation", ""),
        "difficulty_init": (
            snapshot.get("admin_override")
            or snapshot.get("difficulty_ai")
            or snapshot.get("difficulty_init")
            or snapshot.get("difficulty")
            or "중"
        ),
        "option_a": snapshot.get("option_a", ""),
        "option_b": snapshot.get("option_b", ""),
        "option_c": snapshot.get("option_c", ""),
        "option_d": snapshot.get("option_d", ""),
        "version": item.get("question_version") or snapshot.get("version", 1),
    }


def _start_frozen_exam_session(
    assigned_set: dict,
    employee_id: str,
) -> tuple[list[dict], str, dict] | None:
    from services.results.dual_write import (
        build_attempt_id,
        build_attempt_record,
        get_result_write_policy,
    )

    policy = get_result_write_policy()
    if not policy.result_answers:
        return None

    from repositories import exam_v2_repo, result_v2_repo
    if exam_v2_repo is None or result_v2_repo is None:
        raise HTTPException(
            status_code=503,
            detail="정규화 응시 세션 저장소를 사용할 수 없습니다.",
        )

    exam_id = assigned_set.get("exam_id", "")
    now = datetime.now(timezone.utc).isoformat()
    try:
        assignment = exam_v2_repo.find_assignment(exam_id, employee_id)
        if assignment is None or assignment.get("status") != "assigned":
            raise _exam_session_error(
                "EXAM_ATTEMPT_NOT_AVAILABLE",
                "현재 응시 가능한 확정 시험 배정을 찾을 수 없습니다.",
            )
        version = exam_v2_repo.find_version(
            assignment.get("exam_version_id", "")
        )
        if version is None:
            raise _exam_session_error(
                "EXAM_FROZEN_ITEMS_MISSING",
                "배정된 확정 시험 버전을 찾을 수 없습니다.",
            )
        paper_version = _positive_int(version.get("version_no"), 0)
        items = exam_v2_repo.list_version_items(
            version.get("exam_set_id", ""), paper_version
        )
        if not items:
            raise _exam_session_error(
                "EXAM_FROZEN_ITEMS_MISSING",
                "확정 시험 문항을 찾을 수 없습니다.",
            )

        current = result_v2_repo.find_attempt_for_assignment(
            assignment["assignment_id"],
            employee_id,
            {"started", "submitting"},
        )
        attempts_used = _positive_int(assignment.get("attempts_used"), 0)
        max_attempts = _positive_int(assignment.get("max_attempts"), 1)
        attempt_no = attempts_used + 1
        if current is None and attempts_used >= max_attempts:
            raise _exam_session_error(
                "EXAM_ATTEMPT_LIMIT_REACHED",
                "허용된 시험 응시 횟수를 모두 사용했습니다.",
            )
        attempt_id = (
            current.get("attempt_id")
            if current is not None
            else build_attempt_id(assignment["assignment_id"], attempt_no)
        )
        attempt = build_attempt_record(
            attempt_id=attempt_id,
            assignment_id=assignment["assignment_id"],
            exam_id=exam_id,
            exam_version_id=version["exam_version_id"],
            employee_id=employee_id,
            status=current.get("status", "started") if current else "started",
            occurred_at=now,
            current=current,
        )
        result_v2_repo.upsert_attempt(attempt)
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("normalized exam attempt start failed")
        raise HTTPException(
            status_code=503,
            detail="정규화 응시 세션 시작에 실패했습니다.",
        ) from exc

    questions = [_frozen_question(item) for item in items]
    return questions, attempt_id, {
        "employee_id": employee_id,
        "assignment_id": assignment["assignment_id"],
        "exam_version_id": version["exam_version_id"],
        "attempt_id": attempt_id,
        "attempt_no": attempt_no,
        "grading_mode": "frozen_v2",
    }


def generate_exam_questions(team_code: str, preview: bool = False, config: dict = None,
                            total_count: int = 25, manual_dist: dict = None,
                            employee_id: str = "", max_exam_count: int | None = None) -> dict:
    q_repo, r_repo, s_repo = _get_repos()
    data = q_repo.get_all_questions()

    assigned_set = None if preview else _find_assigned_exam_set(employee_id)

    frozen_session = None
    if assigned_set:
        exam_name = assigned_set.get("name") or DEFAULT_EXAM_NAME
        round_exam_id = assigned_set.get("exam_id", "")
        team_code = assigned_set.get("team_code", team_code)
        frozen_session = _start_frozen_exam_session(assigned_set, employee_id)
        if frozen_session is not None:
            questions, result_id, session_meta = frozen_session
        else:
            # 개별 get_question() 호출 대신 전체를 한 번에 불러와 id로 조회 — Sheets API 왕복 횟수를 줄인다.
            all_by_id = {q["question_id"]: q for pool in data.values() for q in pool}
            questions = [all_by_id[qid] for qid in assigned_set.get("question_ids", []) if qid in all_by_id]
    else:
        exam_name = DEFAULT_EXAM_NAME
        round_exam_id = ""
        # T1/T2/T3는 기존 team1/team2/team3 문제풀에 매핑(하위호환), 그 외 신규 팀은 team_code 자체를 풀 키로 사용
        team_key = TEAM_KEY_MAP.get(team_code, team_code)

        # 시험지에 쓰일 문항 풀은 preview 여부와 무관하게 승인된 문제만 포함한다.
        # (관리자 시험지 설정 화면도 이 preview 경로로 풀을 뽑는데, 승인되지 않은
        # 문제가 섞이면 실제 저장(POST /api/admin/exam-sets) 시 409로 거부된다.)
        allowed = {"approved"}
        pool = (
            [q for q in data.get("common",  []) if q.get("status") in allowed]
            + [q for q in data.get(team_key, []) if q.get("status") in allowed]
            + [q for q in data.get("safety",  []) if q.get("status") in allowed]
            + [q for q in data.get("general", []) if q.get("status") in allowed]
        )
        pool = _filter_by_exam_count(pool, max_exam_count)

        dist = manual_dist if manual_dist else _calc_dist(total_count)
        questions = _pick_by_difficulty(pool, dist)
        # 난이도별 부족 시 나머지 풀에서 보충
        if len(questions) < total_count:
            picked_ids = {q.get("question_id") for q in questions}
            remaining = [q for q in pool if q.get("question_id") not in picked_ids]
            random.shuffle(remaining)
            questions += remaining[:total_count - len(questions)]
        random.shuffle(questions)

    if frozen_session is None:
        result_id = str(uuid.uuid4())
        session_meta = {}
    duration_min = (
        _positive_int(
            assigned_set.get(
                "duration_min",
                assigned_set.get("duration_minutes", DEFAULT_DURATION_MIN),
            ),
            DEFAULT_DURATION_MIN,
        )
        if assigned_set
        else DEFAULT_DURATION_MIN
    )
    if duration_min < 1:
        duration_min = DEFAULT_DURATION_MIN

    if not preview:
        # 스냅샷 저장 (approved 문제 정보 + 정답 고정)
        snapshot = {
            q["question_id"]: {
                "question":    q["question"],
                "category":    q.get("category", ""),
                "answer":      q["answer"],
                "explanation": q.get("explanation", ""),
                "difficulty":  q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init"),
                "option_a":    q["option_a"],
                "option_b":    q["option_b"],
                "option_c":    q["option_c"],
                "option_d":    q["option_d"],
                "version":     q.get("version", 1),
            }
            for q in questions
        }
        snapshot["_meta"] = {
            "team_code": team_code,
            "exam_id": round_exam_id,
            "name": exam_name,
            "pass_score": assigned_set.get("pass_score", PASS_SCORE) if assigned_set else PASS_SCORE,
            "duration_min": duration_min,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **session_meta,
        }
        try:
            s_repo.save_snapshot(result_id, snapshot)
        except Exception as exc:
            if frozen_session is None:
                raise
            logging.exception("frozen exam snapshot save failed")
            raise HTTPException(
                status_code=503,
                detail="확정 시험 Snapshot 저장에 실패했습니다.",
            ) from exc

        # 출제 횟수 트래킹 — 실패해도 시험 생성은 계속
        try:
            from repositories import question_stats_repo
            question_stats_repo.increment_batch([q["question_id"] for q in questions])
        except Exception:
            pass

    return {
        "result_id": result_id,
        "team_code": team_code,
        "name": exam_name,
        "preview": preview,
        "duration_min": duration_min,
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
                # admin preview에서는 난이도·정답 포함, 응시자 화면에서는 제외 (설계 §9.4)
                **({
                    "difficulty": q.get("admin_override") or q.get("difficulty_ai") or q.get("difficulty_init", "중"),
                    "answer": q.get("answer"),
                } if preview else {}),
            }
            for q in questions
        ],
    }


def _log_exam_submit_activity(employee_id: str, name: str, meta: dict, result_data: dict) -> None:
    from services.activity_log import record_activity
    record_activity(
        "exam_submit",
        actor_name=name,
        target=meta.get("name") or meta.get("exam_id", ""),
        detail=f"{result_data.get('score', 0)}점, {'합격' if result_data.get('pass') else '불합격'}",
        team_code=result_data.get("team_code", ""),
        is_test=(employee_id or "").upper().startswith("TEMP"),
    )


def _legacy_score_and_save(
    result_id: str,
    answers: dict,
    response_times: dict,
    employee_id: str,
    name: str,
    skip_save: bool,
    snapshot: dict,
    r_repo,
) -> dict:
    """기존 동적 시험의 채점 계약을 변경하지 않고 유지한다."""
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
            score += SCORE_PER_QUESTION
        difficulty = q_snap.get("difficulty", "중")
        if difficulty in difficulty_summary:
            key = "correct" if correct else "incorrect"
            difficulty_summary[difficulty][key] += 1
        results.append({
            "q_id": qid,
            "question": q_snap.get("question", ""),
            "category": q_snap.get("category", ""),
            "options": {
                "A": q_snap.get("option_a", ""),
                "B": q_snap.get("option_b", ""),
                "C": q_snap.get("option_c", ""),
                "D": q_snap.get("option_d", ""),
            },
            "correct": correct,
            "answer": q_snap["answer"],
            "user_answer": user_ans,
            "explanation": q_snap.get("explanation", ""),
            "difficulty": difficulty,
            "response_time": response_times.get(qid, 0),
        })

    result_data = {
        "result_id": result_id,
        "employee_id": employee_id,
        "exam_id": meta.get("exam_id") or "legacy",
        "name": name,
        "score": score,
        "pass": score >= meta.get("pass_score", PASS_SCORE),
        "difficulty_summary": difficulty_summary,
        "results": results,
        "team_code": meta.get("team_code", ""),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    if not skip_save:
        r_repo.append_result(result_data)
        _log_exam_submit_activity(employee_id, name, meta, result_data)
    return result_data


def _submission_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _answer_value(field: str, value):
    if value is None or value == "":
        return ""
    if field == "is_correct":
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        return bool(value)
    if field in {"score", "response_time_seconds"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return str(value)


def _same_result_answers(existing: list[dict], incoming: list[dict]) -> bool:
    fields = (
        "result_answer_id", "result_id", "exam_set_item_id", "question_id",
        "question_version", "selected_choice", "correct_choice", "is_correct",
        "score", "response_time_seconds",
    )
    existing_by_id = {
        str(row.get("result_answer_id", "")): row for row in existing
    }
    incoming_by_id = {
        str(row.get("result_answer_id", "")): row for row in incoming
    }
    if set(existing_by_id) != set(incoming_by_id):
        return False
    return all(
        all(
            _answer_value(field, existing_by_id[row_id].get(field))
            == _answer_value(field, incoming_by_id[row_id].get(field))
            for field in fields
        )
        for row_id in incoming_by_id
    )


def _frozen_result_details(items: list[dict], answer_rows: list[dict]) -> list[dict]:
    answer_by_question = {row["question_id"]: row for row in answer_rows}
    details = []
    for item in sorted(items, key=lambda row: int(row.get("order_no", 0))):
        question = _frozen_question(item)
        answer = answer_by_question[question["question_id"]]
        details.append({
            "q_id": question["question_id"],
            "question": question.get("question", ""),
            "category": question.get("category", ""),
            "options": {
                "A": question.get("option_a", ""),
                "B": question.get("option_b", ""),
                "C": question.get("option_c", ""),
                "D": question.get("option_d", ""),
            },
            "correct": bool(answer["is_correct"]),
            "answer": answer["correct_choice"],
            "user_answer": answer["selected_choice"],
            "explanation": question.get("explanation", ""),
            "difficulty": question.get("difficulty_init", "중"),
            "response_time": answer["response_time_seconds"],
        })
    return details


def _score_frozen_submission(
    result_id: str,
    answers: dict,
    response_times: dict,
    employee_id: str,
    name: str,
    skip_save: bool,
    snapshot: dict,
    r_repo,
    submission_idempotency_key: str,
) -> dict:
    from repositories import exam_v2_repo, result_v2_repo
    from repositories.result_v2 import ImmutableResultAnswerConflict
    from services.results.dual_write import (
        SubmissionValidationError,
        build_attempt_record,
        build_frozen_grading_records,
    )

    meta = snapshot.get("_meta", {})
    if meta.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="시험 응시자 정보가 일치하지 않습니다.")
    if exam_v2_repo is None or result_v2_repo is None:
        raise HTTPException(status_code=503, detail="확정 시험 결과 저장소를 사용할 수 없습니다.")

    try:
        assignment = exam_v2_repo.find_assignment(meta.get("exam_id", ""), employee_id)
        version = exam_v2_repo.find_version(meta.get("exam_version_id", ""))
        if (
            assignment is None
            or assignment.get("assignment_id") != meta.get("assignment_id")
            or version is None
        ):
            raise _submission_error(
                409, "EXAM_ASSIGNMENT_CHANGED",
                "시험 배정 또는 확정 버전 정보가 변경되었습니다.",
            )
        items = exam_v2_repo.list_version_items(
            version.get("exam_set_id", ""),
            _positive_int(version.get("version_no"), 0),
        )
        if not items:
            raise _submission_error(
                409, "EXAM_FROZEN_ITEMS_MISSING",
                "확정 시험 문항을 찾을 수 없습니다.",
            )
        attempt = result_v2_repo.find_attempt(meta.get("attempt_id", ""))
        if (
            attempt is None
            or attempt.get("assignment_id") != meta.get("assignment_id")
            or attempt.get("employee_id") != employee_id
        ):
            raise _submission_error(
                409, "EXAM_ATTEMPT_NOT_FOUND", "유효한 시험 응시 기록을 찾을 수 없습니다."
            )
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("normalized submission read failed")
        raise HTTPException(status_code=503, detail="확정 시험 정보를 읽지 못했습니다.") from exc

    now = datetime.now(timezone.utc).isoformat()
    try:
        answer_rows, grading = build_frozen_grading_records(
            result_id, items, answers, response_times, now
        )
    except SubmissionValidationError as exc:
        raise _submission_error(400, exc.code, exc.message) from exc
    except ValueError as exc:
        raise _submission_error(
            409, "EXAM_FROZEN_ITEMS_INVALID", "확정 시험 문항 정보가 올바르지 않습니다."
        ) from exc

    effective_key = str(submission_idempotency_key or "").strip() or result_id
    current_key = str(attempt.get("submission_idempotency_key", "")).strip()
    if attempt.get("status") == "submitted" and current_key != effective_key:
        raise _submission_error(
            409, "RESULT_ALREADY_SUBMITTED", "이미 다른 제출 요청으로 완료된 시험입니다."
        )
    if current_key and current_key != effective_key:
        raise _submission_error(
            409, "SUBMISSION_IDEMPOTENCY_CONFLICT",
            "같은 시험에 서로 다른 제출 식별자가 사용되었습니다.",
        )

    try:
        existing_answers = result_v2_repo.list_result_answers(result_id)
    except Exception as exc:
        logging.exception("normalized answers read failed")
        raise HTTPException(status_code=503, detail="기존 답안 기록을 읽지 못했습니다.") from exc
    if existing_answers and not _same_result_answers(existing_answers, answer_rows):
        raise _submission_error(
            409, "SUBMISSION_IDEMPOTENCY_CONFLICT",
            "동일한 제출 식별자로 다른 답안을 저장할 수 없습니다.",
        )

    existing_result = r_repo.get_result(result_id)
    submitted_at = (
        existing_result.get("submitted_at") if existing_result else now
    )
    details = _frozen_result_details(items, answer_rows)
    result_data = {
        "result_id": result_id,
        "employee_id": employee_id,
        "exam_id": meta.get("exam_id", ""),
        "name": name,
        "score": grading["score"],
        "pass": grading["score"] >= meta.get("pass_score", PASS_SCORE),
        "difficulty_summary": grading["difficulty_summary"],
        "results": details,
        "team_code": meta.get("team_code", ""),
        "submitted_at": submitted_at,
        "assignment_id": meta.get("assignment_id", ""),
        "attempt_no": _positive_int(meta.get("attempt_no"), 1),
        "started_at": attempt.get("started_at", ""),
        "total_questions": grading["total_questions"],
        "correct_count": grading["correct_count"],
        "response_time_total_seconds": grading["response_time_total_seconds"],
        "grading_summary_json": grading,
        "schema_version": 2,
        "row_version": 1,
        "exam_version_id": meta.get("exam_version_id", ""),
        "attempt_id": meta.get("attempt_id", ""),
        "grading_status": "completed",
        "submission_status": "submitted",
        "error_code": "",
        "reeducation_required": False,
        "retest_assignment_id": "",
    }
    if existing_result:
        # 최초 저장된 이름과 제출 시각 등 불변 결과를 재시도 응답에도 그대로 쓴다.
        result_data = dict(existing_result)
    if skip_save:
        return result_data

    try:
        if not existing_answers:
            result_v2_repo.save_result_answers(answer_rows)

        if attempt.get("status") == "started":
            attempt = build_attempt_record(
                attempt_id=attempt["attempt_id"],
                assignment_id=attempt["assignment_id"],
                exam_id=attempt["exam_id"],
                exam_version_id=attempt["exam_version_id"],
                employee_id=attempt["employee_id"],
                status="submitting",
                occurred_at=now,
                current=attempt,
                submission_idempotency_key=effective_key,
            )
            result_v2_repo.upsert_attempt(attempt)

        if existing_result is None:
            r_repo.append_result(result_data)
            _log_exam_submit_activity(employee_id, name, meta, result_data)

        if attempt.get("status") != "submitted":
            attempt = build_attempt_record(
                attempt_id=attempt["attempt_id"],
                assignment_id=attempt["assignment_id"],
                exam_id=attempt["exam_id"],
                exam_version_id=attempt["exam_version_id"],
                employee_id=attempt["employee_id"],
                status="submitted",
                occurred_at=now,
                current=attempt,
                submission_idempotency_key=effective_key,
            )
            result_v2_repo.upsert_attempt(attempt)

        attempt_no = _positive_int(meta.get("attempt_no"), 1)
        if _positive_int(assignment.get("attempts_used"), 0) < attempt_no:
            updated_assignment = dict(assignment)
            updated_assignment.update({
                "attempts_used": attempt_no,
                "submitted_at": now,
                "row_version": _positive_int(assignment.get("row_version"), 0) + 1,
            })
            exam_v2_repo.upsert_assignment(updated_assignment)
    except HTTPException:
        raise
    except ImmutableResultAnswerConflict as exc:
        raise _submission_error(
            409, "RESULT_ANSWER_IMMUTABLE_CONFLICT",
            "이미 저장된 답안과 제출 답안이 일치하지 않습니다.",
        ) from exc
    except Exception as exc:
        logging.exception("normalized result dual write failed")
        raise HTTPException(status_code=503, detail="시험 결과 저장을 완료하지 못했습니다.") from exc
    return result_data


def score_and_save(
    result_id: str,
    answers: dict,
    response_times: dict,
    employee_id: str = "",
    name: str = "",
    skip_save: bool = False,
    submission_idempotency_key: str = "",
) -> dict:
    q_repo, r_repo, s_repo = _get_repos()

    snapshot = s_repo.get_snapshot(result_id)
    if not snapshot:
        raise HTTPException(
            status_code=410,
            detail="시험 세션이 만료됐습니다. 시험을 다시 시작해주세요.",
        )

    meta = snapshot.get("_meta", {})
    from services.results.dual_write import get_result_write_policy
    policy = get_result_write_policy()
    if meta.get("grading_mode") == "frozen_v2" and policy.result_answers:
        return _score_frozen_submission(
            result_id, answers, response_times, employee_id, name, skip_save,
            snapshot, r_repo, submission_idempotency_key,
        )
    return _legacy_score_and_save(
        result_id, answers, response_times, employee_id, name, skip_save,
        snapshot, r_repo,
    )


def get_exam_result(result_id: str, requester_id: str, requester_role: str) -> dict:
    _, r_repo, _ = _get_repos()
    result = r_repo.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    if requester_role != "admin" and result.get("employee_id") != requester_id:
        raise HTTPException(status_code=403, detail="이 결과를 조회할 권한이 없습니다.")
    return result
