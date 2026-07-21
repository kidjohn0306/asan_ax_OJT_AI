import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import admin as admin_api
from services.auth_service import create_access_token


def _make_app():
    app = FastAPI()
    app.include_router(admin_api.router, prefix="/api/admin")
    return app


class AdminExamDualWriteApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_make_app())
        self.admin_token = create_access_token({
            "sub": "admin001",
            "role": "admin",
        })
        self.headers = {"Authorization": f"Bearer {self.admin_token}"}

    def test_create_exam_forwards_scores_type_key_and_actor(self):
        response_data = {
            "exam_set_id": "set-1",
            "exam_id": "exam-1",
            "exam_version_id": "ver-1",
        }
        with patch(
            "services.admin_service.create_exam_set",
            return_value=response_data,
        ) as create:
            response = self.client.post(
                "/api/admin/exam-sets",
                headers=self.headers,
                json={
                    "name": "연습 시험",
                    "team_code": "T1",
                    "question_ids": ["Q1", "Q2"],
                    "question_scores": {"Q1": 60, "Q2": 40},
                    "evaluation_type": "practice",
                    "idempotency_key": "request-1",
                },
            )
        self.assertEqual(response.status_code, 200)
        create.assert_called_once_with(
            "연습 시험",
            "T1",
            ["Q1", "Q2"],
            created_by="admin001",
            question_scores={"Q1": 60, "Q2": 40},
            evaluation_type="practice",
            exam_category="exam_study",
            idempotency_key="request-1",
            created_by_name="",
        )

    def test_create_exam_forwards_compatible_defaults(self):
        with patch(
            "services.admin_service.create_exam_set",
            return_value={"exam_id": "exam-1"},
        ) as create:
            response = self.client.post(
                "/api/admin/exam-sets",
                headers=self.headers,
                json={
                    "name": "공식 시험",
                    "team_code": "T2",
                    "question_ids": ["Q1"],
                },
            )
        self.assertEqual(response.status_code, 200)
        create.assert_called_once_with(
            "공식 시험",
            "T2",
            ["Q1"],
            created_by="admin001",
            question_scores=None,
            evaluation_type="official",
            exam_category="exam_study",
            idempotency_key="",
            created_by_name="",
        )

    def test_from_paper_forwards_type_key_and_actor(self):
        with patch(
            "services.admin_service.create_exam_round_from_paper",
            return_value={"exam_id": "exam-2"},
        ) as create:
            response = self.client.post(
                "/api/admin/exam-sets/from-paper",
                headers=self.headers,
                json={
                    "exam_set_id": "set-1",
                    "name": "연습 회차",
                    "evaluation_type": "practice",
                    "idempotency_key": "round-1",
                },
            )
        self.assertEqual(response.status_code, 200)
        create.assert_called_once_with(
            "set-1",
            "연습 회차",
            created_by="admin001",
            evaluation_type="practice",
            idempotency_key="round-1",
            exam_datetime=None,
            pass_score=None,
            duration_min=None,
            created_by_name="",
        )

    def test_from_paper_forwards_schedule_score_and_duration(self):
        with patch(
            "services.admin_service.create_exam_round_from_paper",
            return_value={"exam_id": "exam-2"},
        ) as create:
            response = self.client.post(
                "/api/admin/exam-sets/from-paper",
                headers=self.headers,
                json={
                    "exam_set_id": "set-1",
                    "exam_datetime": "2026-07-20T09:00",
                    "pass_score": 80,
                    "duration_min": 90,
                },
            )
        self.assertEqual(response.status_code, 200)
        create.assert_called_once_with(
            "set-1",
            None,
            created_by="admin001",
            evaluation_type=None,
            idempotency_key="",
            exam_datetime="2026-07-20T09:00",
            pass_score=80,
            duration_min=90,
            created_by_name="",
        )

    def test_invalid_evaluation_type_is_422(self):
        response = self.client.post(
            "/api/admin/exam-sets",
            headers=self.headers,
            json={
                "name": "잘못된 시험",
                "team_code": "T1",
                "question_ids": ["Q1"],
                "evaluation_type": "unknown",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_invalid_exam_category_is_422(self):
        response = self.client.post(
            "/api/admin/exam-sets",
            headers=self.headers,
            json={
                "name": "잘못된 시험",
                "team_code": "T1",
                "question_ids": ["Q1"],
                "exam_category": "unknown",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_assign_forwards_authenticated_actor(self):
        with patch(
            "services.admin_service.assign_user_to_exam_set",
            return_value={"success": True},
        ) as assign:
            response = self.client.post(
                "/api/admin/exam-sets/exam-1/assign",
                headers=self.headers,
                json={"employee_id": "E1"},
            )
        self.assertEqual(response.status_code, 200)
        assign.assert_called_once_with(
            "E1",
            "exam-1",
            actor={"sub": "admin001", "role": "admin"},
        )

    def test_unassign_forwards_authenticated_actor(self):
        with patch(
            "services.admin_service.unassign_user_from_exam_set",
            return_value={"success": True},
        ) as unassign:
            response = self.client.delete(
                "/api/admin/exam-sets/exam-1/assign/E1",
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200)
        unassign.assert_called_once_with(
            "E1",
            "exam-1",
            actor={"sub": "admin001", "role": "admin"},
        )

    def test_papers_route_requires_admin_and_forwards_extended_response(self):
        papers = [{
            "exam_id": "exam-1",
            "exam_set_id": "set-1",
            "name": "시험지",
            "team_code": "T1",
            "paper_version": 2,
            "question_count": 2,
            "used_by_exam_count": 3,
            "created_at": "2026-07-15T09:00:00+00:00",
        }]
        unauthorized = self.client.get("/api/admin/exam-sets/papers")
        with patch(
            "services.admin_service.list_question_papers",
            return_value=papers,
        ) as list_papers:
            response = self.client.get(
                "/api/admin/exam-sets/papers", headers=self.headers
            )
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"papers": papers})
        list_papers.assert_called_once_with()

    def test_questions_route_requires_admin_and_forwards_extended_response(self):
        details = {
            "exam_set": {
                "exam_id": "exam-1",
                "exam_set_id": "set-1",
                "exam_version_id": "ver-2",
                "paper_version": 2,
                "question_scores": {"Q1": 60, "Q2": 40},
                "immutable": True,
            },
            "questions": [{
                "question_id": "Q1",
                "question_version": 3,
                "score": 60,
            }],
        }
        unauthorized = self.client.get(
            "/api/admin/exam-sets/exam-1/questions"
        )
        with patch(
            "services.admin_service.get_exam_set_questions",
            return_value=details,
        ) as get_questions:
            response = self.client.get(
                "/api/admin/exam-sets/exam-1/questions",
                headers=self.headers,
            )
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), details)
        get_questions.assert_called_once_with("exam-1")


if __name__ == "__main__":
    unittest.main()
