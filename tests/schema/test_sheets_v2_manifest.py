import unittest

from schema.sheets_v2 import (
    LEGACY_PREFIXES,
    SHEET_HEADERS,
    header_hash,
)


class SheetsV2ManifestTests(unittest.TestCase):
    def test_manifest_has_exactly_55_unique_sheets(self):
        self.assertEqual(len(SHEET_HEADERS), 55)
        self.assertEqual(len(set(SHEET_HEADERS)), 55)

    def test_legacy_prefixes_match_current_repository_contracts(self):
        self.assertEqual(set(LEGACY_PREFIXES), {
            "results",
            "snapshots",
            "question_stats",
            "exam_sets",
            "teams",
            "users",
            "question_bank",
            "material_cache",
        })
        self.assertEqual(LEGACY_PREFIXES["results"], SHEET_HEADERS["results"][:10])
        self.assertEqual(LEGACY_PREFIXES["snapshots"], SHEET_HEADERS["snapshots"][:3])
        self.assertEqual(LEGACY_PREFIXES["question_stats"], SHEET_HEADERS["question_stats"][:4])
        self.assertEqual(LEGACY_PREFIXES["exam_sets"], SHEET_HEADERS["exam_sets"][:11])
        self.assertEqual(LEGACY_PREFIXES["teams"], SHEET_HEADERS["teams"][:5])
        self.assertEqual(LEGACY_PREFIXES["users"], SHEET_HEADERS["users"][:7])
        self.assertEqual(LEGACY_PREFIXES["question_bank"], SHEET_HEADERS["question_bank"][:18])
        self.assertEqual(LEGACY_PREFIXES["material_cache"], SHEET_HEADERS["material_cache"][:3])

    def test_representative_actual_header_widths(self):
        self.assertEqual(len(SHEET_HEADERS["results"]), 26)
        self.assertEqual(len(SHEET_HEADERS["exam_sets"]), 34)
        self.assertEqual(len(SHEET_HEADERS["question_bank"]), 43)
        self.assertEqual(len(SHEET_HEADERS["materials"]), 31)

    def test_header_hash_is_stable_and_order_sensitive(self):
        self.assertEqual(
            header_hash(["a", "b"]),
            "0473ef2dc0d324ab659d3580c1134e9d812035905c4781fdd6d529b0c6860e13",
        )
        self.assertNotEqual(header_hash(["a", "b"]), header_hash(["b", "a"]))


if __name__ == "__main__":
    unittest.main()
