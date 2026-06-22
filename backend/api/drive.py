from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.drive_service import DriveService

router = APIRouter()


class DownloadRequest(BaseModel):
    file_id: str
    local_filename: str


class FolderRequest(BaseModel):
    folder_id: str


@router.get("/status")
def drive_status():
    try:
        return DriveService().status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
def list_drive_files(folder_id: str):
    try:
        return {"folder_id": folder_id, "files": DriveService().list_files(folder_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download")
def download_drive_file(payload: DownloadRequest):
    try:
        return DriveService().download_file(file_id=payload.file_id, local_filename=payload.local_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-test-result")
def upload_test_result(payload: FolderRequest):
    try:
        return DriveService().upload_json_result(folder_id=payload.folder_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
