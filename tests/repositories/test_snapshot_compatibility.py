import json
import unittest

from repositories.sheets_repo import _parse_snapshot_row


SNAPSHOT = {"Q-1": {"answer": "A"}, "_meta": {"team_code": "T1"}}
STAMP = "2026-07-04T05:41:34.859878+00:00"


class SnapshotCompatibilityTests(unittest.TestCase):
    def test_reads_canonical_created_at_then_json(self):
        result_id, created_at, data = _parse_snapshot_row(
            ["result-1", STAMP, json.dumps(SNAPSHOT)]
        )
        self.assertEqual((result_id, created_at, data), ("result-1", STAMP, SNAPSHOT))

    def test_reads_legacy_swapped_json_then_created_at(self):
        result_id, created_at, data = _parse_snapshot_row(
            ["result-2", json.dumps(SNAPSHOT), STAMP]
        )
        self.assertEqual((result_id, created_at, data), ("result-2", STAMP, SNAPSHOT))

    def test_rejects_row_without_json_object(self):
        with self.assertRaisesRegex(ValueError, "snapshot row"):
            _parse_snapshot_row(["result-3", STAMP, "not-json"])


if __name__ == "__main__":
    unittest.main()
