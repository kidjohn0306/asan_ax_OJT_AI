import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from repositories.base import ResultConflict
from repositories.drive_repo import DriveResultRepository
from repositories.local_json import LocalResultRepository
from repositories.sheets_repo import RESULTS_HEADERS, SheetsResultRepository
from schema.sheets_v2 import SHEET_HEADERS


def result(**overrides):
    row = {
        "result_id": "result-1",
        "exam_id": "exam-1",
        "employee_id": "E1",
        "name": "홍길동",
        "score": 60,
        "pass": False,
        "team_code": "T1",
        "submitted_at": "2026-07-15T01:00:00+00:00",
        "difficulty_summary": {"상": {"correct": 1, "incorrect": 0}},
        "results": [{"q_id": "Q1", "correct": True}],
        "assignment_id": "assignment-1",
        "attempt_no": 1,
        "started_at": "2026-07-15T00:50:00+00:00",
        "total_questions": 2,
        "correct_count": 1,
        "response_time_total_seconds": 12.5,
        "grading_summary_json": {"max_score": 100},
        "schema_version": 2,
        "row_version": 1,
        "exam_version_id": "version-1",
        "attempt_id": "attempt-1",
        "grading_status": "completed",
        "submission_status": "submitted",
        "error_code": "",
        "reeducation_required": False,
        "retest_assignment_id": "",
    }
    row.update(overrides)
    return row


class SheetsResultExtensionTests(unittest.TestCase):
    def setUp(self):
        self.strict = patch.dict(
            "os.environ", {"OJT_STRICT_SHEETS_STORAGE": "true"}, clear=False
        )
        self.strict.start()
        self.addCleanup(self.strict.stop)
        self.repo = SheetsResultRepository()
        self.repo._maybe_ensure_tab = MagicMock()
        self.values = MagicMock()
        self.repo._values = MagicMock(return_value=self.values)

    def table(self, records=(), width=None):
        headers = SHEET_HEADERS["results"]
        if width is not None:
            headers = headers[:width]
        return {"values": [
            list(headers),
            *[
                [self.repo._dict_to_row(record)[index] for index in range(len(headers))]
                for record in records
            ],
        ]}

    def test_legacy_headers_remain_exact_prefix(self):
        self.assertEqual(tuple(RESULTS_HEADERS), SHEET_HEADERS["results"][:10])

    def test_read_all_rows_uses_full_canonical_width(self):
        self.values.get.return_value.execute.return_value = {"values": []}
        self.repo._read_all_rows()
        self.assertEqual(
            self.values.get.call_args.kwargs["range"],
            "results!A:Z",
        )

    def test_ten_column_legacy_row_remains_readable(self):
        legacy = result()
        row = self.repo._dict_to_row(legacy)[:10]
        parsed = self.repo._row_to_dict(row)
        self.assertEqual(parsed["result_id"], "result-1")
        self.assertEqual(parsed["score"], 60)
        self.assertEqual(parsed["results"][0]["q_id"], "Q1")
        self.assertEqual(parsed["assignment_id"], "")

    def test_extended_row_round_trips_canonical_fields(self):
        original = result(reeducation_required=True)
        row = self.repo._dict_to_row(original)
        self.assertEqual(len(row), len(SHEET_HEADERS["results"]))
        parsed = self.repo._row_to_dict(row)
        for field in (
            "assignment_id",
            "attempt_no",
            "total_questions",
            "correct_count",
            "response_time_total_seconds",
            "grading_summary_json",
            "exam_version_id",
            "attempt_id",
            "grading_status",
            "submission_status",
            "reeducation_required",
        ):
            self.assertEqual(parsed[field], original[field], field)

    def test_same_result_updates_existing_row_not_append(self):
        existing = result(score=60)
        self.values.get.return_value.execute.return_value = self.table([existing])
        self.repo.append_result(result(score=60))
        self.values.update.assert_called_once()
        self.values.append.assert_not_called()

    def test_same_legacy_result_with_omitted_extended_fields_is_idempotent(self):
        legacy = {
            key: value
            for key, value in result().items()
            if key in RESULTS_HEADERS
        }
        self.values.get.return_value.execute.return_value = self.table([legacy])

        self.repo.append_result(dict(legacy))

        self.values.update.assert_called_once()
        self.values.append.assert_not_called()

    def test_different_existing_result_is_conflict(self):
        self.values.get.return_value.execute.return_value = self.table([result(score=40)])
        with self.assertRaises(ResultConflict):
            self.repo.append_result(result(score=60))
        self.values.update.assert_not_called()
        self.values.append.assert_not_called()


class LocalResultExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = LocalResultRepository()
        self.repo.RESULTS_DIR = root / "results"
        self.repo._TMP_RESULTS_DIR = root / "tmp-results"

    def test_multiple_results_for_same_exam_and_employee_coexist(self):
        self.repo.append_result(result(result_id="result-1"))
        self.repo.append_result(result(result_id="result-2"))
        rows = self.repo.list_results_by_exam("exam-1")
        self.assertEqual(
            sorted(row["result_id"] for row in rows),
            ["result-1", "result-2"],
        )
        self.assertTrue(
            (self.repo.RESULTS_DIR / "exam-1" / "result-1.json").exists()
        )

    def test_same_result_is_idempotent_but_different_content_conflicts(self):
        self.repo.append_result(result())
        self.repo.append_result(result())
        self.assertEqual(len(self.repo.list_results_by_exam("exam-1")), 1)
        with self.assertRaises(ResultConflict):
            self.repo.append_result(result(score=40))

    def test_historical_employee_named_file_remains_readable(self):
        historical = self.repo.RESULTS_DIR / "exam-1" / "E1.json"
        historical.parent.mkdir(parents=True)
        historical.write_text(
            json.dumps(result(result_id="historical"), ensure_ascii=False),
            encoding="utf-8",
        )
        self.assertEqual(
            self.repo.get_result("historical")["result_id"], "historical"
        )


class FakeDriveResultRepository(DriveResultRepository):
    def __init__(self, rows=()):
        self._folder_id = "folder-1"
        self.lines = [json.dumps(row, ensure_ascii=False) for row in rows]
        self.uploads = []

    def _service(self):
        return object()

    def _find_file_id(self, service):
        return "file-1" if self.lines else None

    def _download_lines(self, service, file_id):
        return list(self.lines)

    def _upload(self, service, lines, file_id):
        self.lines = list(lines)
        self.uploads.append((list(lines), file_id))
        return file_id or "file-1"


class DriveResultExtensionTests(unittest.TestCase):
    def test_same_result_retry_does_not_duplicate_line(self):
        repo = FakeDriveResultRepository([result()])
        repo.append_result(result())
        self.assertEqual(len(repo.lines), 1)

    def test_different_existing_result_is_conflict(self):
        repo = FakeDriveResultRepository([result(score=40)])
        with self.assertRaises(ResultConflict):
            repo.append_result(result(score=60))

    def test_new_result_appends_line(self):
        repo = FakeDriveResultRepository([result()])
        repo.append_result(result(result_id="result-2"))
        self.assertEqual(len(repo.lines), 2)


if __name__ == "__main__":
    unittest.main()
