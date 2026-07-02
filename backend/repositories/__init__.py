import os
from repositories.local_json import (
    LocalQuestionRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalFeedbackRepository,
    LocalExamSetRepository,
)

_backend = os.getenv("STORAGE_BACKEND", "local")
# EXAM_SET_STORAGE 가 없으면 STORAGE_BACKEND=sheets 로 활성화
_exam_backend = os.getenv("EXAM_SET_STORAGE", _backend)

if _exam_backend == "sheets" or _backend == "sheets":
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
