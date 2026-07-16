import logging
import os
from config.storage import should_fallback_to_local
from repositories.local_json import (
    LocalQuestionRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalFeedbackRepository,
    LocalExamSetRepository,
    LocalTeamRepository,
    LocalQuestionStatsRepository,
    LocalMaterialRepository,
    LocalUserRepository,
)


def _fallback_or_raise(error: Exception, local_factory, label: str):
    if not should_fallback_to_local():
        raise error
    logging.warning("%s initialization failed; using local fallback: %s", label, error)
    return local_factory()

_backend = os.getenv("STORAGE_BACKEND", "local")
_exam_backend = os.getenv("EXAM_SET_STORAGE", "")

# 명시적 지정 → 그대로 사용
# 미지정 + GOOGLE_SERVICE_ACCOUNT_JSON 존재 → 프로덕션으로 간주해 Sheets 사용
if _exam_backend:
    _use_sheets = (_exam_backend == "sheets")
elif _backend == "sheets":
    _use_sheets = True
else:
    _use_sheets = bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))

if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsExamSetRepository
        exam_set_repo = SheetsExamSetRepository()
    except Exception as _sheets_err:
        exam_set_repo = _fallback_or_raise(
            _sheets_err, LocalExamSetRepository, "SheetsExamSetRepository"
        )
else:
    exam_set_repo = LocalExamSetRepository()

if _backend == "sheets":
    # 문제은행은 로컬 유지 — results·snapshots만 Sheets로
    question_repo = LocalQuestionRepository()
    try:
        from repositories.sheets_repo import SheetsResultRepository, SheetsSnapshotRepository
        result_repo = SheetsResultRepository()
        snapshot_repo = SheetsSnapshotRepository()
    except Exception as _sheets_rs_err:
        result_repo = _fallback_or_raise(
            _sheets_rs_err, LocalResultRepository, "SheetsResultRepository"
        )
        snapshot_repo = _fallback_or_raise(
            _sheets_rs_err, LocalSnapshotRepository, "SheetsSnapshotRepository"
        )
    feedback_repo = LocalFeedbackRepository()
elif _backend == "local":
    result_repo = LocalResultRepository()
    snapshot_repo = LocalSnapshotRepository()
    feedback_repo = LocalFeedbackRepository()
elif _backend == "drive":
    from repositories.drive_repo import DriveQuestionRepository, DriveResultRepository, DriveSnapshotRepository
    question_repo = DriveQuestionRepository()
    result_repo = DriveResultRepository()
    snapshot_repo = DriveSnapshotRepository()
    feedback_repo = LocalFeedbackRepository()
else:
    raise NotImplementedError(f"STORAGE_BACKEND={_backend} 미구현.")

# 팀 저장소 — Sheets 우선, 실패 시 Local 폴백
if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsTeamRepository
        team_repo = SheetsTeamRepository()
    except Exception as _e:
        team_repo = _fallback_or_raise(_e, LocalTeamRepository, "SheetsTeamRepository")
else:
    team_repo = LocalTeamRepository()

# 문제 출제 횟수 저장소 — Sheets 우선, 실패 시 Local 폴백
if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsQuestionStatsRepository
        question_stats_repo = SheetsQuestionStatsRepository()
    except Exception as _e:
        question_stats_repo = _fallback_or_raise(
            _e, LocalQuestionStatsRepository, "SheetsQuestionStatsRepository"
        )
else:
    question_stats_repo = LocalQuestionStatsRepository()

# 문제은행 저장소 — Sheets 우선, 실패 시 Local 폴백 (drive 백엔드는 기존 DriveQuestionRepository 유지)
if _backend != "drive":
    if _use_sheets:
        try:
            from repositories.sheets_repo import SheetsQuestionRepository
            question_repo = SheetsQuestionRepository()
        except Exception as _e:
            question_repo = _fallback_or_raise(
                _e, LocalQuestionRepository, "SheetsQuestionRepository"
            )
    else:
        question_repo = LocalQuestionRepository()

# 교육자료 스캔 캐시 저장소 — Sheets 우선, 실패 시 Local 폴백
if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsMaterialRepository
        material_repo = SheetsMaterialRepository()
    except Exception as _e:
        material_repo = _fallback_or_raise(
            _e, LocalMaterialRepository, "SheetsMaterialRepository"
        )
else:
    material_repo = LocalMaterialRepository()

# 승인된 응시자 저장소 — Sheets 우선, 실패 시 Local 폴백. 관리자 계정은 별도로
# repositories.local_json.load_local_admins()가 항상 로컬에서만 읽는다.
if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsUserRepository
        user_repo = SheetsUserRepository()
    except Exception as _e:
        user_repo = _fallback_or_raise(_e, LocalUserRepository, "SheetsUserRepository")
else:
    user_repo = LocalUserRepository()

# Phase 3 normalized generation writer. It is inert by default and never falls
# back to Local storage when explicitly enabled.
from repositories.generation_v2 import build_generation_v2_repository

generation_v2_repo = build_generation_v2_repository(use_sheets=_use_sheets)

# Phase 4 normalized exam writer. It is inert by default and never falls back
# to Local storage when explicitly enabled.
from repositories.exam_v2 import build_exam_v2_repository

exam_v2_repo = build_exam_v2_repository(use_sheets=_use_sheets)

# Phase 5 normalized result writer. It is inert by default and never falls
# back to Local storage when explicitly enabled.
from repositories.result_v2 import build_result_v2_repository

result_v2_repo = build_result_v2_repository(use_sheets=_use_sheets)

# 관리자 행동 감사 로그. OJT_USE_AUDIT_LOG=true일 때만 audit_logs 탭에 기록하며
# 기본값은 비활성(None) — Local 폴백은 두지 않는다(감사 기록은 Sheets 전용).
from repositories.audit_v2 import build_audit_v2_repository

audit_repo = build_audit_v2_repository(
    enabled=_use_sheets and os.getenv("OJT_USE_AUDIT_LOG", "false").strip().lower() == "true",
)
