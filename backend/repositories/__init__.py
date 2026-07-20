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
    LocalAuditRepository,
)
from repositories.audit_queue import QueuedAuditRepository


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
    # results·snapshots를 Sheets로. question_repo는 아래 공통 블록에서 _use_sheets에 따라 결정한다.
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
elif _backend == "local":
    result_repo = LocalResultRepository()
    snapshot_repo = LocalSnapshotRepository()
elif _backend == "drive":
    from repositories.drive_repo import DriveQuestionRepository, DriveResultRepository, DriveSnapshotRepository
    question_repo = DriveQuestionRepository()
    result_repo = DriveResultRepository()
    snapshot_repo = DriveSnapshotRepository()
else:
    raise NotImplementedError(f"STORAGE_BACKEND={_backend} 미구현.")

# 난이도 판정 피드백 저장소 — Sheets 우선, 실패 시 Local 폴백
if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsFeedbackRepository
        feedback_repo = SheetsFeedbackRepository()
    except Exception as _e:
        feedback_repo = _fallback_or_raise(_e, LocalFeedbackRepository, "SheetsFeedbackRepository")
else:
    feedback_repo = LocalFeedbackRepository()

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

# 관리자 행동 감사 로그.
# - Sheets 사용 + OJT_USE_AUDIT_LOG=true: audit_logs 탭에 기록. Sheets 쓰기 API는 분당 호출
#   한도가 있으므로 이벤트마다 즉시 append하지 않고 QueuedAuditRepository로 모았다가
#   주기적으로 배치 기록한다(OJT_AUDIT_FLUSH_INTERVAL_SECONDS·OJT_AUDIT_MAX_QUEUE_SIZE로 조절).
# - 그 외(로컬 개발): 파일 기반 LocalAuditRepository로 항상 즉시 기록한다 — 쓰기 한도가
#   없으므로 큐잉이 필요 없고, Sheets 없이도 승인·반려·수정·상태변경 감사 로그가 바로 보인다.
from repositories.audit_v2 import build_audit_v2_repository

if _use_sheets and os.getenv("OJT_USE_AUDIT_LOG", "false").strip().lower() == "true":
    _audit_sink = build_audit_v2_repository(enabled=True)
    audit_repo = QueuedAuditRepository(
        _audit_sink,
        flush_interval=float(os.getenv("OJT_AUDIT_FLUSH_INTERVAL_SECONDS", "20")),
        max_queue_size=int(os.getenv("OJT_AUDIT_MAX_QUEUE_SIZE", "25")),
    ) if _audit_sink else None
else:
    audit_repo = LocalAuditRepository()
