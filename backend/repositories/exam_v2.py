import json
from collections.abc import Mapping

from repositories.schema_sheets import column_name, quote_sheet_name
from schema.sheets_v2 import PRIMARY_KEYS, SHEET_HEADERS
from services.exams.dual_write import get_exam_write_policy


IMMUTABLE_TIME_FIELDS = {
    "exam_versions": frozenset({"confirmed_at", "created_at"}),
    "exam_set_items": frozenset({"created_at"}),
}


class ImmutableExamConflict(RuntimeError):
    pass


def _cell_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return value


def _comparison_value(value) -> str:
    return str(_cell_value(value))


class SheetsExamV2Repository:
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

    def _validate_record(self, sheet: str, record: Mapping) -> None:
        headers = set(SHEET_HEADERS[sheet])
        unknown = set(record) - headers
        if unknown:
            raise ValueError(f"unknown fields for {sheet}: {sorted(unknown)}")
        primary_key = PRIMARY_KEYS[sheet]
        if not str(record.get(primary_key, "")).strip():
            raise ValueError(f"{sheet}.{primary_key} is required")

    def _read_records(self, sheet: str) -> list[dict]:
        headers = SHEET_HEADERS[sheet]
        end = column_name(len(headers))
        response = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet_name(sheet)}!A:{end}",
        ).execute()
        rows = response.get("values", [])
        current_header = tuple(rows[0]) if rows else ()
        if current_header != headers:
            raise RuntimeError(f"{sheet} header does not match canonical schema")
        return [
            {
                header: row[index] if len(row) > index else ""
                for index, header in enumerate(headers)
            }
            for row in rows[1:]
        ]

    def _row(self, sheet: str, record: Mapping) -> list:
        return [
            _cell_value(record.get(header, ""))
            for header in SHEET_HEADERS[sheet]
        ]

    def _append_rows(self, sheet: str, records: list[Mapping]) -> None:
        if not records:
            return
        end = column_name(len(SHEET_HEADERS[sheet]))
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet_name(sheet)}!A:{end}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [self._row(sheet, record) for record in records]},
        ).execute()

    def _same_immutable_record(
        self,
        sheet: str,
        existing: Mapping,
        incoming: Mapping,
    ) -> bool:
        ignored = IMMUTABLE_TIME_FIELDS[sheet]
        return all(
            _comparison_value(existing.get(header, ""))
            == _comparison_value(incoming.get(header, ""))
            for header in SHEET_HEADERS[sheet]
            if header not in ignored
        )

    def _append_immutable(self, sheet: str, records: list[Mapping]) -> None:
        if not records:
            return
        for record in records:
            self._validate_record(sheet, record)
        primary_key = PRIMARY_KEYS[sheet]
        existing = {
            str(record.get(primary_key, "")): record
            for record in self._read_records(sheet)
            if str(record.get(primary_key, "")).strip()
        }
        pending = []
        seen = dict(existing)
        for record in records:
            key = str(record[primary_key])
            current = seen.get(key)
            if current is None:
                pending.append(record)
                seen[key] = dict(record)
                continue
            if not self._same_immutable_record(sheet, current, record):
                raise ImmutableExamConflict(
                    f"immutable conflict for {sheet}.{primary_key}={key}"
                )
        self._append_rows(sheet, pending)

    def _upsert(self, sheet: str, record: Mapping) -> None:
        self._validate_record(sheet, record)
        headers = SHEET_HEADERS[sheet]
        primary_key = PRIMARY_KEYS[sheet]
        key = str(record[primary_key])
        rows = self._read_records(sheet)
        for row_number, current in enumerate(rows, start=2):
            if str(current.get(primary_key, "")) != key:
                continue
            merged = {**current, **dict(record)}
            end = column_name(len(headers))
            self._values().update(
                spreadsheetId=self.spreadsheet_id,
                range=(
                    f"{quote_sheet_name(sheet)}!"
                    f"A{row_number}:{end}{row_number}"
                ),
                valueInputOption="RAW",
                body={"values": [self._row(sheet, merged)]},
            ).execute()
            return
        self._append_rows(sheet, [record])

    def save_frozen_exam(
        self,
        version: Mapping,
        items: list[Mapping],
    ) -> None:
        self._append_immutable("exam_versions", [version])
        self._append_immutable("exam_set_items", items)

    def find_current_version(self, exam_set_id: str) -> dict | None:
        matches = [
            record
            for record in self._read_records("exam_versions")
            if record.get("exam_set_id") == exam_set_id
        ]
        if not matches:
            return None

        def version_number(record):
            try:
                return int(record.get("version_no", 0))
            except (TypeError, ValueError):
                return 0

        return max(matches, key=version_number)

    def find_version(self, exam_version_id: str) -> dict | None:
        return next((
            record
            for record in self._read_records("exam_versions")
            if record.get("exam_version_id") == exam_version_id
        ), None)

    def list_version_items(
        self,
        exam_set_id: str,
        paper_version: int,
    ) -> list[dict]:
        def version_number(record):
            try:
                return int(record.get("paper_version", 0))
            except (TypeError, ValueError):
                return 0

        def order_number(record):
            try:
                return int(record.get("order_no", 0))
            except (TypeError, ValueError):
                return 0

        matches = [
            record
            for record in self._read_records("exam_set_items")
            if record.get("exam_set_id") == exam_set_id
            and version_number(record) == int(paper_version)
        ]
        return sorted(matches, key=order_number)

    def find_assignment(
        self,
        exam_id: str,
        employee_id: str,
    ) -> dict | None:
        return next((
            record
            for record in self._read_records("assignments")
            if record.get("exam_id") == exam_id
            and record.get("employee_id") == employee_id
        ), None)

    def list_active_assignments(self, employee_id: str) -> list[dict]:
        return [
            record
            for record in self._read_records("assignments")
            if record.get("employee_id") == employee_id
            and record.get("status") == "assigned"
        ]

    def upsert_assignment(self, record: Mapping) -> None:
        self._upsert("assignments", record)


def build_exam_v2_repository(
    use_sheets: bool,
    env: Mapping[str, str] | None = None,
    service=None,
    spreadsheet_id: str | None = None,
):
    policy = get_exam_write_policy(env)
    if not use_sheets or not policy.frozen_exams:
        return None
    return SheetsExamV2Repository(
        service=service,
        spreadsheet_id=spreadsheet_id,
    )
