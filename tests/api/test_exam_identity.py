import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import exam as exam_api
from services.auth_service import create_access_token


class ExamIdentityTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(exam_api.router, prefix="/api/exam")
        self.client = TestClient(app)
        self.token = create_access_token({
            "sub": "2024001",
            "name": "홍길동",
            "role": "examinee",
            "team": "T1",
        })
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @patch("services.exam_service.generate_exam_questions")
    def test_generate_rejects_mismatched_claimed_employee(self, generate):
        generate.return_value = {"questions": []}
        response = self.client.post(
            "/api/exam/generate",
            headers=self.headers,
            json={"team_code": "T2", "employee_id": "2024999"},
        )
        self.assertEqual(response.status_code, 403)
        generate.assert_not_called()

    @patch("services.exam_service.generate_exam_questions")
    def test_generate_uses_jwt_identity_and_team(self, generate):
        generate.return_value = {"questions": []}
        response = self.client.post(
            "/api/exam/generate",
            headers=self.headers,
            json={"team_code": "T2"},
        )
        self.assertEqual(response.status_code, 200)
        generate.assert_called_once_with("T1", employee_id="2024001")

    def test_assigned_name_requires_authentication(self):
        response = self.client.get("/api/exam/assigned-name?employee_id=2024001")
        self.assertEqual(response.status_code, 401)

    @patch("services.exam_service.get_assigned_exam_preview")
    def test_assigned_name_returns_duration_and_question_count(self, get_preview):
        get_preview.return_value = {
            "name": "OJT 심화평가",
            "duration_min": 10,
            "question_count": 25,
        }
        response = self.client.get("/api/exam/assigned-name", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "name": "OJT 심화평가",
            "duration_min": 10,
            "question_count": 25,
        })
        get_preview.assert_called_once_with("2024001")

    def test_exit_event_requires_authentication(self):
        response = self.client.post("/api/exam/exit-event", json={"reason": "tab_switch"})
        self.assertEqual(response.status_code, 401)

    @patch("services.exam_service.record_exam_exit_event")
    def test_exit_event_forwards_identity_reason_and_result_id(self, record_exit):
        response = self.client.post(
            "/api/exam/exit-event",
            headers=self.headers,
            json={"reason": "tab_switch", "result_id": "r1"},
        )
        self.assertEqual(response.status_code, 200)
        record_exit.assert_called_once_with("2024001", "홍길동", "tab_switch", "r1")

    def test_exit_event_rejects_unknown_reason(self):
        response = self.client.post(
            "/api/exam/exit-event",
            headers=self.headers,
            json={"reason": "unknown_reason"},
        )
        self.assertEqual(response.status_code, 422)

    @patch("services.exam_service.score_and_save")
    def test_submit_uses_jwt_identity_and_name(self, score_and_save):
        score_and_save.return_value = {"result_id": "r1"}
        response = self.client.post(
            "/api/exam/submit",
            headers=self.headers,
            json={
                "result_id": "r1",
                "answers": {},
                "response_times": {},
                "name": "위조 이름",
            },
        )
        self.assertEqual(response.status_code, 200)
        score_and_save.assert_called_once_with(
            "r1",
            {},
            {},
            "2024001",
            "홍길동",
            skip_save=False,
            submission_idempotency_key="",
        )

    @patch("services.exam_service.score_and_save")
    def test_submit_forwards_idempotency_key(self, score_and_save):
        score_and_save.return_value = {"result_id": "r1"}
        response = self.client.post(
            "/api/exam/submit",
            headers=self.headers,
            json={
                "result_id": "r1",
                "answers": {"Q1": "A"},
                "response_times": {"Q1": 1.5},
                "submission_idempotency_key": "submit-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        score_and_save.assert_called_once_with(
            "r1",
            {"Q1": "A"},
            {"Q1": 1.5},
            "2024001",
            "홍길동",
            skip_save=False,
            submission_idempotency_key="submit-1",
        )

    @patch("services.exam_service.score_and_save")
    def test_submit_rejects_mismatched_claimed_employee(self, score_and_save):
        response = self.client.post(
            "/api/exam/submit",
            headers=self.headers,
            json={
                "result_id": "r1",
                "answers": {},
                "response_times": {},
                "employee_id": "2024999",
            },
        )
        self.assertEqual(response.status_code, 403)
        score_and_save.assert_not_called()

    @patch("services.exam_service.get_exam_result")
    def test_result_passes_requester_identity(self, get_result):
        get_result.return_value = {"result_id": "r1"}
        response = self.client.get("/api/exam/result/r1", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        get_result.assert_called_once_with("r1", "2024001", "examinee")

    def test_examinee_cannot_read_another_users_result(self):
        with patch("repositories.result_repo.get_result", return_value={
            "result_id": "r1",
            "employee_id": "2024002",
        }):
            response = self.client.get("/api/exam/result/r1", headers=self.headers)
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
