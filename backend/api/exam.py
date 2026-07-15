from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import require_auth

router = APIRouter()

# 팀 관리 기능으로 T1/T2/T3 외 임의의 team_code를 생성할 수 있으므로 Literal로 제한하지 않는다.
# (admin.py의 TeamCode = str 와 동일하게 맞춤 — 새로 만든 팀 소속 사용자는 이 값이 그대로 넘어온다)
TeamCode = str


class GenerateRequest(BaseModel):
    team_code: TeamCode


class SubmitRequest(BaseModel):
    result_id: str
    answers: dict[str, str]          # { "C-001": "A", "T1-001": "C", ... }
    response_times: dict[str, float]  # { "C-001": 12.5, ... }  단위: 초


@router.get("/assigned-name")
def assigned_exam_name(auth: dict = Depends(require_auth)):
    """
    로그인 직후 응시자에게 배정된 시험명 조회 (시험 생성 없이 이름만 확인)
    """
    from services.exam_service import get_assigned_exam_name
    return {"name": get_assigned_exam_name(auth["sub"])}


@router.post("/generate")
def generate_exam(body: GenerateRequest, auth: dict = Depends(require_auth)):
    """
    팀코드 입력 → 25문항 자동 출제
    구성: 공통5 + 팀별10 + 환경안전5 + 일반상식5
    난이도 배분: 상7 : 중10 : 하8
    USE_MOCK_DATA=true 이면 mock_data/questions.json 사용
    """
    from services.exam_service import generate_exam_questions
    return generate_exam_questions(body.team_code, employee_id=auth["sub"])


@router.post("/submit")
def submit_exam(body: SubmitRequest, auth: dict = Depends(require_auth)):
    """
    답안 + 응답시간 → 자동 채점 → Google Drive 결과로그 저장
    관리자 계정으로 제출 시 채점은 하되 결과 저장 생략
    """
    skip_save = auth.get("role") == "admin"
    from services.exam_service import score_and_save
    return score_and_save(body.result_id, body.answers, body.response_times, auth["sub"], auth.get("name", ""), skip_save=skip_save)


@router.get("/result/{result_id}")
def get_result(result_id: str, auth: dict = Depends(require_auth)):
    from services.exam_service import get_exam_result
    result = get_exam_result(result_id)
    if auth.get("role") != "admin" and result.get("employee_id") != auth.get("sub"):
        raise HTTPException(status_code=403, detail="본인 응시 결과만 조회할 수 있습니다.")
    return result
