"""Canonical headers copied from the actual 55-sheet final design workbook.

The workbook's row-1 headers are authoritative. Embedded catalog/range rows are
documentation and may not override this manifest.
"""

import hashlib
import json
from collections.abc import Sequence


def _headers(value: str) -> tuple[str, ...]:
    return tuple(value.split("|"))


SHEET_HEADERS: dict[str, tuple[str, ...]] = {
    "results": _headers("result_id|exam_id|employee_id|name|score|pass|team_code|submitted_at|difficulty_summary|results|assignment_id|attempt_no|started_at|total_questions|correct_count|response_time_total_seconds|grading_summary_json|schema_version|row_version|exam_version_id|attempt_id|grading_status|submission_status|error_code|reeducation_required|retest_assignment_id"),
    "snapshots": _headers("result_id|created_at|data_json|schema_version|exam_id|assignment_id|status|expires_at|checksum|exam_version_id|attempt_id"),
    "question_stats": _headers("question_id|exam_count|last_used_at|flagged_frequent|correct_count|incorrect_count|avg_response_time_seconds|last_result_at|sample_size|measured_difficulty|difficulty_gap|review_recommended"),
    "exam_sets": _headers("exam_set_id|name|team_code|question_ids|assigned_users|created_at|exam_datetime|pass_score|status|created_by|exam_id|schema_version|lifecycle_status|evaluation_type|blueprint_json|frozen_at|frozen_by|paper_version|snapshot_checksum|row_version|migration_status|workflow_status|live_status|duration_minutes|max_attempts|reentry_policy|confirmed_by|confirmed_at|scheduled_start_at|scheduled_end_at|closed_at|archived_at|current_exam_version_id|idempotency_key"),
    "teams": _headers("team_id|team_name|team_code|created_at|updated_at|is_active|display_order|row_version"),
    "users": _headers("employee_id|password_hash|name|team|role|exam_date|approved|shift_type|process_code|task_code|is_active|approved_by|approved_at|created_at|updated_at|row_version|department|employment_status|last_login_at"),
    "question_bank": _headers("pool_key|question_id|category|question|option_a|option_b|option_c|option_d|answer|difficulty_init|difficulty_ai|admin_override|status|version|explanation|flags|gate_errors|reject_reason|question_type|team_code|process_code|task_code|material_id|slide_id|knowledge_unit_id|source_evidence|candidate_id|payload_json|gate_snapshot_json|schema_version|migration_status|approved_by|approved_at|row_version|review_status|current_revision_id|usage_count|last_used_at|measured_correct_rate|measured_difficulty|review_recommended|archived_by|archived_at"),
    "material_cache": _headers("category|files_json|scanned_at"),
    "materials": _headers("material_id|category|team_code|title|file_name|mime_type|source_type|source_ref|drive_file_id|drive_modified_time|file_hash|revision|security_status|sync_status|extraction_status|slide_count|error_message|last_scanned_at|created_at|updated_at|row_version|active_version_id|security_reviewed_by|security_reviewed_at|question_use_enabled|parse_status|index_status|chunk_count|last_indexed_at|conflict_status|last_sync_run_id"),
    "material_slides": _headers("slide_id|material_id|slide_no|title|extracted_text|markdown_path|render_path|image_count|table_count|vision_required|extraction_status|warning_json|created_at|updated_at|row_version|document_version_id|chunk_count|index_status|security_mask_status|last_indexed_at"),
    "knowledge_units": _headers("unit_id|material_id|slide_id|team_code|process_code|task_code|unit_type|title|statement|evidence_text|media_refs_json|difficulty_hint|confidence|status|reviewed_by|reviewed_at|created_at|updated_at|row_version"),
    "generation_jobs": _headers("generation_job_id|requested_by|evaluation_type|team_code|category_counts_json|difficulty_counts_json|knowledge_unit_ids_json|requested_count|candidate_multiplier|provider|model_name|prompt_version|status|started_at|completed_at|error_message|row_version|work_name|preset_id|reuse_policy_json|progress_percent|completed_count|review_required_count|failed_count|eta_seconds|submitted_for_review_at|archived_at"),
    "question_candidates": _headers("candidate_id|generation_job_id|unit_id|question_type|category|team_code|process_code|task_code|question_text|option_a|option_b|option_c|option_d|correct_answer|explanation|difficulty_designed|difficulty_reason|source_material_id|source_slide_id|source_evidence|overall_gate_status|status|payload_json|provider|model_name|prompt_version|generated_at|reviewed_by|reviewed_at|row_version|review_status|quality_warning_count|duplicate_similarity|review_requested_at|approved_question_id|rejection_reason|last_saved_at"),
    "gate_results": _headers("gate_result_id|candidate_id|gate_run_no|gate_code|status|reason|confidence|details_json|provider|model_name|prompt_version|checked_at"),
    "question_history": _headers("history_id|question_id|version|action|before_payload_json|after_payload_json|changed_by|changed_at|reason"),
    "exam_set_items": _headers("exam_set_item_id|exam_set_id|paper_version|order_no|question_id|question_version|score|question_snapshot_json|created_at|checksum"),
    "assignments": _headers("assignment_id|exam_id|employee_id|available_from|available_until|max_attempts|attempts_used|status|assigned_by|assigned_at|started_at|submitted_at|row_version|exam_version_id|cancelled_by|cancelled_at|extra_time_seconds|reentry_allowed|last_seen_at|live_status"),
    "result_answers": _headers("result_answer_id|result_id|exam_set_item_id|question_id|question_version|selected_choice|correct_choice|is_correct|score|response_time_seconds|created_at"),
    "difficulty_feedback": _headers("feedback_id|question_id|question_version|ai_difficulty|admin_difficulty|reason_code|reason_text|reviewer_id|created_at|prompt_version|status"),
    "schema_meta": _headers("entity_name|schema_version|status|primary_key|header_hash|applied_at|applied_by"),
    "00_README": ("OJT Google Sheets v2 — Append-only Schema Preview",),
    "schema_catalog": _headers("sheet|current_range|target_range|strategy|primary_key|description"),
    "data_dictionary": _headers("entity|position|field|data_type|required|key_role|description|example|phase"),
    "migration_plan": _headers("phase|name|action|guard"),
    "relation_map": _headers("parent_entity|parent_field|child_entity|child_field|cardinality|enforcement"),
    "enum_values": _headers("field|value|description"),
    "feature_flags": _headers("flag|default|allowed_values|description"),
    "sheet_ranges": _headers("sheet|current_range|target_range|current_columns|target_columns|strategy|primary_key"),
    "dry_snapshot": _headers("result_id|row_no|detected_format|created_at_column|data_json_column|recommended_action"),
    "dry_category": _headers("question_id|pool_key|current_category|target_category|target_team_code|recommended_action"),
    "dry_question": _headers("question_id|version|question_type|team_code|schema_version|migration_status|row_version"),
    "dry_result": _headers("result_id|exam_id|total_questions|correct_count|response_time_total_seconds|schema_version"),
    "sample_rows": _headers("entity|row_count|purpose|sample_json"),
    "01_상세설명": ("OJT Google Sheets v2 — 상세 구조·무중단 이관 설명",),
    "02_적용체크리스트": _headers("단계|작업|완료|담당자|검증 결과|비고"),
    "generation_presets": _headers("preset_id|name|description|evaluation_type|team_code|setup_json|is_default|is_active|created_by|created_at|updated_at|row_version"),
    "document_versions": _headers("document_version_id|material_id|version_no|drive_revision_id|file_hash|file_name|mime_type|size_bytes|change_summary|security_status|parse_status|index_status|chunk_count|created_by|created_at|is_current|row_version"),
    "document_chunks": _headers("chunk_id|document_version_id|material_id|slide_id|chunk_no|chunk_type|content_text|token_count|embedding_status|index_key|security_mask_status|source_locator_json|created_at|updated_at|row_version"),
    "sync_runs": _headers("sync_run_id|source_type|scope_json|status|requested_by|started_at|completed_at|files_scanned|files_added|files_updated|files_failed|conflict_count|error_message|details_json|row_version"),
    "sync_conflicts": _headers("conflict_id|sync_run_id|material_id|document_version_id|conflict_type|drive_version_json|system_version_json|status|resolution|resolution_reason|resolved_by|resolved_at|created_at|row_version"),
    "question_reviews": _headers("review_id|candidate_id|question_id|question_revision_id|review_action|checklist_json|reason|reviewer_id|reviewed_at|before_payload_json|after_payload_json"),
    "exam_versions": _headers("exam_version_id|exam_set_id|version_no|status|question_count|total_score|blueprint_json|question_hash|confirmed_by|confirmed_at|created_at|row_version"),
    "exam_attempts": _headers("attempt_id|assignment_id|exam_id|exam_version_id|employee_id|status|entered_at|started_at|last_seen_at|submitted_at|closed_at|client_session_id|submission_idempotency_key|error_code|error_message|row_version"),
    "exam_events": _headers("event_id|exam_id|exam_version_id|assignment_id|attempt_id|employee_id|event_type|severity|event_time|actor_type|actor_id|payload_json|idempotency_key"),
    "admin_tasks": _headers("task_id|task_type|priority|title|description|target_type|target_id|due_at|status|source_type|source_id|completed_by|completed_at|created_at|updated_at"),
    "operational_alerts": _headers("alert_id|severity|domain|alert_code|title|message|target_type|target_id|status|detected_at|acknowledged_by|acknowledged_at|resolved_by|resolved_at|details_json"),
    "audit_logs": _headers("audit_id|actor_id|actor_role|action_type|target_type|target_id|before_json|after_json|reason|request_id|ip_address|user_agent|created_at"),
    "system_status_checks": _headers("check_id|service_name|status|latency_ms|checked_at|error_code|error_message|details_json|environment|deployment_version"),
    "export_jobs": _headers("export_job_id|export_type|filters_json|format|status|requested_by|requested_at|started_at|completed_at|file_path|expires_at|error_message"),
    "reeducation_records": _headers("reeducation_id|result_id|employee_id|exam_id|reason_code|reason_text|status|action_type|assigned_exam_id|due_at|completed_at|created_by|created_at"),
    "ui_routes_v3": ("관리자 페이지 v3 URL·화면 구조",),
    "api_contracts_v3": ("관리자 고도화 API와 Sheet 연결",),
    "state_models_v3": ("문제·시험·실시간·자료 상태 전이",),
    "feature_matrix_v3": ("신규 관리자 기능과 데이터 구조",),
    "03_관리자기능_v3_요약": ("OJT 관리자 페이지 v3 — Google Sheets 확장 요약",),
}


