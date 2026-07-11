import os
import json
import logging
import functools
from datetime import datetime, timezone
from repositories.base import ExamSetRepository, ResultRepository, SnapshotRepository
from repositories.local_json import (
    LocalExamSetRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalTeamRepository,
    LocalQuestionStatsRepository,
    LocalQuestionRepository,
)


def _fallback_on_error(local_cls):
    """Sheets API 호출 실패(할당량 초과·API 비활성화 등) 시 동일 시그니처의 Local 저장소로 위임."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                logging.warning(f"{type(self).__name__}.{func.__name__} 실패, {local_cls.__name__}로 폴백: {exc}")
                if getattr(self, "_local_fallback", None) is None:
                    self._local_fallback = local_cls()
                return getattr(self._local_fallback, func.__name__)(*args, **kwargs)
        return wrapper
    return decorator


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_TAB = "exam_sets"
HEADERS = ["exam_set_id", "name", "team_code", "question_ids", "assigned_users", "created_at", "exam_datetime"]
# 컬럼 문자 매핑 — 헤더 순서와 반드시 일치해야 한다.
_COLUMNS = {h: chr(ord("A") + i) for i, h in enumerate(HEADERS)}

RESULTS_TAB = "results"
RESULTS_HEADERS = [
    "exam_id", "exam_set_id", "employee_id", "name", "score",
    "pass", "team_code", "submitted_at", "difficulty_summary", "results",
]

SNAPSHOTS_SHEET_TAB = "snapshots"
SNAPSHOTS_HEADERS = ["exam_id", "created_at", "data_json"]

_HTTP_TIMEOUT_SECONDS = 15

TEAMS_TAB = "teams"
TEAMS_HEADERS = ["team_id", "team_name", "team_code", "created_at", "updated_at"]
DEFAULT_TEAMS = [
    {"team_id": "default-t1", "team_name": "1팀", "team_code": "T1", "created_at": "", "updated_at": ""},
    {"team_id": "default-t2", "team_name": "2팀", "team_code": "T2", "created_at": "", "updated_at": ""},
    {"team_id": "default-t3", "team_name": "3팀", "team_code": "T3", "created_at": "", "updated_at": ""},
]

STATS_TAB = "question_stats"
STATS_HEADERS = ["question_id", "exam_count", "last_used_at", "flagged_frequent"]
FREQUENT_THRESHOLD = 5

QUESTIONS_TAB = "question_bank"
QUESTIONS_HEADERS = [
    "pool_key", "question_id", "category", "question",
    "option_a", "option_b", "option_c", "option_d", "answer",
    "difficulty_init", "difficulty_ai", "admin_override", "status", "version",
    "explanation", "flags", "gate_errors", "reject_reason",
]


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

    @_fallback_on_error(LocalExamSetRepository)
    def list_exam_sets(self) -> list:
        self._maybe_ensure_tab()
        return [self._row_to_dict(r) for r in self._read_all_rows()]

    @_fallback_on_error(LocalExamSetRepository)
    def get_exam_set(self, exam_set_id: str) -> dict | None:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["exam_set_id"] == exam_set_id:
                return d
        return None

    @_fallback_on_error(LocalExamSetRepository)
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

    @_fallback_on_error(LocalExamSetRepository)
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

    @_fallback_on_error(LocalExamSetRepository)
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

    한 행 = 한 응시 결과. difficulty_summary·results 등 중첩 구조는 JSON 컬럼으로,
    나머지는 조회·필터링이 쉽도록 고정 컬럼으로 저장한다.
    """

    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            _ensure_tab(self._svc, self._spreadsheet_id, RESULTS_TAB, RESULTS_HEADERS)
            self._tab_ready = True

    def _values(self):
        return self._svc.spreadsheets().values()

    def _read_all_rows(self) -> list[list]:
        self._maybe_ensure_tab()
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{RESULTS_TAB}!A:J",
        ).execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        try:
            difficulty_summary = json.loads(_get(8)) if _get(8) else {}
        except (json.JSONDecodeError, ValueError):
            difficulty_summary = {}
        try:
            results = json.loads(_get(9)) if _get(9) else []
        except (json.JSONDecodeError, ValueError):
            results = []
        return {
            "exam_id": _get(0),
            "exam_set_id": _get(1),
            "employee_id": _get(2),
            "name": _get(3),
            "score": int(_get(4)) if _get(4) else 0,
            "pass": _get(5) == "TRUE",
            "team_code": _get(6),
            "submitted_at": _get(7),
            "difficulty_summary": difficulty_summary,
            "results": results,
        }

    @staticmethod
    def _dict_to_row(data: dict) -> list:
        return [
            data.get("exam_id", ""),
            data.get("exam_set_id", ""),
            data.get("employee_id", ""),
            data.get("name", ""),
            str(data.get("score", 0)),
            "TRUE" if data.get("pass") else "FALSE",
            data.get("team_code", ""),
            data.get("submitted_at", ""),
            json.dumps(data.get("difficulty_summary", {}), ensure_ascii=False),
            json.dumps(data.get("results", []), ensure_ascii=False),
        ]

    @_fallback_on_error(LocalResultRepository)
    def append_result(self, result: dict) -> None:
        self._maybe_ensure_tab()
        result.setdefault("submitted_at", datetime.now(timezone.utc).isoformat())
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{RESULTS_TAB}!A:J",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(result)]},
        ).execute()

    @_fallback_on_error(LocalResultRepository)
    def get_result(self, exam_id: str) -> dict | None:
        for row in self._read_all_rows():
            if row and row[0] == exam_id:
                return self._row_to_dict(row)
        return None

    @_fallback_on_error(LocalResultRepository)
    def get_all_results(self) -> dict:
        results = {}
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["exam_id"]:
                results[d["exam_id"]] = d
        return results

    @_fallback_on_error(LocalResultRepository)
    def count(self) -> int:
        return len(self._read_all_rows())

    @_fallback_on_error(LocalResultRepository)
    def list_results_by_set(self, exam_set_id: str) -> list:
        return [
            self._row_to_dict(row) for row in self._read_all_rows()
            if len(row) > 1 and row[1] == exam_set_id
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

    @_fallback_on_error(LocalSnapshotRepository)
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

    @_fallback_on_error(LocalSnapshotRepository)
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


class SheetsTeamRepository:
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False
        self._sheet_id = None

    def _values(self):
        return self._svc.spreadsheets().values()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    def _ensure_tab(self):
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}
        if TEAMS_TAB not in existing:
            resp = self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": TEAMS_TAB}}}]},
            ).execute()
            self._sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
        else:
            self._sheet_id = existing[TEAMS_TAB]
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{TEAMS_TAB}!A1:E1").execute()
        if not res.get("values"):
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{TEAMS_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [TEAMS_HEADERS]},
            ).execute()

    def _read_all_rows(self) -> list:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{TEAMS_TAB}!A:E").execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        return {
            "team_id": _get(0),
            "team_name": _get(1),
            "team_code": _get(2),
            "created_at": _get(3),
            "updated_at": _get(4),
        }

    @staticmethod
    def _dict_to_row(data: dict) -> list:
        return [
            data.get("team_id", ""),
            data.get("team_name", ""),
            data.get("team_code", ""),
            data.get("created_at", ""),
            data.get("updated_at", ""),
        ]

    def _find_row_index(self, team_id: str) -> int:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{TEAMS_TAB}!A:A").execute()
        for i, row in enumerate(res.get("values", []), start=1):
            if row and row[0] == team_id:
                return i
        return -1

    @_fallback_on_error(LocalTeamRepository)
    def list_teams(self) -> list:
        self._maybe_ensure_tab()
        teams = [self._row_to_dict(r) for r in self._read_all_rows() if r and r[0]]
        return teams if teams else list(DEFAULT_TEAMS)

    @_fallback_on_error(LocalTeamRepository)
    def get_team(self, team_id: str) -> dict | None:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["team_id"] == team_id:
                return d
        return None

    @_fallback_on_error(LocalTeamRepository)
    def create_team(self, data: dict) -> dict:
        self._maybe_ensure_tab()
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("updated_at", data["created_at"])
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{TEAMS_TAB}!A:E",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(data)]},
        ).execute()
        return data

    @_fallback_on_error(LocalTeamRepository)
    def update_team(self, team_id: str, fields: dict) -> dict | None:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(team_id)
        if row_idx == -1:
            return None
        team = self.get_team(team_id)
        team.update({k: v for k, v in fields.items() if k != "team_code"})
        team["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{TEAMS_TAB}!A{row_idx}:E{row_idx}",
            valueInputOption="RAW",
            body={"values": [self._dict_to_row(team)]},
        ).execute()
        return team

    @_fallback_on_error(LocalTeamRepository)
    def delete_team(self, team_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(team_id)
        if row_idx == -1:
            return False
        self._svc.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId": self._sheet_id,
                "dimension": "ROWS",
                "startIndex": row_idx - 1,
                "endIndex": row_idx,
            }}}]},
        ).execute()
        return True


