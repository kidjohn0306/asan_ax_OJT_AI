from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter()
security = HTTPBearer()


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class LoginResponse(BaseModel):
    token: str
    name: str
    team: str | None
    role: str
    approved: bool


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    # 과제 특성상 실제 사내 인사 DB 연동은 불가 — mock_data/users.json 기반으로 동작
    from services.auth_service import authenticate_user
    return authenticate_user(body.employee_id, body.password)


@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    from services.auth_service import revoke_token
    revoke_token(credentials.credentials)
    return {"message": "로그아웃 완료. 클라이언트 데이터를 삭제하세요."}
