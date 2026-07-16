import json
import unittest
from unittest.mock import MagicMock

import repositories
from repositories.sheets_repo import HEADERS, SheetsExamSetRepository, _COLUMNS
from schema.sheets_v2 import SHEET_HEADERS


class ExamSetExtensionTests(unittest.TestCase):
    def test_legacy_headers_remain_exact_canonical_prefix(self):
        self.assertEqual(HEADERS, list(SHEET_HEADERS["exam_sets"][:11]))

    def test_row_parser_exposes_frozen_exam_extensions(self):
        headers = SHEET_HEADERS["exam_sets"]
        values = {
            "exam_set_id": "set-1",
            "name": "연습 시험",
            "team_code": "T1",
            "question_ids": '["Q1"]',
            "assigned_users": '["E1"]',
            "pass_score": "70",
            "status": "active",
            "exam_id": "exam-1",
            "evaluation_type": "practice",
            "blueprint_json": '{"scores":{"Q1":100}}',
            "frozen_at": "2026-07-15T00:00:00+00:00",
            "frozen_by": "admin-1",
            "paper_version": "2",
            "snapshot_checksum": "sha256-value",
            "row_version": "3",
            "confirmed_by": "admin-1",
            "confirmed_at": "2026-07-15T00:00:00+00:00",
            "current_exam_version_id": "ver-2",
            "idempotency_key": "request-1",
            "duration_minutes": "90",
        }
        row = [values.get(header, "") for header in headers]

        parsed = SheetsExamSetRepository._row_to_dict(row)

        self.assertEqual(parsed["evaluation_type"], "practice")
        self.assertEqual(parsed["blueprint_json"], {"scores": {"Q1": 100}})
        self.assertEqual(parsed["frozen_by"], "admin-1")
        self.assertEqual(parsed["paper_version"], 2)
        self.assertEqual(parsed["row_version"], 3)
        self.assertEqual(parsed["current_exam_version_id"], "ver-2")
        self.assertEqual(parsed["idempotency_key"], "request-1")
        self.assertEqual(parsed["duration_min"], 90)

    def test_read_all_rows_uses_full_canonical_width(self):
        repo = SheetsExamSetRepository.__new__(SheetsExamSetRepository)
        repo._spreadsheet_id = "copy-sheet"
        values = MagicMock()
        values.get.return_value.execute.return_value = {
            "values": [list(SHEET_HEADERS["exam_sets"])]
        }
        repo._values = MagicMock(return_value=values)

        self.assertEqual(repo._read_all_rows(), [])

        self.assertEqual(
            values.get.call_args.kwargs["range"],
            "exam_sets!A:AH",
        )

    def test_extended_columns_use_canonical_column_letters(self):
        self.assertEqual(_COLUMNS["evaluation_type"], "N")
        self.assertEqual(_COLUMNS["frozen_at"], "P")
        self.assertEqual(_COLUMNS["frozen_by"], "Q")
        self.assertEqual(_COLUMNS["paper_version"], "R")
        self.assertEqual(_COLUMNS["snapshot_checksum"], "S")
        self.assertEqual(_COLUMNS["row_version"], "T")
        self.assertEqual(_COLUMNS["confirmed_by"], "AA")
        self.assertEqual(_COLUMNS["confirmed_at"], "AB")
        self.assertEqual(_COLUMNS["current_exam_version_id"], "AG")
        self.assertEqual(_COLUMNS["idempotency_key"], "AH")
        self.assertEqual(_COLUMNS["duration_min"], "X")

    def test_update_serializes_extended_json_and_writes_exact_columns(self):
        repo = SheetsExamSetRepository.__new__(SheetsExamSetRepository)
        repo._spreadsheet_id = "copy-sheet"
        repo._tab_ready = True
        repo._find_sheet_row = MagicMock(return_value=2)
        values = MagicMock()
        repo._values = MagicMock(return_value=values)

        result = repo.update_exam_set("exam-1", {
            "evaluation_type": "practice",
            "blueprint_json": {"scores": {"Q1": 100}},
            "current_exam_version_id": "ver-1",
            "duration_min": 90,
        })

        self.assertTrue(result)
        data = values.batchUpdate.call_args.kwargs["body"]["data"]
        self.assertEqual(
            [entry["range"] for entry in data],
            ["exam_sets!N2", "exam_sets!O2", "exam_sets!AG2", "exam_sets!X2"],
        )
        self.assertEqual(
            data[1]["values"],
            [[json.dumps({"scores": {"Q1": 100}}, ensure_ascii=False, sort_keys=True)]],
        )

    def test_default_repository_factory_exposes_inert_exam_v2_repo(self):
        self.assertTrue(hasattr(repositories, "exam_v2_repo"))
        self.assertIsNone(repositories.exam_v2_repo)


if __name__ == "__main__":
    unittest.main()