class SheetsQuestionStatsRepository:
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False

    def _values(self):
        return self._svc.spreadsheets().values()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    def _ensure_tab(self):
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if STATS_TAB not in existing:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": STATS_TAB}}}]},
            ).execute()
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{STATS_TAB}!A1:D1").execute()
        if not res.get("values"):
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{STATS_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [STATS_HEADERS]},
            ).execute()

    def _read_all_rows(self) -> list:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{STATS_TAB}!A:D").execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        try:
            count = int(_get(1)) if _get(1) else 0
        except ValueError:
            count = 0
        return {
            "question_id": _get(0),
            "exam_count": count,
            "last_used_at": _get(2),
            "flagged_frequent": _get(3) == "TRUE",
        }

    @_fallback_on_error(LocalQuestionStatsRepository)
    def get_stats(self, question_id: str) -> dict | None:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            if row and row[0] == question_id:
                return self._row_to_dict(row)
        return None

    @_fallback_on_error(LocalQuestionStatsRepository)
    def list_all_stats(self) -> dict:
        self._maybe_ensure_tab()
        return {d["question_id"]: d for d in (self._row_to_dict(r) for r in self._read_all_rows()) if d["question_id"]}

    @_fallback_on_error(LocalQuestionStatsRepository)
    def list_flagged(self) -> list:
        self._maybe_ensure_tab()
        return [d for d in (self._row_to_dict(r) for r in self._read_all_rows()) if d["flagged_frequent"]]

    @_fallback_on_error(LocalQuestionStatsRepository)
    def increment_batch(self, question_ids: list) -> None:
        if not question_ids:
            return
        self._maybe_ensure_tab()
        ids = list(set(question_ids))
        now = datetime.now(timezone.utc).isoformat()
        all_rows = self._read_all_rows()
        existing = {}
        for i, row in enumerate(all_rows, start=2):
            if row and row[0]:
                try:
                    count = int(row[1]) if len(row) > 1 and row[1] else 0
                except ValueError:
                    count = 0
                existing[row[0]] = (i, count)
        update_data, new_rows = [], []
        for qid in ids:
            if qid in existing:
                row_idx, old_count = existing[qid]
                new_count = old_count + 1
                flagged = "TRUE" if new_count >= FREQUENT_THRESHOLD else "FALSE"
                update_data.append({
                    "range": f"{STATS_TAB}!A{row_idx}:D{row_idx}",
                    "values": [[qid, str(new_count), now, flagged]],
                })
            else:
                new_rows.append([qid, "1", now, "FALSE"])
        if update_data:
            self._values().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"valueInputOption": "RAW", "data": update_data},
            ).execute()
        if new_rows:
            self._values().append(
                spreadsheetId=self._spreadsheet_id,
                range=f"{STATS_TAB}!A:D",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": new_rows},
            ).execute()


