from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Literal, Optional

router = APIRouter()
security = HTTPBearer()

DifficultyLevel = Literal["상", "중", "하"]
TeamCode = Literal["T1", "T2", "T3"]


class DifficultyPatchRequest(BaseModel):
    question_id: str
    new_difficulty: DifficultyLevel


class PreviewExamRequest(BaseModel):
    team_code: TeamCode
    config: Optional[dict] = None  # { "난이도분포": {"상": 7, "중": 10, "하": 8} }


class ApproveUserRequest(BaseModel):
    employee_id: str
    name: str
    team: TeamCode
    exam_date: str  # "YYYY-MM-DD"


@router.get("/logs")
def get_logs(team: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """응시 이력 조회 — 팀/날짜 필터 지원"""
    from services.admin_service import fetch_logs
    return fetch_logs(team, date_from, date_to)


@router.get("/questions")
def get_questions(team: Optional[str] = None, category: Optional[str] = None):
    """문제은행 조회 및 난이도 확인"""
    from services.admin_service import fetch_questions
    return fetch_questions(team, category)


@router.patch("/difficulty")
def update_difficulty(body: DifficultyPatchRequest):
    """관리자 난이도 재조정 → AI 즉시 재학습 트리거"""
    from services.admin_service import override_difficulty
    return override_difficulty(body.question_id, body.new_difficulty)


@router.post("/preview-exam")
def preview_exam(body: PreviewExamRequest):
    """문제지 미리보기 — 마음에 안 들면 재생성 가능"""
    from services.exam_service import generate_exam_questions
    return generate_exam_questions(body.team_code, preview=True, config=body.config)


@router.post("/approve-user")
def approve_user(body: ApproveUserRequest):
    """신입사원 승인 목록 추가"""
    from services.admin_service import approve_new_user
    return approve_new_user(body.employee_id, body.name, body.team, body.exam_date)
