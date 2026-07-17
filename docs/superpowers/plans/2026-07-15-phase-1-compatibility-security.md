# Phase 1 Compatibility and Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 8개 Sheet와 사원 UI를 유지하면서 Silent Local fallback, Snapshot 혼합 열, 위험한 Migration, 요청 Body 신원 신뢰, 승인 전 문제 시험 사용을 제거한다.

**Architecture:** 저장 정책과 호환 파싱을 작은 순수 함수로 분리하고 Repository/API 경계에서 강제한다. 모든 변경은 기존 Legacy 데이터 형식을 계속 읽되 검증·운영 환경에서 실패를 숨기지 않는 방향으로 적용한다.

**Tech Stack:** Python 3, FastAPI 0.111, `unittest`, `unittest.mock`, Google Sheets API v4, python-jose, React 18 기존 사원 UI 무변경

## Global Constraints

- 제품 코드는 이 계획 실행 승인을 받은 뒤에만 변경한다.
- 기존 8개 Sheet 이름과 기존 열 순서를 변경하지 않는다.
- 신규 Sheet와 관리자 UI는 이 계획 범위에 포함하지 않는다.
- 검증·운영 환경에서 `OJT_STRICT_SHEETS_STORAGE=true`를 사용한다.
- Local fallback은 로컬 개발 환경에서만 명시적으로 허용한다.
- 사원 UI의 요청 형식은 하위호환을 위해 유지하되 서버는 JWT 신원을 기준으로 처리한다.
- 모든 구현은 실패 테스트를 먼저 작성한다.
- 각 Task 종료 시 전체 `python -m unittest discover -s tests -v`를 실행한다.
- 프런트엔드 소스를 변경하지 않으므로 이 계획에서는 `frontend/dist`를 재빌드하지 않는다.

---

## File Structure

### 새 파일

- `backend/config/__init__.py`: 설정 패키지 표식
- `backend/config/storage.py`: Strict Sheets 정책을 파싱하는 순수 함수
- `tests/config/test_storage_policy.py`: 환경별 Strict/fallback 정책 테스트
- `tests/repositories/test_sheets_fallback_policy.py`: Sheets 호출 실패 시 strict/fallback 동작 테스트
- `tests/repositories/test_snapshot_compatibility.py`: Snapshot B/C 혼재 파싱 테스트
- `tests/scripts/test_migration_safety.py`: Migration Dry-run, 열 위치, 중복 방지 테스트
- `tests/api/test_exam_identity.py`: JWT 신원 강제와 결과 소유권 테스트
- `tests/services/test_exam_set_approval_guard.py`: 승인 문제만 시험에 사용할 수 있는지 검증

### 수정 파일

- `backend/repositories/sheets_repo.py`: Strict fallback 정책과 Snapshot 호환 Reader 적용
- `backend/repositories/__init__.py`: 초기화 실패 시 환경 정책에 따라 fail-closed
- `backend/scripts/migrate_exam_sets_pk.py`: K열 백필, Dry-run 기본, 명시적 Apply
- `backend/scripts/migrate_questions_to_sheets.py`: 기존 ID 조회, 중복 Skip, Dry-run 기본
- `backend/api/exam.py`: JWT 신원 사용, assigned-name 인증, 결과 소유권 정보 전달
- `backend/services/exam_service.py`: JWT 기반 식별자 사용과 결과 소유권 검사
- `backend/services/admin_service.py`: 시험 저장 시 승인 상태 검증
- `backend/api/admin.py`: 시험 생성 오류 계약 유지
- `CLAUDE.md`: Strict 저장과 안전한 Migration 실행 규칙 문서화

---

### Task 1: Strict Sheets 저장 정책

**Files:**
- Create: `backend/config/__init__.py`
- Create: `backend/config/storage.py`
- Create: `tests/config/test_storage_policy.py`
- Create: `tests/repositories/test_sheets_fallback_policy.py`
- Modify: `backend/repositories/sheets_repo.py:20-34`
- Modify: `backend/repositories/__init__.py:14-123`

**Interfaces:**
- Produces: `is_strict_sheets_storage(env: Mapping[str, str] | None = None) -> bool`
- Produces: `should_fallback_to_local(env: Mapping[str, str] | None = None) -> bool`
- Consumed by: `_fallback_on_error()` and repository initialization

