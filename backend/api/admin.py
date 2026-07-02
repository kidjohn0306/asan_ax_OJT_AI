from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Literal, Optional

router = APIRouter()
_bearer = HTTPBearer()

DifficultyLevel = Literal["상", "중", "하"]
TeamCode = Literal["T1", "T2", "T3"]
StatusType = Literal["draft", "reviewing", "approved", "rejected"]


def require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    from services.auth_service import decode_token
    payload = decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload


class DifficultyPatchRequest(BaseModel):
    question_id: str
    new_difficulty: DifficultyLevel
    reason_code: Optional[str] = ""


class PreviewExamRequest(BaseModel):
    team_code: TeamCode
    total_count: int = 25
    manual_dist: Optional[dict] = None
    config: Optional[dict] = None


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


@router.get("/users")
def get_users(_: dict = Depends(require_admin)):
    from services.admin_service import fetch_users
    return fetch_users()


@router.delete("/users/{employee_id}")
def delete_user(employee_id: str, _: dict = Depends(require_admin)):
    from services.admin_service import delete_user
    return delete_user(employee_id)


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
        total_count=body.total_count, manual_dist=body.manual_dist
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


@router.get("/exam-sets/{exam_set_id}/results")
def get_exam_set_results(exam_set_id: str, _: dict = Depends(require_admin)):
    from repositories import result_repo
    return {"results": result_repo.list_results_by_set(exam_set_id)}
