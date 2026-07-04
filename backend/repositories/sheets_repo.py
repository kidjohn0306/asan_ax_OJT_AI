import os
import json
from datetime import datetime, timezone
from repositories.base import ExamSetRepository, ResultRepository, SnapshotRepository

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_TAB = "exam_sets"
HEADERS = ["exam_set_id", "name", "team_code", "question_ids", "assigned_users", "created_at", "exam_datetime"]
# 컬럼 문자 매핑 — 헤더 순서와 반드시 일치해야 한다.
_COLUMNS = {h: chr(ord("A") + i) for i, h in enumerate(HEADERS)}

RESULTS_SHEET_TAB = "results"
RESULTS_HEADERS = ["exam_id", "employee_id", "exam_set_id", "team_code", "score", "submitted_at", "data_json"]

SNAPSHOTS_SHEET_TAB = "snapshots"
SNAPSHOTS_HEADERS = ["exam_id", "created_at", "data_json"]

_HTTP_TIMEOUT_SECONDS = 15


def _default_sheet_id():
    return (
        os.getenv("GOOGLE_SHEETS_ID")
        or os.getenv("GOOGLE_EXAM_SETS_SHEET_ID")
        or "1l-79bi-ZctkIN3NNrKuQuyDJ8hJjEyOmTWPfoDsZl8E"
    )


def _build_sheets_service():
    import httplib2
    from google.oauth2 import service_account
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build
    from pathlib import Path

    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        key_file = Path(__file__).parent.parent / "credentials" / "service_account.json"
        creds = service_account.Credentials.from_service_account_file(str(key_file), scopes=SCOPES)

    # 기본값은 무제한 대기 — 네트워크가 끊기면 요청이 영원히 걸려 서버 스레드풀을 고갈시킨다.
    authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=_HTTP_TIMEOUT_SECONDS))
    return build("sheets", "v4", http=authed_http)


def _safe_json_list(s) -> list:
    if not s:
        return []
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return []


def _ensure_tab(svc, spreadsheet_id: str, tab: str, headers: list[str]) -> None:
    """탭이 없으면 생성하고 헤더가 없으면 추가한다."""
    meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if tab not in existing:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()

    last_col = chr(ord("A") + len(headers) - 1)
    res = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{tab}!A1:{last_col}1",
    ).execute()
    current_header = res.get("values", [[]])[0] if res.get("values") else []
    if current_header != headers:
        svc.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


class SheetsExamSetRepository(ExamSetRepository):
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _values(self):
        return self._svc.spreadsheets().values()

    def _ensure_tab(self):
        _ensure_tab(self._svc, self._spreadsheet_id, SHEET_TAB, HEADERS)

    def _read_all_rows(self) -> list[list]:
        """헤더를 제외한 데이터 행 반환 (raw list)."""
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A:G",
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
            "question_ids": _safe_json_list(_get(3)),
            "assigned_users": _safe_json_list(_get(4)),
            "created_at": _get(5),
            "exam_datetime": _get(6),
        }

    @staticmethod
    def _dict_to_row(data: dict) -> list:
        return [
            data.get("exam_set_id", ""),
            data.get("name", ""),
            data.get("team_code", ""),
            json.dumps(data.get("question_ids", []), ensure_ascii=False),
            json.dumps(data.get("assigned_users", []), ensure_ascii=False),
            data.get("created_at", ""),
            data.get("exam_datetime", ""),
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
            range=f"{SHEET_TAB}!E{sheet_row}",
            valueInputOption="RAW",
            body={"values": [[json.dumps(assigned, ensure_ascii=False)]]},
        ).execute()

    # ── 공개 인터페이스 ──────────────────────────────────────────────────────

    def list_exam_sets(self) -> list:
        self._maybe_ensure_tab()
        return [self._row_to_dict(r) for r in self._read_all_rows()]

    def get_exam_set(self, exam_set_id: str) -> dict | None:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["exam_set_id"] == exam_set_id:
                return d
        return None

    def create_exam_set(self, data: dict) -> dict:
        self._maybe_ensure_tab()
        data.setdefault("assigned_users", [])
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("exam_datetime", "")
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A:G",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(data)]},
        ).execute()
        return data

    def assign_user(self, exam_set_id: str, employee_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_set_id)
        if row_idx == -1:
            return False
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!E{row_idx}",
        ).execute()
        cell = res.get("values", [[""]])[0]
        assigned = _safe_json_list(cell[0] if cell else "")
        if employee_id not in assigned:
            assigned.append(employee_id)
            self._update_assigned_users(row_idx, assigned)
        return True

    def unassign_user(self, exam_set_id: str, employee_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_set_id)
        if row_idx == -1:
            return False
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!E{row_idx}",
        ).execute()
        cell = res.get("values", [[""]])[0]
        assigned = _safe_json_list(cell[0] if cell else "")
        if employee_id in assigned:
            assigned.remove(employee_id)
            self._update_assigned_users(row_idx, assigned)
        return True

    def update_exam_set(self, exam_set_id: str, fields: dict) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_set_id)
        if row_idx == -1:
            return False
        updates = []
        for key, value in fields.items():
            col = _COLUMNS.get(key)
            if not col:
                continue
            updates.append({"range": f"{SHEET_TAB}!{col}{row_idx}", "values": [[value]]})
        if not updates:
            return True
        self._values().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()
        return True


