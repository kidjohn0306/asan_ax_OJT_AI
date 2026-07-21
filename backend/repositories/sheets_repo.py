import os
import json
import logging
import functools
import threading
from datetime import datetime, timezone
from config.storage import should_fallback_to_local
from repositories.base import (
    ExamSetRepository,
    FeedbackRepository,
    ResultConflict,
    ResultRepository,
    SnapshotRepository,
)
from repositories.schema_sheets import column_name
from schema.sheets_v2 import SHEET_HEADERS
from repositories.local_json import (
    LocalExamSetRepository,
    LocalResultRepository,
    LocalSnapshotRepository,
    LocalFeedbackRepository,
    LocalTeamRepository,
    LocalQuestionStatsRepository,
    LocalQuestionRepository,
    LocalMaterialRepository,
    LocalUserRepository,
)


def _fallback_on_error(local_cls):
    """Sheets API 호출 실패(할당량 초과·API 비활성화 등) 시 동일 시그니처의 Local 저장소로 위임."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except ResultConflict:
                raise
            except Exception as exc:
                if not should_fallback_to_local():
                    logging.exception(
                        "%s.%s failed in strict Sheets mode",
                        type(self).__name__,
                        func.__name__,
                    )
                    raise
                logging.warning(f"{type(self).__name__}.{func.__name__} 실패, {local_cls.__name__}로 폴백: {exc}")
                if getattr(self, "_local_fallback", None) is None:
                    self._local_fallback = local_cls()
                return getattr(self._local_fallback, func.__name__)(*args, **kwargs)
        return wrapper
    return decorator


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_TAB = "exam_sets"
HEADERS = list(SHEET_HEADERS["exam_sets"][:11])
# 컬럼 문자 매핑 — 헤더 순서와 반드시 일치해야 한다.
_COLUMNS = {
    header: column_name(index)
    for index, header in enumerate(SHEET_HEADERS["exam_sets"], start=1)
}
# API/Legacy 저장소는 duration_min을 사용하고, canonical Sheet는
# duration_minutes(X열)를 사용한다. 기존 11열 prefix 사이에 새 열을 끼우지 않는다.
_COLUMNS["duration_min"] = _COLUMNS["duration_minutes"]
_EXAM_SET_INDEX = {
    header: index
    for index, header in enumerate(SHEET_HEADERS["exam_sets"])
}

RESULTS_TAB = "results"
RESULTS_HEADERS = list(SHEET_HEADERS["results"][:10])

SNAPSHOTS_SHEET_TAB = "snapshots"
SNAPSHOTS_HEADERS = ["result_id", "created_at", "data_json"]

_HTTP_TIMEOUT_SECONDS = 15

FEEDBACK_TAB = "difficulty_feedback"
FEEDBACK_HEADERS = [
    "question_id", "question_text", "ai_difficulty", "admin_difficulty",
    "reason_code", "auto_confirmed", "recorded_at",
]

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

MATERIAL_CACHE_TAB = "material_cache"
MATERIAL_CACHE_HEADERS = ["category", "files_json", "scanned_at"]

USERS_TAB = "users"
USERS_HEADERS = ["employee_id", "password_hash", "name", "team", "role", "approved", "shift_type", "process_code", "task_code", "is_active", "approved_by", "approved_date", "created_at", "updated_at", "row_version", "department", "employment_status", "last_login_at"]


def _default_sheet_id():
    return (
        os.getenv("GOOGLE_SHEETS_ID")
        or os.getenv("GOOGLE_EXAM_SETS_SHEET_ID")
        or "1bHMEYi5_MxdtxM9Vt1CEpgP28Eu6vJwE_QLZn0USLV0"
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


def _json_object_or_none(value):
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_snapshot_row(row: list) -> tuple[str, str, dict]:
    """Read both canonical B=created_at/C=JSON and legacy swapped rows."""
    result_id = row[0] if row else ""
    second = row[1] if len(row) > 1 else ""
    third = row[2] if len(row) > 2 else ""
    second_json = _json_object_or_none(second)
    third_json = _json_object_or_none(third)
    if third_json is not None:
        return result_id, second, third_json
    if second_json is not None:
        return result_id, third, second_json
    raise ValueError(f"invalid snapshot row for result_id={result_id!r}")


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
        _warn_if_header_mismatch(tab, current_header, headers)
        svc.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


# httplib2.Http (google-api-python-client의 기본 전송 계층)는 스레드 안전하지 않다.
# FastAPI가 동기 라우트를 스레드풀에서 동시 실행하므로, 서비스 클라이언트를 프로세스
# 전체에서 하나만 만들어 공유하면 동시 요청 시 응답이 뒤섞이거나(잘못된 값) 크래시가
# 난다. 스레드마다 하나씩만 만들어 재사용해 이 문제를 피한다.
_thread_local = threading.local()


def _thread_local_sheets_service():
    if not hasattr(_thread_local, "service"):
        _thread_local.service = _build_sheets_service()
    return _thread_local.service


def _warn_if_header_mismatch(tab_name: str, current_header: list, expected_headers: list) -> None:
    """다른 브랜치/버전의 코드가 같은 시트를 다른 컬럼 순서로 쓰면, 위치 기반 파싱이 조용히
    엉뚱한 값을 읽어버린다 (컬럼 개수가 같으면 기존 길이 체크로는 못 잡음 — 실제로 여러 번
    발생한 사고). 내용까지 비교해 다르면 바로 로그에 남겨 원인 파악 시간을 줄인다."""
    if current_header and current_header[:len(expected_headers)] != expected_headers:
        logging.warning(
            f"[{tab_name}] 시트 헤더가 코드 기대값과 다릅니다 — 다른 코드가 같은 시트를 "
            f"다른 스키마로 쓰고 있을 수 있습니다. 기대: {expected_headers} / 실제: {current_header}"
        )


class SheetsExamSetRepository(ExamSetRepository):
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False
        self._sheet_id = None

    @property
    def _svc(self):
        return _thread_local_sheets_service()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _values(self):
        return self._svc.spreadsheets().values()

    def _ensure_tab(self):
        """exam_sets 탭이 없으면 생성하고 헤더를 추가한다."""
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}

        if SHEET_TAB not in existing:
            resp = self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": SHEET_TAB}}}]},
            ).execute()
            self._sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]
        else:
            self._sheet_id = existing[SHEET_TAB]

        # 헤더 확인 — 없으면 새로 쓰고, 이전 스키마(컬럼 수 부족)면 최신 컬럼까지 확장해 갱신한다.
        # 기존 값과 정확히 일치할 때만 안 건드리는 방식(!=)은 스키마가 계속 진화하는 동안
        # 서로 다른 코드가 번갈아 덮어써 헤더가 왔다갔다하는 문제가 있어, 컬럼 수가 부족할 때만 확장한다.
        last_col = chr(ord("A") + len(HEADERS) - 1)
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A1:{last_col}1",
        ).execute()
        current_header = res.get("values", [[]])[0] if res.get("values") else []
        _warn_if_header_mismatch(SHEET_TAB, current_header, HEADERS)
        if len(current_header) < len(HEADERS):
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
            range=f"{SHEET_TAB}!A:AH",
        ).execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        def _field(name): return _get(_EXAM_SET_INDEX[name])
        def _int_field(name, default):
            try:
                return int(_field(name)) if _field(name) != "" else default
            except (TypeError, ValueError):
                return default
        def _json_dict(name):
            value = _field(name)
            if isinstance(value, dict):
                return value
            try:
                parsed = json.loads(value or "{}")
            except (TypeError, json.JSONDecodeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        try:
            pass_score = int(_get(7)) if _get(7) else 70
        except ValueError:
            pass_score = 70
        duration_min = _int_field("duration_minutes", 60)
        return {
            "exam_set_id": _get(0),
            "name": _get(1),
            "team_code": _get(2),
            "question_ids": _safe_json_list(_get(3)),
            "assigned_users": _safe_json_list(_get(4)),
            "created_at": _get(5),
            "exam_datetime": _get(6),
            "pass_score": pass_score,
            # 예전 스키마로 만들어진 세트는 status 컬럼이 없어 빈 문자열로 읽히는데, 그걸 그대로
            # "미확정"으로 두면 배정 조회(_find_assigned_exam_set)에서 영원히 걸러지므로 active로 간주한다.
            "status": _get(8) or "active",
            "created_by": _get(9),
            "exam_id": _get(10),
            "evaluation_type": _field("evaluation_type") or "official",
            "blueprint_json": _json_dict("blueprint_json"),
            "frozen_at": _field("frozen_at"),
            "frozen_by": _field("frozen_by"),
            "paper_version": _int_field("paper_version", 0),
            "snapshot_checksum": _field("snapshot_checksum"),
            "row_version": _int_field("row_version", 0),
            "confirmed_by": _field("confirmed_by"),
            "confirmed_at": _field("confirmed_at"),
            "current_exam_version_id": _field("current_exam_version_id"),
            "idempotency_key": _field("idempotency_key"),
            "duration_min": duration_min,
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
            str(data.get("pass_score", 70)),
            data.get("status", "active"),
            data.get("created_by", ""),
            data.get("exam_id", ""),
            str(data.get("duration_min", 60)),
        ]

    def _find_sheet_row(self, exam_id: str) -> int:
        """1-based 행 번호 반환 (헤더=1, 첫 데이터=2). 없으면 -1. exam_id(회차 PK, K열)로 찾는다."""
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!K:K",
        ).execute()
        for i, row in enumerate(res.get("values", []), start=1):
            if row and row[0] == exam_id:
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
    def get_exam(self, exam_id: str) -> dict | None:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["exam_id"] == exam_id:
                return d
        return None

    @_fallback_on_error(LocalExamSetRepository)
    def create_exam_set(self, data: dict) -> dict:
        self._maybe_ensure_tab()
        data.setdefault("assigned_users", [])
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("exam_datetime", "")
        data.setdefault("pass_score", 70)
        data.setdefault("duration_min", 60)
        data.setdefault("question_ids", [])
        data.setdefault("status", "active")
        data.setdefault("created_by", "")
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_TAB}!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(data)]},
        ).execute()
        return data

    @_fallback_on_error(LocalExamSetRepository)
    def assign_user(self, exam_id: str, employee_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_id)
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
    def unassign_user(self, exam_id: str, employee_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_id)
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

    def update_exam_set(self, exam_id: str, fields: dict) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_id)
        if row_idx == -1:
            return False
        updates = []
        for key, value in fields.items():
            col = _COLUMNS.get(key)
            if not col:
                continue
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            elif isinstance(value, bool):
                value = "TRUE" if value else "FALSE"
            updates.append({"range": f"{SHEET_TAB}!{col}{row_idx}", "values": [[value]]})
        if not updates:
            return True
        self._values().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()
        return True

    @_fallback_on_error(LocalExamSetRepository)
    def delete_exam_set(self, exam_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_sheet_row(exam_id)
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


class SheetsResultRepository(ResultRepository):
    """Google Sheets 'results' 탭 기반 ResultRepository.

    한 행 = 한 응시 결과. difficulty_summary·results 등 중첩 구조는 JSON 컬럼으로,
    나머지는 조회·필터링이 쉽도록 고정 컬럼으로 저장한다.
    """

    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

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
            range=f"{RESULTS_TAB}!A:Z",
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
        try:
            grading_summary = json.loads(_get(16)) if _get(16) else {}
        except (json.JSONDecodeError, ValueError):
            grading_summary = {}

        def _int(index, default=0):
            try:
                return int(_get(index)) if _get(index) != "" else default
            except (TypeError, ValueError):
                return default

        def _float(index, default=0.0):
            try:
                return float(_get(index)) if _get(index) != "" else default
            except (TypeError, ValueError):
                return default

        return {
            "result_id": _get(0),
            "exam_id": _get(1),
            "employee_id": _get(2),
            "name": _get(3),
            "score": int(_get(4)) if _get(4) else 0,
            "pass": _get(5) == "TRUE",
            "team_code": _get(6),
            "submitted_at": _get(7),
            "difficulty_summary": difficulty_summary,
            "results": results,
            "assignment_id": _get(10),
            "attempt_no": _int(11),
            "started_at": _get(12),
            "total_questions": _int(13),
            "correct_count": _int(14),
            "response_time_total_seconds": _float(15),
            "grading_summary_json": grading_summary,
            "schema_version": _int(17),
            "row_version": _int(18),
            "exam_version_id": _get(19),
            "attempt_id": _get(20),
            "grading_status": _get(21),
            "submission_status": _get(22),
            "error_code": _get(23),
            "reeducation_required": _get(24) in ("TRUE", "True", True),
            "retest_assignment_id": _get(25),
        }

    @staticmethod
    def _dict_to_row(data: dict) -> list:
        return [
            data.get("result_id", ""),
            data.get("exam_id", ""),
            data.get("employee_id", ""),
            data.get("name", ""),
            str(data.get("score", 0)),
            "TRUE" if data.get("pass") else "FALSE",
            data.get("team_code", ""),
            data.get("submitted_at", ""),
            json.dumps(data.get("difficulty_summary", {}), ensure_ascii=False),
            json.dumps(data.get("results", []), ensure_ascii=False),
            data.get("assignment_id", ""),
            str(data.get("attempt_no", 0)),
            data.get("started_at", ""),
            str(data.get("total_questions", 0)),
            str(data.get("correct_count", 0)),
            str(float(data.get("response_time_total_seconds", 0) or 0)),
            json.dumps(
                data.get("grading_summary_json", {}),
                ensure_ascii=False,
                sort_keys=True,
            ),
            str(data.get("schema_version", 0)),
            str(data.get("row_version", 0)),
            data.get("exam_version_id", ""),
            data.get("attempt_id", ""),
            data.get("grading_status", ""),
            data.get("submission_status", ""),
            data.get("error_code", ""),
            "TRUE" if data.get("reeducation_required") else "FALSE",
            data.get("retest_assignment_id", ""),
        ]

    @_fallback_on_error(LocalResultRepository)
    def append_result(self, result: dict) -> None:
        self._maybe_ensure_tab()
        result.setdefault("submitted_at", datetime.now(timezone.utc).isoformat())
        result_id = str(result.get("result_id", "")).strip()
        if not result_id:
            raise ValueError("result_id is required")
        incoming_row = self._dict_to_row(result)
        existing_rows = self._read_all_rows()
        for row_number, row in enumerate(existing_rows, start=2):
            if not row or str(row[0]) != result_id:
                continue
            existing_row = self._dict_to_row(self._row_to_dict(row))
            if existing_row != incoming_row:
                raise ResultConflict(
                    f"immutable result conflict for result_id={result_id}"
                )
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{RESULTS_TAB}!A{row_number}:Z{row_number}",
                valueInputOption="RAW",
                body={"values": [incoming_row]},
            ).execute()
            return
        # .append()의 자동 테이블 인식은 A:Z 범위에 헤더보다 적은 컬럼만 채워진 행이
        # 섞여 있으면 엉뚱한 열(예: Y열)부터 삽입하는 경우가 있어, 다음 빈 행 번호를
        # 직접 계산해 update()로 명시적 위치에 쓴다.
        next_row = len(existing_rows) + 2
        self._values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{RESULTS_TAB}!A{next_row}:Z{next_row}",
            valueInputOption="RAW",
            body={"values": [incoming_row]},
        ).execute()

    @_fallback_on_error(LocalResultRepository)
    def get_result(self, result_id: str) -> dict | None:
        for row in self._read_all_rows():
            if row and row[0] == result_id:
                return self._row_to_dict(row)
        return None

    @_fallback_on_error(LocalResultRepository)
    def get_all_results(self) -> dict:
        results = {}
        for row in self._read_all_rows():
            d = self._row_to_dict(row)
            if d["result_id"]:
                results[d["result_id"]] = d
        return results

    @_fallback_on_error(LocalResultRepository)
    def count(self) -> int:
        return len(self._read_all_rows())

    @_fallback_on_error(LocalResultRepository)
    def list_results_by_exam(self, exam_id: str) -> list:
        return [
            self._row_to_dict(row) for row in self._read_all_rows()
            if len(row) > 1 and row[1] == exam_id
        ]


class SheetsSnapshotRepository(SnapshotRepository):
    """Google Sheets 'snapshots' 탭 기반 SnapshotRepository.

    시험 생성 시 문제·정답을 스냅샷으로 저장해 서버리스 콜드스타트에도 채점 정보가 유지되게 한다.
    """

    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            _ensure_tab(self._svc, self._spreadsheet_id, SNAPSHOTS_SHEET_TAB, SNAPSHOTS_HEADERS)
            self._tab_ready = True

    def _values(self):
        return self._svc.spreadsheets().values()

    @_fallback_on_error(LocalSnapshotRepository)
    def save_snapshot(self, result_id: str, snapshot: dict) -> None:
        self._maybe_ensure_tab()
        row = [result_id, datetime.now(timezone.utc).isoformat(), json.dumps(snapshot, ensure_ascii=False)]
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SNAPSHOTS_SHEET_TAB}!A:C",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    @_fallback_on_error(LocalSnapshotRepository)
    def get_snapshot(self, result_id: str) -> dict | None:
        self._maybe_ensure_tab()
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SNAPSHOTS_SHEET_TAB}!A:C",
        ).execute()
        rows = res.get("values", [])
        for row in rows[1:]:
            if row and row[0] == result_id:
                _, _, snapshot = _parse_snapshot_row(row)
                return snapshot
        return None


class SheetsFeedbackRepository(FeedbackRepository):
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

    def _values(self):
        return self._svc.spreadsheets().values()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    def _ensure_tab(self):
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if FEEDBACK_TAB not in existing:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": FEEDBACK_TAB}}}]},
            ).execute()
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{FEEDBACK_TAB}!A1:G1",
        ).execute()
        if not res.get("values"):
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{FEEDBACK_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [FEEDBACK_HEADERS]},
            ).execute()

    @_fallback_on_error(LocalFeedbackRepository)
    def append_feedback(self, record: dict) -> None:
        self._maybe_ensure_tab()
        record = dict(record)
        record.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{FEEDBACK_TAB}!A:G",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [[
                record.get("question_id", ""),
                record.get("question_text", ""),
                record.get("ai_difficulty", ""),
                record.get("admin_difficulty", ""),
                record.get("reason_code", ""),
                str(bool(record.get("auto_confirmed", False))),
                record["recorded_at"],
            ]]},
        ).execute()

    @_fallback_on_error(LocalFeedbackRepository)
    def list_recent_feedback(self, limit: int = 20) -> list:
        self._maybe_ensure_tab()
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{FEEDBACK_TAB}!A:G",
        ).execute()
        rows = res.get("values", [])[1:]  # 헤더 제외

        def _get(row, i):
            return row[i] if len(row) > i else ""

        records = [
            {
                "question_id": _get(row, 0),
                "question_text": _get(row, 1),
                "ai_difficulty": _get(row, 2),
                "admin_difficulty": _get(row, 3),
                "reason_code": _get(row, 4),
                "auto_confirmed": _get(row, 5) == "True",
                "recorded_at": _get(row, 6),
            }
            for row in rows if row
        ]
        return list(reversed(records[-limit:]))


class SheetsTeamRepository:
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False
        self._sheet_id = None

    @property
    def _svc(self):
        return _thread_local_sheets_service()

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
        current_header = res.get("values", [[]])[0] if res.get("values") else []
        _warn_if_header_mismatch(TEAMS_TAB, current_header, TEAMS_HEADERS)
        if not current_header:
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
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

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
        current_header = res.get("values", [[]])[0] if res.get("values") else []
        _warn_if_header_mismatch(STATS_TAB, current_header, STATS_HEADERS)
        if not current_header:
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
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

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
        current_header = res.get("values", [[]])[0] if res.get("values") else []
        _warn_if_header_mismatch(QUESTIONS_TAB, current_header, QUESTIONS_HEADERS)
        if not current_header:
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


class SheetsMaterialRepository:
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

    def _values(self):
        return self._svc.spreadsheets().values()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    def _ensure_tab(self):
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if MATERIAL_CACHE_TAB not in existing:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": MATERIAL_CACHE_TAB}}}]},
            ).execute()
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{MATERIAL_CACHE_TAB}!A1:C1").execute()
        current_header = res.get("values", [[]])[0] if res.get("values") else []
        _warn_if_header_mismatch(MATERIAL_CACHE_TAB, current_header, MATERIAL_CACHE_HEADERS)
        if not current_header:
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{MATERIAL_CACHE_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [MATERIAL_CACHE_HEADERS]},
            ).execute()

    def _find_row_index(self, category: str) -> int:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{MATERIAL_CACHE_TAB}!A:A").execute()
        rows = res.get("values", [])
        for i, row in enumerate(rows[1:], start=2):
            if row and row[0] == category:
                return i
        return -1

    @staticmethod
    def _row_to_manifest(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        try:
            files = json.loads(_get(1)) if _get(1) else []
        except json.JSONDecodeError:
            files = []
        return {
            "category": _get(0),
            "files": files,
            "scanned_at": _get(2),
        }

    @staticmethod
    def _manifest_to_row(category: str, manifest: dict) -> list:
        return [
            category,
            json.dumps(manifest.get("files", []), ensure_ascii=False),
            manifest.get("scanned_at", ""),
        ]

    @_fallback_on_error(LocalMaterialRepository)
    def get_manifest(self, category: str) -> dict | None:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(category)
        if row_idx == -1:
            return None
        res = self._values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{MATERIAL_CACHE_TAB}!A{row_idx}:C{row_idx}",
        ).execute()
        rows = res.get("values", [])
        if not rows:
            return None
        return self._row_to_manifest(rows[0])

    @_fallback_on_error(LocalMaterialRepository)
    def save_manifest(self, category: str, manifest: dict) -> None:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(category)
        row = self._manifest_to_row(category, manifest)
        if row_idx == -1:
            self._values().append(
                spreadsheetId=self._spreadsheet_id,
                range=f"{MATERIAL_CACHE_TAB}!A:C",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
        else:
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{MATERIAL_CACHE_TAB}!A{row_idx}:C{row_idx}",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()


class SheetsUserRepository:
    def __init__(self):
        self._spreadsheet_id = _default_sheet_id()
        self._tab_ready = False

    @property
    def _svc(self):
        return _thread_local_sheets_service()

    def _values(self):
        return self._svc.spreadsheets().values()

    def _maybe_ensure_tab(self):
        if not self._tab_ready:
            self._ensure_tab()
            self._tab_ready = True

    def _ensure_tab(self):
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if USERS_TAB not in existing:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": USERS_TAB}}}]},
            ).execute()
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{USERS_TAB}!A1:R1").execute()
        current_header = res.get("values", [[]])[0] if res.get("values") else []
        _warn_if_header_mismatch(USERS_TAB, current_header, USERS_HEADERS)
        if not current_header:
            self._values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{USERS_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [USERS_HEADERS]},
            ).execute()

    def _read_all_rows(self) -> list:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{USERS_TAB}!A:R").execute()
        rows = res.get("values", [])
        return rows[1:] if len(rows) > 1 else []

    @staticmethod
    def _row_to_dict(row: list) -> dict:
        def _get(i): return row[i] if len(row) > i else ""
        return {
            "employee_id": _get(0),
            "password_hash": _get(1),
            "name": _get(2),
            "team": _get(3),
            "role": _get(4) or "examinee",
            "approved": _get(5) in ("TRUE", "True", True),
            "shift_type": _get(6),
            "process_code": _get(7),
            "task_code": _get(8),
            "is_active": _get(9) in ("TRUE", "True", True),
            "approved_by": _get(10),
            "approved_date": _get(11),
            "created_at": _get(12),
            "updated_at": _get(13),
            "row_version": _get(14),
            "department": _get(15),
            "employment_status": _get(16),
            "last_login_at": _get(17),
        }

    @staticmethod
    def _dict_to_row(data: dict) -> list:
        return [
            data.get("employee_id", ""),
            data.get("password_hash", ""),
            data.get("name", ""),
            data.get("team", ""),
            data.get("role", "examinee"),
            "TRUE" if data.get("approved") else "FALSE",
            data.get("shift_type", ""),
            data.get("process_code", ""),
            data.get("task_code", ""),
            "TRUE" if data.get("is_active") else "FALSE",
            data.get("approved_by", ""),
            data.get("approved_date", ""),
            data.get("created_at", ""),
            data.get("updated_at", ""),
            data.get("row_version", ""),
            data.get("department", ""),
            data.get("employment_status", ""),
            data.get("last_login_at", ""),
        ]

    def _find_row_index(self, employee_id: str) -> int:
        res = self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{USERS_TAB}!A:A").execute()
        for i, row in enumerate(res.get("values", []), start=1):
            if row and row[0] == employee_id:
                return i
        return -1

    @_fallback_on_error(LocalUserRepository)
    def list_users(self) -> list:
        self._maybe_ensure_tab()
        return [self._row_to_dict(r) for r in self._read_all_rows() if r and r[0]]

    @_fallback_on_error(LocalUserRepository)
    def find_user(self, employee_id: str) -> dict | None:
        self._maybe_ensure_tab()
        for row in self._read_all_rows():
            if row and row[0] == employee_id:
                return self._row_to_dict(row)
        return None

    @_fallback_on_error(LocalUserRepository)
    def add_user(self, user: dict) -> None:
        self._maybe_ensure_tab()
        self._values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{USERS_TAB}!A:R",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._dict_to_row(user)]},
        ).execute()

    @_fallback_on_error(LocalUserRepository)
    def delete_user(self, employee_id: str) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(employee_id)
        if row_idx == -1:
            return False
        meta = self._svc.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        sheet_id = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == USERS_TAB)
        self._svc.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId": sheet_id, "dimension": "ROWS",
                "startIndex": row_idx - 1, "endIndex": row_idx,
            }}}]},
        ).execute()
        return True

    @_fallback_on_error(LocalUserRepository)
    def update_user(self, employee_id: str, fields: dict) -> bool:
        self._maybe_ensure_tab()
        row_idx = self._find_row_index(employee_id)
        if row_idx == -1:
            return False
        user = self.find_user(employee_id)
        user.update(fields)
        self._values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{USERS_TAB}!A{row_idx}:G{row_idx}",
            valueInputOption="RAW",
            body={"values": [self._dict_to_row(user)]},
        ).execute()
        return True
