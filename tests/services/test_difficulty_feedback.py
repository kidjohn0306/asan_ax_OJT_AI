"""난이도 AI 자동 확정 피드백 루프 검증.

1) LocalFeedbackRepository.list_recent_feedback()이 최신순으로 limit개를 반환하는지
2) override_difficulty()가 실제 피드백 이력을 반영해 3연속 스트릭을 이어가는지
   (이전에는 매번 빈 리스트를 넘겨 auto_confirmed가 절대 True가 될 수 없었음)
3) generate_ai_questions()가 관리자 난이도 재조정 이력을 프롬프트 보정 예시로 전달하는지
4) build_prompt()가 difficulty_corrections를 올바르게 블록으로 렌더링하는지
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_engine._shared import build_prompt
from repositories.local_json import LocalFeedbackRepository
from services import admin_service


class LocalFeedbackRepositoryTests(unittest.TestCase):
    """실제 저장소 파일이 아닌 임시 디렉터리를 대상으로 검증한다."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = LocalFeedbackRepository()
        base = Path(self._tmpdir.name)
        patchers = [
            patch.object(LocalFeedbackRepository, "_file", base / "difficulty_feedback.jsonl"),
            patch.object(LocalFeedbackRepository, "_tmp_file", base / "difficulty_feedback.tmp.jsonl"),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_empty_repo_returns_empty_list(self):
        self.assertEqual(self.repo.list_recent_feedback(), [])

    def test_returns_newest_first_respecting_limit(self):
        for i in range(5):
            self.repo.append_feedback({"question_id": f"Q{i}", "ai_difficulty": "중", "admin_difficulty": "중"})
        recent = self.repo.list_recent_feedback(limit=2)
        self.assertEqual([r["question_id"] for r in recent], ["Q4", "Q3"])


class FakeQuestionRepository:
    """QuestionRepository 계약을 만족하는 인메모리 테스트 대역."""

    def __init__(self):
        self._questions = {}  # question_id -> (pool_key, question dict)

    def get_all_questions(self) -> dict:
        pools = {}
        for pool_key, q in self._questions.values():
            pools.setdefault(pool_key, []).append(q)
        return pools

    def get_approved_questions(self, team_key=None, category=None) -> list:
        return [q for _, q in self._questions.values() if q.get("status") == "approved"]

    def list_by_status(self, status: str) -> list:
        return [q for _, q in self._questions.values() if q.get("status") == status]

    def get_question(self, question_id: str):
        entry = self._questions.get(question_id)
        return entry[1] if entry else None

    def add_question(self, pool_key: str, question: dict) -> None:
        self._questions[question["question_id"]] = (pool_key, question)

    def update_question(self, question_id: str, fields: dict) -> None:
        entry = self._questions.get(question_id)
        if entry:
            entry[1].update(fields)

    def count_by_status(self, status: str) -> int:
        return len(self.list_by_status(status))


class FakeFeedbackRepository:
    """LocalFeedbackRepository와 동일한 계약의 인메모리 테스트 대역."""

    def __init__(self):
        self._records = []  # append 순서 = 오래된 것부터

    def append_feedback(self, record: dict) -> None:
        self._records.append(dict(record))

    def list_recent_feedback(self, limit: int = 20) -> list:
        return list(reversed(self._records[-limit:]))


class FakeQuestionStatsRepo:
    def list_flagged(self) -> list:
        return []

    def increment_batch(self, question_ids) -> None:
        pass


class OverrideDifficultyStreakTests(unittest.TestCase):
    def setUp(self):
        self.fake_repo = FakeQuestionRepository()
        self.fake_feedback = FakeFeedbackRepository()
        patchers = [
            patch("repositories.question_repo", self.fake_repo),
            patch("repositories.feedback_repo", self.fake_feedback),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def _add_question(self, qid: str, difficulty_ai: str = "중"):
        self.fake_repo.add_question("team2", {
            "question_id": qid,
            "question": f"질문 {qid}",
            "difficulty_ai": difficulty_ai,
            "status": "reviewing",
        })

    def test_auto_confirmed_false_before_three_consecutive_matches(self):
        self._add_question("Q1")
        result = admin_service.override_difficulty("Q1", "중")
        self.assertFalse(result["auto_confirmed"])

    def test_auto_confirmed_true_after_three_consecutive_matches(self):
        result = None
        for qid in ["Q1", "Q2", "Q3"]:
            self._add_question(qid)
            result = admin_service.override_difficulty(qid, "중")
        self.assertTrue(result["auto_confirmed"])

    def test_auto_confirmed_resets_after_a_mismatch(self):
        self._add_question("Q1")
        admin_service.override_difficulty("Q1", "중")  # 일치
        self._add_question("Q2")
        admin_service.override_difficulty("Q2", "상")  # 불일치 (difficulty_ai 기본값 "중")
        self._add_question("Q3")
        result = admin_service.override_difficulty("Q3", "중")  # 일치하지만 직전 불일치가 섞여 3연속 아님
        self.assertFalse(result["auto_confirmed"])

    def test_feedback_record_includes_question_text_for_prompt_reuse(self):
        self._add_question("Q1", difficulty_ai="중")
        admin_service.override_difficulty("Q1", "상")
        recent = self.fake_feedback.list_recent_feedback(limit=1)
        self.assertEqual(recent[0]["question_text"], "질문 Q1")
        self.assertEqual(recent[0]["ai_difficulty"], "중")
        self.assertEqual(recent[0]["admin_difficulty"], "상")


class GenerateAIQuestionsDifficultyFeedbackTests(unittest.TestCase):
    """generate_ai_questions()가 난이도 재조정 이력을 프롬프트 보정 예시로 전달하는지 검증."""

    def setUp(self):
        self.fake_repo = FakeQuestionRepository()
        self.fake_stats = FakeQuestionStatsRepo()
        self.fake_feedback = FakeFeedbackRepository()
        patchers = [
            patch("repositories.question_repo", self.fake_repo),
            patch("repositories.question_stats_repo", self.fake_stats),
            patch("repositories.feedback_repo", self.fake_feedback),
            patch("services.material_service.get_material_text_for_team", return_value=""),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_mismatched_feedback_is_forwarded_as_difficulty_corrections(self):
        self.fake_feedback.append_feedback({
            "question_id": "Q0",
            "question_text": "기존 문제",
            "ai_difficulty": "중",
            "admin_difficulty": "상",
        })
        with patch("ai_engine.router.generate_questions_from_material", return_value=[]) as mock_gen:
            admin_service.generate_ai_questions("T2", "", 1, "중")
        difficulty_corrections = mock_gen.call_args.args[-1]
        self.assertEqual(len(difficulty_corrections), 1)
        self.assertEqual(difficulty_corrections[0]["question_text"], "기존 문제")
        self.assertEqual(difficulty_corrections[0]["ai_difficulty"], "중")
        self.assertEqual(difficulty_corrections[0]["admin_difficulty"], "상")

    def test_matching_feedback_is_not_forwarded(self):
        self.fake_feedback.append_feedback({
            "question_id": "Q0",
            "question_text": "기존 문제",
            "ai_difficulty": "중",
            "admin_difficulty": "중",
        })
        with patch("ai_engine.router.generate_questions_from_material", return_value=[]) as mock_gen:
            admin_service.generate_ai_questions("T2", "", 1, "중")
        difficulty_corrections = mock_gen.call_args.args[-1]
        self.assertEqual(difficulty_corrections, [])


class BuildPromptDifficultyBlockTests(unittest.TestCase):
    def test_block_present_when_corrections_given(self):
        prompt = build_prompt(
            "자료", "팀별", 1, "중", [], [],
            [{"question_text": "예시 문제", "ai_difficulty": "중", "admin_difficulty": "상"}],
        )
        self.assertIn("난이도 판정 보정 이력", prompt)
        self.assertIn("예시 문제", prompt)
        self.assertIn("AI 예측: 중", prompt)
        self.assertIn("관리자 확정: 상", prompt)

    def test_block_absent_when_no_corrections(self):
        prompt = build_prompt("자료", "팀별", 1, "중", [], [], [])
        self.assertNotIn("난이도 판정 보정 이력", prompt)


if __name__ == "__main__":
    unittest.main()
