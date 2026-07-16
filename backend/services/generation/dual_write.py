import copy
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from config.features import get_schema_mode, is_feature_enabled


GATE_CODES = ("V01", "V02", "V03", "V04", "V05", "V06", "V07")


@dataclass(frozen=True)
class GenerationWritePolicy:
    mode: str
    candidates: bool
    gates: bool


def get_generation_write_policy(
    env: Mapping[str, str] | None = None,
) -> GenerationWritePolicy:
    mode = get_schema_mode(env)
    normalized_mode = mode in {"dual", "v2"}
    candidates = normalized_mode and is_feature_enabled(
        "OJT_USE_CANDIDATE_TAB", env
    )
    gates = candidates and is_feature_enabled(
        "OJT_USE_GATE_RESULTS_TAB", env
    )
    return GenerationWritePolicy(mode=mode, candidates=candidates, gates=gates)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, value).hex}"


def assign_candidate_ids(
    questions: list[dict],
    generation_job_id: str,
) -> list[dict]:
    result = []
    for index, question in enumerate(questions, start=1):
        item = copy.deepcopy(question)
        item["candidate_id"] = _stable_id(
            "cand",
            f"ojt:{generation_job_id}:candidate:{index}",
        )
        result.append(item)
    return result


def link_candidate_to_legacy(question: dict, candidate_id: str) -> dict:
    linked = copy.deepcopy(question)
    linked["candidate_id"] = candidate_id
    flags = dict(linked.get("flags") or {})
    flags["candidate_id"] = candidate_id
    linked["flags"] = flags
    return linked


def build_candidate_row(
    question: dict,
    generation_job_id: str,
    team_code: str,
    provider: str,
    generated_at: str,
    model_name: str = "",
    prompt_version: str = "",
) -> dict:
    snapshot = (question.get("flags") or {}).get("gate_snapshot") or {}
    gates = snapshot.get("gates") or {}
    warning_count = sum(
        1 for result in gates.values()
        if result.get("status") == "WARNING"
    )
    v06 = gates.get("V06") or {}
    v06_details = v06.get("details") or {}
    return {
        "candidate_id": question.get("candidate_id", ""),
        "generation_job_id": generation_job_id,
        "unit_id": question.get("knowledge_unit_id", ""),
        "question_type": question.get("question_type", "MULTIPLE_CHOICE_SINGLE"),
        "category": question.get("category", ""),
        "team_code": team_code,
        "process_code": question.get("process_code", ""),
        "task_code": question.get("task_code", ""),
        "question_text": question.get("question", ""),
        "option_a": question.get("option_a", ""),
        "option_b": question.get("option_b", ""),
        "option_c": question.get("option_c", ""),
        "option_d": question.get("option_d", ""),
        "correct_answer": question.get("answer", ""),
        "explanation": question.get("explanation", ""),
        "difficulty_designed": (
            question.get("difficulty_ai")
            or question.get("difficulty_init", "")
        ),
        "difficulty_reason": question.get("difficulty_reason", ""),
        "source_material_id": question.get("material_id", ""),
        "source_slide_id": question.get("slide_id", ""),
        "source_evidence": question.get("source_evidence", ""),
        "overall_gate_status": snapshot.get("overall_status", ""),
        "status": question.get("status", "draft"),
        "payload_json": json.dumps(question, ensure_ascii=False, sort_keys=True),
        "provider": provider,
        "model_name": model_name,
        "prompt_version": prompt_version,
        "generated_at": generated_at,
        "reviewed_by": "",
        "reviewed_at": "",
        "row_version": "1",
        "review_status": question.get("status", "draft"),
        "quality_warning_count": warning_count,
        "duplicate_similarity": v06_details.get("similarity", ""),
        "review_requested_at": generated_at if question.get("status") == "reviewing" else "",
        "approved_question_id": "",
        "rejection_reason": question.get("reject_reason", ""),
        "last_saved_at": generated_at,
    }


def build_gate_rows(question: dict, checked_at: str) -> list[dict]:
    candidate_id = question.get("candidate_id", "")
    snapshot = (question.get("flags") or {}).get("gate_snapshot") or {}
    gates = snapshot.get("gates") or {}
    rows = []
    for code in GATE_CODES:
        result = gates.get(code) or {}
        rows.append({
            "gate_result_id": _stable_id(
                "gate",
                f"ojt:{candidate_id}:{code}:1",
            ),
            "candidate_id": candidate_id,
            "gate_run_no": "1",
            "gate_code": code,
            "status": result.get("status", "NOT_RUN"),
            "reason": result.get("reason", ""),
            "confidence": result.get("confidence", ""),
            "details_json": json.dumps(result, ensure_ascii=False, sort_keys=True),
            "provider": snapshot.get("provider", ""),
            "model_name": snapshot.get("model_name", ""),
            "prompt_version": snapshot.get("prompt_version", ""),
            "checked_at": checked_at,
        })
    return rows


def build_review_records(
    before: dict,
    after: dict,
    action: str,
    actor_id: str,
    reason: str,
    reviewed_at: str,
) -> tuple[dict, dict]:
    before_snapshot = copy.deepcopy(before)
    after_snapshot = copy.deepcopy(after)
    question_id = str(
        after_snapshot.get("question_id")
        or before_snapshot.get("question_id")
        or ""
    )
    flags = before_snapshot.get("flags") or {}
    candidate_id = str(
        after_snapshot.get("candidate_id")
        or before_snapshot.get("candidate_id")
        or flags.get("candidate_id")
        or ""
    )
    version = after_snapshot.get("version") or before_snapshot.get("version") or 1
    action = action.strip().upper()
    stable_key = f"ojt:{question_id}:{version}:{action}"
    before_json = json.dumps(before_snapshot, ensure_ascii=False, sort_keys=True)
    after_json = json.dumps(after_snapshot, ensure_ascii=False, sort_keys=True)

    review = {
        "review_id": _stable_id("review", stable_key),
        "candidate_id": candidate_id,
        "question_id": question_id,
        "question_revision_id": str(
            after_snapshot.get("current_revision_id")
            or before_snapshot.get("current_revision_id")
            or ""
        ),
        "review_action": action,
        "checklist_json": "{}",
        "reason": reason,
        "reviewer_id": actor_id,
        "reviewed_at": reviewed_at,
        "before_payload_json": before_json,
        "after_payload_json": after_json,
    }
    history = {
        "history_id": _stable_id("history", stable_key),
        "question_id": question_id,
        "version": version,
        "action": action,
        "before_payload_json": before_json,
        "after_payload_json": after_json,
        "changed_by": actor_id,
        "changed_at": reviewed_at,
        "reason": reason,
    }
    return review, history
