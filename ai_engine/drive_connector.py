"""
C팀 담당: Google Drive Service Account 연동 모듈
USE_MOCK_DATA=true 이면 로컬 mock_data 파일 사용
"""
import os
import json
from pathlib import Path

USE_MOCK = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
MOCK_DIR = Path(__file__).parent.parent / "backend" / "mock_data"

FOLDER_MAP = {
    "common":  os.getenv("GDRIVE_COMMON_FOLDER_ID", ""),
    "team1":   os.getenv("GDRIVE_TEAM1_FOLDER_ID", ""),
    "team2":   os.getenv("GDRIVE_TEAM2_FOLDER_ID", ""),
    "team3":   os.getenv("GDRIVE_TEAM3_FOLDER_ID", ""),
    "safety":  os.getenv("GDRIVE_SAFETY_FOLDER_ID", ""),
    "general": os.getenv("GDRIVE_GENERAL_FOLDER_ID", ""),
    "result":  os.getenv("GDRIVE_RESULT_LOG_FOLDER_ID", ""),
}


def get_drive_service():
    """Google Drive API 클라이언트 반환 (Service Account 인증)"""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./service_account.json")
    creds = service_account.Credentials.from_service_account_file(
        sa_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def read_question_file(category: str) -> list[dict]:
    """문제은행 폴더에서 Excel 파일 읽어 dict 리스트 반환"""
    if USE_MOCK:
        with open(MOCK_DIR / "questions.json", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(category, [])

    # TODO: Drive에서 xlsx 다운로드 → openpyxl로 파싱
    service = get_drive_service()
    folder_id = FOLDER_MAP.get(category)
    if not folder_id:
        return []

    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'",
        fields="files(id, name)",
    ).execute()

    # TODO: 파일 다운로드 + 파싱
    return []


def write_result_log(result: dict) -> bool:
    """채점 결과를 Drive 결과로그 시트에 기록"""
    if USE_MOCK:
        print(f"[MOCK] Drive 저장 건너뜀: {result.get('exam_id')}")
        return True

    # TODO: Drive Sheets API로 결과로그에 행 추가
    return True
