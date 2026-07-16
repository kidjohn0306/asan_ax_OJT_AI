import unittest
from unittest.mock import MagicMock

from repositories.exam_v2 import (
    ImmutableExamConflict,
    SheetsExamV2Repository,
    build_exam_v2_repository,
)
from schema.sheets_v2 import SHEET_HEADERS


def _version(**overrides):
    row = {
        "exam_version_id": "ver-1",
        "exam_set_id": "set-1",
        "version_no": 1,
        "status": "confirmed",
        "question_count": 1,
        "total_score": 100,
        "blueprint_json": "[]",
        "question_hash": "hash-1",
        "confirmed_by": "admin-1",
        "confirmed_at": "2026-07-15T00:00:00+00:00",
        "created_at": "2026-07-15T00:00:00+00:00",
        "row_version": 1,
    }
    row.update(overrides)
    return row


def _item(**overrides):
    row = {
        "exam_set_item_id": "item-1",
        "exam_set_id": "set-1",
        "paper_version": 1,
        "order_no": 1,
        "question_id": "Q1",
        "question_version": 2,
        "score": 100,
        "question_snapshot_json": "{}",
        "created_at": "2026-07-15T00:00:00+00:00",
        "checksum": "checksum-1",
    }
    row.update(overrides)
    return row


def _assignment(**overrides):
    row = {
        "assignment_id": "assignment-1",
        "exam_id": "exam-1",
        "employee_id": "E1",
        "status": "assigned",
        "assigned_by": "admin-1",
        "assigned_at": "2026-07-15T00:00:00+00:00",
        "row_version": 1,
        "exam_version_id": "ver-1",
    }
    row.update(overrides)
    return row


