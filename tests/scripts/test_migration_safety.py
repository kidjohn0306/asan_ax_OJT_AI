import unittest
from unittest.mock import MagicMock, patch

from scripts import migrate_exam_sets_pk, migrate_questions_to_sheets
from scripts.migrate_exam_sets_pk import build_exam_id_updates
from scripts.migrate_questions_to_sheets import build_question_rows


class MigrationSafetyTests(unittest.TestCase):
    def test_exam_id_backfill_targets_column_k(self):
        rows = [[
            "set-1", "시험", "T1", "[]", "[]", "", "", "70",
            "active", "admin", "",
        ]]
        self.assertEqual(
            build_exam_id_updates(rows),
            [{"range": "exam_sets!K2", "values": [["set-1"]]}],
        )

    def test_existing_exam_id_is_not_overwritten(self):
        rows = [[
            "set-1", "시험", "T1", "[]", "[]", "", "", "70",
            "active", "admin", "exam-1",
        ]]
        self.assertEqual(build_exam_id_updates(rows), [])

    def test_existing_question_id_is_skipped(self):
        data = {
            "team1": [
                {"question_id": "Q-1", "question": "existing"},
                {"question_id": "Q-2", "question": "new"},
            ]
        }
        rows = build_question_rows(data, {"Q-1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Q-2")

    @patch.object(migrate_exam_sets_pk, "_ensure_tab")
    @patch.object(migrate_exam_sets_pk, "SheetsExamSetRepository")
    def test_exam_backfill_dry_run_does_not_write(self, repo_class, ensure_tab):
        repo = repo_class.return_value
        repo._spreadsheet_id = "sheet-copy"
        repo._read_all_rows.return_value = [["set-1"]]
        repo_class._row_to_dict.return_value = {
            "exam_set_id": "set-1",
            "exam_id": "",
        }

        migrate_exam_sets_pk.main([])

        ensure_tab.assert_not_called()
        repo._values.assert_not_called()

    @patch.object(migrate_questions_to_sheets, "SheetsQuestionRepository")
    @patch.object(migrate_questions_to_sheets, "LocalQuestionRepository")
    def test_question_migration_dry_run_does_not_write(self, local_class, sheets_class):
        local_class.return_value.get_all_questions.return_value = {
            "team1": [{"question_id": "Q-2"}]
        }
        sheets = sheets_class.return_value
        sheets._spreadsheet_id = "sheet-copy"
        sheets._read_all_rows.return_value = []
        sheets_class._dict_to_row = MagicMock(return_value=["team1", "Q-2"])

        migrate_questions_to_sheets.main([])

        sheets._maybe_ensure_tab.assert_not_called()
        sheets._values.assert_not_called()


if __name__ == "__main__":
    unittest.main()
