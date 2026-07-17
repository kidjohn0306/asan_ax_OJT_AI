import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import admin_service


class FakeQuestions:
    def __init__(self, fail_update=False):
        self.question = {
            "question_id": "Q1",
            "candidate_id": "cand-1",
            "category": "팀별",
            "question": "안전 확인 방법은?",
            "option_a": "A",
            "option_b": "B",
            "option_c": "C",
            "option_d": "D",
            "answer": "A",
            "explanation": "근거",
            "difficulty_init": "하",
            "admin_override": "하",
            "status": "reviewing",
            "version": 1,
            "flags": {"candidate_id": "cand-1"},
        }
        self.fail_update = fail_update
        self.events = []

    def get_question(self, question_id):
        return self.question if question_id == "Q1" else None

    def update_question(self, question_id, fields):
        self.events.append("legacy")
        if self.fail_update:
            raise RuntimeError("legacy update failed")
        self.question.update(fields)


class FakeV2:
    def __init__(self, fail_review=False, events=None):
        self.fail_review = fail_review
        self.events = events if events is not None else []
        self.reviews = []
        self.candidates = []

    def record_review(self, review, history):
        self.events.append("review")
        if self.fail_review:
            raise RuntimeError("review failed")
        self.reviews.append((dict(review), dict(history)))

    def update_candidate(self, candidate_id, fields):
        self.events.append("candidate")
        self.candidates.append((candidate_id, dict(fields)))


class QuestionReviewDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.questions = FakeQuestions()
        self.events = self.questions.events
        self.v2 = FakeV2(events=self.events)
        self.actor = {"sub": "admin-1", "role": "admin"}
        self.repo_patches = [
            patch("repositories.question_repo", self.questions),
            patch("repositories.generation_v2_repo", self.v2),
        ]
        for repo_patch in self.repo_patches:
            repo_patch.start()
            self.addCleanup(repo_patch.stop)

    def env(self, mode="dual", enabled="true"):
        return patch.dict("os.environ", {
            "OJT_SHEETS_SCHEMA_MODE": mode,
            "OJT_USE_CANDIDATE_TAB": enabled,
            "OJT_GATE_MODE": "legacy",
        }, clear=False)

    def test_legacy_default_does_not_write_review(self):
        with self.env(mode="legacy", enabled="false"):
            result = admin_service.approve_question("Q1", actor=self.actor)
        self.assertTrue(result["approved"])
        self.assertEqual(self.v2.reviews, [])

    def test_dual_approval_records_review_before_legacy_update(self):
        with self.env():
            result = admin_service.approve_question("Q1", actor=self.actor)
        self.assertTrue(result["approved"])
        self.assertEqual(self.events, ["review", "candidate", "legacy"])
        review, history = self.v2.reviews[0]
        self.assertEqual(review["reviewer_id"], "admin-1")
        self.assertEqual(review["review_action"], "APPROVE")
        self.assertEqual(history["action"], "APPROVE")
        self.assertEqual(self.questions.question["status"], "approved")

    def test_dual_rejection_records_actor_reason_and_snapshots(self):
        with self.env():
            result = admin_service.reject_question(
                "Q1", "근거 부족", actor=self.actor
            )
        self.assertTrue(result["rejected"])
        review, history = self.v2.reviews[0]
        self.assertEqual(review["reviewer_id"], "admin-1")
        self.assertEqual(review["reason"], "근거 부족")
        self.assertIn('"status": "reviewing"', review["before_payload_json"])
        self.assertIn('"status": "rejected"', review["after_payload_json"])
        self.assertEqual(history["reason"], "근거 부족")

    def test_review_failure_leaves_legacy_state_unchanged(self):
        self.v2.fail_review = True
        with self.env():
            with self.assertRaises(HTTPException) as raised:
                admin_service.approve_question("Q1", actor=self.actor)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.questions.question["status"], "reviewing")
        self.assertNotIn("legacy", self.events)

    def test_legacy_failure_after_review_returns_503(self):
        self.questions.fail_update = True
        with self.env():
            with self.assertRaises(HTTPException) as raised:
                admin_service.reject_question("Q1", "반려", actor=self.actor)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(len(self.v2.reviews), 1)


if __name__ == "__main__":
    unittest.main()
