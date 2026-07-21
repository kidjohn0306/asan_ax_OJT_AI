"""score_and_save()의 legacy(비-frozen) 채점 경로 재제출 안전성 검증.

Ralph architect 리뷰에서 발견된 버그: _legacy_score_and_save가 매 호출마다 새
submitted_at으로 result_data를 다시 만들어 append_result에 넘기면, 같은
result_id로 재시도(응답 유실 후 "다시 제출하기" 등)할 때 저장소가 이전에
저장된 값과 달라 ResultConflict(불변 결과 충돌)를 던져 500으로 이어지고,
재시도할수록 영원히 결과 화면에 도달하지 못하는 문제가 있었다.
"""
import unittest
from unittest.mock import patch

from repositories.base import ResultConflict
from services import exam_service


def legacy_snapshot():
    return {
        "Q1": {
            "question": "테스트 문제",
            "category": "공통",
            "answer": "A",
            "explanation": "해설",
            "option_a": "A 보기", "option_b": "B 보기", "option_c": "C 보기", "option_d": "D 보기",
            "difficulty": "중",
        },
        "_meta": {
            "team_code": "T1",
            "exam_id": "exam-1",
            "name": "레거시 시험",
            "pass_score": 70,
            # grading_mode가 없으므로(=frozen_v2가 아니므로) legacy 채점 경로로 간다.
        },
    }


class FakeSnapshots:
    def __init__(self):
        self.rows = {"r1": legacy_snapshot(), "r-admin": legacy_snapshot()}

    def get_snapshot(self, result_id):
        return self.rows.get(result_id)


class FakeLegacyResults:
    """실제 Sheets/Local 저장소처럼 result_id당 1행만 유지하고, 저장된 값과 다른
    페이로드로 재저장을 시도하면 ResultConflict를 던진다(불변 결과 계약)."""

    def __init__(self):
        self.rows = {}
        self.append_calls = 0

    def get_result(self, result_id):
        return self.rows.get(result_id)

    def append_result(self, result):
        self.append_calls += 1
        result_id = result["result_id"]
        existing = self.rows.get(result_id)
        if existing is not None and existing != result:
            raise ResultConflict(f"immutable result conflict for result_id={result_id}")
        self.rows[result_id] = dict(result)


class LegacyResubmissionTests(unittest.TestCase):
    def setUp(self):
        self.snapshots = FakeSnapshots()
        self.results = FakeLegacyResults()
        patchers = [
            patch("repositories.question_repo", object()),
            patch("repositories.result_repo", self.results),
            patch("repositories.snapshot_repo", self.snapshots),
            patch("services.activity_log.record_activity"),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_resubmitting_same_result_id_returns_existing_result_without_conflict(self):
        first = exam_service.score_and_save("r1", {"Q1": "A"}, {"Q1": 1.0}, "E1", "홍길동")
        self.assertEqual(self.results.append_calls, 1)

        # 재시도 — submitted_at이 매번 새로 생성됐다면 저장된 값과 달라 ResultConflict가 났을 것.
        second = exam_service.score_and_save("r1", {"Q1": "A"}, {"Q1": 1.0}, "E1", "홍길동")

        self.assertEqual(second, first)
        self.assertEqual(second["submitted_at"], first["submitted_at"])
        # 재계산·재저장이 아니라 기존 결과를 그대로 반환해야 한다 — append는 최초 1회만.
        self.assertEqual(self.results.append_calls, 1)

    def test_three_retries_all_return_the_identical_result(self):
        results = [
            exam_service.score_and_save("r1", {"Q1": "A"}, {"Q1": 1.0}, "E1", "홍길동")
            for _ in range(3)
        ]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(self.results.append_calls, 1)

    def test_skip_save_does_not_touch_result_repo(self):
        # 회귀 테스트가 아니라 불변식 가드: skip_save 경로는 애초에 저장을 안 하므로
        # 이 테스트는 수정 전 코드에서도 통과한다 — 새 early-return이 admin 응시 흐름의
        # "저장소 미접근" 계약을 깨지 않았는지만 확인한다.
        result = exam_service.score_and_save(
            "r-admin", {"Q1": "A"}, {"Q1": 1.0}, "admin001", "관리자", skip_save=True,
        )
        self.assertEqual(result["score"], 4)
        self.assertEqual(self.results.append_calls, 0)
        self.assertIsNone(self.results.get_result("r-admin"))


if __name__ == "__main__":
    unittest.main()
