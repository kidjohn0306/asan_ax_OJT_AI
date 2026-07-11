import os
import json
from pathlib import Path
from typing import List, Dict, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

BASE_DIR = Path(__file__).resolve().parents[1]
MOCK_DATA_DIR = BASE_DIR / "mock_data"
CREDENTIALS_DIR = BASE_DIR / "credentials"

SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "service_account.json"


class DriveService:
    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        creds = self._get_service_account_creds()
        return build("drive", "v3", credentials=creds)

    def _get_service_account_creds(self) -> service_account.Credentials:
        # Vercel 환경: 환경변수에서 서비스 계정 JSON 로드
        sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if sa_json:
            info = json.loads(sa_json)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

        # 로컬 환경: 파일에서 로드
        if SERVICE_ACCOUNT_FILE.exists():
            return service_account.Credentials.from_service_account_file(
                str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
            )

        raise RuntimeError(
            "Google Drive 인증 정보 없음: "
            "GOOGLE_SERVICE_ACCOUNT_JSON 환경변수 또는 "
            "backend/credentials/service_account.json 파일이 필요합니다."
        )

    def status(self) -> Dict[str, Any]:
        about = self.service.about().get(fields="user").execute()
        return {
            "connected": True,
            "user": about.get("user", {}).get("emailAddress"),
            "message": "Google Drive API connected"
        }

    def list_files(self, folder_id: str, page_size: int = 20) -> List[Dict[str, Any]]:
        query = f"'{folder_id}' in parents and trashed = false"
        files: List[Dict[str, Any]] = []
        page_token = None
        while True:
            result = self.service.files().list(
                q=query,
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                pageToken=page_token,
            ).execute()
            files.extend(result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return files

    def find_child_folder(self, parent_folder_id: str, name: str) -> str | None:
        # Drive query 리터럴 이스케이프 (백슬래시·작은따옴표) — 호출부에서 이미 검증하더라도 방어적으로 처리
        safe_name = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"'{parent_folder_id}' in parents and trashed = false "
            f"and mimeType = 'application/vnd.google-apps.folder' and name = '{safe_name}'"
        )
        result = self.service.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
        files = result.get("files", [])
        return files[0]["id"] if files else None

    def download_bytes(self, file_id: str) -> bytes:
        return self.service.files().get_media(fileId=file_id).execute()

    def download_file(self, file_id: str, local_filename: str) -> Dict[str, Any]:
        MOCK_DATA_DIR.mkdir(parents=True, exist_ok=True)
        local_path = MOCK_DATA_DIR / local_filename

        request = self.service.files().get_media(fileId=file_id)
        with open(local_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return {"downloaded": True, "local_path": str(local_path)}

    def upload_json_result(self, folder_id: str) -> Dict[str, Any]:
        temp_path = BASE_DIR / "drive_test_result.json"
        payload = {
            "type": "GOOGLE_DRIVE_POC",
            "message": "Drive upload test success"
        }
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        file_metadata = {"name": "drive_test_result.json", "parents": [folder_id]}
        media = MediaFileUpload(str(temp_path), mimetype="application/json", resumable=False)

        created = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name",
            supportsAllDrives=True
        ).execute()

        return {"uploaded": True, "file": created}
