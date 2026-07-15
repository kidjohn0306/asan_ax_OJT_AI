from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=False)


def _require_credentials(creds: HTTPAuthorizationCredentials | None) -> HTTPAuthorizationCredentials:
    if creds is None:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return creds


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    from services.auth_service import decode_token
    creds = _require_credentials(creds)
    payload = decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload


def require_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    from services.auth_service import decode_token
    creds = _require_credentials(creds)
    return decode_token(creds.credentials)
