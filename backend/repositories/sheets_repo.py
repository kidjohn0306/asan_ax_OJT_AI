import os
import json
from datetime import datetime, timezone
from repositories.base import ExamSetRepository

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_TAB = "exam_sets"
HEADERS = ["exam_set_id", "name", "team_code", "assigned_users", "created_at"]


def _build_sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from pathlib import Path

    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        key_file = Path(__file__).parent.parent / "credentials" / "service_account.json"
        creds = service_account.Credentials.from_service_account_file(str(key_file), scopes=SCOPES)

    return build("sheets", "v4", credentials=creds)


class SheetsExamSetRepository(ExamSetRepository):
    def __init__(self):
        self._spreadsheet_id = os.getenv(
            "GOOGLE_EXAM_SETS_SHEET_ID",
            "1l-79bi-ZctkIN3NNrKuQuyDJ8hJjEyOmTWPfoDsZl8E",
        )
        self._svc = _build_sheets_service()
        self._ensure_tab()

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _values(self):
        return self._svc.spreadsheets().values()

    def _ensure_tab(self):
        """exam_sets 탭이 없으면 생성하고 헤더를 추가한다."""
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]

        if SHEET_TAB not in existing:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": SHEET_TAB}}}]},
            ).execute()

        # 헤더 확인
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A1:E1",
        ).execute()
        if not res.get("values"):
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{SHEET_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS]},
            ).execute()

    def _read_all_rows(self) -> list[list]:
        """헤더를 제외한 데이터 행 반환 (raw list)."""
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A:E",
        ).execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        return {
            "exam_set_id": _get(0),
            "name": _get(1),
            "team_code": _get(2),
            "assigned_users": json.loads(_get(3)) if _get(3) else [],
            "created_at": _get(4),
        }

    @staticmethod
    def _dict_to_row(data: dict) -> list:
        return [
            data.get("exam_set_id", ""),
            data.get("name", ""),
            data.get("team_code", ""),
            json.dumps(data.get("assigned_users", []), ensure_ascii=False),
            data.get("created_at", ""),
        ]

    def _find_sheet_row(self, exam_set_id: str) -> int:
        """1-based 행 번호 반환 (헤더=1, 첫 데이터=2). 없으면 -1."""
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A:A",
        ).execute()
        for i, row in enumerate(res.get("values", []), start=1):
            if row and row[0] == exam_set_id:
                return i
        return -1

    def _update_assigned_users(self, sheet_row: int, assigned: list):
        self._values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!D{sheet_row}",
            valueInputOption="RAW",
            body={"values": [[json.dumps(assigned, ensure_ascii=False)]]},
        ).execute()

    # ── 공개 인터페이스 ──────────────────────────────────────────────────────

    def list_exam_sets(self) -> list:
        return [self._row_to_dict(r) for r in self._read_all_rows()]

    def get_exam_set(self, exam_set_id: str) -> dict | None:
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["exam_set_id"] == exam_set_id:
                return d
        return None

    def create_exam_set(self, data: dict) -> dict:
        data.setdefault("assigned_users", [])
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A:E",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(data)]},
        ).execute()
        return data

    def assign_user(self, exam_set_id: str, employee_id: str) -> bool:
        row_idx = self._find_sheet_row(exam_set_id)
        if row_idx == -1:
            return False
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!D{row_idx}",
        ).execute()
        cell = res.get("values", [[""]])[0]
        assigned = json.loads(cell[0]) if cell and cell[0] else []
        if employee_id not in assigned:
            assigned.append(employee_id)
            self._update_assigned_users(row_idx, assigned)
        return True

    def unassign_user(self, exam_set_id: str, employee_id: str) -> bool:
        row_idx = self._find_sheet_row(exam_set_id)
        if row_idx == -1:
            return False
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!D{row_idx}",
        ).execute()
        cell = res.get("values", [[""]])[0]
        assigned = json.loads(cell[0]) if cell and cell[0] else []
        if employee_id in assigned:
            assigned.remove(employee_id)
            self._update_assigned_users(row_idx, assigned)
        return True
