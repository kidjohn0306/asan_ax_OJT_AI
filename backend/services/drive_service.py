import os
import json
from pathlib import Path
from typing import List, Dict, Any

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

BASE_DIR = Path(__file__).resolve().parents[1]
MOCK_DATA_DIR = BASE_DIR / "mock_data"
CREDENTIALS_DIR = BASE_DIR / "credentials"

SCOPES = ["https://www.googleapis.com/auth/drive"]
OAUTH_CLIENT_FILE = CREDENTIALS_DIR / "oauth_client.json"
OAUTH_TOKEN_FILE = CREDENTIALS_DIR / "oauth_token.json"


class DriveService:
    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        # OAuth 클라이언트 파일이 있으면 OAuth 사용, 없으면 서비스 계정 폴백
        if OAUTH_CLIENT_FILE.exists():
            creds = self._get_oauth_creds()
        else:
            sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(CREDENTIALS_DIR / "service_account.json"))
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)

    def _get_oauth_creds(self) -> Credentials:
        creds = None
        if OAUTH_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
            OAUTH_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def status(self) -> Dict[str, Any]:
        about = self.service.about().get(fields="user").execute()
        return {
            "connected": True,
            "user": about.get("user", {}).get("emailAddress"),
            "message": "Google Drive API connected"
        }

    def list_files(self, folder_id: str, page_size: int = 20) -> List[Dict[str, Any]]:
        query = f"'{folder_id}' in parents and trashed = false"
        result = self.service.files().list(
            q=query,
            pageSize=page_size,
            fields="files(id, name, mimeType, modifiedTime, size)"
        ).execute()
        return result.get("files", [])

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