class SheetsExamV2RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.values = self.service.spreadsheets.return_value.values.return_value
        self.repo = SheetsExamV2Repository(
            service=self.service,
            spreadsheet_id="copy-sheet",
        )

    def table(self, sheet, records=()):
        headers = SHEET_HEADERS[sheet]
        rows = [
            [record.get(header, "") for header in headers]
            for record in records
        ]
        return {"values": [list(headers), *rows]}

    def test_constructor_performs_no_external_call(self):
        self.service.spreadsheets.assert_not_called()

    def test_unknown_fields_fail_before_api_call(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.repo.save_frozen_exam(
                {"exam_version_id": "ver-1", "bad": "x"},
                [],
            )
        self.service.spreadsheets.assert_not_called()

    def test_save_frozen_exam_appends_version_before_items(self):
        self.values.get.return_value.execute.side_effect = [
            self.table("exam_versions"),
            self.table("exam_set_items"),
        ]

        self.repo.save_frozen_exam(
            _version(),
            [_item(), _item(exam_set_item_id="item-2", question_id="Q2")],
        )

        self.assertEqual(self.values.append.call_count, 2)
        calls = self.values.append.call_args_list
        self.assertIn("exam_versions", calls[0].kwargs["range"])
        self.assertIn("exam_set_items", calls[1].kwargs["range"])
        self.assertEqual(len(calls[1].kwargs["body"]["values"]), 2)

    def test_same_immutable_record_ignores_record_timestamps(self):
        existing = _version(
            confirmed_at="2026-07-14T00:00:00+00:00",
            created_at="2026-07-14T00:00:00+00:00",
        )
        self.values.get.return_value.execute.side_effect = [
            self.table("exam_versions", [existing]),
        ]

        self.repo.save_frozen_exam(_version(), [])

        self.values.append.assert_not_called()

    def test_different_immutable_version_raises_conflict(self):
        self.values.get.return_value.execute.return_value = self.table(
            "exam_versions", [_version(question_hash="old-hash")]
        )
        with self.assertRaises(ImmutableExamConflict):
            self.repo.save_frozen_exam(_version(question_hash="new-hash"), [])
        self.values.append.assert_not_called()

    def test_different_immutable_item_raises_conflict(self):
        self.values.get.return_value.execute.side_effect = [
            self.table("exam_versions", [_version()]),
            self.table("exam_set_items", [_item(score=40)]),
        ]
        with self.assertRaises(ImmutableExamConflict):
            self.repo.save_frozen_exam(_version(), [_item(score=100)])

    def test_find_current_version_uses_highest_version_number(self):
        self.values.get.return_value.execute.return_value = self.table(
            "exam_versions",
            [
                _version(exam_version_id="ver-1", version_no="1"),
                _version(exam_version_id="ver-2", version_no="2"),
                _version(
                    exam_version_id="other-9",
                    exam_set_id="other-set",
                    version_no="9",
                ),
            ],
        )
        current = self.repo.find_current_version("set-1")
        self.assertEqual(current["exam_version_id"], "ver-2")
        self.assertEqual(current["version_no"], "2")

    def test_find_version_uses_exact_version_id(self):
        self.values.get.return_value.execute.return_value = self.table(
            "exam_versions",
            [
                _version(exam_version_id="ver-1", version_no="1"),
                _version(exam_version_id="ver-2", version_no="2"),
            ],
        )
        found = self.repo.find_version("ver-1")
        self.assertEqual(found["exam_version_id"], "ver-1")
        self.assertEqual(found["version_no"], "1")

    def test_list_version_items_filters_and_orders_rows(self):
        self.values.get.return_value.execute.return_value = self.table(
            "exam_set_items",
            [
                _item(exam_set_item_id="item-2", order_no="2"),
                _item(
                    exam_set_item_id="other-set",
                    exam_set_id="set-2",
                    order_no="1",
                ),
                _item(
                    exam_set_item_id="other-version",
                    paper_version="2",
                    order_no="1",
                ),
                _item(exam_set_item_id="item-1", order_no="1"),
            ],
        )
        rows = self.repo.list_version_items("set-1", 1)
        self.assertEqual(
            [row["exam_set_item_id"] for row in rows],
            ["item-1", "item-2"],
        )

    def test_find_assignment_uses_exam_and_employee(self):
        self.values.get.return_value.execute.return_value = self.table(
            "assignments",
            [
                _assignment(assignment_id="a-other", employee_id="E2"),
                _assignment(assignment_id="a-target"),
            ],
        )
        found = self.repo.find_assignment("exam-1", "E1")
        self.assertEqual(found["assignment_id"], "a-target")

    def test_list_active_assignments_filters_employee_and_status(self):
        self.values.get.return_value.execute.return_value = self.table(
            "assignments",
            [
                _assignment(assignment_id="a-active"),
                _assignment(assignment_id="a-cancelled", status="cancelled"),
                _assignment(assignment_id="a-other", employee_id="E2"),
            ],
        )
        rows = self.repo.list_active_assignments("E1")
        self.assertEqual([row["assignment_id"] for row in rows], ["a-active"])

    def test_assignment_upsert_updates_existing_row(self):
        self.values.get.return_value.execute.return_value = self.table(
            "assignments", [_assignment()]
        )
        self.repo.upsert_assignment(_assignment(
            status="cancelled",
            cancelled_by="admin-2",
            cancelled_at="2026-07-16T00:00:00+00:00",
            row_version=2,
        ))
        self.values.update.assert_called_once()
        headers = SHEET_HEADERS["assignments"]
        row = self.values.update.call_args.kwargs["body"]["values"][0]
        self.assertEqual(row[headers.index("status")], "cancelled")
        self.assertEqual(row[headers.index("cancelled_by")], "admin-2")
        self.values.append.assert_not_called()

    def test_assignment_upsert_appends_new_row(self):
        self.values.get.return_value.execute.return_value = self.table("assignments")
        self.repo.upsert_assignment(_assignment())
        self.values.append.assert_called_once()
        self.values.update.assert_not_called()

    def test_api_errors_propagate_without_fallback(self):
        self.values.get.return_value.execute.side_effect = RuntimeError("read failed")
        with self.assertRaisesRegex(RuntimeError, "read failed"):
            self.repo.find_current_version("set-1")


class ExamV2FactoryTests(unittest.TestCase):
    def test_defaults_do_not_construct_repository(self):
        self.assertIsNone(build_exam_v2_repository(use_sheets=True, env={}))

    def test_local_backend_does_not_construct_repository(self):
        env = {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
        }
        self.assertIsNone(build_exam_v2_repository(use_sheets=False, env=env))

    def test_dual_sheets_frozen_flag_constructs_repository(self):
        env = {
            "OJT_SHEETS_SCHEMA_MODE": "dual",
            "OJT_USE_FROZEN_EXAM": "true",
        }
        repo = build_exam_v2_repository(
            use_sheets=True,
            env=env,
            service=MagicMock(),
            spreadsheet_id="copy-sheet",
        )
        self.assertIsInstance(repo, SheetsExamV2Repository)


if __name__ == "__main__":
    unittest.main()
