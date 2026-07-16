"""Dry-run-first lean 18-sheet header migration for the lean-ops target sheet.

Scope is intentionally narrow: preserve the 8 existing legacy tabs (append only
the missing canonical suffix headers) and create the 10 dual-write extension
tabs the current codebase actually reads/writes. The other ~45 sheets from the
full 55-sheet design (docs/catalog/sample/unimplemented tabs) are out of scope
and this script never touches them.

Writes are only ever allowed against the one explicitly authorized target
spreadsheet (``EXPECTED_SPREADSHEET_ID``); any other id is rejected before any
API call is made, for both dry-run and apply.
"""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict

from repositories.schema_sheets import SchemaSheetsInspector
from repositories.sheets_repo import _build_sheets_service
from schema.sheets_v2 import LEGACY_PREFIXES, PRIMARY_KEYS, SHEET_HEADERS, header_hash
from scripts.migrate_schema_v2 import _apply_actions
from services.schema_service import SchemaAction, SchemaIssue, SchemaReport


EXPECTED_SPREADSHEET_ID = "1grDKmABkUxPAU7NyM0BEOSckE4EQjl0mkSes9H3CnVo"

LEGACY_TABS: tuple[str, ...] = (
    "results",
    "snapshots",
    "question_stats",
    "exam_sets",
    "teams",
    "users",
    "question_bank",
    "material_cache",
)

NEW_TABS: tuple[str, ...] = (
    "generation_jobs",
    "question_candidates",
    "gate_results",
    "question_reviews",
    "question_history",
    "exam_versions",
    "exam_set_items",
    "assignments",
    "exam_attempts",
    "result_answers",
)

LEAN_TABS: tuple[str, ...] = LEGACY_TABS + NEW_TABS

LEAN_HEADERS: dict[str, tuple[str, ...]] = {
    sheet: SHEET_HEADERS[sheet] for sheet in LEAN_TABS
}
LEAN_LEGACY_PREFIXES: dict[str, tuple[str, ...]] = {
    sheet: LEGACY_PREFIXES[sheet] for sheet in LEGACY_TABS
}
LEAN_PRIMARY_KEYS: dict[str, str] = {
    sheet: PRIMARY_KEYS[sheet] for sheet in LEAN_TABS
}


def inspect_lean_schema(actual: Mapping[str, Sequence[str]]) -> SchemaReport:
    """Same rules as services.schema_service.inspect_schema, scoped to the 18 lean tabs."""
    issues: list[SchemaIssue] = []
    expected_hashes = {
        sheet: header_hash(headers) for sheet, headers in LEAN_HEADERS.items()
    }
    actual_headers = {sheet: tuple(headers) for sheet, headers in actual.items()}
    actual_hashes = {
        sheet: header_hash(headers) for sheet, headers in actual_headers.items()
    }

    for sheet, expected in LEAN_HEADERS.items():
        current = actual_headers.get(sheet)
        if current is None:
            issues.append(SchemaIssue(
                code="MISSING_SHEET",
                sheet=sheet,
                message=f"required lean sheet {sheet!r} is missing",
                blocking=False,
            ))
            continue

        legacy_prefix = LEAN_LEGACY_PREFIXES.get(sheet)
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

    for sheet in actual_headers.keys() - LEAN_HEADERS.keys():
        issues.append(SchemaIssue(
            code="UNEXPECTED_SHEET",
            sheet=sheet,
            message=f"sheet {sheet!r} is outside the lean 18-tab scope",
            blocking=False,
        ))

    return SchemaReport(
        issues=tuple(issues),
        expected_hashes=expected_hashes,
        actual_hashes=actual_hashes,
    )


def build_lean_schema_plan(actual: Mapping[str, Sequence[str]]) -> list[SchemaAction]:
    report = inspect_lean_schema(actual)
    if report.blocking_issues:
        return []

    actions: list[SchemaAction] = []
    for sheet, expected in LEAN_HEADERS.items():
        current = actual.get(sheet)
        if current is None:
            actions.append(SchemaAction(kind="CREATE_SHEET", sheet=sheet, headers=expected))
            continue
        current_tuple = tuple(current)
        if (
            (sheet in LEAN_LEGACY_PREFIXES and len(current_tuple) < len(expected))
            or (sheet not in LEAN_LEGACY_PREFIXES and not current_tuple)
        ):
            actions.append(SchemaAction(
                kind="APPEND_HEADERS",
                sheet=sheet,
                headers=expected[len(current_tuple):],
                start_index=len(current_tuple),
            ))
    return actions


