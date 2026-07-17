import unittest
from unittest.mock import MagicMock

from repositories.audit_v2 import SheetsAuditV2Repository, build_audit_v2_repository
from schema.sheets_v2 import SHEET_HEADERS


class SheetsAuditV2RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.values = self.service.spreadsheets.return_value.values.return_value
        self.repo = SheetsAuditV2Repository(service=self.service, spreadsheet_id="copy-sheet")

    def table(self, rows=None):
        return {"values": [list(SHEET_HEADERS["audit_logs"]), *(rows or [])]}

    def test_constructor_performs_no_external_call(self):
        self.service.spreadsheets.assert_not_called()

    def test_record_appends_a_single_row(self):
        self.repo.record(
            actor_id="admin-1", actor_role="admin",
            action_type="APPROVE_QUESTION", target_type="question", target_id="Q1",
            before={"status": "reviewing"}, after={"status": "approved"}, reason="ok",
        )
        self.values.append.assert_called_once()
        body = self.values.append.call_args.kwargs["body"]
        row = dict(zip(SHEET_HEADERS["audit_logs"], body["values"][0]))
        self.assertEqual(row["actor_id"], "admin-1")
        self.assertEqual(row["action_type"], "APPROVE_QUESTION")
        self.assertEqual(row["target_id"], "Q1")
        self.assertTrue(row["audit_id"].startswith("audit-"))

    def test_list_logs_sorted_newest_first_and_limited(self):
        headers = SHEET_HEADERS["audit_logs"]
        older = [""] * len(headers)
        older[headers.index("audit_id")] = "audit-old"
        older[headers.index("created_at")] = "2026-01-01T00:00:00+00:00"
        newer = [""] * len(headers)
        newer[headers.index("audit_id")] = "audit-new"
        newer[headers.index("created_at")] = "2026-06-01T00:00:00+00:00"
        self.values.get.return_value.execute.return_value = self.table([older, newer])

        logs = self.repo.list_logs(limit=1)

        self.assertEqual([log["audit_id"] for log in logs], ["audit-new"])

    def test_list_logs_on_empty_sheet_returns_empty_list(self):
        self.values.get.return_value.execute.return_value = self.table([])
        self.assertEqual(self.repo.list_logs(), [])


class AuditFactoryTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertIsNone(build_audit_v2_repository(enabled=False))

    def test_enabled_constructs_repository(self):
        repo = build_audit_v2_repository(enabled=True, service=MagicMock(), spreadsheet_id="copy-sheet")
        self.assertIsInstance(repo, SheetsAuditV2Repository)


if __name__ == "__main__":
    unittest.main()
