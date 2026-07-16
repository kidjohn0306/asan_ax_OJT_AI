import unittest

from schema.sheets_v2 import SHEET_HEADERS, header_hash
from services.schema_service import (
    build_schema_plan,
    inspect_schema,
    validate_primary_keys,
)


def canonical_actual():
    return {name: list(headers) for name, headers in SHEET_HEADERS.items()}


class SchemaInspectionTests(unittest.TestCase):
    def test_missing_sheet_is_reported_and_planned_for_creation(self):
        actual = canonical_actual()
        del actual["materials"]

        report = inspect_schema(actual)
        actions = build_schema_plan(actual)

        self.assertIn("MISSING_SHEET", [issue.code for issue in report.issues])
        self.assertFalse(report.blocking_issues)
        self.assertEqual(
            [(action.kind, action.sheet) for action in actions],
            [("CREATE_SHEET", "materials")],
        )

    def test_legacy_prefix_mismatch_blocks_apply(self):
        actual = canonical_actual()
        actual["results"][0:2] = ["exam_id", "result_id"]

        report = inspect_schema(actual)

        self.assertIn(
            "LEGACY_PREFIX_MISMATCH",
            [issue.code for issue in report.blocking_issues],
        )
        self.assertEqual(build_schema_plan(actual), [])

    def test_missing_legacy_suffix_creates_append_action(self):
        actual = canonical_actual()
        actual["results"] = actual["results"][:10]

        actions = build_schema_plan(actual)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, "APPEND_HEADERS")
        self.assertEqual(actions[0].sheet, "results")
        self.assertEqual(actions[0].start_index, 10)
        self.assertEqual(actions[0].headers, SHEET_HEADERS["results"][10:])

    def test_unexpected_extended_header_blocks_apply(self):
        actual = canonical_actual()
        actual["results"][10] = "unexpected_assignment"

        report = inspect_schema(actual)

        self.assertIn("HEADER_MISMATCH", [i.code for i in report.blocking_issues])
        self.assertEqual(build_schema_plan(actual), [])

    def test_empty_normalized_sheet_can_recover_header_initialization(self):
        actual = canonical_actual()
        actual["materials"] = []

        report = inspect_schema(actual)
        actions = build_schema_plan(actual)

        self.assertFalse(report.blocking_issues)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, "APPEND_HEADERS")
        self.assertEqual(actions[0].sheet, "materials")
        self.assertEqual(actions[0].start_index, 0)
        self.assertEqual(actions[0].headers, SHEET_HEADERS["materials"])

    def test_exact_schema_has_matching_hashes_and_no_actions(self):
        actual = canonical_actual()

        report = inspect_schema(actual)

        self.assertTrue(report.is_valid)
        self.assertEqual(report.issues, ())
        self.assertEqual(build_schema_plan(actual), [])
        self.assertEqual(
            report.actual_hashes["question_bank"],
            header_hash(SHEET_HEADERS["question_bank"]),
        )


class PrimaryKeyValidationTests(unittest.TestCase):
    def test_duplicate_non_empty_primary_key_is_reported(self):
        issues = validate_primary_keys({"results": [["r1"], ["r1"]]})
        self.assertEqual([issue.code for issue in issues], ["DUPLICATE_PRIMARY_KEY"])
        self.assertEqual(issues[0].values, ("r1",))

    def test_blank_primary_key_is_reported_separately(self):
        issues = validate_primary_keys({"results": [["", "exam-1"], ["r1"]]})
        self.assertEqual([issue.code for issue in issues], ["MISSING_PRIMARY_KEY"])
        self.assertEqual(issues[0].row_numbers, (2,))

    def test_completely_blank_rows_are_ignored(self):
        issues = validate_primary_keys({"results": [[], [""], [None, None], ["r1"]]})
        self.assertEqual(issues, [])

    def test_question_bank_uses_second_column_as_primary_key(self):
        issues = validate_primary_keys({
            "question_bank": [["common", "Q1"], ["team1", "Q1"]]
        })
        self.assertEqual([issue.code for issue in issues], ["DUPLICATE_PRIMARY_KEY"])


if __name__ == "__main__":
    unittest.main()
