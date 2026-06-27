import json
from pathlib import Path
from datetime import datetime, timezone
from repositories.base import QuestionRepository, ResultRepository, SnapshotRepository, FeedbackRepository

MOCK_DIR = Path(__file__).parent.parent / "mock_data"

TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}


class LocalQuestionRepository(QuestionRepository):
    def _load(self) -> dict:
        with open(MOCK_DIR / "questions.json", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        with open(MOCK_DIR / "questions.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _all_flat(self, data: dict) -> list:
        result = []
        for pool in data.values():
            result.extend(pool)
        return result

    def get_all_questions(self) -> dict:
        return self._load()

    def get_approved_questions(self, team_key: str = None, category: str = None) -> list:
        data = self._load()
        if team_key:
            pools = [data.get(team_key, []), data.get("common", []),
                     data.get("safety", []), data.get("general", [])]
            flat = [q for pool in pools for q in pool]
        else:
            flat = self._all_flat(data)
        flat = [q for q in flat if q.get("status") == "approved"]
        if category:
            flat = [q for q in flat if q.get("category") == category]
        return flat

    def list_by_status(self, status: str) -> list:
        data = self._load()
        return [q for q in self._all_flat(data) if q.get("status") == status]

    def get_question(self, question_id: str) -> dict:
        data = self._load()
        for q in self._all_flat(data):
            if q["question_id"] == question_id:
                return q
        return None

    def add_question(self, pool_key: str, question: dict) -> None:
        data = self._load()
        if pool_key not in data:
            data[pool_key] = []
        data[pool_key].append(question)
        try:
            self._save(data)
        except OSError:
            # Vercel read-only filesystem — 로컬 저장 불가, 호출부에서 처리
            raise RuntimeError("questions.json 쓰기 실패: 읽기 전용 파일시스템입니다. DriveQuestionRepository가 필요합니다.")

    _CONTENT_FIELDS = {"question", "option_a", "option_b", "option_c", "option_d", "answer", "explanation"}

    def update_question(self, question_id: str, fields: dict) -> None:
        data = self._load()
        for pool in data.values():
            for q in pool:
                if q["question_id"] == question_id:
                    q.update(fields)
                    # 콘텐츠 필드 변경 시에만 버전 증가 (상태·난이도 관리 메타 변경은 버전 유지)
                    if any(k in self._CONTENT_FIELDS for k in fields):
                        q["version"] = q.get("version", 1) + 1
                    self._save(data)
                    return

    def count_by_status(self, status: str) -> int:
        return len(self.list_by_status(status))


class LocalResultRepository(ResultRepository):
    _file = MOCK_DIR / "results.jsonl"

    def append_result(self, result: dict) -> None:
        result.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def get_result(self, exam_id: str) -> dict:
        if not self._file.exists():
            return None
        with open(self._file, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line.strip())
                if r.get("exam_id") == exam_id:
                    return r
        return None

    def get_all_results(self) -> dict:
        if not self._file.exists():
            return {}
        results = {}
        with open(self._file, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line.strip())
                results[r["exam_id"]] = r
        return results

    def count(self) -> int:
        if not self._file.exists():
            return 0
        with open(self._file, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())


class LocalSnapshotRepository(SnapshotRepository):
    _file = Path("/tmp") / "snapshots.jsonl"

    def save_snapshot(self, exam_id: str, snapshot: dict) -> None:
        record = {"exam_id": exam_id, "snapshot": snapshot,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_snapshot(self, exam_id: str) -> dict:
        if not self._file.exists():
            return None
        with open(self._file, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line.strip())
                if r.get("exam_id") == exam_id:
                    return r.get("snapshot")
        return None


class LocalFeedbackRepository(FeedbackRepository):
    _file = MOCK_DIR / "difficulty_feedback.jsonl"

    def append_feedback(self, record: dict) -> None:
        record.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
