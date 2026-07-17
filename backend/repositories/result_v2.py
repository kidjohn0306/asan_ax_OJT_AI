import json
from collections.abc import Mapping

from repositories.schema_sheets import column_name, quote_sheet_name
from schema.sheets_v2 import PRIMARY_KEYS, SHEET_HEADERS
from services.results.dual_write import get_result_write_policy


class ImmutableResultAnswerConflict(RuntimeError):
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


class SheetsResultV2Repository:
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

    def _upsert(self, sheet: str, record: Mapping) -> None:
        self._validate_record(sheet, record)
        headers = SHEET_HEADERS[sheet]
        primary_key = PRIMARY_KEYS[sheet]
        key = str(record[primary_key])
        for row_number, current in enumerate(self._read_records(sheet), start=2):
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

    def find_attempt(self, attempt_id: str) -> dict | None:
        return next((
            record
            for record in self._read_records("exam_attempts")
            if record.get("attempt_id") == attempt_id
        ), None)

    def find_attempt_for_assignment(
        self,
        assignment_id: str,
        employee_id: str,
        statuses: set[str] | None = None,
    ) -> dict | None:
        matches = [
            record
            for record in self._read_records("exam_attempts")
            if record.get("assignment_id") == assignment_id
            and record.get("employee_id") == employee_id
            and (statuses is None or record.get("status") in statuses)
        ]
        if not matches:
            return None

        def row_version(record):
            try:
                return int(record.get("row_version", 0))
            except (TypeError, ValueError):
                return 0

        return max(matches, key=row_version)

    def upsert_attempt(self, record: Mapping) -> None:
        self._upsert("exam_attempts", record)

    def list_result_answers(self, result_id: str) -> list[dict]:
        return [
            record
            for record in self._read_records("result_answers")
            if record.get("result_id") == result_id
        ]

    @staticmethod
    def _same_answer(existing: Mapping, incoming: Mapping) -> bool:
        return all(
            _comparison_value(existing.get(header, ""))
            == _comparison_value(incoming.get(header, ""))
            for header in SHEET_HEADERS["result_answers"]
            if header != "created_at"
        )

    def save_result_answers(self, records: list[Mapping]) -> None:
        if not records:
            return
        for record in records:
            self._validate_record("result_answers", record)
        primary_key = PRIMARY_KEYS["result_answers"]
        existing = {
            str(record.get(primary_key, "")): record
            for record in self._read_records("result_answers")
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
            if not self._same_answer(current, record):
                raise ImmutableResultAnswerConflict(
                    f"immutable conflict for result_answers.{primary_key}={key}"
                )
        self._append_rows("result_answers", pending)


def build_result_v2_repository(
    use_sheets: bool,
    env: Mapping[str, str] | None = None,
    service=None,
    spreadsheet_id: str | None = None,
):
    policy = get_result_write_policy(env)
    if not use_sheets or not policy.result_answers:
        return None
    return SheetsResultV2Repository(
        service=service,
        spreadsheet_id=spreadsheet_id,
    )
