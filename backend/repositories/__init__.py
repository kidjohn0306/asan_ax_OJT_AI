import os
from repositories.local_json import (
    LocalQuestionRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalFeedbackRepository,
    LocalExamSetRepository,
    LocalTeamRepository,
    LocalQuestionStatsRepository,
)

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
        import logging
        logging.warning(f"SheetsExamSetRepository 초기화 실패, LocalExamSetRepository로 폴백: {_sheets_err}")
        exam_set_repo = LocalExamSetRepository()
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
        import logging
        logging.warning(f"Sheets Result/Snapshot 초기화 실패, Local로 폴백: {_sheets_rs_err}")
        result_repo = LocalResultRepository()
        snapshot_repo = LocalSnapshotRepository()
    feedback_repo = LocalFeedbackRepository()
elif _backend == "local":
    question_repo = LocalQuestionRepository()
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
        import logging
        logging.warning(f"SheetsTeamRepository 초기화 실패, Local로 폴백: {_e}")
        team_repo = LocalTeamRepository()
else:
    team_repo = LocalTeamRepository()

# 문제 출제 횟수 저장소 — Sheets 우선, 실패 시 Local 폴백
if _use_sheets:
    try:
        from repositories.sheets_repo import SheetsQuestionStatsRepository
        question_stats_repo = SheetsQuestionStatsRepository()
    except Exception as _e:
        import logging
        logging.warning(f"SheetsQuestionStatsRepository 초기화 실패, Local로 폴백: {_e}")
        question_stats_repo = LocalQuestionStatsRepository()
else:
    question_stats_repo = LocalQuestionStatsRepository()
