import os
import json
from pathlib import Path
from typing import List, Dict, Any

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
        creds = self._get_oauth_creds()
        return build("drive", "v3", credentials=creds)

    def _get_oauth_creds(self) -> Credentials:
        creds = None

        # Vercel 환경: 환경변수에서 토큰 로드
        token_json = os.getenv("GOOGLE_OAUTH_TOKEN")
        if token_json:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        elif OAUTH_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # 만료된 토큰 자동 갱신 (Vercel 포함)
                creds.refresh(Request())
                if not token_json:
                    OAUTH_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            else:
                # 로컬 최초 인증 (브라우저 플로우)
                if not OAUTH_CLIENT_FILE.exists():
                    raise RuntimeError("GOOGLE_OAUTH_TOKEN 환경변수 또는 oauth_client.json 필요")
                flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT_FILE), SCOPES)
                creds = flow.run_local_server(port=0, open_browser=False)
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
