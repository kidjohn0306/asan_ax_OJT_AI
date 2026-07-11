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
    TeamRepository,
    QuestionStatsRepository,
    MaterialRepository,
)

MOCK_DIR = Path(__file__).parent.parent / "mock_data"


class LocalQuestionRepository(QuestionRepository):
    _FILE = MOCK_DIR / "questions.json"
    _TMP_FILE = Path("/tmp/questions.json")

    def _load(self) -> dict:
        # Vercel read-only FS: prefer /tmp copy if it exists (contains runtime mutations)
        target = self._TMP_FILE if self._TMP_FILE.exists() else self._FILE
        with open(target, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        try:
            with open(self._FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            # Vercel: filesystem is read-only, fall back to /tmp
            with open(self._TMP_FILE, "w", encoding="utf-8") as f:
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
        self._save(data)

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
    Vercel 읽기전용 FS 대응: /tmp/results/ 에 저장, mock_data/results/ 에서 읽기 폴백.
    """

    RESULTS_DIR = MOCK_DIR / "results"
    _TMP_RESULTS_DIR = Path("/tmp/results")

    def _result_path(self, exam_set_id: str, employee_id: str, base: Path = None) -> Path:
        base = base or self.RESULTS_DIR
        set_dir = base / exam_set_id
        os.makedirs(set_dir, exist_ok=True)
        return set_dir / f"{employee_id}.json"

    def _iter_result_files(self):
        # RESULTS_DIR 먼저, _TMP_RESULTS_DIR 나중에 — get_all_results에서 dict 덮어쓰기 시 /tmp(런타임 변경) 우선
        for base in (self.RESULTS_DIR, self._TMP_RESULTS_DIR):
            if not base.exists():
                continue
            for set_dir in base.iterdir():
                if not set_dir.is_dir():
                    continue
                yield from set_dir.glob("*.json")

    def _read(self, path: Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_result(self, result: dict) -> None:
        result.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        exam_set_id = result.get("exam_set_id") or "legacy"
        employee_id = result.get("employee_id") or result.get("exam_id")
        try:
            path = self._result_path(exam_set_id, employee_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except OSError:
            # Vercel: filesystem is read-only, fall back to /tmp
            path = self._result_path(exam_set_id, employee_id, base=self._TMP_RESULTS_DIR)
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
        results = []
        for base in (self.RESULTS_DIR, self._TMP_RESULTS_DIR):
            set_dir = base / exam_set_id
            if set_dir.exists():
                results.extend(self._read(f) for f in set_dir.glob("*.json"))
        return results

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
    _tmp_file = Path("/tmp/difficulty_feedback.jsonl")

    def append_feedback(self, record: dict) -> None:
        record.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            with open(self._tmp_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


class LocalExamSetRepository(ExamSetRepository):
    EXAM_SETS_FILE = MOCK_DIR / "exam_sets.json"
    _TMP_FILE = Path("/tmp/exam_sets.json")

    def _load(self) -> dict:
        # Vercel read-only FS: prefer /tmp copy if it exists (contains runtime mutations)
        target = self._TMP_FILE if self._TMP_FILE.exists() else self.EXAM_SETS_FILE
        if not target.exists():
            return {"sets": []}
        with open(target, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        try:
            os.makedirs(self.EXAM_SETS_FILE.parent, exist_ok=True)
            with open(self.EXAM_SETS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            # Vercel: filesystem is read-only, fall back to /tmp
            with open(self._TMP_FILE, "w", encoding="utf-8") as f:
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

    def unassign_user(self, exam_set_id: str, employee_id: str) -> bool:
        stored = self._load()
        for s in stored.get("sets", []):
            if s.get("exam_set_id") == exam_set_id:
                assigned = s.get("assigned_users", [])
                if employee_id in assigned:
                    assigned.remove(employee_id)
                    self._save(stored)
                return True
        return False

    def update_exam_set(self, exam_set_id: str, fields: dict) -> bool:
        stored = self._load()
        for s in stored.get("sets", []):
            if s.get("exam_set_id") == exam_set_id:
                s.update(fields)
                self._save(stored)
                return True
        return False


_DEFAULT_TEAMS = [
    {"team_id": "default-t1", "team_name": "1팀", "team_code": "T1", "created_at": "", "updated_at": ""},
    {"team_id": "default-t2", "team_name": "2팀", "team_code": "T2", "created_at": "", "updated_at": ""},
    {"team_id": "default-t3", "team_name": "3팀", "team_code": "T3", "created_at": "", "updated_at": ""},
]
_FREQUENT_THRESHOLD = 5


class LocalTeamRepository(TeamRepository):
    _file = MOCK_DIR / "teams.json"
    _tmp_file = Path("/tmp/teams.json")

    def _load(self) -> list:
        target = self._tmp_file if self._tmp_file.exists() else self._file
        if not target.exists():
            return list(_DEFAULT_TEAMS)
        with open(target, encoding="utf-8") as f:
            return json.load(f).get("teams", list(_DEFAULT_TEAMS))

    def _save(self, teams: list) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump({"teams": teams}, f, ensure_ascii=False, indent=2)
        except OSError:
            with open(self._tmp_file, "w", encoding="utf-8") as f:
                json.dump({"teams": teams}, f, ensure_ascii=False, indent=2)

    def list_teams(self) -> list:
        return self._load()

    def get_team(self, team_id: str) -> dict | None:
        return next((t for t in self._load() if t["team_id"] == team_id), None)

    def create_team(self, data: dict) -> dict:
        teams = self._load()
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("updated_at", data["created_at"])
        teams.append(data)
        self._save(teams)
        return data

    def update_team(self, team_id: str, fields: dict) -> dict | None:
        teams = self._load()
        for t in teams:
            if t["team_id"] == team_id:
                t.update({k: v for k, v in fields.items() if k != "team_code"})
                t["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(teams)
                return t
        return None

    def delete_team(self, team_id: str) -> bool:
        teams = self._load()
        new_teams = [t for t in teams if t["team_id"] != team_id]
        if len(new_teams) == len(teams):
            return False
        self._save(new_teams)
        return True


class LocalQuestionStatsRepository(QuestionStatsRepository):
    _file = MOCK_DIR / "question_stats.json"
    _tmp_file = Path("/tmp/question_stats.json")

    def _load(self) -> dict:
        target = self._tmp_file if self._tmp_file.exists() else self._file
        if not target.exists():
            return {}
        with open(target, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            with open(self._tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def increment_batch(self, question_ids: list) -> None:
        if not question_ids:
            return
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for qid in set(question_ids):
            entry = data.get(qid, {"question_id": qid, "exam_count": 0, "last_used_at": "", "flagged_frequent": False})
            entry["exam_count"] = entry.get("exam_count", 0) + 1
            entry["last_used_at"] = now
            entry["flagged_frequent"] = entry["exam_count"] >= _FREQUENT_THRESHOLD
            data[qid] = entry
        self._save(data)

    def get_stats(self, question_id: str) -> dict | None:
        return self._load().get(question_id)

    def list_all_stats(self) -> dict:
        return self._load()

    def list_flagged(self) -> list:
        return [v for v in self._load().values() if v.get("flagged_frequent")]


class LocalMaterialRepository(MaterialRepository):
    _file = MOCK_DIR / "material_cache.json"
    _tmp_file = Path("/tmp/material_cache.json")

    def _load(self) -> dict:
        target = self._tmp_file if self._tmp_file.exists() else self._file
        if not target.exists():
            return {}
        with open(target, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            with open(self._tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def get_manifest(self, category: str) -> dict | None:
        return self._load().get(category)

    def save_manifest(self, category: str, manifest: dict) -> None:
        data = self._load()
        data[category] = manifest
        self._save(data)
