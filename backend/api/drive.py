from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import require_admin
from services.drive_service import DriveService

router = APIRouter()


class DownloadRequest(BaseModel):
    file_id: str
    local_filename: str


class FolderRequest(BaseModel):
    folder_id: str


@router.get("/status")
def drive_status(_: dict = Depends(require_admin)):
    try:
        return DriveService().status()
    except Exception:
        raise HTTPException(status_code=500, detail="Drive 상태 확인에 실패했습니다.")


@router.get("/files")
def list_drive_files(folder_id: str, _: dict = Depends(require_admin)):
    try:
        return {"folder_id": folder_id, "files": DriveService().list_files(folder_id)}
    except Exception:
        raise HTTPException(status_code=500, detail="Drive 파일 목록 조회에 실패했습니다.")


@router.post("/download")
def download_drive_file(payload: DownloadRequest, _: dict = Depends(require_admin)):
    try:
        return DriveService().download_file(file_id=payload.file_id, local_filename=payload.local_filename)
    except Exception:
        raise HTTPException(status_code=500, detail="Drive 파일 다운로드에 실패했습니다.")


@router.post("/upload-test-result")
def upload_test_result(payload: FolderRequest, _: dict = Depends(require_admin)):
    try:
        return DriveService().upload_json_result(folder_id=payload.folder_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Drive 업로드에 실패했습니다.")
