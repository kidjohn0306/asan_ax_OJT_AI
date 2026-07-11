import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from jose import jwt, JWTError
from passlib.context import CryptContext

MOCK_DIR = Path(__file__).parent.parent / "mock_data"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ojt-dev-secret-change-in-prod-2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 480  # 8시간

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 로그아웃된 토큰의 jti 집합. 프로세스 재시작·인스턴스 교체 시 초기화되는 한계는
# 다른 in-memory 상태(_exam_sessions 등)와 동일 — Vercel 콜드스타트 시 재로그인 필요할 수 있음.
_revoked_jtis: set[str] = set()


def _load_users() -> dict:
    with open(MOCK_DIR / "users.json", encoding="utf-8") as f:
        return json.load(f)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    if payload.get("jti") in _revoked_jtis:
        raise HTTPException(status_code=401, detail="로그아웃된 토큰입니다. 다시 로그인해주세요.")
    return payload


def revoke_token(token: str) -> None:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    jti = payload.get("jti")
    if jti:
        _revoked_jtis.add(jti)


def create_access_token(data: dict) -> str:
    payload = {**data, "jti": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(employee_id: str, password: str) -> dict:
    data = _load_users()
    all_users = data["approved_users"] + data["admins"]

    user = next((u for u in all_users if u["employee_id"] == employee_id), None)
    if not user:
        raise HTTPException(status_code=403, detail="승인되지 않은 계정입니다.")
    if not user.get("approved"):
        raise HTTPException(status_code=403, detail="응시 승인이 완료되지 않았습니다.")

    pw_hash = user.get("password_hash", "")
    if pw_hash != "mock_hash":
        if not pwd_context.verify(password, pw_hash):
            raise HTTPException(status_code=403, detail="비밀번호가 올바르지 않습니다.")
    # mock_hash → 개발 모드: 비밀번호 검증 생략

    token = create_access_token({
        "sub": employee_id,
        "name": user["name"],
        "role": user["role"],
        "team": user.get("team"),
    })

    return {
        "token": token,
        "name": user["name"],
        "team": user.get("team"),
        "role": user["role"],
        "approved": user["approved"],
    }
