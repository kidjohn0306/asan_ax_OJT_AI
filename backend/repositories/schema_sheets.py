"""Fail-closed Google Sheets adapter for schema inspection and migration."""

from schema.sheets_v2 import PRIMARY_KEYS, SHEET_HEADERS


def column_name(index: int) -> str:
    """Convert a one-based column index to Google Sheets A1 notation."""
    if index < 1:
        raise ValueError("column index must be positive")
    value = index
    letters = []
    while value:
        value, remainder = divmod(value - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def quote_sheet_name(sheet: str) -> str:
    return "'" + sheet.replace("'", "''") + "'"


class SchemaSheetsInspector:
    def __init__(self, service, spreadsheet_id: str):
        if not spreadsheet_id:
            raise ValueError("spreadsheet_id is required")
        self._service = service
        self._spreadsheet_id = spreadsheet_id

    def read_headers(self) -> dict[str, list[str]]:
        spreadsheets = self._service.spreadsheets()
        metadata = spreadsheets.get(
            spreadsheetId=self._spreadsheet_id,
            fields="sheets.properties.title",
        ).execute()
        titles = [
            sheet.get("properties", {}).get("title", "")
            for sheet in metadata.get("sheets", [])
        ]
        titles = [title for title in titles if title]
        if not titles:
            return {}

        ranges = [f"{quote_sheet_name(title)}!1:1" for title in titles]
        response = spreadsheets.values().batchGet(
            spreadsheetId=self._spreadsheet_id,
            ranges=ranges,
            majorDimension="ROWS",
        ).execute()
        value_ranges = response.get("valueRanges", [])

        headers: dict[str, list[str]] = {}
        for index, title in enumerate(titles):
            value_range = value_ranges[index] if index < len(value_ranges) else {}
            rows = value_range.get("values", [])
            headers[title] = list(rows[0]) if rows else []
        return headers

    def read_primary_key_rows(
        self,
        existing_sheets,
    ) -> dict[str, list[list[object]]]:
        sheets = [
            sheet
            for sheet in existing_sheets
            if sheet in PRIMARY_KEYS and sheet in SHEET_HEADERS
        ]
        if not sheets:
            return {}
        ranges = [
            (
                f"{quote_sheet_name(sheet)}!A2:"
                f"{column_name(len(SHEET_HEADERS[sheet]))}"
            )
            for sheet in sheets
        ]
        response = self._service.spreadsheets().values().batchGet(
            spreadsheetId=self._spreadsheet_id,
            ranges=ranges,
            majorDimension="ROWS",
        ).execute()
        value_ranges = response.get("valueRanges", [])
        result = {}
        for index, sheet in enumerate(sheets):
            value_range = value_ranges[index] if index < len(value_ranges) else {}
            result[sheet] = [
                list(row)
                for row in value_range.get("values", [])
            ]
        return result
