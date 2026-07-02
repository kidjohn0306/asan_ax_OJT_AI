import os
from repositories.local_json import (
    LocalQuestionRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalFeedbackRepository,
    LocalExamSetRepository,
)

_backend = os.getenv("STORAGE_BACKEND", "local")
_exam_backend = os.getenv("EXAM_SET_STORAGE", _backend)

if _exam_backend == "sheets":
    try:
        from repositories.sheets_repo import SheetsExamSetRepository
        exam_set_repo = SheetsExamSetRepository()
    except Exception:
        exam_set_repo = LocalExamSetRepository()
else:
    exam_set_repo = LocalExamSetRepository()

if _backend == "local":
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
