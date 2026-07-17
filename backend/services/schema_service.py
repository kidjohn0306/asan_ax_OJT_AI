from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from schema.sheets_v2 import (
    LEGACY_PREFIXES,
    PRIMARY_KEYS,
    SHEET_HEADERS,
    header_hash,
)


@dataclass(frozen=True)
class SchemaIssue:
    code: str
    sheet: str
    message: str
    blocking: bool = True
    values: tuple[str, ...] = ()
    row_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class SchemaAction:
    kind: str
    sheet: str
    headers: tuple[str, ...]
    start_index: int = 0


@dataclass(frozen=True)
class SchemaReport:
    issues: tuple[SchemaIssue, ...]
    expected_hashes: dict[str, str]
    actual_hashes: dict[str, str]

    @property
    def blocking_issues(self) -> tuple[SchemaIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    @property
    def is_valid(self) -> bool:
        return not self.blocking_issues


def inspect_schema(actual: Mapping[str, Sequence[str]]) -> SchemaReport:
    issues: list[SchemaIssue] = []
    expected_hashes = {
        sheet: header_hash(headers)
        for sheet, headers in SHEET_HEADERS.items()
    }
    actual_headers = {
        sheet: tuple(headers)
        for sheet, headers in actual.items()
    }
    actual_hashes = {
        sheet: header_hash(headers)
        for sheet, headers in actual_headers.items()
    }

    for sheet, expected in SHEET_HEADERS.items():
        current = actual_headers.get(sheet)
        if current is None:
            issues.append(SchemaIssue(
                code="MISSING_SHEET",
                sheet=sheet,
                message=f"required sheet {sheet!r} is missing",
                blocking=False,
            ))
            continue

        legacy_prefix = LEGACY_PREFIXES.get(sheet)
        if legacy_prefix is not None:
            if len(current) < len(legacy_prefix) or current[:len(legacy_prefix)] != legacy_prefix:
                issues.append(SchemaIssue(
                    code="LEGACY_PREFIX_MISMATCH",
                    sheet=sheet,
                    message="legacy header prefix differs from the repository contract",
                ))
            elif current == expected:
                continue
            elif len(current) < len(expected) and current == expected[:len(current)]:
                issues.append(SchemaIssue(
                    code="MISSING_HEADERS",
                    sheet=sheet,
                    message=f"{len(expected) - len(current)} suffix headers are missing",
                    blocking=False,
                ))
            else:
                issues.append(SchemaIssue(
                    code="HEADER_MISMATCH",
                    sheet=sheet,
                    message="extended headers differ from the canonical order",
                ))
        elif not current:
            issues.append(SchemaIssue(
                code="MISSING_HEADERS",
                sheet=sheet,
                message=f"{len(expected)} headers are missing from an empty sheet",
                blocking=False,
            ))
        elif current != expected:
            issues.append(SchemaIssue(
                code="HEADER_MISMATCH",
                sheet=sheet,
                message="headers differ from the canonical order",
            ))

    for sheet in actual_headers.keys() - SHEET_HEADERS.keys():
        issues.append(SchemaIssue(
            code="UNEXPECTED_SHEET",
            sheet=sheet,
            message=f"unmanaged sheet {sheet!r} is present",
            blocking=False,
        ))

    return SchemaReport(
        issues=tuple(issues),
        expected_hashes=expected_hashes,
        actual_hashes=actual_hashes,
    )


def build_schema_plan(actual: Mapping[str, Sequence[str]]) -> list[SchemaAction]:
    report = inspect_schema(actual)
    if report.blocking_issues:
        return []

    actions: list[SchemaAction] = []
    for sheet, expected in SHEET_HEADERS.items():
        current = actual.get(sheet)
        if current is None:
            actions.append(SchemaAction(
                kind="CREATE_SHEET",
                sheet=sheet,
                headers=expected,
            ))
            continue
        current_tuple = tuple(current)
        if (
            (sheet in LEGACY_PREFIXES and len(current_tuple) < len(expected))
            or (sheet not in LEGACY_PREFIXES and not current_tuple)
        ):
            actions.append(SchemaAction(
                kind="APPEND_HEADERS",
                sheet=sheet,
                headers=expected[len(current_tuple):],
                start_index=len(current_tuple),
            ))
    return actions


def validate_primary_keys(
    rows_by_sheet: Mapping[str, Sequence[Sequence[object]]],
) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    for sheet, rows in rows_by_sheet.items():
        primary_key = PRIMARY_KEYS.get(sheet)
        headers = SHEET_HEADERS.get(sheet)
        if not primary_key or not headers:
            continue
        key_index = headers.index(primary_key)
        values: list[str] = []
        missing_rows: list[int] = []
        for row_number, row in enumerate(rows, start=2):
            has_data = any(
                str(cell).strip()
                for cell in row
                if cell is not None
            )
            if not has_data:
                continue
            value = row[key_index] if len(row) > key_index else ""
            normalized = str(value).strip() if value is not None else ""
            if not normalized:
                missing_rows.append(row_number)
            else:
                values.append(normalized)

        if missing_rows:
            issues.append(SchemaIssue(
                code="MISSING_PRIMARY_KEY",
                sheet=sheet,
                message=f"blank {primary_key} values found",
                row_numbers=tuple(missing_rows),
            ))

        counts = Counter(values)
        duplicates = tuple(value for value in values if counts[value] > 1)
        unique_duplicates = tuple(dict.fromkeys(duplicates))
        if unique_duplicates:
            issues.append(SchemaIssue(
                code="DUPLICATE_PRIMARY_KEY",
                sheet=sheet,
                message=f"duplicate {primary_key} values found",
                values=unique_duplicates,
            ))
    return issues