- [ ] **Step 1: Write storage policy tests**

```python
import os
import unittest
from unittest.mock import patch

from config.storage import is_strict_sheets_storage, should_fallback_to_local


class StoragePolicyTests(unittest.TestCase):
    def test_strict_true_disables_local_fallback(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "true"}, clear=False):
            self.assertTrue(is_strict_sheets_storage())
            self.assertFalse(should_fallback_to_local())

    def test_strict_false_allows_local_fallback(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "false"}, clear=False):
            self.assertFalse(is_strict_sheets_storage())
            self.assertTrue(should_fallback_to_local())

    def test_invalid_value_fails_closed(self):
        with patch.dict(os.environ, {"OJT_STRICT_SHEETS_STORAGE": "yes"}, clear=False):
            with self.assertRaisesRegex(ValueError, "OJT_STRICT_SHEETS_STORAGE"):
                is_strict_sheets_storage()
```

- [ ] **Step 2: Run the policy test and verify failure**

Run from `backend`:

```powershell
python -m unittest ../tests/config/test_storage_policy.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'config.storage'`.

- [ ] **Step 3: Implement the policy parser**

```python
import os
from collections.abc import Mapping


def is_strict_sheets_storage(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    raw = source.get("OJT_STRICT_SHEETS_STORAGE", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise ValueError(
            "OJT_STRICT_SHEETS_STORAGE must be either 'true' or 'false'"
        )
    return raw == "true"


def should_fallback_to_local(env: Mapping[str, str] | None = None) -> bool:
    return not is_strict_sheets_storage(env)
```

- [ ] **Step 4: Test decorator behavior before changing it**

```python
import unittest
from unittest.mock import patch

from repositories.sheets_repo import _fallback_on_error


class FakeLocal:
    def read(self):
        return "local"


class FakeSheets:
    _local_fallback = None

    @_fallback_on_error(FakeLocal)
    def read(self):
        raise RuntimeError("sheets unavailable")


class SheetsFallbackPolicyTests(unittest.TestCase):
    def test_strict_mode_reraises_sheets_error(self):
        with patch.dict("os.environ", {"OJT_STRICT_SHEETS_STORAGE": "true"}):
            with self.assertRaisesRegex(RuntimeError, "sheets unavailable"):
                FakeSheets().read()

    def test_non_strict_mode_uses_local_fallback(self):
        with patch.dict("os.environ", {"OJT_STRICT_SHEETS_STORAGE": "false"}):
            self.assertEqual(FakeSheets().read(), "local")
```

- [ ] **Step 5: Run the decorator test and verify strict case fails**

Run:

```powershell
python -m unittest ../tests/repositories/test_sheets_fallback_policy.py -v
```

Expected: `test_strict_mode_reraises_sheets_error` FAIL because the current decorator returns `local`.

- [ ] **Step 6: Apply strict policy to Sheets calls and initialization**

Change `_fallback_on_error` to re-raise before constructing a local repository:

```python
from config.storage import should_fallback_to_local


def _fallback_on_error(local_cls):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                if not should_fallback_to_local():
                    logging.exception(
                        "%s.%s failed in strict Sheets mode",
                        type(self).__name__,
                        func.__name__,
                    )
                    raise
                logging.warning(
                    "%s.%s failed; falling back to %s: %s",
                    type(self).__name__, func.__name__, local_cls.__name__, exc,
                )
                if getattr(self, "_local_fallback", None) is None:
                    self._local_fallback = local_cls()
                return getattr(self._local_fallback, func.__name__)(*args, **kwargs)
        return wrapper
    return decorator
```

In `repositories/__init__.py`, replace each unconditional initialization fallback with one helper:

```python
from config.storage import should_fallback_to_local


def _fallback_or_raise(error: Exception, local_factory, label: str):
    if not should_fallback_to_local():
        raise error
    import logging
    logging.warning("%s initialization failed; using local fallback: %s", label, error)
    return local_factory()
```

- [ ] **Step 7: Run focused and full tests**

Run:

```powershell
python -m unittest ../tests/config/test_storage_policy.py ../tests/repositories/test_sheets_fallback_policy.py -v
python -m unittest discover -s ../tests -v
```

Expected: focused tests PASS; full suite reports `OK` with zero failures.

- [ ] **Step 8: Commit Task 1**

