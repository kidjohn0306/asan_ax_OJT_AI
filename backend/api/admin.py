import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Literal, Optional

from api.deps import require_admin

router = APIRouter()

DifficultyLevel = Literal["상", "중", "하"]
TeamCode = str


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
    idempotency_key: str = ""


class ApproveUserRequest(BaseModel):
    employee_id: str
    name: str
    team: TeamCode
    exam_date: str


class RejectQuestionRequest(BaseModel):
    reason: str


class ApproveQuestionRequest(BaseModel):
    override_reason: str = ""


class CreateExamSetRequest(BaseModel):
    name: str
    team_code: TeamCode
    question_ids: list[str]
    question_scores: Optional[dict[str, int]] = None
    evaluation_type: Literal["official", "practice"] = "official"
    idempotency_key: str = ""


class FromPaperRequest(BaseModel):
    exam_set_id: str
    name: Optional[str] = None
    evaluation_type: Optional[Literal["official", "practice"]] = None
    idempotency_key: str = ""
    exam_datetime: Optional[str] = None
    pass_score: Optional[int] = Field(None, ge=0, le=100)
    duration_min: Optional[int] = Field(None, ge=1, le=600)


class AssignUserRequest(BaseModel):
    employee_id: str


class ScheduleExamRequest(BaseModel):
    exam_datetime: str


class PassScoreRequest(BaseModel):
    pass_score: int = Field(ge=0, le=100)


class DurationRequest(BaseModel):
    duration_min: int = Field(ge=1, le=600)


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


