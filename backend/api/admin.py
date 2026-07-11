import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Literal, Optional

from api.deps import require_admin

router = APIRouter()

DifficultyLevel = Literal["상", "중", "하"]
TeamCode = str
StatusType = Literal["draft", "reviewing", "approved", "rejected"]


class DifficultyPatchRequest(BaseModel):
    question_id: str
    new_difficulty: DifficultyLevel
    reason_code: Optional[str] = ""


class PreviewExamRequest(BaseModel):
    team_code: TeamCode
    total_count: int = 25
    manual_dist: Optional[dict] = None
    config: Optional[dict] = None
    max_exam_count: Optional[int] = None


class GenerateAIRequest(BaseModel):
    team_code: TeamCode
    material_text: str = ""
    count: int = 10
    difficulty_hint: str = "중"


class ApproveUserRequest(BaseModel):
    employee_id: str
    name: str
    team: TeamCode
    exam_date: str


class RejectQuestionRequest(BaseModel):
    reason: str


class CreateExamSetRequest(BaseModel):
    name: str
    team_code: TeamCode
    question_ids: list[str]


class AssignUserRequest(BaseModel):
    employee_id: str


class CreateTeamRequest(BaseModel):
    team_id: str
    team_name: str
    team_code: str


class UpdateTeamRequest(BaseModel):
    team_name: str


class MaterialScanRequest(BaseModel):
    team_code: TeamCode