```powershell
git add backend/config backend/repositories/sheets_repo.py backend/repositories/__init__.py tests/config tests/repositories/test_sheets_fallback_policy.py
git commit -m "fix: enforce strict Sheets storage policy"
```

Expected: one commit containing only Task 1 files. If Git author identity is missing, stop and request repository-local `user.name` and `user.email`; do not invent an identity.

---

### Task 2: Snapshot B/C 혼재 호환 Reader

**Files:**
- Create: `tests/repositories/test_snapshot_compatibility.py`
- Modify: `backend/repositories/sheets_repo.py:504-550`

**Interfaces:**
- Produces: `_parse_snapshot_row(row: list) -> tuple[str, str, dict]`
- Consumed by: `SheetsSnapshotRepository.get_snapshot()`

- [ ] **Step 1: Write failing mixed-format tests**

```python
import json
import unittest

from repositories.sheets_repo import _parse_snapshot_row


SNAPSHOT = {"Q-1": {"answer": "A"}, "_meta": {"team_code": "T1"}}
STAMP = "2026-07-04T05:41:34.859878+00:00"


class SnapshotCompatibilityTests(unittest.TestCase):
    def test_reads_canonical_created_at_then_json(self):
        result_id, created_at, data = _parse_snapshot_row(
            ["result-1", STAMP, json.dumps(SNAPSHOT)]
        )
        self.assertEqual((result_id, created_at, data), ("result-1", STAMP, SNAPSHOT))

    def test_reads_legacy_swapped_json_then_created_at(self):
        result_id, created_at, data = _parse_snapshot_row(
            ["result-2", json.dumps(SNAPSHOT), STAMP]
        )
        self.assertEqual((result_id, created_at, data), ("result-2", STAMP, SNAPSHOT))

    def test_rejects_row_without_json_object(self):
        with self.assertRaisesRegex(ValueError, "snapshot row"):
            _parse_snapshot_row(["result-3", STAMP, "not-json"])
```

- [ ] **Step 2: Run and verify import failure**

Run:

```powershell
python -m unittest ../tests/repositories/test_snapshot_compatibility.py -v
```

Expected: FAIL because `_parse_snapshot_row` is not defined.

- [ ] **Step 3: Implement content-based parser**

```python
def _json_object_or_none(value):
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_snapshot_row(row: list) -> tuple[str, str, dict]:
    result_id = row[0] if row else ""
    second = row[1] if len(row) > 1 else ""
    third = row[2] if len(row) > 2 else ""
    second_json = _json_object_or_none(second)
    third_json = _json_object_or_none(third)
    if third_json is not None:
        return result_id, second, third_json
    if second_json is not None:
        return result_id, third, second_json
    raise ValueError(f"invalid snapshot row for result_id={result_id!r}")
```

Update `get_snapshot()`:

```python
for row in rows[1:]:
    if row and row[0] == result_id:
        _, _, snapshot = _parse_snapshot_row(row)
        return snapshot
```

Keep `save_snapshot()` canonical as `[result_id, created_at, data_json]`.

- [ ] **Step 4: Run focused and full tests**

Run:

```powershell
python -m unittest ../tests/repositories/test_snapshot_compatibility.py -v
python -m unittest discover -s ../tests -v
```

Expected: all Snapshot tests PASS and full suite reports `OK`.

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/repositories/sheets_repo.py tests/repositories/test_snapshot_compatibility.py
git commit -m "fix: read mixed snapshot column layouts"
```

---

### Task 3: 안전한 Migration Dry-run과 중복 방지

**Files:**
- Create: `tests/scripts/test_migration_safety.py`
- Modify: `backend/scripts/migrate_exam_sets_pk.py`
- Modify: `backend/scripts/migrate_questions_to_sheets.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Produces: `build_exam_id_updates(rows: list[list]) -> list[dict]`
- Produces: `build_question_rows(local_data: dict, existing_ids: set[str]) -> list[list]`
- Both scripts accept `--apply`; omission means Dry-run and no external Write.

- [ ] **Step 1: Write migration safety tests**

