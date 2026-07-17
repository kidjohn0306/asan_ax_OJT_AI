import json
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from config.features import get_schema_mode, is_feature_enabled


@dataclass(frozen=True)
class ResultWritePolicy:
    mode: str
    frozen_exams: bool
    assignments: bool
    result_answers: bool


class SubmissionValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def get_result_write_policy(
    env: Mapping[str, str] | None = None,
) -> ResultWritePolicy:
    mode = get_schema_mode(env)
    normalized = mode in {"dual", "v2"}
    frozen_exams = normalized and is_feature_enabled(
        "OJT_USE_FROZEN_EXAM", env
    )
    assignments = frozen_exams and is_feature_enabled(
        "OJT_USE_ASSIGNMENTS_TAB", env
    )
    result_answers = assignments and is_feature_enabled(
        "OJT_USE_RESULT_ANSWERS", env
    )
    return ResultWritePolicy(
        mode=mode,
        frozen_exams=frozen_exams,
        assignments=assignments,
        result_answers=result_answers,
    )


def _stable_id(kind: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ojt:{kind}:{value}"))


def build_attempt_id(assignment_id: str, attempt_no: int) -> str:
    if not str(assignment_id).strip():
        raise ValueError("assignment_id is required")
    if isinstance(attempt_no, bool) or not isinstance(attempt_no, int) or attempt_no < 1:
        raise ValueError("attempt_no must be a positive integer")
    return _stable_id("attempt", f"{assignment_id}:{attempt_no}")


def _ordered_items(items: list[Mapping]) -> list[dict]:
    ordered = sorted(
        (dict(item) for item in items),
        key=lambda item: int(item.get("order_no", 0)),
    )
    question_ids = [str(item.get("question_id", "")) for item in ordered]
    if not question_ids or any(not question_id for question_id in question_ids):
        raise ValueError("frozen items require question ids")
    if len(set(question_ids)) != len(question_ids):
        raise ValueError("duplicate frozen question ids are not allowed")
    return ordered


def _unknown_keys(
    question_ids: set[str],
    values: Mapping,
) -> list[str]:
    return sorted(str(key) for key in set(values) - question_ids)


def normalize_submission(
    items: list[Mapping],
    answers: Mapping,
    response_times: Mapping,
) -> tuple[dict, dict]:
    ordered = _ordered_items(items)
    question_ids = {str(item["question_id"]) for item in ordered}
    unknown = _unknown_keys(question_ids, answers)
    unknown.extend(_unknown_keys(question_ids, response_times))
    if unknown:
        raise SubmissionValidationError(
            "SUBMISSION_UNKNOWN_QUESTION",
            f"시험에 없는 문항 ID가 포함되어 있습니다: {sorted(set(unknown))}",
        )

    normalized_answers = {}
    normalized_times = {}
    for item in ordered:
        question_id = str(item["question_id"])
        if question_id in answers:
            choice = answers[question_id]
            if not isinstance(choice, str) or choice.upper() not in {"A", "B", "C", "D"}:
                raise SubmissionValidationError(
                    "SUBMISSION_INVALID_CHOICE",
                    f"{question_id}의 답안은 A, B, C, D 중 하나여야 합니다.",
                )
            normalized_answers[question_id] = choice.upper()
        else:
            normalized_answers[question_id] = None

        response_time = response_times.get(question_id, 0)
        if (
            isinstance(response_time, bool)
            or not isinstance(response_time, (int, float))
            or not math.isfinite(response_time)
            or response_time < 0
        ):
            raise SubmissionValidationError(
                "SUBMISSION_INVALID_RESPONSE_TIME",
                f"{question_id}의 응답시간은 0 이상의 유한한 숫자여야 합니다.",
            )
        normalized_times[question_id] = float(response_time)
    return normalized_answers, normalized_times


def _snapshot(value) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid frozen question snapshot") from exc
    if not isinstance(parsed, dict):
        raise ValueError("frozen question snapshot must be an object")
    return parsed


def _difficulty(snapshot: Mapping) -> str:
    value = (
        snapshot.get("admin_override")
        or snapshot.get("difficulty_ai")
        or snapshot.get("difficulty_init")
        or snapshot.get("difficulty")
        or "중"
    )
    return value if value in {"상", "중", "하"} else "중"


def build_frozen_grading_records(
    result_id: str,
    items: list[Mapping],
    answers: Mapping,
    response_times: Mapping,
    created_at: str,
) -> tuple[list[dict], dict]:
    ordered = _ordered_items(items)
    normalized_answers, normalized_times = normalize_submission(
        ordered, answers, response_times
    )
    difficulty_summary = {
        "상": {"correct": 0, "incorrect": 0},
        "중": {"correct": 0, "incorrect": 0},
        "하": {"correct": 0, "incorrect": 0},
    }
    rows = []
    total_score = 0
    correct_count = 0
    for item in ordered:
        question_id = str(item["question_id"])
        snapshot = _snapshot(item.get("question_snapshot_json"))
        correct_choice = str(snapshot.get("answer", "")).upper()
        selected_choice = normalized_answers[question_id]
        is_correct = selected_choice is not None and selected_choice == correct_choice
        maximum_score = int(item.get("score", 0))
        awarded_score = maximum_score if is_correct else 0
        difficulty = _difficulty(snapshot)
        difficulty_summary[difficulty][
            "correct" if is_correct else "incorrect"
        ] += 1
        total_score += awarded_score
        correct_count += int(is_correct)
        item_id = str(item.get("exam_set_item_id", ""))
        rows.append({
            "result_answer_id": _stable_id(
                "result-answer", f"{result_id}:{item_id}"
            ),
            "result_id": result_id,
            "exam_set_item_id": item_id,
            "question_id": question_id,
            "question_version": item.get("question_version", ""),
            "selected_choice": selected_choice,
            "correct_choice": correct_choice,
            "is_correct": is_correct,
            "score": awarded_score,
            "response_time_seconds": normalized_times[question_id],
            "created_at": created_at,
        })
    return rows, {
        "score": total_score,
        "total_questions": len(rows),
        "correct_count": correct_count,
        "response_time_total_seconds": sum(
            row["response_time_seconds"] for row in rows
        ),
        "difficulty_summary": difficulty_summary,
    }


def build_attempt_record(
    attempt_id: str,
    assignment_id: str,
    exam_id: str,
    exam_version_id: str,
    employee_id: str,
    status: str,
    occurred_at: str,
    current: Mapping | None = None,
    submission_idempotency_key: str = "",
) -> dict:
    current = dict(current or {})
    try:
        row_version = int(current.get("row_version", 0)) + 1
    except (TypeError, ValueError):
        row_version = 1
    started_at = current.get("started_at") or occurred_at
    submitted_at = current.get("submitted_at", "")
    if status == "submitted":
        submitted_at = occurred_at
    return {
        "attempt_id": attempt_id,
        "assignment_id": assignment_id,
        "exam_id": exam_id,
        "exam_version_id": exam_version_id,
        "employee_id": employee_id,
        "status": status,
        "entered_at": current.get("entered_at") or started_at,
        "started_at": started_at,
        "last_seen_at": occurred_at,
        "submitted_at": submitted_at,
        "closed_at": current.get("closed_at", ""),
        "client_session_id": current.get("client_session_id", ""),
        "submission_idempotency_key": (
            submission_idempotency_key
            or current.get("submission_idempotency_key", "")
        ),
        "error_code": "",
        "error_message": "",
        "row_version": row_version,
    }
