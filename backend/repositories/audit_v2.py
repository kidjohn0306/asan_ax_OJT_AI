import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone

from repositories.schema_sheets import column_name, quote_sheet_name
from schema.sheets_v2 import SHEET_HEADERS


def _cell_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


class SheetsAuditV2Repository:
    """audit_logs 탭에 관리자 행동을 append-only로 기록한다. 실패해도 원래 작업을 막지 않도록
    호출 측(record_audit)에서 예외를 흡수한다 — 이 클래스 자체는 오류를 그대로 전파한다."""

    def __init__(self, service=None, spreadsheet_id: str | None = None):
        self._service = service
        self._spreadsheet_id = spreadsheet_id

    @property
    def _svc(self):
        if self._service is None:
            from repositories.sheets_repo import _thread_local_sheets_service
            self._service = _thread_local_sheets_service()
        return self._service

    @property
    def spreadsheet_id(self) -> str:
        if not self._spreadsheet_id:
            from repositories.sheets_repo import _default_sheet_id
            self._spreadsheet_id = _default_sheet_id()
        return self._spreadsheet_id

    def _values(self):
        return self._svc.spreadsheets().values()

    def record_batch(self, rows: list[Mapping]) -> None:
        """여러 감사 로그 행을 한 번의 append 호출로 기록한다.
        Sheets 쓰기 API는 분당 호출 횟수 한도가 있어, 이벤트마다 즉시 기록하는 대신
        QueuedAuditRepository가 모아둔 여러 건을 배치로 내보내 호출 수를 줄인다."""
        if not rows:
            return
        headers = SHEET_HEADERS["audit_logs"]
        values = [[_cell_value(row.get(header, "")) for header in headers] for row in rows]
        end = column_name(len(headers))
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet_name('audit_logs')}!A:{end}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()

    def record(
        self,
        actor_id: str,
        actor_role: str,
        action_type: str,
        target_type: str,
        target_id: str,
        before: Mapping | None = None,
        after: Mapping | None = None,
        reason: str = "",
    ) -> None:
        self.record_batch([{
            "audit_id": "audit-" + uuid.uuid4().hex,
            "actor_id": actor_id or "",
            "actor_role": actor_role or "",
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "before_json": before or {},
            "after_json": after or {},
            "reason": reason or "",
            "request_id": "",
            "ip_address": "",
            "user_agent": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }])

    def list_logs(self, limit: int = 200) -> list[dict]:
        headers = SHEET_HEADERS["audit_logs"]
        end = column_name(len(headers))
        response = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet_name('audit_logs')}!A:{end}",
        ).execute()
        rows = response.get("values", [])[1:]
        records = [
            {header: row[index] if len(row) > index else "" for index, header in enumerate(headers)}
            for row in rows
        ]
        records.sort(key=lambda record: record.get("created_at") or "", reverse=True)
        return records[:limit]


def build_audit_v2_repository(
    enabled: bool,
    service=None,
    spreadsheet_id: str | None = None,
):
    if not enabled:
        return None
    return SheetsAuditV2Repository(service=service, spreadsheet_id=spreadsheet_id)