```python
import unittest

from scripts.migrate_exam_sets_pk import build_exam_id_updates
from scripts.migrate_questions_to_sheets import build_question_rows


class MigrationSafetyTests(unittest.TestCase):
    def test_exam_id_backfill_targets_column_k(self):
        rows = [["set-1", "시험", "T1", "[]", "[]", "", "", "70", "active", "admin", ""]]
        self.assertEqual(
            build_exam_id_updates(rows),
            [{"range": "exam_sets!K2", "values": [["set-1"]]}],
        )

    def test_existing_exam_id_is_not_overwritten(self):
        rows = [["set-1", "시험", "T1", "[]", "[]", "", "", "70", "active", "admin", "exam-1"]]
        self.assertEqual(build_exam_id_updates(rows), [])

    def test_existing_question_id_is_skipped(self):
        data = {"team1": [{"question_id": "Q-1", "question": "existing"},
                          {"question_id": "Q-2", "question": "new"}]}
        rows = build_question_rows(data, {"Q-1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Q-2")
```

- [ ] **Step 2: Run and verify missing helper failures**

Run from `backend`:

```powershell
python -m unittest ../tests/scripts/test_migration_safety.py -v
```

Expected: FAIL because both helper functions are missing.

- [ ] **Step 3: Extract pure update builders**

In `migrate_exam_sets_pk.py`:

```python
def build_exam_id_updates(rows: list[list]) -> list[dict]:
    updates = []
    for row_no, row in enumerate(rows, start=2):
        data = SheetsExamSetRepository._row_to_dict(row)
        if data.get("exam_id") or not data.get("exam_set_id"):
            continue
        updates.append({
            "range": f"{SHEET_TAB}!K{row_no}",
            "values": [[data["exam_set_id"]]],
        })
    return updates
```

In `migrate_questions_to_sheets.py`:

```python
def build_question_rows(data: dict, existing_ids: set[str]) -> list[list]:
    return [
        SheetsQuestionRepository._dict_to_row(pool_key, question)
        for pool_key, questions in data.items()
        for question in questions
        if question.get("question_id") not in existing_ids
    ]
```

- [ ] **Step 4: Make Dry-run the default**

Use this CLI pattern in both scripts:

```python
import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 Google Sheet에 변경을 적용합니다. 생략하면 Dry-run입니다.",
    )
    return parser.parse_args()
```

Before every `batchUpdate` or `append`, print target row counts and return without writing unless `args.apply` is true.

- [ ] **Step 5: Document exact safe commands**

Add to `CLAUDE.md`:

````markdown
### 안전한 Sheets Migration

두 Migration은 기본이 Dry-run이다.

```powershell
cd backend
python scripts/migrate_exam_sets_pk.py
python scripts/migrate_questions_to_sheets.py
```

출력과 대상 Spreadsheet ID를 확인한 뒤에만 적용한다.

```powershell
python scripts/migrate_exam_sets_pk.py --apply
python scripts/migrate_questions_to_sheets.py --apply
```
````

- [ ] **Step 6: Run focused and full tests**

Run:

```powershell
python -m unittest ../tests/scripts/test_migration_safety.py -v
python -m unittest discover -s ../tests -v
```

Expected: migration tests PASS; full suite reports `OK`.

- [ ] **Step 7: Commit Task 3**

```powershell
git add backend/scripts tests/scripts CLAUDE.md
git commit -m "fix: make Sheets migrations dry-run and idempotent"
```

---

### Task 4: JWT 사용자 신원과 결과 소유권 강제

**Files:**
- Create: `tests/api/test_exam_identity.py`
- Modify: `backend/api/exam.py:14-62`
- Modify: `backend/services/exam_service.py:30-41,80-82,180-251`

**Interfaces:**
- Produces: `_require_claim_match(auth: dict, claimed_employee_id: str) -> str`
- Changes: `get_exam_result(result_id: str, requester_id: str, requester_role: str) -> dict`
- Existing request Body fields remain optional for compatibility.

- [ ] **Step 1: Write API identity tests**

```python
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
            "sub": "2024001", "name": "홍길동", "role": "examinee", "team": "T1",
        })
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @patch("services.exam_service.generate_exam_questions")
    def test_generate_uses_jwt_identity_and_team(self, generate):
        generate.return_value = {"questions": []}
        response = self.client.post(
            "/api/exam/generate",
            headers=self.headers,
            json={"team_code": "T2", "employee_id": "2024999"},
        )
        self.assertEqual(response.status_code, 403)
        generate.assert_not_called()

    def test_assigned_name_requires_authentication(self):
        response = self.client.get("/api/exam/assigned-name?employee_id=2024001")
        self.assertEqual(response.status_code, 401)

    @patch("services.exam_service.get_exam_result")
    def test_result_passes_requester_identity(self, get_result):
        get_result.return_value = {"result_id": "r1"}
        response = self.client.get("/api/exam/result/r1", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        get_result.assert_called_once_with("r1", "2024001", "examinee")
```