@router.get("/users")
def get_users(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_users
    return fetch_users()


@router.delete("/users/{employee_id}")
def delete_user(employee_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import delete_user
    return delete_user(employee_id)


@router.post("/users/{employee_id}/reset-password")
def reset_password(employee_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import reset_user_password
    return reset_user_password(employee_id)


@router.get("/user-count")
def get_user_count(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_user_count
    return fetch_user_count()


@router.get("/exam-count")
def get_exam_count(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_exam_count
    return fetch_exam_count()


@router.get("/approved-question-count")
def get_approved_question_count(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_approved_question_count
    return fetch_approved_question_count()


@router.get("/reviewing-question-count")
def get_reviewing_question_count(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_reviewing_question_count
    return fetch_reviewing_question_count()


@router.get("/logs")
def get_logs(
    team: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    from services.admin_service import fetch_logs
    return fetch_logs(team, date_from, date_to)


@router.get("/results-summary")
def get_results_summary(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_results_summary
    return fetch_results_summary()


@router.get("/questions")
def get_questions(
    team: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    from services.admin_service import fetch_questions
    return fetch_questions(team, category, status)


@router.patch("/difficulty")
def update_difficulty(body: DifficultyPatchRequest, _: dict = Depends(require_admin)):
    from services.admin_service import override_difficulty
    return override_difficulty(body.question_id, body.new_difficulty, body.reason_code)


@router.post("/questions/{question_id}/approve")
def approve_question(question_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import approve_question
    return approve_question(question_id)


@router.post("/questions/{question_id}/reject")
def reject_question(question_id: str, body: RejectQuestionRequest, _: dict = Depends(require_admin)):
    from services.admin_service import reject_question
    return reject_question(question_id, body.reason)


@router.post("/preview-exam")
def preview_exam(body: PreviewExamRequest, _: dict = Depends(require_admin)):
    from services.exam_service import generate_exam_questions
    return generate_exam_questions(
        body.team_code, preview=True, config=body.config,
        total_count=body.total_count, manual_dist=body.manual_dist,
        max_exam_count=body.max_exam_count
    )


@router.post("/generate-ai-questions")
def generate_ai_questions(body: GenerateAIRequest, _: dict = Depends(require_admin)):
    from services.admin_service import generate_ai_questions as _generate
    return _generate(body.team_code, body.material_text, body.count, body.difficulty_hint)


@router.post("/approve-user")
def approve_user(body: ApproveUserRequest, _: dict = Depends(require_admin)):
    from services.admin_service import approve_new_user
    return approve_new_user(body.employee_id, body.name, body.team, body.exam_date)


@router.get("/exam-sets")
def list_exam_sets(_: dict = Depends(require_admin)):
    from services.admin_service import list_exam_sets as _list
    return {"sets": _list()}


@router.post("/exam-sets")
def create_exam_set(body: CreateExamSetRequest, _: dict = Depends(require_admin)):
    from services.admin_service import create_exam_set as _create
    return _create(body.name, body.team_code, body.question_ids)


@router.post("/exam-sets/{exam_set_id}/assign")
def assign_user(exam_set_id: str, body: AssignUserRequest, _: dict = Depends(require_admin)):
    from services.admin_service import assign_user_to_exam_set
    return assign_user_to_exam_set(body.employee_id, exam_set_id)


@router.get("/exam-sets/{exam_set_id}/assignees")
def get_exam_set_assignees(exam_set_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import get_exam_set_assignees as _get
    return {"assignees": _get(exam_set_id)}


@router.delete("/exam-sets/{exam_set_id}/assign/{employee_id}")
def unassign_user(exam_set_id: str, employee_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import unassign_user_from_exam_set
    return unassign_user_from_exam_set(employee_id, exam_set_id)


@router.delete("/exam-sets/{exam_set_id}")
def delete_exam_set(exam_set_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import delete_exam_set as _delete
    return _delete(exam_set_id)


@router.get("/exam-sets/{exam_set_id}/results")
def get_exam_set_results(exam_set_id: str, _: dict = Depends(require_admin)):
    from repositories import result_repo
    return {"results": result_repo.list_results_by_set(exam_set_id)}


@router.post("/seed-mock-data")
def seed_mock_data(_: dict = Depends(require_admin)):
    from services.admin_service import seed_mock_data as _seed
    return _seed()


@router.get("/stats")
def get_stats(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_dashboard_stats
    return fetch_dashboard_stats()


@router.get("/system-status")
def get_system_status(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_system_status
    return fetch_system_status()


@router.get("/teams")
def get_teams(_: dict = Depends(require_admin)):
    from services.admin_service import list_teams
    return {"teams": list_teams()}


@router.get("/teams/headcount")
def get_team_headcounts(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_team_headcounts
    return fetch_team_headcounts()


@router.post("/teams")
def create_team(body: CreateTeamRequest, _: dict = Depends(require_admin)):
    from services.admin_service import create_team as _create
    return _create(body.team_id, body.team_name, body.team_code)


@router.patch("/teams/{team_id}")
def update_team(team_id: str, body: UpdateTeamRequest, _: dict = Depends(require_admin)):
    from services.admin_service import update_team as _update
    return _update(team_id, body.team_name)


@router.delete("/teams/{team_id}")
def delete_team(team_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import delete_team as _delete
    return _delete(team_id)


@router.post("/upload-users")
async def upload_users(file: UploadFile = File(...), _: dict = Depends(require_admin)):
    from services.admin_service import bulk_upload_users
    raw = await file.read()
    # Excel/메모장 BOM 처리
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")
    return bulk_upload_users(text)


@router.get("/question-stats")
def get_question_stats(_: dict = Depends(require_admin)):
    from repositories import question_stats_repo
    return {"stats": question_stats_repo.list_all_stats()}


@router.get("/question-stats/flagged")
def get_flagged_questions(_: dict = Depends(require_admin)):
    from repositories import question_stats_repo
    return {"flagged": question_stats_repo.list_flagged()}


_CATEGORY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _material_categories_for_team(team_code: str) -> list[str]:
    from services.material_service import categories_for_team
    categories = categories_for_team(team_code)
    if not all(_CATEGORY_PATTERN.match(c) for c in categories):
        raise HTTPException(status_code=400, detail="잘못된 team_code입니다.")
    return categories


@router.get("/materials/status")
def get_materials_status(team_code: TeamCode, _: dict = Depends(require_admin)):
    from services.material_service import check_new_materials
    categories = {cat: check_new_materials(cat) for cat in _material_categories_for_team(team_code)}
    return {"categories": categories, "has_new_any": any(c["has_new"] for c in categories.values())}


@router.post("/materials/scan")
def scan_materials(body: MaterialScanRequest, _: dict = Depends(require_admin)):
    from services.material_service import scan_materials as _scan
    results = {}
    for cat in _material_categories_for_team(body.team_code):
        manifest = _scan(cat)
        results[cat] = {
            "category": cat,
            "file_count": len(manifest.get("files", [])),
            "scanned_at": manifest.get("scanned_at", ""),
            "skipped": manifest.get("skipped", []),
        }
    return {"categories": results}


@router.get("/debug/storage")
def debug_storage(_: dict = Depends(require_admin)):
    import os
    from repositories import exam_set_repo

    sheets_error = None
    if type(exam_set_repo).__name__ != "SheetsExamSetRepository":
        try:
            from repositories.sheets_repo import SheetsExamSetRepository
            SheetsExamSetRepository()
        except Exception as e:
            sheets_error = str(e)

    def _set(key: str) -> bool:
        return bool(os.getenv(key))

    return {
        # 값 자체가 동작 모드 판단에 필요한 비민감 설정 — 값 그대로 표시
        "STORAGE_BACKEND": os.getenv("STORAGE_BACKEND", "(not set)"),
        "AI_PROVIDER": os.getenv("AI_PROVIDER", "(not set)"),
        "EXAM_SET_STORAGE": os.getenv("EXAM_SET_STORAGE", "(not set)"),
        # ID·크리덴셜류는 설정 여부만 노출 (값·다른 인프라 환경변수 이름은 노출하지 않음)
        "GOOGLE_SHEETS_ID_SET": _set("GOOGLE_SHEETS_ID"),
        "GOOGLE_EXAM_SETS_SHEET_ID_SET": _set("GOOGLE_EXAM_SETS_SHEET_ID"),
        "GOOGLE_SERVICE_ACCOUNT_JSON_SET": _set("GOOGLE_SERVICE_ACCOUNT_JSON"),
        "DRIVE_RESULTS_FOLDER_ID_SET": _set("DRIVE_RESULTS_FOLDER_ID"),
        "exam_set_repo_class": type(exam_set_repo).__name__,
        "sheets_init_error": sheets_error,
    }
