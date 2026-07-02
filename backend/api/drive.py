from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from services.drive_service import DriveService

router = APIRouter()
_bearer = HTTPBearer()


def require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    from services.auth_service import decode_token
    payload = decode_token(creds.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return payload


class DownloadRequest(BaseModel):
    file_id: str
    local_filename: str


class FolderRequest(BaseModel):
    folder_id: str


@router.get("/status")
def drive_status(_: dict = Depends(require_admin)):
    try:
        return DriveService().status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
def list_drive_files(folder_id: str, _: dict = Depends(require_admin)):
    try:
        return {"folder_id": folder_id, "files": DriveService().list_files(folder_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download")
def download_drive_file(payload: DownloadRequest, _: dict = Depends(require_admin)):
    try:
        return DriveService().download_file(file_id=payload.file_id, local_filename=payload.local_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-test-result")
def upload_test_result(payload: FolderRequest, _: dict = Depends(require_admin)):
    try:
        return DriveService().upload_json_result(folder_id=payload.folder_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