@router.get("/generation-jobs")
def get_generation_jobs(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_generation_jobs
    return fetch_generation_jobs()


@router.get("/audit-logs")
def get_audit_logs(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_audit_logs
    return fetch_audit_logs()


@router.get("/logs")
def get_logs(
    team: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    from services.admin_service import fetch_logs
    return fetch_logs(team, date_from, date_to)


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
def approve_question(
    question_id: str,
    body: Optional[ApproveQuestionRequest] = None,
    actor: dict = Depends(require_admin),
):
    from services.admin_service import approve_question
    return approve_question(question_id, actor=actor, override_reason=body.override_reason if body else "")


@router.post("/questions/{question_id}/reject")
def reject_question(question_id: str, body: RejectQuestionRequest, actor: dict = Depends(require_admin)):
    from services.admin_service import reject_question
    return reject_question(question_id, body.reason, actor=actor)


@router.post("/preview-exam")
def preview_exam(body: PreviewExamRequest, _: dict = Depends(require_admin)):
    from services.exam_service import generate_exam_questions
    return generate_exam_questions(
        body.team_code, preview=True, config=body.config,
        total_count=body.total_count, manual_dist=body.manual_dist,
        max_exam_count=body.max_exam_count
    )


@router.post("/generate-ai-questions")
def generate_ai_questions(body: GenerateAIRequest, actor: dict = Depends(require_admin)):
    from services.admin_service import generate_ai_questions as _generate
    return _generate(
        body.team_code,
        body.material_text,
        body.count,
        body.difficulty_hint,
        requested_by=actor.get("sub", ""),
        idempotency_key=body.idempotency_key,
    )


@router.post("/approve-user")
def approve_user(body: ApproveUserRequest, _: dict = Depends(require_admin)):
    from services.admin_service import approve_new_user
    return approve_new_user(body.employee_id, body.name, body.team, body.exam_date)


@router.get("/exam-sets")
def list_exam_sets(_: dict = Depends(require_admin)):
    from services.admin_service import list_exam_sets as _list
    return {"sets": _list()}


@router.post("/exam-sets")
def create_exam_set(body: CreateExamSetRequest, actor: dict = Depends(require_admin)):
    from services.admin_service import create_exam_set as _create
    return _create(
        body.name,
        body.team_code,
        body.question_ids,
        created_by=actor.get("sub", ""),
        question_scores=body.question_scores,
        evaluation_type=body.evaluation_type,
        idempotency_key=body.idempotency_key,
    )


@router.get("/exam-sets/papers")
def list_question_papers(_: dict = Depends(require_admin)):
    from services.admin_service import list_question_papers as _list
    return {"papers": _list()}


@router.post("/exam-sets/from-paper")
def create_exam_round_from_paper(body: FromPaperRequest, actor: dict = Depends(require_admin)):
    from services.admin_service import create_exam_round_from_paper as _create
    return _create(
        body.exam_set_id,
        body.name,
        created_by=actor.get("sub", ""),
        evaluation_type=body.evaluation_type,
        idempotency_key=body.idempotency_key,
        exam_datetime=body.exam_datetime,
        pass_score=body.pass_score,
        duration_min=body.duration_min,
    )


@router.post("/exam-sets/{exam_id}/assign")
def assign_user(exam_id: str, body: AssignUserRequest, actor: dict = Depends(require_admin)):
    from services.admin_service import assign_user_to_exam_set
    audit_actor = {key: actor[key] for key in ("sub", "role") if key in actor}
    return assign_user_to_exam_set(body.employee_id, exam_id, actor=audit_actor)


@router.get("/exam-sets/{exam_id}/assignees")
def get_exam_set_assignees(exam_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import get_exam_set_assignees as _get
    return {"assignees": _get(exam_id)}


@router.delete("/exam-sets/{exam_id}/assign/{employee_id}")
def unassign_user(exam_id: str, employee_id: str, actor: dict = Depends(require_admin)):
    from services.admin_service import unassign_user_from_exam_set
    audit_actor = {key: actor[key] for key in ("sub", "role") if key in actor}
    return unassign_user_from_exam_set(employee_id, exam_id, actor=audit_actor)


@router.patch("/exam-sets/{exam_id}/schedule")
def schedule_exam(exam_id: str, body: ScheduleExamRequest, _: dict = Depends(require_admin)):
    from services.admin_service import set_exam_datetime
    return set_exam_datetime(exam_id, body.exam_datetime)


@router.patch("/exam-sets/{exam_id}/pass-score")
def set_pass_score(exam_id: str, body: PassScoreRequest, _: dict = Depends(require_admin)):
    from services.admin_service import set_pass_score as _set
    return _set(exam_id, body.pass_score)


@router.patch("/exam-sets/{exam_id}/duration")
def set_exam_duration(exam_id: str, body: DurationRequest, _: dict = Depends(require_admin)):
    from services.admin_service import set_exam_duration as _set
    return _set(exam_id, body.duration_min)


@router.delete("/exam-sets/{exam_id}")
def delete_exam_set(exam_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import delete_exam_set as _delete
    return _delete(exam_id)


@router.get("/exam-sets/{exam_id}/results")
def get_exam_set_results(exam_id: str, _: dict = Depends(require_admin)):
    from repositories import result_repo
    return {"results": result_repo.list_results_by_exam(exam_id)}


@router.get("/exam-sets/{exam_id}/questions")
def get_exam_set_questions(exam_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import get_exam_set_questions as _get
    return _get(exam_id)


@router.get("/results-analysis")
def get_results_analysis(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_results_analysis
    return fetch_results_analysis()


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


@router.get("/materials/list")
def list_materials(team_code: Optional[TeamCode] = None, _: dict = Depends(require_admin)):
    from services.material_service import list_cached_materials
    if team_code:
        _material_categories_for_team(team_code)  # team_code 형식 검증
    return list_cached_materials(team_code)


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
    from repositories import exam_set_repo, result_repo, snapshot_repo

    sheets_error = None
    if type(exam_set_repo).__name__ != "SheetsExamSetRepository":
        try:
            from repositories.sheets_repo import SheetsExamSetRepository
            SheetsExamSetRepository()
        except Exception as e:
            sheets_error = str(e)

    results_sheets_error = None
    if type(result_repo).__name__ != "SheetsResultRepository":
        try:
            from repositories.sheets_repo import SheetsResultRepository
            SheetsResultRepository()
        except Exception as e:
            results_sheets_error = str(e)

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
        "result_repo_class": type(result_repo).__name__,
        "snapshot_repo_class": type(snapshot_repo).__name__,
        "sheets_init_error": sheets_error,
        "results_sheets_init_error": results_sheets_error,
    }
