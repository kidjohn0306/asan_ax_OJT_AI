import json
from collections.abc import Mapping

from repositories.schema_sheets import column_name, quote_sheet_name
from schema.sheets_v2 import PRIMARY_KEYS, SHEET_HEADERS
from services.generation.dual_write import get_generation_write_policy


def _cell_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return value


class SheetsGenerationV2Repository:
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

    def _read_table(self, sheet: str) -> list[list]:
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
        return [list(row) for row in rows[1:]]

    def _row(self, sheet: str, record: Mapping) -> list:
        return [_cell_value(record.get(header, "")) for header in SHEET_HEADERS[sheet]]

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

    def _append_new(self, sheet: str, records: list[Mapping]) -> None:
        if not records:
            return
        for record in records:
            self._validate_record(sheet, record)
        headers = SHEET_HEADERS[sheet]
        primary_key = PRIMARY_KEYS[sheet]
        key_index = headers.index(primary_key)
        existing_rows = self._read_table(sheet)
        existing = {
            str(row[key_index])
            for row in existing_rows
            if len(row) > key_index and str(row[key_index]).strip()
        }
        pending = []
        seen = set(existing)
        for record in records:
            key = str(record[primary_key])
            if key in seen:
                continue
            pending.append(record)
            seen.add(key)
        self._append_rows(sheet, pending)

    def _upsert(self, sheet: str, record: Mapping) -> None:
        self._validate_record(sheet, record)
        headers = SHEET_HEADERS[sheet]
        primary_key = PRIMARY_KEYS[sheet]
        key_index = headers.index(primary_key)
        rows = self._read_table(sheet)
        key = str(record[primary_key])
        for row_number, row in enumerate(rows, start=2):
            current_key = str(row[key_index]) if len(row) > key_index else ""
            if current_key != key:
                continue
            current = {
                header: row[index] if len(row) > index else ""
                for index, header in enumerate(headers)
            }
            current.update(record)
            end = column_name(len(headers))
            self._values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{quote_sheet_name(sheet)}!A{row_number}:{end}{row_number}",
                valueInputOption="RAW",
                body={"values": [self._row(sheet, current)]},
            ).execute()
            return
        self._append_rows(sheet, [record])

    def create_job(self, job: Mapping) -> None:
        self._upsert("generation_jobs", job)

    def update_job(self, job_id: str, fields: Mapping) -> None:
        self._upsert(
            "generation_jobs",
            {"generation_job_id": job_id, **dict(fields)},
        )

    def list_jobs(self) -> list[dict]:
        headers = SHEET_HEADERS["generation_jobs"]
        rows = [
            {header: row[index] if len(row) > index else "" for index, header in enumerate(headers)}
            for row in self._read_table("generation_jobs")
        ]
        rows.sort(key=lambda row: row.get("started_at") or "", reverse=True)
        return rows

    def save_candidates(self, rows: list[Mapping]) -> None:
        self._append_new("question_candidates", rows)

    def update_candidate(self, candidate_id: str, fields: Mapping) -> None:
        self._upsert(
            "question_candidates",
            {"candidate_id": candidate_id, **dict(fields)},
        )

    def save_gate_results(self, rows: list[Mapping]) -> None:
        self._append_new("gate_results", rows)

    def record_review(self, review: Mapping, history: Mapping) -> None:
        self._append_new("question_reviews", [review])
        self._append_new("question_history", [history])

    def find_candidate_by_question_id(self, question_id: str) -> dict | None:
        headers = SHEET_HEADERS["question_candidates"]
        for row in self._read_table("question_candidates"):
            record = {
                header: row[index] if len(row) > index else ""
                for index, header in enumerate(headers)
            }
            if record.get("approved_question_id") == question_id:
                return record
            try:
                payload = json.loads(record.get("payload_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                payload = {}
            if payload.get("question_id") == question_id:
                return record
        return None


def build_generation_v2_repository(
    use_sheets: bool,
    env: Mapping[str, str] | None = None,
    service=None,
    spreadsheet_id: str | None = None,
):
    policy = get_generation_write_policy(env)
    if not use_sheets or not policy.candidates:
        return None
    return SheetsGenerationV2Repository(
        service=service,
        spreadsheet_id=spreadsheet_id,
    )