- [ ] **Step 2: Run and verify current contract fails**

Run:

```powershell
python -m unittest ../tests/api/test_exam_identity.py -v
```

Expected: all three new assertions FAIL against the current API.

- [ ] **Step 3: Implement claim matching at the API boundary**

```python
def _require_claim_match(auth: dict, claimed_employee_id: str = "") -> str:
    requester_id = auth.get("sub", "")
    if not requester_id:
        raise HTTPException(status_code=401, detail="사용자 신원을 확인할 수 없습니다.")
    if claimed_employee_id and claimed_employee_id != requester_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 신원을 사용할 수 없습니다.")
    return requester_id
```

For examinees, use JWT team and name:

```python
employee_id = _require_claim_match(auth, body.employee_id)
team_code = auth.get("team") or body.team_code
return generate_exam_questions(team_code, employee_id=employee_id)
```

For submission:

```python
employee_id = _require_claim_match(auth, body.employee_id)
name = auth.get("name", "")
return score_and_save(
    body.result_id, body.answers, body.response_times,
    employee_id, name, skip_save=auth.get("role") == "admin",
)
```

Add `Depends(require_auth)` to `assigned-name` and ignore a mismatched query ID.

- [ ] **Step 4: Enforce result ownership in the service**

```python
def get_exam_result(result_id: str, requester_id: str, requester_role: str) -> dict:
    _, result_repo, _ = _get_repos()
    result = result_repo.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    if requester_role != "admin" and result.get("employee_id") != requester_id:
        raise HTTPException(status_code=403, detail="이 결과를 조회할 권한이 없습니다.")
    return result
```

- [ ] **Step 5: Add service ownership cases**

Extend `test_exam_identity.py` with a fake result repository and assert:

```python
def test_examinee_cannot_read_another_users_result(self):
    with patch("repositories.result_repo.get_result", return_value={
        "result_id": "r1", "employee_id": "2024002",
    }):
        response = self.client.get("/api/exam/result/r1", headers=self.headers)
    self.assertEqual(response.status_code, 403)
```

- [ ] **Step 6: Run focused and full tests**

Run:

```powershell
python -m unittest ../tests/api/test_exam_identity.py -v
python -m unittest discover -s ../tests -v
```

Expected: identity tests PASS; full suite reports `OK`.

- [ ] **Step 7: Commit Task 4**

```powershell
git add backend/api/exam.py backend/services/exam_service.py tests/api/test_exam_identity.py
git commit -m "fix: enforce JWT identity for exam operations"
```

---

### Task 5: 승인 문제만 시험 저장 허용

**Files:**
- Create: `tests/services/test_exam_set_approval_guard.py`
- Modify: `backend/services/admin_service.py:582-604`

**Interfaces:**
- Produces: `_validate_exam_question_ids(question_repo, question_ids: list[str]) -> list[str]`
- Raises: `HTTPException(409)` with `detail.code == "EXAM_QUESTION_NOT_APPROVED"`

- [ ] **Step 1: Write failing approval guard tests**

```python
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import admin_service


class FakeQuestions:
    def __init__(self, statuses):
        self.statuses = statuses

    def get_question(self, question_id):
        status = self.statuses.get(question_id)
        return None if status is None else {"question_id": question_id, "status": status}


class FakeExamSets:
    def create_exam_set(self, data):
        return data


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
        self.assertEqual(raised.exception.detail["code"], "EXAM_QUESTION_NOT_APPROVED")

    def test_missing_question_is_rejected(self):
        with patch("repositories.question_repo", FakeQuestions({})), \
             patch("repositories.exam_set_repo", FakeExamSets()):
            with self.assertRaises(HTTPException) as raised:
                admin_service.create_exam_set("시험", "T1", ["missing"])
        self.assertIn("missing", raised.exception.detail["question_ids"])
```

- [ ] **Step 2: Run and verify reviewing case fails**

Run:

```powershell
python -m unittest ../tests/services/test_exam_set_approval_guard.py -v
```

