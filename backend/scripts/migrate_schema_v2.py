"""Dry-run-first 55-sheet header migration for copied spreadsheets only."""

import argparse
import hashlib
import json
from dataclasses import asdict

from repositories.schema_sheets import (
    SchemaSheetsInspector,
    column_name,
    quote_sheet_name,
)
from repositories.sheets_repo import _build_sheets_service
from services.schema_service import (
    build_schema_plan,
    inspect_schema,
    validate_primary_keys,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--target-kind",
        choices=("copy", "production"),
        default="",
        help="Phase 2 apply is allowed only for an explicit copied spreadsheet.",
    )
    args = parser.parse_args(argv)
    if args.apply and args.target_kind != "copy":
        parser.error("--apply requires --target-kind copy in Phase 2")
    return args


def _target_fingerprint(spreadsheet_id: str) -> str:
    return hashlib.sha256(spreadsheet_id.encode("utf-8")).hexdigest()[:12]


def _serialize_issues(issues) -> list[dict]:
    return [asdict(issue) for issue in issues]


def _serialize_actions(actions) -> list[dict]:
    return [asdict(action) for action in actions]


def _apply_actions(service, spreadsheet_id: str, actions) -> None:
    spreadsheets = service.spreadsheets()
    create_requests = [
        {"addSheet": {"properties": {"title": action.sheet}}}
        for action in actions
        if action.kind == "CREATE_SHEET"
    ]
    if create_requests:
        spreadsheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": create_requests},
        ).execute()

    data = []
    for action in actions:
        if action.kind == "CREATE_SHEET":
            start_index = 0
        elif action.kind == "APPEND_HEADERS":
            start_index = action.start_index
        else:
            raise ValueError(f"unsupported schema action: {action.kind}")
        start_column = column_name(start_index + 1)
        end_column = column_name(start_index + len(action.headers))
        data.append({
            "range": f"{quote_sheet_name(action.sheet)}!{start_column}1:{end_column}1",
            "values": [list(action.headers)],
        })

    if data:
        spreadsheets.values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()


def run_migration(
    spreadsheet_id: str,
    apply: bool = False,
    target_kind: str = "",
    service=None,
) -> dict:
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id is required")
    if apply and target_kind != "copy":
        raise ValueError("Phase 2 apply is allowed only for target_kind='copy'")

    sheets_service = service or _build_sheets_service()
    inspector = SchemaSheetsInspector(sheets_service, spreadsheet_id)
    initial_headers = inspector.read_headers()
    initial_report = inspect_schema(initial_headers)
    initial_data_issues = validate_primary_keys(
        inspector.read_primary_key_rows(initial_headers.keys())
    )
    initial_actions = build_schema_plan(initial_headers)

    report = {
        "target_fingerprint": _target_fingerprint(spreadsheet_id),
        "applied": False,
        "before_sheet_count": len(initial_headers),
        "after_sheet_count": len(initial_headers),
        "issues": _serialize_issues(initial_report.issues + tuple(initial_data_issues)),
        "actions": _serialize_actions(initial_actions),
        "before_hashes": initial_report.actual_hashes,
        "expected_hashes": initial_report.expected_hashes,
        "after_hashes": initial_report.actual_hashes,
    }

    if not apply:
        return report
    if initial_report.blocking_issues or initial_data_issues:
        raise RuntimeError("blocking schema issues prevent apply")

    current_headers = inspector.read_headers()
    current_report = inspect_schema(current_headers)
    current_data_issues = validate_primary_keys(
        inspector.read_primary_key_rows(current_headers.keys())
    )
    current_actions = build_schema_plan(current_headers)
    if current_report.blocking_issues or current_data_issues:
        raise RuntimeError("blocking schema issues prevent apply")
    if current_actions != initial_actions:
        raise RuntimeError("schema changed after Dry-run; rerun inspection")

    _apply_actions(sheets_service, spreadsheet_id, current_actions)

    final_headers = inspector.read_headers()
    final_report = inspect_schema(final_headers)
    final_actions = build_schema_plan(final_headers)
    if final_report.issues or final_actions:
        raise RuntimeError("post-apply schema validation failed")

    report.update({
        "applied": True,
        "after_sheet_count": len(final_headers),
        "after_hashes": final_report.actual_hashes,
        "post_apply_issues": [],
    })
    return report


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
