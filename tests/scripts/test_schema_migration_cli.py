import unittest
from unittest.mock import MagicMock, patch

from schema.sheets_v2 import SHEET_HEADERS
from scripts import migrate_schema_v2


def canonical_actual():
    return {name: list(headers) for name, headers in SHEET_HEADERS.items()}


class SchemaMigrationCliTests(unittest.TestCase):
    @patch.object(migrate_schema_v2, "_build_sheets_service")
    def test_missing_spreadsheet_id_exits_before_service_build(self, build_service):
        with self.assertRaises(SystemExit):
            migrate_schema_v2.main([])
        build_service.assert_not_called()

    def test_apply_requires_explicit_copy_target(self):
        with self.assertRaises(SystemExit):
            migrate_schema_v2.main([
                "--spreadsheet-id", "copy-id", "--apply",
            ])

    @patch.object(migrate_schema_v2, "_build_sheets_service")
    def test_default_dry_run_performs_no_writes(self, build_service):
        service = build_service.return_value
        with patch.object(
            migrate_schema_v2.SchemaSheetsInspector,
            "read_headers",
            return_value=canonical_actual(),
        ):
            report = migrate_schema_v2.run_migration(
                spreadsheet_id="copy-id",
                apply=False,
                service=service,
            )

        self.assertFalse(report["applied"])
        self.assertNotIn("copy-id", str(report))
        spreadsheets = service.spreadsheets.return_value
        spreadsheets.batchUpdate.assert_not_called()
        spreadsheets.values.return_value.update.assert_not_called()
        spreadsheets.values.return_value.batchUpdate.assert_not_called()

    @patch.object(migrate_schema_v2, "_build_sheets_service")
    def test_blocking_issue_prevents_apply(self, build_service):
        actual = canonical_actual()
        actual["results"][0] = "wrong_result_id"
        with patch.object(
            migrate_schema_v2.SchemaSheetsInspector,
            "read_headers",
            return_value=actual,
        ):
            with self.assertRaisesRegex(RuntimeError, "blocking schema issues"):
                migrate_schema_v2.run_migration(
                    spreadsheet_id="copy-id",
                    apply=True,
                    target_kind="copy",
                    service=build_service.return_value,
                )

    def test_duplicate_primary_key_is_in_dry_run_and_blocks_apply(self):
        service = MagicMock()
        with patch.object(
            migrate_schema_v2.SchemaSheetsInspector,
            "read_headers",
            return_value=canonical_actual(),
        ), patch.object(
            migrate_schema_v2.SchemaSheetsInspector,
            "read_primary_key_rows",
            return_value={"results": [["r1"], ["r1"]]},
        ):
            report = migrate_schema_v2.run_migration(
                spreadsheet_id="copy-id",
                apply=False,
                service=service,
            )
            self.assertIn(
                "DUPLICATE_PRIMARY_KEY",
                [issue["code"] for issue in report["issues"]],
            )
            with self.assertRaisesRegex(RuntimeError, "blocking schema issues"):
                migrate_schema_v2.run_migration(
                    spreadsheet_id="copy-id",
                    apply=True,
                    target_kind="copy",
                    service=service,
                )

    def test_apply_rechecks_and_emits_only_header_writes(self):
        service = MagicMock()
        before = canonical_actual()
        del before["materials"]
        before["results"] = before["results"][:10]
        after = canonical_actual()

        with patch.object(
            migrate_schema_v2.SchemaSheetsInspector,
            "read_headers",
            side_effect=[before, before, after],
        ) as read_headers:
            report = migrate_schema_v2.run_migration(
                spreadsheet_id="copy-id",
                apply=True,
                target_kind="copy",
                service=service,
            )

        self.assertTrue(report["applied"])
        self.assertEqual(read_headers.call_count, 3)
        spreadsheets = service.spreadsheets.return_value
        requests = spreadsheets.batchUpdate.call_args.kwargs["body"]["requests"]
        self.assertEqual(requests, [{"addSheet": {"properties": {"title": "materials"}}}])
        data = spreadsheets.values.return_value.batchUpdate.call_args.kwargs["body"]["data"]
        self.assertTrue(all(item["range"].endswith("1") for item in data))
        self.assertTrue(all(len(item["values"]) == 1 for item in data))
        spreadsheets.values.return_value.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
