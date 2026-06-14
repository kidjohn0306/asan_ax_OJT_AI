from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Literal

router = APIRouter()
security = HTTPBearer()

TeamCode = Literal["T1", "T2", "T3"]


class GenerateRequest(BaseModel):
    team_code: TeamCode


class SubmitRequest(BaseModel):
    exam_id: str
    answers: dict[str, str]          # { "C-001": "A", "T1-001": "C", ... }
    response_times: dict[str, float]  # { "C-001": 12.5, ... }  단위: 초


@router.post("/generate")
def generate_exam(body: GenerateRequest):
    """
    팀코드 입력 → 25문항 자동 출제
    구성: 공통5 + 팀별10 + 환경안전5 + 일반상식5
    난이도 배분: 상7 : 중10 : 하8
    USE_MOCK_DATA=true 이면 mock_data/questions.json 사용
    """
    from services.exam_service import generate_exam_questions
    return generate_exam_questions(body.team_code)


@router.post("/submit")
def submit_exam(body: SubmitRequest):
    """
    답안 + 응답시간 → 자동 채점 → Google Drive 결과로그 저장
    USE_MOCK_DATA=true 이면 Drive 저장 건너뜀
    """
    from services.exam_service import score_and_save
    return score_and_save(body.exam_id, body.answers, body.response_times)


@router.get("/result/{exam_id}")
def get_result(exam_id: str):
    from services.exam_service import get_exam_result
    return get_exam_result(exam_id)
