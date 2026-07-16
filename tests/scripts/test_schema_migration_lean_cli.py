import unittest
from unittest.mock import MagicMock, patch

from scripts import migrate_schema_lean


def canonical_lean_actual():
    return {
        name: list(headers)
        for name, headers in migrate_schema_lean.LEAN_HEADERS.items()
    }


def legacy_only_actual():
    return {
        sheet: list(migrate_schema_lean.LEAN_LEGACY_PREFIXES[sheet])
        for sheet in migrate_schema_lean.LEGACY_TABS
    }


class SchemaMigrationLeanCliTests(unittest.TestCase):
    def test_rejects_unexpected_spreadsheet_id_even_for_dry_run(self):
        with self.assertRaises(ValueError):
            migrate_schema_lean.run_migration(
                spreadsheet_id="some-other-sheet",
                apply=False,
                service=MagicMock(),
            )

    def test_apply_requires_explicit_copy_target(self):
        with self.assertRaises(SystemExit):
            migrate_schema_lean.main([
                "--spreadsheet-id", migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                "--apply",
            ])

    def test_dry_run_from_legacy_only_plans_10_new_tabs_and_header_appends(self):
        service = MagicMock()
        with patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_headers",
            return_value=legacy_only_actual(),
        ), patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={},
        ):
            report = migrate_schema_lean.run_migration(
                spreadsheet_id=migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                apply=False,
                service=service,
            )

        self.assertFalse(report["applied"])
        self.assertEqual(report["before_sheet_count"], 8)
        self.assertEqual(report["after_sheet_count"], 18)
        self.assertEqual(len(report["new_tab_actions"]), 10)
        self.assertEqual(
            {a["sheet"] for a in report["new_tab_actions"]},
            set(migrate_schema_lean.NEW_TABS),
        )
        self.assertEqual(len(report["header_append_actions"]), 7)
        self.assertEqual(report["blocking_issues"], [])
        spreadsheets = service.spreadsheets.return_value
        spreadsheets.batchUpdate.assert_not_called()
        spreadsheets.values.return_value.batchUpdate.assert_not_called()

    def test_canonical_lean_schema_has_no_actions(self):
        with patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_headers",
            return_value=canonical_lean_actual(),
        ), patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={},
        ):
            report = migrate_schema_lean.run_migration(
                spreadsheet_id=migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                apply=False,
                service=MagicMock(),
            )

        self.assertEqual(report["actions"], [])
        self.assertEqual(report["blocking_issues"], [])

    def test_legacy_prefix_mismatch_blocks_apply(self):
        actual = legacy_only_actual()
        actual["results"][0:2] = ["exam_id", "result_id"]
        with patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_headers",
            return_value=actual,
        ), patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={},
        ):
            with self.assertRaisesRegex(RuntimeError, "blocking schema issues"):
                migrate_schema_lean.run_migration(
                    spreadsheet_id=migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                    apply=True,
                    target_kind="copy",
                    service=MagicMock(),
                )

    def test_duplicate_primary_key_blocks_apply(self):
        with patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_headers",
            return_value=canonical_lean_actual(),
        ), patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={"results": [["r1"], ["r1"]]},
        ):
            with self.assertRaisesRegex(RuntimeError, "blocking schema issues"):
                migrate_schema_lean.run_migration(
                    spreadsheet_id=migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                    apply=True,
                    target_kind="copy",
                    service=MagicMock(),
                )

    def test_apply_creates_tabs_and_appends_headers_only(self):
        service = MagicMock()
        before = legacy_only_actual()
        after = canonical_lean_actual()

        with patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_headers",
            side_effect=[before, before, after],
        ) as read_headers, patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={},
        ):
            report = migrate_schema_lean.run_migration(
                spreadsheet_id=migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                apply=True,
                target_kind="copy",
                service=service,
            )

        self.assertTrue(report["applied"])
        self.assertEqual(report["after_sheet_count"], 18)
        self.assertEqual(read_headers.call_count, 3)
        spreadsheets = service.spreadsheets.return_value
        create_requests = spreadsheets.batchUpdate.call_args.kwargs["body"]["requests"]
        self.assertEqual(
            {r["addSheet"]["properties"]["title"] for r in create_requests},
            set(migrate_schema_lean.NEW_TABS),
        )
        header_data = spreadsheets.values.return_value.batchUpdate.call_args.kwargs["body"]["data"]
        self.assertEqual(len(header_data), 17)
        self.assertTrue(all(item["range"].endswith("1") for item in header_data))

    def test_schema_drift_after_dry_run_blocks_apply(self):
        service = MagicMock()
        before = legacy_only_actual()
        drifted = legacy_only_actual()
        drifted["generation_jobs"] = list(
            migrate_schema_lean.LEAN_HEADERS["generation_jobs"]
        )

        with patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_headers",
            side_effect=[before, drifted],
        ), patch.object(
            migrate_schema_lean.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={},
        ):
            with self.assertRaisesRegex(RuntimeError, "schema changed after Dry-run"):
                migrate_schema_lean.run_migration(
                    spreadsheet_id=migrate_schema_lean.EXPECTED_SPREADSHEET_ID,
                    apply=True,
                    target_kind="copy",
                    service=service,
                )


if __name__ == "__main__":
    unittest.main()
