from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
security = HTTPBearer()
_optional_bearer = HTTPBearer(auto_error=False)

# 팀 관리 기능으로 T1/T2/T3 외 임의의 team_code를 생성할 수 있으므로 Literal로 제한하지 않는다.
# (admin.py의 TeamCode = str 와 동일하게 맞춤 — 새로 만든 팀 소속 사용자는 이 값이 그대로 넘어온다)
TeamCode = str


class GenerateRequest(BaseModel):
    team_code: TeamCode
    employee_id: Optional[str] = ""


class SubmitRequest(BaseModel):
    exam_id: str
    answers: dict[str, str]          # { "C-001": "A", "T1-001": "C", ... }
    response_times: dict[str, float]  # { "C-001": 12.5, ... }  단위: 초
    employee_id: Optional[str] = ""
    name: Optional[str] = ""


@router.get("/assigned-name")
def assigned_exam_name(employee_id: str = ""):
    """
    로그인 직후 응시자에게 배정된 시험명 조회 (시험 생성 없이 이름만 확인)
    """
    from services.exam_service import get_assigned_exam_name
    return {"name": get_assigned_exam_name(employee_id)}


@router.post("/generate")
def generate_exam(body: GenerateRequest):
    """
    팀코드 입력 → 25문항 자동 출제
    구성: 공통5 + 팀별10 + 환경안전5 + 일반상식5
    난이도 배분: 상7 : 중10 : 하8
    USE_MOCK_DATA=true 이면 mock_data/questions.json 사용
    """
    from services.exam_service import generate_exam_questions
    return generate_exam_questions(body.team_code, employee_id=body.employee_id)


@router.post("/submit")
def submit_exam(body: SubmitRequest, creds: HTTPAuthorizationCredentials = Depends(_optional_bearer)):
    """
    답안 + 응답시간 → 자동 채점 → Google Drive 결과로그 저장
    관리자 계정으로 제출 시 채점은 하되 결과 저장 생략
    """
    skip_save = False
    if creds:
        try:
            from services.auth_service import decode_token
            payload = decode_token(creds.credentials)
            skip_save = payload.get("role") == "admin"
        except Exception:
            skip_save = False
    from services.exam_service import score_and_save
    return score_and_save(body.exam_id, body.answers, body.response_times, body.employee_id, body.name, skip_save=skip_save)


@router.get("/result/{exam_id}")
def get_result(exam_id: str):
    from services.exam_service import get_exam_result
    return get_exam_result(exam_id)