def validate_lean_primary_keys(
    rows_by_sheet: Mapping[str, Sequence[Sequence[object]]],
) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    for sheet, rows in rows_by_sheet.items():
        primary_key = LEAN_PRIMARY_KEYS.get(sheet)
        headers = LEAN_HEADERS.get(sheet)
        if not primary_key or not headers:
            continue
        key_index = headers.index(primary_key)
        values: list[str] = []
        missing_rows: list[int] = []
        for row_number, row in enumerate(rows, start=2):
            has_data = any(str(cell).strip() for cell in row if cell is not None)
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


def _target_fingerprint(spreadsheet_id: str) -> str:
    return hashlib.sha256(spreadsheet_id.encode("utf-8")).hexdigest()[:12]


def _serialize_issues(issues) -> list[dict]:
    return [asdict(issue) for issue in issues]


def _serialize_actions(actions) -> list[dict]:
    return [asdict(action) for action in actions]


def _require_expected_spreadsheet(spreadsheet_id: str) -> None:
    if spreadsheet_id != EXPECTED_SPREADSHEET_ID:
        raise ValueError(
            "refusing to touch an unexpected spreadsheet: "
            f"expected {EXPECTED_SPREADSHEET_ID!r}, got {spreadsheet_id!r}"
        )


def run_migration(
    spreadsheet_id: str,
    apply: bool = False,
    target_kind: str = "",
    service=None,
) -> dict:
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id is required")
    _require_expected_spreadsheet(spreadsheet_id)
    if apply and target_kind != "copy":
        raise ValueError("apply is allowed only for target_kind='copy'")

    sheets_service = service or _build_sheets_service()
    inspector = SchemaSheetsInspector(sheets_service, spreadsheet_id)
    initial_headers = inspector.read_headers()
    initial_report = inspect_lean_schema(initial_headers)
    initial_pk_rows = {
        sheet: rows
        for sheet, rows in inspector.read_primary_key_rows(initial_headers.keys()).items()
        if sheet in LEAN_TABS
    }
    initial_data_issues = validate_lean_primary_keys(initial_pk_rows)
    initial_actions = build_lean_schema_plan(initial_headers)

    create_actions = [a for a in initial_actions if a.kind == "CREATE_SHEET"]
    append_actions = [a for a in initial_actions if a.kind == "APPEND_HEADERS"]

    report = {
        "target_fingerprint": _target_fingerprint(spreadsheet_id),
        "applied": False,
        "before_sheet_count": len(initial_headers),
        "after_sheet_count": len(initial_headers) + len(create_actions),
        "new_tab_actions": _serialize_actions(create_actions),
        "header_append_actions": _serialize_actions(append_actions),
        "actions": _serialize_actions(initial_actions),
        "issues": _serialize_issues(initial_report.issues + tuple(initial_data_issues)),
        "blocking_issues": _serialize_issues(
            initial_report.blocking_issues + tuple(
                issue for issue in initial_data_issues if issue.blocking
            )
        ),
        "before_hashes": initial_report.actual_hashes,
        "expected_hashes": initial_report.expected_hashes,
        "after_hashes": initial_report.actual_hashes,
    }

    if not apply:
        return report
    if initial_report.blocking_issues or any(i.blocking for i in initial_data_issues):
        raise RuntimeError("blocking schema issues prevent apply")

    current_headers = inspector.read_headers()
    current_report = inspect_lean_schema(current_headers)
    current_pk_rows = {
        sheet: rows
        for sheet, rows in inspector.read_primary_key_rows(current_headers.keys()).items()
        if sheet in LEAN_TABS
    }
    current_data_issues = validate_lean_primary_keys(current_pk_rows)
    current_actions = build_lean_schema_plan(current_headers)
    if current_report.blocking_issues or any(i.blocking for i in current_data_issues):
        raise RuntimeError("blocking schema issues prevent apply")
    if current_actions != initial_actions:
        raise RuntimeError("schema changed after Dry-run; rerun inspection")

    _apply_actions(sheets_service, spreadsheet_id, current_actions)

    final_headers = inspector.read_headers()
    final_report = inspect_lean_schema(final_headers)
    final_actions = build_lean_schema_plan(final_headers)
    remaining_blocking = final_report.blocking_issues
    if remaining_blocking or final_actions:
        raise RuntimeError("post-apply schema validation failed")

    report.update({
        "applied": True,
        "after_sheet_count": len(final_headers),
        "after_hashes": final_report.actual_hashes,
        "post_apply_issues": _serialize_issues(final_report.issues),
    })
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", default=EXPECTED_SPREADSHEET_ID)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--target-kind",
        choices=("copy", "production"),
        default="",
        help="--apply requires --target-kind copy.",
    )
    args = parser.parse_args(argv)
    if args.apply and args.target_kind != "copy":
        parser.error("--apply requires --target-kind copy")
    return args


def main(argv=None):
    args = parse_args(argv)
    report = run_migration(
        spreadsheet_id=args.spreadsheet_id,
        apply=args.apply,
        target_kind=args.target_kind,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