Expected: reviewing and missing cases FAIL because current code only checks existence through `get_all_questions()`.

- [ ] **Step 3: Implement one server-side guard**

```python
def _validate_exam_question_ids(question_repo, question_ids: list[str]) -> list[str]:
    rejected = []
    approved = []
    for question_id in dict.fromkeys(question_ids):
        question = question_repo.get_question(question_id)
        if not question or question.get("status") != "approved":
            rejected.append(question_id)
        else:
            approved.append(question_id)
    if rejected:
        raise HTTPException(status_code=409, detail={
            "code": "EXAM_QUESTION_NOT_APPROVED",
            "message": "승인된 문제만 시험에 사용할 수 있습니다.",
            "question_ids": rejected,
        })
    if not approved:
        raise HTTPException(status_code=400, detail="시험에는 승인 문제 한 개 이상이 필요합니다.")
    return approved
```

Call it before constructing the exam set:

```python
valid_ids = _validate_exam_question_ids(question_repo, question_ids)
```

Remove the current `invalid_question_ids` partial-success response. Invalid or unapproved input must fail atomically.

- [ ] **Step 4: Run focused, API contract, and full tests**

Run:

```powershell
python -m unittest ../tests/services/test_exam_set_approval_guard.py -v
python -m unittest ../tests/api/test_admin_gate_approval.py -v
python -m unittest discover -s ../tests -v
```

Expected: all commands report `OK` with zero failures.

- [ ] **Step 5: Commit Task 5**

```powershell
git add backend/services/admin_service.py tests/services/test_exam_set_approval_guard.py
git commit -m "fix: require approved questions for exam sets"
```

---

### Task 6: Phase 1 통합 검증과 문서 갱신

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/frd.md` only if implementation changes an explicitly approved contract

**Interfaces:**
- Consumes: all Task 1–5 behavior
- Produces: verified Phase 1 completion evidence and exact local/validation environment settings

- [ ] **Step 1: Run the complete backend test suite**

Run from `backend`:

```powershell
python -m unittest discover -s ../tests -v
```

Expected: final line `OK`; zero errors and zero failures.

- [ ] **Step 2: Run strict-mode focused regression**

Run:

```powershell
$env:OJT_STRICT_SHEETS_STORAGE='true'
python -m unittest ../tests/config/test_storage_policy.py ../tests/repositories/test_sheets_fallback_policy.py ../tests/repositories/test_snapshot_compatibility.py ../tests/api/test_exam_identity.py ../tests/services/test_exam_set_approval_guard.py -v
```

Expected: all listed tests PASS in strict mode.

- [ ] **Step 3: Verify no frontend product files changed**

Run from repository root:

```powershell
git diff --name-only HEAD -- frontend/src frontend/dist
```

Expected: no output.

- [ ] **Step 4: Verify formatting and scope**

Run:

```powershell
git diff --check
git status --short
```

Expected: `git diff --check` has no output. Status contains only Phase 1 files and previously approved documentation files.

- [ ] **Step 5: Update operational documentation**

Add these exact rules to `CLAUDE.md` if they are not already present:

```markdown
- 검증·운영: `OJT_STRICT_SHEETS_STORAGE=true`; Sheets 오류는 API 실패로 노출한다.
- 로컬 개발: fallback이 필요할 때만 `OJT_STRICT_SHEETS_STORAGE=false`를 명시한다.
- Migration은 기본 Dry-run이며 `--apply` 없이는 외부 Write를 수행하지 않는다.
- 응시자 식별자는 JWT `sub`, `team`, `name`을 사용한다.
- 시험 세트에는 `approved` 문제만 저장할 수 있다.
```

- [ ] **Step 6: Commit Phase 1 verification docs**

```powershell
git add CLAUDE.md docs/frd.md
git commit -m "docs: document Phase 1 safety contracts"
```

Skip `docs/frd.md` from `git add` when it has no implementation-driven change. Do not create an empty commit.

- [ ] **Step 7: Record handoff evidence**

The handoff must include:

```text
- full unittest command and pass count
- strict focused command and pass count
- git diff --check result
- changed file list
- migration Dry-run commands
- remaining Git author identity blocker, if present
- explicit statement that no Google Sheet was modified
```

Do not claim Phase 1 complete without fresh command output from Steps 1–4.
