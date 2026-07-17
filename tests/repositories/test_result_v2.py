import unittest
from unittest.mock import MagicMock

from repositories.result_v2 import (
    ImmutableResultAnswerConflict,
    SheetsResultV2Repository,
    build_result_v2_repository,
)
from schema.sheets_v2 import SHEET_HEADERS


def attempt(**overrides):
    row = {
        "attempt_id": "attempt-1",
        "assignment_id": "assignment-1",
        "exam_id": "exam-1",
        "exam_version_id": "version-1",
        "employee_id": "E1",
        "status": "started",
        "entered_at": "2026-07-15T00:00:00+00:00",
        "started_at": "2026-07-15T00:00:00+00:00",
        "last_seen_at": "2026-07-15T00:00:00+00:00",
        "submitted_at": "",
        "closed_at": "",
        "client_session_id": "",
        "submission_idempotency_key": "",
        "error_code": "",
        "error_message": "",
        "row_version": 1,
    }
    row.update(overrides)
    return row


def answer(**overrides):
    row = {
        "result_answer_id": "answer-1",
        "result_id": "result-1",
        "exam_set_item_id": "item-1",
        "question_id": "Q1",
        "question_version": 2,
        "selected_choice": "A",
        "correct_choice": "A",
        "is_correct": True,
        "score": 60,
        "response_time_seconds": 12.5,
        "created_at": "2026-07-15T01:00:00+00:00",
    }
    row.update(overrides)
    return row


class SheetsResultV2RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.values = self.service.spreadsheets.return_value.values.return_value
        self.repo = SheetsResultV2Repository(
            service=self.service,
            spreadsheet_id="copy-sheet",
        )

    def table(self, sheet, records=()):
        headers = SHEET_HEADERS[sheet]
        return {"values": [
            list(headers),
            *[
                [record.get(header, "") for header in headers]
                for record in records
            ],
        ]}

    def test_constructor_performs_no_external_call(self):
        self.service.spreadsheets.assert_not_called()

    def test_unknown_fields_fail_before_api_call(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.repo.upsert_attempt({"attempt_id": "attempt-1", "bad": "x"})
        self.service.spreadsheets.assert_not_called()

    def test_find_attempt_and_active_assignment_attempt(self):
        rows = [
            attempt(attempt_id="other", employee_id="E2"),
            attempt(attempt_id="cancelled", status="cancelled"),
            attempt(attempt_id="target", status="submitting"),
        ]
        self.values.get.return_value.execute.return_value = self.table(
            "exam_attempts", rows
        )
        self.assertEqual(self.repo.find_attempt("target")["attempt_id"], "target")
        found = self.repo.find_attempt_for_assignment(
            "assignment-1", "E1", {"started", "submitting"}
        )
        self.assertEqual(found["attempt_id"], "target")

    def test_attempt_upsert_updates_existing_row(self):
        self.values.get.return_value.execute.return_value = self.table(
            "exam_attempts", [attempt()]
        )
        self.repo.upsert_attempt(attempt(status="submitting", row_version=2))
        self.values.update.assert_called_once()
        self.values.append.assert_not_called()
        headers = SHEET_HEADERS["exam_attempts"]
        row = self.values.update.call_args.kwargs["body"]["values"][0]
        self.assertEqual(row[headers.index("status")], "submitting")

    def test_attempt_upsert_appends_new_row(self):
        self.values.get.return_value.execute.return_value = self.table("exam_attempts")
        self.repo.upsert_attempt(attempt())
        self.values.append.assert_called_once()
        self.values.update.assert_not_called()

    def test_list_result_answers_filters_result(self):
        self.values.get.return_value.execute.return_value = self.table(
            "result_answers",
            [answer(), answer(result_answer_id="other", result_id="result-2")],
        )
        rows = self.repo.list_result_answers("result-1")
        self.assertEqual([row["result_answer_id"] for row in rows], ["answer-1"])

    def test_identical_answer_retry_ignores_created_at(self):
        self.values.get.return_value.execute.return_value = self.table(
            "result_answers", [answer(created_at="old-time")]
        )
        self.repo.save_result_answers([answer(created_at="new-time")])
        self.values.append.assert_not_called()

    def test_different_immutable_answer_raises_conflict(self):
        self.values.get.return_value.execute.return_value = self.table(
            "result_answers", [answer(selected_choice="B", is_correct=False, score=0)]
        )
        with self.assertRaises(ImmutableResultAnswerConflict):
            self.repo.save_result_answers([answer()])
        self.values.append.assert_not_called()

    def test_new_answers_append_once(self):
        self.values.get.return_value.execute.return_value = self.table("result_answers")
        self.repo.save_result_answers([
            answer(),
            answer(
                result_answer_id="answer-2",
                exam_set_item_id="item-2",
                question_id="Q2",
                selected_choice=None,
                is_correct=False,
                score=0,
            ),
        ])
        self.values.append.assert_called_once()
        self.assertEqual(
            len(self.values.append.call_args.kwargs["body"]["values"]), 2
        )

    def test_api_errors_propagate_without_fallback(self):
        self.values.get.return_value.execute.return_value = self.table("result_answers")
        self.values.append.return_value.execute.side_effect = RuntimeError("write failed")
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.repo.save_result_answers([answer()])


class ResultV2FactoryTests(unittest.TestCase):
    def flags(self):
        return {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
            "OJT_USE_ASSIGNMENTS_TAB": "true",
            "OJT_USE_RESULT_ANSWERS": "true",
        }

    def test_defaults_do_not_construct_repository(self):
        self.assertIsNone(build_result_v2_repository(use_sheets=True, env={}))

    def test_local_backend_does_not_construct_repository(self):
        self.assertIsNone(
            build_result_v2_repository(use_sheets=False, env=self.flags())
        )

    def test_all_flags_construct_sheets_repository(self):
        repo = build_result_v2_repository(
            use_sheets=True,
            env=self.flags(),
            service=MagicMock(),
            spreadsheet_id="copy-sheet",
        )
        self.assertIsInstance(repo, SheetsResultV2Repository)


if __name__ == "__main__":
    unittest.main()
