import unittest
from unittest.mock import MagicMock, patch

from services import admin_service
from services.admin_service import approve_question, fetch_audit_logs, reject_question


class FakeQuestions:
    def __init__(self):
        self.question = {
            "question_id": "Q1",
            "status": "reviewing",
            "flags": {},
        }

    def get_question(self, question_id):
        return self.question if question_id == "Q1" else None

    def update_question(self, question_id, fields):
        self.question.update(fields)


class FetchAuditLogsTests(unittest.TestCase):
    def test_returns_disabled_when_repository_not_configured(self):
        with patch("repositories.audit_repo", None):
            result = fetch_audit_logs()
        self.assertEqual(result, {"logs": [], "enabled": False})

    def test_returns_logs_from_repository_when_configured(self):
        repo = MagicMock()
        repo.list_logs.return_value = [{"audit_id": "audit-1"}]
        with patch("repositories.audit_repo", repo):
            result = fetch_audit_logs()
        self.assertEqual(result, {"logs": [{"audit_id": "audit-1"}], "enabled": True})
        repo.list_logs.assert_called_once()


class ApproveRejectAuditHookTests(unittest.TestCase):
    def setUp(self):
        self.questions = FakeQuestions()
        patcher = patch("repositories.question_repo", self.questions)
        patcher.start()
        self.addCleanup(patcher.stop)
        gen_patcher = patch("repositories.generation_v2_repo", None)
        gen_patcher.start()
        self.addCleanup(gen_patcher.stop)

    def test_approve_question_records_audit_entry(self):
        audit_repo = MagicMock()
        with patch("repositories.audit_repo", audit_repo):
            approve_question("Q1", actor={"sub": "admin-1", "role": "admin"})
        audit_repo.record.assert_called_once()
        kwargs = audit_repo.record.call_args.kwargs
        self.assertEqual(kwargs["actor_id"], "admin-1")
        self.assertEqual(kwargs["action_type"], "APPROVE_QUESTION")
        self.assertEqual(kwargs["target_id"], "Q1")

    def test_reject_question_records_audit_entry(self):
        audit_repo = MagicMock()
        with patch("repositories.audit_repo", audit_repo):
            reject_question("Q1", "reason text", actor={"sub": "admin-1", "role": "admin"})
        audit_repo.record.assert_called_once()
        self.assertEqual(audit_repo.record.call_args.kwargs["action_type"], "REJECT_QUESTION")

    def test_audit_write_failure_does_not_break_approval(self):
        audit_repo = MagicMock()
        audit_repo.record.side_effect = RuntimeError("sheets down")
        with patch("repositories.audit_repo", audit_repo):
            result = approve_question("Q1", actor={"sub": "admin-1", "role": "admin"})
        self.assertTrue(result["approved"])

    def test_no_audit_write_when_repository_not_configured(self):
        with patch("repositories.audit_repo", None):
            result = approve_question("Q1", actor={"sub": "admin-1", "role": "admin"})
        self.assertTrue(result["approved"])


if __name__ == "__main__":
    unittest.main()
