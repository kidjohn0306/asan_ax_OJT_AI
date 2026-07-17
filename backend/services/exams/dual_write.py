import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from config.features import get_schema_mode, is_feature_enabled


_SNAPSHOT_KEYS = (
    "question_id",
    "question_type",
    "category",
    "question",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "answer",
    "explanation",
    "difficulty_init",
    "difficulty_ai",
    "admin_override",
    "version",
)


@dataclass(frozen=True)
class ExamWritePolicy:
    mode: str
    frozen_exams: bool
    assignments: bool


def get_exam_write_policy(
    env: Mapping[str, str] | None = None,
) -> ExamWritePolicy:
    mode = get_schema_mode(env)
    normalized = mode in {"dual", "v2"}
    frozen_exams = normalized and is_feature_enabled(
        "OJT_USE_FROZEN_EXAM", env
    )
    assignments = frozen_exams and is_feature_enabled(
        "OJT_USE_ASSIGNMENTS_TAB", env
    )
    return ExamWritePolicy(
        mode=mode,
        frozen_exams=frozen_exams,
        assignments=assignments,
    )


def resolve_question_scores(
    question_ids: list[str],
    question_scores: Mapping[str, int] | None = None,
) -> dict[str, int]:
    ordered_ids = list(dict.fromkeys(question_ids))
    if not ordered_ids:
        raise ValueError("at least one question is required")
    if len(ordered_ids) != len(question_ids):
        raise ValueError("duplicate question ids are not allowed")
    if len(ordered_ids) > 100:
        raise ValueError("at most 100 questions are allowed")

    if question_scores is None:
        base, remainder = divmod(100, len(ordered_ids))
        return {
            question_id: base + (1 if index < remainder else 0)
            for index, question_id in enumerate(ordered_ids)
        }

    missing = sorted(set(ordered_ids) - set(question_scores))
    unknown = sorted(set(question_scores) - set(ordered_ids))
    if missing or unknown:
        raise ValueError(f"missing={missing}; unknown={unknown}")
    if any(
        isinstance(score, bool)
        or not isinstance(score, int)
        or score <= 0
        for score in question_scores.values()
    ):
        raise ValueError("scores must be positive integers")
    if sum(question_scores.values()) != 100:
        raise ValueError("score total must be 100")
    return {
        question_id: question_scores[question_id]
        for question_id in ordered_ids
    }


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, value).hex}"


def _short_operation_id(prefix: str, value: str | None = None) -> str:
    operation_uuid = (
        uuid.uuid5(uuid.NAMESPACE_URL, value)
        if value
        else uuid.uuid4()
    )
    return f"{prefix}-{operation_uuid.hex[:8]}"


def build_exam_ids(idempotency_key: str = "") -> tuple[str, str]:
    key = idempotency_key.strip()
    if not key:
        return _short_operation_id("set"), _short_operation_id("exam")
    return (
        _short_operation_id("set", f"ojt:exam-set:{key}"),
        _short_operation_id("exam", f"ojt:exam-round:{key}"),
    )


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_frozen_exam_records(
    exam_set_id: str,
    questions: list[dict],
    scores: Mapping[str, int],
    confirmed_by: str,
    confirmed_at: str,
    version_no: int,
) -> tuple[dict, list[dict]]:
    items = []
    blueprint = []
    item_hash_inputs = []

    for order_no, question in enumerate(questions, start=1):
        question_id = str(question.get("question_id", ""))
        snapshot = {
            key: question.get(key, 1 if key == "version" else "")
            for key in _SNAPSHOT_KEYS
        }
        snapshot_json = _canonical_json(snapshot)
        checksum = _sha256(snapshot_json)
        score = scores[question_id]
        question_version = question.get("version", 1)
        blueprint.append({
            "order_no": order_no,
            "question_id": question_id,
            "question_version": question_version,
            "score": score,
        })
        item_hash_inputs.append({
            "order_no": order_no,
            "question_id": question_id,
            "question_version": question_version,
            "score": score,
            "checksum": checksum,
        })
        items.append({
            "exam_set_item_id": "",
            "exam_set_id": exam_set_id,
            "paper_version": version_no,
            "order_no": order_no,
            "question_id": question_id,
            "question_version": question_version,
            "score": score,
            "question_snapshot_json": snapshot_json,
            "created_at": confirmed_at,
            "checksum": checksum,
        })

    question_hash = _sha256(_canonical_json(item_hash_inputs))
    exam_version_id = _stable_id(
        "examver",
        f"ojt:{exam_set_id}:version:{version_no}:{question_hash}",
    )
    for item in items:
        item["exam_set_item_id"] = _stable_id(
            "examitem",
            (
                f"ojt:{exam_version_id}:item:{item['order_no']}:"
                f"{item['question_id']}"
            ),
        )

    version = {
        "exam_version_id": exam_version_id,
        "exam_set_id": exam_set_id,
        "version_no": version_no,
        "status": "confirmed",
        "question_count": len(items),
        "total_score": sum(item["score"] for item in items),
        "blueprint_json": _canonical_json(blueprint),
        "question_hash": question_hash,
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at,
        "created_at": confirmed_at,
        "row_version": 1,
    }
    return version, items


def build_assignment_record(
    exam_id: str,
    exam_version_id: str,
    employee_id: str,
    actor_id: str,
    assigned_at: str,
    current: Mapping | None = None,
    status: str = "assigned",
) -> dict:
    current = dict(current or {})
    try:
        row_version = int(current.get("row_version", 0)) + 1
    except (TypeError, ValueError):
        row_version = 1
    assignment_id = current.get("assignment_id") or _stable_id(
        "assignment",
        f"ojt:{exam_id}:{employee_id}",
    )
    cancelled = status == "cancelled"
    return {
        "assignment_id": assignment_id,
        "exam_id": exam_id,
        "employee_id": employee_id,
        "available_from": current.get("available_from", ""),
        "available_until": current.get("available_until", ""),
        "max_attempts": current.get("max_attempts", 1),
        "attempts_used": current.get("attempts_used", 0),
        "status": status,
        "assigned_by": current.get("assigned_by") or actor_id,
        "assigned_at": current.get("assigned_at") or assigned_at,
        "started_at": current.get("started_at", ""),
        "submitted_at": current.get("submitted_at", ""),
        "row_version": row_version,
        "exam_version_id": exam_version_id,
        "cancelled_by": actor_id if cancelled else "",
        "cancelled_at": assigned_at if cancelled else "",
        "extra_time_seconds": current.get("extra_time_seconds", 0),
        "reentry_allowed": current.get("reentry_allowed", False),
        "last_seen_at": current.get("last_seen_at", ""),
        "live_status": current.get("live_status", "not_started"),
    }
