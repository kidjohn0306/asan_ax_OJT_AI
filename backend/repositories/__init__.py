import os
from repositories.local_json import (
    LocalQuestionRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalFeedbackRepository,
    LocalExamSetRepository,
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
    from repositories.sheets_repo import SheetsExamSetRepository
    exam_set_repo = SheetsExamSetRepository()
else:
    exam_set_repo = LocalExamSetRepository()

# exam_set 외 다른 repo는 local 또는 drive 만 사용
_other_backend = "local" if _backend == "sheets" else _backend
if _other_backend == "local":
    question_repo = LocalQuestionRepository()
    result_repo = LocalResultRepository()
    snapshot_repo = LocalSnapshotRepository()
    feedback_repo = LocalFeedbackRepository()
elif _other_backend == "drive":
    from repositories.drive_repo import DriveQuestionRepository, DriveResultRepository, DriveSnapshotRepository
    question_repo = DriveQuestionRepository()
    result_repo = DriveResultRepository()
    snapshot_repo = DriveSnapshotRepository()
    feedback_repo = LocalFeedbackRepository()
else:
    raise NotImplementedError(f"STORAGE_BACKEND={_backend} 미구현.")
