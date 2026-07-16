import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import admin_service


class FakeQuestions:
    def __init__(self, statuses):
        self.statuses = statuses

    def get_question(self, question_id):
        status = self.statuses.get(question_id)
        return None if status is None else {
            "question_id": question_id,
            "status": status,
        }


class FakeExamSets:
    def __init__(self, exam_sets=None):
        self.exam_sets = exam_sets or []

    def create_exam_set(self, data):
        return data

    def list_exam_sets(self):
        return self.exam_sets


class ExamSetApprovalGuardTests(unittest.TestCase):
    def test_all_approved_questions_are_accepted(self):
        with patch("repositories.question_repo", FakeQuestions({"Q1": "approved"})), \
             patch("repositories.exam_set_repo", FakeExamSets()):
            result = admin_service.create_exam_set("시험", "T1", ["Q1"])
        self.assertEqual(result["question_ids"], ["Q1"])

    def test_reviewing_question_is_rejected(self):
        with patch("repositories.question_repo", FakeQuestions({"Q1": "reviewing"})), \
             patch("repositories.exam_set_repo", FakeExamSets()):
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set("시험", "T1", ["Q1"])
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"],
            "EXAM_QUESTION_NOT_APPROVED",
        )

    def test_missing_question_is_rejected(self):
        with patch("repositories.question_repo", FakeQuestions({})), \
             patch("repositories.exam_set_repo", FakeExamSets()):
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set("시험", "T1", ["missing"])
        self.assertIn("missing", raised.exception.detail["question_ids"])

    def test_empty_question_list_is_rejected(self):
        with patch("repositories.question_repo", FakeQuestions({})), \
             patch("repositories.exam_set_repo", FakeExamSets()):
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set("시험", "T1", [])
        self.assertEqual(raised.exception.status_code, 400)

    def test_new_round_revalidates_source_questions(self):
        exam_sets = FakeExamSets([{
            "exam_set_id": "set-1",
            "name": "기존 시험지",
            "team_code": "T1",
            "question_ids": ["Q1"],
        }])
        with patch("repositories.question_repo", FakeQuestions({"Q1": "reviewing"})), \
             patch("repositories.exam_set_repo", exam_sets):
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_round_from_paper("set-1")
        self.assertEqual(
            raised.exception.detail["code"],
            "EXAM_QUESTION_NOT_APPROVED",
        )


if __name__ == "__main__":
    unittest.main()