class SheetsQuestionRepository:
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._svc = _build_sheets_service()
        self._tab_ready = False

    def _values(self):
        return self._svc.spreadsheets().values()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    def _ensure_tab(self):
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if QUESTIONS_TAB not in existing:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": QUESTIONS_TAB}}}]},
            ).execute()
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{QUESTIONS_TAB}!A1:R1").execute()
        if not res.get("values"):
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{QUESTIONS_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [QUESTIONS_HEADERS]},
            ).execute()

    def _read_all_rows(self) -> list:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{QUESTIONS_TAB}!A:R").execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        try:
            flags = json.loads(_get(15)) if _get(15) else {}
        except (json.JSONDecodeError, ValueError):
            flags = {}
        try:
            gate_errors = json.loads(_get(16)) if _get(16) else []
        except (json.JSONDecodeError, ValueError):
            gate_errors = []
        return {
            "pool_key": _get(0),
            "question_id": _get(1),
            "category": _get(2),
            "question": _get(3),
            "option_a": _get(4),
            "option_b": _get(5),
            "option_c": _get(6),
            "option_d": _get(7),
            "answer": _get(8),
            "difficulty_init": _get(9),
            "difficulty_ai": _get(10),
            "admin_override": _get(11),
            "status": _get(12),
            "version": int(_get(13)) if _get(13) else 1,
            "explanation": _get(14),
            "flags": flags,
            "gate_errors": gate_errors,
            "reject_reason": _get(17),
        }

    @staticmethod
    def _dict_to_row(pool_key: str, data: dict) -> list:
        return [
            pool_key,
            data.get("question_id", ""),
            data.get("category", ""),
            data.get("question", ""),
            data.get("option_a", ""),
            data.get("option_b", ""),
            data.get("option_c", ""),
            data.get("option_d", ""),
            data.get("answer", ""),
            data.get("difficulty_init", ""),
            data.get("difficulty_ai", ""),
            data.get("admin_override", ""),
            data.get("status", ""),
            str(data.get("version", 1)),
            data.get("explanation", ""),
            json.dumps(data.get("flags", {}), ensure_ascii=False),
            json.dumps(data.get("gate_errors", []), ensure_ascii=False),
            data.get("reject_reason", ""),
        ]

    def _find_row_index(self, question_id: str) -> int:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{QUESTIONS_TAB}!B:B").execute()
        for i, row in enumerate(res.get("values", []), start=1):
            if row and row[0] == question_id:
                return i
        return -1

    _CONTENT_FIELDS = {"question", "option_a", "option_b", "option_c", "option_d", "answer", "explanation"}

    @_fallback_on_error(LocalQuestionRepository)
    def get_all_questions(self) -> dict:
        self._maybe_ensure_tab()
        result: dict = {}
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            pool_key = d.pop("pool_key")
            if not pool_key:
                continue
            result.setdefault(pool_key, []).append(d)
        return result

    @_fallback_on_error(LocalQuestionRepository)
    def get_approved_questions(self, team_key: str = None, category: str = None) -> list:
        data = self.get_all_questions()
        if team_key:
            pools = [data.get(team_key, []), data.get("common", []),
                     data.get("safety", []), data.get("general", [])]
            flat = [q for pool in pools for q in pool]
        else:
            flat = [q for pool in data.values() for q in pool]
        flat = [q for q in flat if q.get("status") == "approved"]
        if category:
            flat = [q for q in flat if q.get("category") == category]
        return flat

    @_fallback_on_error(LocalQuestionRepository)
    def list_by_status(self, status: str) -> list:
        data = self.get_all_questions()
        return [q for pool in data.values() for q in pool if q.get("status") == status]

    @_fallback_on_error(LocalQuestionRepository)
    def get_question(self, question_id: str) -> dict:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["question_id"] == question_id:
                d.pop("pool_key", None)
                return d
        return None

    @_fallback_on_error(LocalQuestionRepository)
    def add_question(self, pool_key: str, question: dict) -> None:
        self._maybe_ensure_tab()
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{QUESTIONS_TAB}!A:R",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(pool_key, question)]},
        ).execute()

    @_fallback_on_error(LocalQuestionRepository)
    def update_question(self, question_id: str, fields: dict) -> None:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(question_id)
        if row_idx == -1:
            return
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{QUESTIONS_TAB}!A{row_idx}:R{row_idx}",
        ).execute()
        rows = res.get("values", [])
        if not rows:
            return
        current = self._row_to_dict(rows[0])
        pool_key = current.pop("pool_key")
        current.update(fields)
        if any(k in self._CONTENT_FIELDS for k in fields):
            current["version"] = current.get("version", 1) + 1
        self._values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{QUESTIONS_TAB}!A{row_idx}:R{row_idx}",
            valueInputOption="RAW",
            body={"values": [self._dict_to_row(pool_key, current)]},
        ).execute()

    @_fallback_on_error(LocalQuestionRepository)
    def count_by_status(self, status: str) -> int:
        return len(self.list_by_status(status))
