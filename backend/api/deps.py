from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer()


def require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    from services.auth_service import decode_token
    payload = decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload
