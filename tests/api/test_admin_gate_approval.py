"""POST /api/admin/questions/{id}/approve API 계약 테스트.
기존 body 없는 호출 하위호환과 선택적 override_reason 전달, 인증·인가를 검증한다."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import admin as admin_api
from services.auth_service import create_access_token
from services.generation.gate_service import GateContext, evaluate_candidate

VALID_QUESTION = {
    "question_type": "MULTIPLE_CHOICE_SINGLE",
    "question_id": "team2-api-001",
    "category": "팀별",
    "question": "Baffle 분리 작업의 최소 작업 인원은 몇 명인가?",
    "option_a": "1명",
    "option_b": "2명",
    "option_c": "3명",
    "option_d": "4명",
    "answer": "B",
    "explanation": "Baffle 분리 작업은 2인이 수행한다.",
    "difficulty_init": "하",
    "difficulty_ai": "하",
    "admin_override": "하",
    "status": "draft",
}

CONTEXT = GateContext(
    material_text="Baffle 분리 작업은 2인이 수행하며 최소 작업 인원은 2명이다.",
    team_code="T2",
    pool_key="team2",
    category_label="팀별",
)


class FakeAllPassVerifier:
    provider = "fake"

    def verify(self, question, context):
        return {
            "grounding": "SUPPORTED", "grounding_reason": "",
            "single_answer": "PASS", "single_answer_reason": "",
            "distractor_status": "PASS", "distractor_reason": "",
            "scope_status": "PASS", "scope_reason": "",
        }


class FakeQuestionRepository:
    def __init__(self):
        self._questions = {}

    def get_all_questions(self):
        pools = {}
        for pool_key, q in self._questions.values():
            pools.setdefault(pool_key, []).append(q)
        return pools

    def get_approved_questions(self, team_key=None, category=None):
        return [q for _, q in self._questions.values() if q.get("status") == "approved"]

    def list_by_status(self, status):
        return [q for _, q in self._questions.values() if q.get("status") == status]

    def get_question(self, question_id):
        entry = self._questions.get(question_id)
        return entry[1] if entry else None

    def add_question(self, pool_key, question):
        self._questions[question["question_id"]] = (pool_key, question)

    def update_question(self, question_id, fields):
        entry = self._questions.get(question_id)
        if entry:
            entry[1].update(fields)

    def count_by_status(self, status):
        return len(self.list_by_status(status))


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_api.router, prefix="/api/admin")
    return app


class ApprovalApiContractTests(unittest.TestCase):
    def setUp(self):
        self.fake_repo = FakeQuestionRepository()

        question = dict(VALID_QUESTION)
        question["status"] = "reviewing"
        gate_result = evaluate_candidate(question, CONTEXT, FakeAllPassVerifier(), mode="strict")
        question["flags"] = {
            "warning": gate_result["flags"]["warning"],
            "security_hold": gate_result["flags"]["security_hold"],
            "gate_snapshot": gate_result,
        }
        self.fake_repo.add_question("team2", question)
        self.question_id = question["question_id"]

        patchers = [
            patch("repositories.question_repo", self.fake_repo),
            patch.dict("os.environ", {"OJT_GATE_MODE": "strict"}),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        self.client = TestClient(_make_app())
        self.admin_token = create_access_token({"sub": "admin001", "role": "admin"})
        self.user_token = create_access_token({"sub": "2024001", "role": "examinee"})

    def _approve_url(self) -> str:
        return f"/api/admin/questions/{self.question_id}/approve"

    def _reject_url(self) -> str:
        return f"/api/admin/questions/{self.question_id}/reject"

    def test_approve_without_body_succeeds_when_all_pass(self):
        resp = self.client.post(
            self._approve_url(), headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["approved"])

    def test_approve_with_override_reason_body_is_forwarded(self):
        resp = self.client.post(
            self._approve_url(),
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"override_reason": "관리자 확인 후 승인"},
        )
        self.assertEqual(resp.status_code, 200)
        _, stored = list(self.fake_repo._questions.values())[0]
        self.assertEqual(stored["flags"]["gate_approval"]["override_reason"], "관리자 확인 후 승인")
        self.assertEqual(stored["flags"]["gate_approval"]["approved_by"], "admin001")

    def test_approve_rejects_non_admin_token(self):
        resp = self.client.post(
            self._approve_url(), headers={"Authorization": f"Bearer {self.user_token}"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_approve_rejects_missing_token(self):
        resp = self.client.post(self._approve_url())
        self.assertEqual(resp.status_code, 401)

    def test_reject_forwards_authenticated_actor(self):
        with patch(
            "services.admin_service.reject_question",
            return_value={"rejected": True, "question_id": self.question_id},
        ) as reject:
            resp = self.client.post(
                self._reject_url(),
                headers={"Authorization": f"Bearer {self.admin_token}"},
                json={"reason": "근거 부족"},
            )
        self.assertEqual(resp.status_code, 200)
        reject.assert_called_once()
        args, kwargs = reject.call_args
        self.assertEqual(args, (self.question_id, "근거 부족"))
        self.assertEqual(kwargs["actor"]["sub"], "admin001")
        self.assertEqual(kwargs["actor"]["role"], "admin")


if __name__ == "__main__":
    unittest.main()
