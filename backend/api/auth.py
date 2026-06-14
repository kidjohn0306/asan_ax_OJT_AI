from fastapi import APIRouter, HTTPException, Depends
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
    # TODO: 실제 사내 인사 DB 연동
    # 현재는 mock_data/users.json 기반으로 동작
    from services.auth_service import authenticate_user
    return authenticate_user(body.employee_id, body.password)


@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # TODO: 서버 세션 무효화 + 클라이언트에 캐시 삭제 지시
    return {"message": "로그아웃 완료. 클라이언트 데이터를 삭제하세요."}