class SheetsResultRepository(ResultRepository):
    """Google Sheets 'results' 탭 기반 ResultRepository.

    한 행 = 한 응시 결과. 조회 키(exam_id·employee_id·exam_set_id 등)는 별도 열로,
    전체 결과는 data_json 열에 JSON으로 저장해 스키마 변경에 유연하게 대응한다.
    (score_and_save()가 만드는 result_data는 difficulty_summary·results 등 중첩 구조를
    포함하므로, 고정 컬럼이 아닌 JSON 컬럼으로 저장해야 값 손실이 없다.)
    """

    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            _ensure_tab(self._svc, self._spreadsheet_id, RESULTS_SHEET_TAB, RESULTS_HEADERS)
            self._tab_ready = True

    def _values(self):
        return self._svc.spreadsheets().values()

    def _read_all_rows(self) -> list[list]:
        self._maybe_ensure_tab()
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{RESULTS_SHEET_TAB}!A:G",
        ).execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_result(row: list) -> dict:
        data_json = row[6] if len(row) > 6 else ""
        return json.loads(data_json) if data_json else {}

    def append_result(self, result: dict) -> None:
        self._maybe_ensure_tab()
        result.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        row = [
            result.get("exam_id", ""),
            result.get("employee_id", ""),
            result.get("exam_set_id", ""),
            result.get("team_code", ""),
            result.get("score", ""),
            result.get("submitted_at", ""),
            json.dumps(result, ensure_ascii=False),
        ]
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{RESULTS_SHEET_TAB}!A:G",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    def get_result(self, exam_id: str) -> dict | None:
        for row in self._read_all_rows():
            if row and row[0] == exam_id:
                return self._row_to_result(row)
        return None

    def get_all_results(self) -> dict:
        results = {}
        for row in self._read_all_rows():
            r = self._row_to_result(row)
            key = r.get("exam_id") or (row[0] if row else "")
            if key:
                results[key] = r
        return results

    def count(self) -> int:
        return len(self._read_all_rows())

    def list_results_by_set(self, exam_set_id: str) -> list:
        return [
            self._row_to_result(row) for row in self._read_all_rows()
            if len(row) > 2 and row[2] == exam_set_id
        ]


class SheetsSnapshotRepository(SnapshotRepository):
    """Google Sheets 'snapshots' 탭 기반 SnapshotRepository.

    시험 생성 시 문제·정답을 스냅샷으로 저장해 서버리스 콜드스타트에도 채점 정보가 유지되게 한다.
    """

    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            _ensure_tab(self._svc, self._spreadsheet_id, SNAPSHOTS_SHEET_TAB, SNAPSHOTS_HEADERS)
            self._tab_ready = True

    def _values(self):
        return self._svc.spreadsheets().values()

    def save_snapshot(self, exam_id: str, snapshot: dict) -> None:
        self._maybe_ensure_tab()
        row = [exam_id, datetime.now(timezone.utc).isoformat(), json.dumps(snapshot, ensure_ascii=False)]
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SNAPSHOTS_SHEET_TAB}!A:C",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    def get_snapshot(self, exam_id: str) -> dict | None:
        self._maybe_ensure_tab()
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SNAPSHOTS_SHEET_TAB}!A:C",
        ).execute()
        rows = res.get("values", [])
        for row in rows[1:]:
            if row and row[0] == exam_id:
                data_json = row[2] if len(row) > 2 else ""
                return json.loads(data_json) if data_json else None
        return None
