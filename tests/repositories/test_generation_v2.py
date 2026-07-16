import unittest
from unittest.mock import MagicMock

from repositories.generation_v2 import (
    SheetsGenerationV2Repository,
    build_generation_v2_repository,
)
from schema.sheets_v2 import SHEET_HEADERS


class SheetsGenerationV2RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.values = self.service.spreadsheets.return_value.values.return_value
        self.repo = SheetsGenerationV2Repository(
            service=self.service,
            spreadsheet_id="copy-sheet",
        )

    def table(self, sheet, rows=None):
        return {
            "values": [list(SHEET_HEADERS[sheet]), *(rows or [])]
        }

    def test_constructor_performs_no_external_call(self):
        self.service.spreadsheets.assert_not_called()

    def test_unknown_fields_fail_before_api_call(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.repo.create_job({
                "generation_job_id": "job-1",
                "not_a_column": "x",
            })
        self.service.spreadsheets.assert_not_called()

    def test_candidates_are_appended_idempotently(self):
        existing = ["cand-1"] + [""] * (len(SHEET_HEADERS["question_candidates"]) - 1)
        self.values.get.return_value.execute.return_value = self.table(
            "question_candidates", [existing]
        )

        self.repo.save_candidates([
            {"candidate_id": "cand-1", "question_text": "existing"},
            {"candidate_id": "cand-2", "question_text": "new"},
            {"candidate_id": "cand-2", "question_text": "duplicate retry"},
        ])

        self.values.append.assert_called_once()
        body = self.values.append.call_args.kwargs["body"]
        self.assertEqual(len(body["values"]), 1)
        self.assertEqual(body["values"][0][0], "cand-2")

    def test_update_job_updates_existing_row_not_append(self):
        headers = SHEET_HEADERS["generation_jobs"]
        existing = [""] * len(headers)
        existing[headers.index("generation_job_id")] = "job-1"
        existing[headers.index("status")] = "RUNNING"
        self.values.get.return_value.execute.return_value = self.table(
            "generation_jobs", [existing]
        )

        self.repo.update_job("job-1", {"status": "COMPLETED", "completed_count": 2})

        self.values.update.assert_called_once()
        self.assertEqual(
            self.values.update.call_args.kwargs["range"],
            "'generation_jobs'!A2:AA2",
        )
        self.values.append.assert_not_called()

    def test_update_candidate_updates_existing_row(self):
        headers = SHEET_HEADERS["question_candidates"]
        existing = [""] * len(headers)
        existing[headers.index("candidate_id")] = "cand-1"
        existing[headers.index("status")] = "reviewing"
        self.values.get.return_value.execute.return_value = self.table(
            "question_candidates", [existing]
        )

        self.repo.update_candidate("cand-1", {
            "status": "approved",
            "approved_question_id": "Q1",
        })

        self.values.update.assert_called_once()
        body = self.values.update.call_args.kwargs["body"]
        row = body["values"][0]
        self.assertEqual(row[headers.index("status")], "approved")
        self.assertEqual(row[headers.index("approved_question_id")], "Q1")

    def test_record_review_retry_skips_existing_review_and_writes_history(self):
        review_headers = SHEET_HEADERS["question_reviews"]
        existing_review = ["review-1"] + [""] * (len(review_headers) - 1)
        self.values.get.return_value.execute.side_effect = [
            self.table("question_reviews", [existing_review]),
            self.table("question_history", []),
        ]

        self.repo.record_review(
            {"review_id": "review-1", "review_action": "APPROVE"},
            {"history_id": "history-1", "action": "APPROVE"},
        )

        self.values.append.assert_called_once()
        self.assertIn("question_history", self.values.append.call_args.kwargs["range"])

    def test_list_jobs_returns_rows_sorted_by_started_at_desc(self):
        headers = SHEET_HEADERS["generation_jobs"]
        older = [""] * len(headers)
        older[headers.index("generation_job_id")] = "job-old"
        older[headers.index("started_at")] = "2026-01-01T00:00:00+00:00"
        newer = [""] * len(headers)
        newer[headers.index("generation_job_id")] = "job-new"
        newer[headers.index("started_at")] = "2026-06-01T00:00:00+00:00"
        self.values.get.return_value.execute.return_value = self.table(
            "generation_jobs", [older, newer]
        )

        jobs = self.repo.list_jobs()

        self.assertEqual([job["generation_job_id"] for job in jobs], ["job-new", "job-old"])
        self.values.append.assert_not_called()
        self.values.update.assert_not_called()

    def test_list_jobs_on_empty_sheet_returns_empty_list(self):
        self.values.get.return_value.execute.return_value = self.table("generation_jobs", [])
        self.assertEqual(self.repo.list_jobs(), [])

    def test_api_errors_propagate_without_fallback(self):
        self.values.get.return_value.execute.return_value = self.table(
            "question_candidates", []
        )
        self.values.append.return_value.execute.side_effect = RuntimeError("write failed")
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.repo.save_candidates([{"candidate_id": "cand-1"}])


class GenerationV2FactoryTests(unittest.TestCase):
    def test_defaults_do_not_construct_repository(self):
        self.assertIsNone(build_generation_v2_repository(use_sheets=True, env={}))

    def test_local_backend_does_not_construct_repository(self):
        env = {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_CANDIDATE_TAB": "true",
        }
        self.assertIsNone(build_generation_v2_repository(use_sheets=False, env=env))

    def test_dual_sheets_candidate_flag_constructs_repository(self):
        env = {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_CANDIDATE_TAB": "true",
        }
        repo = build_generation_v2_repository(
            use_sheets=True,
            env=env,
            service=self.service if hasattr(self, "service") else MagicMock(),
            spreadsheet_id="copy-sheet",
        )
        self.assertIsInstance(repo, SheetsGenerationV2Repository)


if __name__ == "__main__":
    unittest.main()
