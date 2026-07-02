import json
import os
from pathlib import Path
from datetime import datetime, timezone
from repositories.base import (
    QuestionRepository,
    ResultRepository,
    SnapshotRepository,
    FeedbackRepository,
    ExamSetRepository,
)

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
    """폴더 기반 결과 저장소.

    results/{exam_set_id}/{employee_id}.json 구조로 저장한다.
    employee_id가 없는 구형 데이터는 results/legacy/{exam_id}.json에 존재한다.
    """

    RESULTS_DIR = MOCK_DIR / "results"

    def _result_path(self, exam_set_id: str, employee_id: str) -> Path:
        set_dir = self.RESULTS_DIR / exam_set_id
        os.makedirs(set_dir, exist_ok=True)
        return set_dir / f"{employee_id}.json"

    def _iter_result_files(self):
        if not self.RESULTS_DIR.exists():
            return
        for set_dir in self.RESULTS_DIR.iterdir():
            if not set_dir.is_dir():
                continue
            for f in set_dir.glob("*.json"):
                yield f

    def _read(self, path: Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_result(self, result: dict) -> None:
        result.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        exam_set_id = result.get("exam_set_id") or "legacy"
        employee_id = result.get("employee_id") or result.get("exam_id")
        path = self._result_path(exam_set_id, employee_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # base.py ResultRepository 시그니처 유지 (append_result -> save_result 위임)
    def append_result(self, result: dict) -> None:
        self.save_result(result)

    def get_result(self, exam_id: str) -> dict:
        for path in self._iter_result_files():
            r = self._read(path)
            if r.get("exam_id") == exam_id:
                return r
        return None

    def list_results_by_set(self, exam_set_id: str) -> list:
        set_dir = self.RESULTS_DIR / exam_set_id
        if not set_dir.exists():
            return []
        return [self._read(f) for f in set_dir.glob("*.json")]

    def get_all_results(self) -> dict:
        results = {}
        for path in self._iter_result_files():
            r = self._read(path)
            key = r.get("exam_id") or path.stem
            results[key] = r
        return results

    def count(self) -> int:
        return sum(1 for _ in self._iter_result_files())


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


class LocalExamSetRepository(ExamSetRepository):
    EXAM_SETS_FILE = MOCK_DIR / "exam_sets.json"

    def _load(self) -> dict:
        if not self.EXAM_SETS_FILE.exists():
            return {"sets": []}
        with open(self.EXAM_SETS_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        os.makedirs(self.EXAM_SETS_FILE.parent, exist_ok=True)
        with open(self.EXAM_SETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_exam_sets(self) -> list:
        return self._load().get("sets", [])

    def get_exam_set(self, exam_set_id: str) -> dict | None:
        for s in self.list_exam_sets():
            if s.get("exam_set_id") == exam_set_id:
                return s
        return None

    def create_exam_set(self, data: dict) -> dict:
        stored = self._load()
        data.setdefault("assigned_users", [])
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        stored.setdefault("sets", []).append(data)
        self._save(stored)
        return data

    def assign_user(self, exam_set_id: str, employee_id: str) -> bool:
        stored = self._load()
        for s in stored.get("sets", []):
            if s.get("exam_set_id") == exam_set_id:
                assigned = s.setdefault("assigned_users", [])
                if employee_id not in assigned:
                    assigned.append(employee_id)
                self._save(stored)
                return True
        return False