LEGACY_PREFIXES: dict[str, tuple[str, ...]] = {
    "results": SHEET_HEADERS["results"][:10],
    "snapshots": SHEET_HEADERS["snapshots"][:3],
    "question_stats": SHEET_HEADERS["question_stats"][:4],
    "exam_sets": SHEET_HEADERS["exam_sets"][:11],
    "teams": SHEET_HEADERS["teams"][:5],
    "users": SHEET_HEADERS["users"][:7],
    "question_bank": SHEET_HEADERS["question_bank"][:18],
    "material_cache": SHEET_HEADERS["material_cache"][:3],
}


PRIMARY_KEYS: dict[str, str] = {
    "results": "result_id",
    "snapshots": "result_id",
    "question_stats": "question_id",
    "exam_sets": "exam_id",
    "teams": "team_id",
    "users": "employee_id",
    "question_bank": "question_id",
    "material_cache": "category",
    "schema_meta": "entity_name",
    "materials": "material_id",
    "material_slides": "slide_id",
    "knowledge_units": "unit_id",
    "generation_jobs": "generation_job_id",
    "question_candidates": "candidate_id",
    "gate_results": "gate_result_id",
    "question_history": "history_id",
    "exam_set_items": "exam_set_item_id",
    "assignments": "assignment_id",
    "result_answers": "result_answer_id",
    "difficulty_feedback": "feedback_id",
    "generation_presets": "preset_id",
    "document_versions": "document_version_id",
    "document_chunks": "chunk_id",
    "sync_runs": "sync_run_id",
    "sync_conflicts": "conflict_id",
    "question_reviews": "review_id",
    "exam_versions": "exam_version_id",
    "exam_attempts": "attempt_id",
    "exam_events": "event_id",
    "admin_tasks": "task_id",
    "operational_alerts": "alert_id",
    "audit_logs": "audit_id",
    "system_status_checks": "check_id",
    "export_jobs": "export_job_id",
    "reeducation_records": "reeducation_id",
}


def header_hash(headers: Sequence[str]) -> str:
    payload = json.dumps(
        list(headers),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
