import unittest
from unittest.mock import MagicMock

from repositories.schema_sheets import (
    SchemaSheetsInspector,
    column_name,
)


class ColumnNameTests(unittest.TestCase):
    def test_converts_beyond_z(self):
        self.assertEqual(column_name(1), "A")
        self.assertEqual(column_name(26), "Z")
        self.assertEqual(column_name(27), "AA")
        self.assertEqual(column_name(28), "AB")
        self.assertEqual(column_name(52), "AZ")
        self.assertEqual(column_name(53), "BA")

    def test_rejects_non_positive_index(self):
        with self.assertRaises(ValueError):
            column_name(0)


class SchemaSheetsInspectorTests(unittest.TestCase):
    def make_service(self):
        service = MagicMock()
        spreadsheets = service.spreadsheets.return_value
        spreadsheets.get.return_value.execute.return_value = {
            "sheets": [
                {"properties": {"title": "results"}},
                {"properties": {"title": "question_bank"}},
            ]
        }
        spreadsheets.values.return_value.batchGet.return_value.execute.return_value = {
            "valueRanges": [
                {"range": "results!A1:Z1", "values": [["result_id", "exam_id"]]},
                {"range": "question_bank!A1:AQ1", "values": [["pool_key", "question_id"]]},
            ]
        }
        return service

    def test_reads_metadata_once_and_row_one_only(self):
        service = self.make_service()
        inspector = SchemaSheetsInspector(service, "copy-sheet")

        headers = inspector.read_headers()

        self.assertEqual(headers, {
            "results": ["result_id", "exam_id"],
            "question_bank": ["pool_key", "question_id"],
        })
        spreadsheets = service.spreadsheets.return_value
        spreadsheets.get.assert_called_once_with(
            spreadsheetId="copy-sheet",
            fields="sheets.properties.title",
        )
        call = spreadsheets.values.return_value.batchGet.call_args
        self.assertEqual(call.kwargs["spreadsheetId"], "copy-sheet")
        self.assertEqual(call.kwargs["ranges"], ["'results'!1:1", "'question_bank'!1:1"])

    def test_dry_run_never_calls_write_methods(self):
        service = self.make_service()

        SchemaSheetsInspector(service, "copy-sheet").read_headers()

        spreadsheets = service.spreadsheets.return_value
        spreadsheets.batchUpdate.assert_not_called()
        values = spreadsheets.values.return_value
        values.update.assert_not_called()
        values.append.assert_not_called()
        values.batchUpdate.assert_not_called()

    def test_api_errors_propagate_without_fallback(self):
        service = self.make_service()
        service.spreadsheets.return_value.get.return_value.execute.side_effect = RuntimeError(
            "sheets unavailable"
        )

        with self.assertRaisesRegex(RuntimeError, "sheets unavailable"):
            SchemaSheetsInspector(service, "copy-sheet").read_headers()

    def test_reads_present_primary_key_entity_rows_with_target_width(self):
        service = MagicMock()
        service.spreadsheets.return_value.values.return_value.batchGet.return_value.execute.return_value = {
            "valueRanges": [
                {"values": [["r1"], ["r2"]]},
                {"values": [["set-1", "", "", "", "", "", "", "", "", "", "exam-1"]]},
                {"values": [["common", "Q1"]]},
            ]
        }

        rows = SchemaSheetsInspector(service, "copy-sheet").read_primary_key_rows(
            ["results", "exam_sets", "question_bank"]
        )

        self.assertEqual(rows["results"], [["r1"], ["r2"]])
        values = service.spreadsheets.return_value.values.return_value
        self.assertEqual(values.batchGet.call_args.kwargs["ranges"], [
            "'results'!A2:Z",
            "'exam_sets'!A2:AI",
            "'question_bank'!A2:AQ",
        ])


if __name__ == "__main__":
    unittest.main()
