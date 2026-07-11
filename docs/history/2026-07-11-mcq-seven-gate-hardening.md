# 객관식 문제 생성 7-Gate 고도화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. 모든 단계는 체크박스를 갱신하고 테스트 실패를 먼저 확인한 뒤 구현한다.

**Goal:** 기존 문제 생성 흐름과 API 경로를 유지하면서 4지선다 단일정답 문제의 V01~V07 검증을 실패 폐쇄 방식으로 고도화하고, Hard Fail·필수 Gate 미통과·오래된 Gate Snapshot 문제의 승인을 서버에서 차단한다.

**Architecture:** `gates.py`는 외부 I/O가 없는 판정 함수와 Legacy 호환 응답을 담당한다. 새 `gate_service.py`는 교육자료, 팀, 문제은행, 출제 통계를 수집해 Gate Context를 만들고 V02·V03의 의미 검증기를 호출한다. 상세 결과는 기존 `question_bank.flags` JSON 안의 `gate_snapshot`에 저장해 이번 범위에서는 Repository와 Google Sheets 열을 변경하지 않는다.

**Tech Stack:** Python 3, FastAPI, 표준 라이브러리 `unittest`, `dataclasses`, `hashlib`, `difflib`, `re`, `unicodedata`, 기존 Gemini·Claude·Mock AI Provider.

## Global Constraints

- 활성 문제 유형은 `MULTIPLE_CHOICE_SINGLE` 하나뿐이다.
- 빈칸형, 단답형, 서술형, 다중정답, 부분점수는 구현하지 않는다.
- 기존 `POST /api/admin/generate-ai-questions` 경로를 유지한다.
- 기존 `POST /api/admin/questions/{question_id}/approve` 경로를 유지한다.
- 기존 `question_repo`와 `question_bank`를 계속 사용한다.
- `question_bank_v2`, 별도 Gate 앱, `/api/v2`를 만들지 않는다.
- 관리자 UI, 시험 생성, 시험 응시, 채점, Material Parser를 수정하지 않는다.
- Google Sheets 열 추가, 열 이동, Write Migration을 실행하지 않는다.
- Feature Flag 기본값은 `legacy`다.
- `strict` 모드에서는 검증기 오류와 불명확한 결과를 PASS로 바꾸지 않는다.
- V01, V02, V03, V07은 승인 필수 PASS Gate다.
- V04, V05, V06의 WARNING 승인은 관리자 사유가 있을 때만 허용한다.
- HARD_FAIL과 REVIEW_REQUIRED는 승인할 수 없다.
- 테스트를 먼저 작성하고 Task별로 작은 Commit을 만든다.
- 구현 시작 전 최신 `origin/develop`을 다시 확인한다.

---

## 1. 기준 코드와 원격 충돌 상황

계획 작성 시 최신 원격 기준은 `origin/develop`의 `7d51335`다. 현재 작업 브랜치는 문서 전용 `codex/docs-history-rules`이며 최신 원격으로 Rebase하려 했지만 승인 시스템 사용량 제한으로 실행되지 않았다. 구현 에이전트는 이 문서를 작성한 브랜치에서 바로 코딩하지 말고 최신 `origin/develop`에서 별도 Feature Branch 또는 Worktree를 만들어야 한다.

최신 원격에서 Gate 관련 실제 호출은 다음과 같다.

```text
POST /api/admin/generate-ai-questions
→ backend/api/admin.py::generate_ai_questions
→ backend/services/admin_service.py::generate_ai_questions
→ ai_engine.router.generate_questions_from_material
→ services.generation.gates.run_gates(question)
→ pass=True인 문제만 question_repo.add_question(..., status="reviewing")

POST /api/admin/questions/{question_id}/approve
→ backend/api/admin.py::approve_question
→ backend/services/admin_service.py::approve_question
→ status가 reviewing 또는 draft이면 question_repo.update_question(status="approved")
```

현재 `gates.py`는 다음 한계를 가진다.

- V01은 필드 존재만 검사하고 `question_type`과 정확히 네 개의 보기 계약을 검사하지 않는다.
- V02는 보기 중복만 검사하며 실제로는 Grounding Gate가 아니다.
- V03은 정답 문자가 A~D인지 확인할 뿐 복수정답 가능성과 사실 정합성을 검사하지 않는다.
- V04는 해설 존재만 확인하고 출처가 문제와 정답을 뒷받침하는지 검사하지 않는다.
- V05는 난이도 값의 범위만 확인한다.
- V06 실패는 `warning=true`만 남기며 실패 이유가 사라진다.
- V07 실패는 `security_hold=true`만 남기고 `pass=true`가 될 수 있다.
- 승인 함수는 Gate Snapshot을 확인하지 않고 `draft`도 승인한다.
- Gate 결과가 문제 내용과 같은 버전인지 확인할 fingerprint가 없다.
- 의미 검증기 호출 실패 시의 정책이 없다.

원격 `7d51335`에서 다음 파일은 다른 팀원이 최근 수정했으므로 구현 직전 충돌 보고가 필요하다.

```text
backend/api/admin.py
backend/services/admin_service.py
frontend/src/pages/Admin.jsx
```

이번 계획은 `frontend/src/pages/Admin.jsx`를 수정하지 않는다. 앞의 두 백엔드 파일은 최신 함수 내용을 보존한 상태에서 Gate 관련 최소 구간만 수정한다.

---

## 2. 고려한 접근 방식

### 접근 A. 정규식과 길이 검사만 강화

장점은 빠르고 외부 API 비용이 없다는 점이다. 단점은 질문과 정답이 교육자료로 증명되는지, 보기 중 두 개가 의미상 같은지, 정답이 실제로 하나인지 판단할 수 없다는 점이다. V02와 V03을 완성했다고 주장할 수 없어 채택하지 않는다.

### 접근 B. 모든 Gate를 AI 한 번에 위임

장점은 구현 파일이 적다는 점이다. 단점은 같은 입력의 판정이 흔들릴 수 있고 Schema, 개인정보 패턴, 중복 보기 같은 확정 규칙까지 모델 판단에 맡기게 된다는 점이다. API 장애 때 전체 Gate가 불투명해지고 테스트 재현성이 낮아 채택하지 않는다.

### 접근 C. 결정론적 검사와 의미 검증기 결합

이 계획의 채택안이다.

- V01, V04 일부, V05 일부, V06 문자열 유사도, V07 개인정보 패턴은 순수 함수로 검사한다.
- V02 Grounding과 V03 Single Answer는 구조 검사 통과 후 의미 검증기를 호출한다.
- V04·V05의 정성 판정도 의미 검증 결과를 보조 근거로 사용한다.
- 의미 검증기 오류는 `REVIEW_REQUIRED`이며 PASS가 아니다.
- Legacy 응답 필드는 유지하고 상세 판정 필드를 추가한다.

이 방식은 코드 변경 범위를 Gate 인접 모듈로 제한하면서도 규칙 기반 검증의 한계를 숨기지 않는다.

---

## 3. 이번 범위와 제외 범위

### 구현 범위

- 객관식 단일정답 V01~V07 판정 계약.
- Gate별 상태·코드·이유·상세정보.
- 전체 상태 계산과 Legacy 호환 결과.
- 문제와 Gate Snapshot 일치 여부를 확인하는 fingerprint.
- 생성 시 Gate Context 구성.
- strict 모드의 의미 검증기 호출.
- Gate 결과를 기존 `flags` JSON에 저장.
- Gate 통과·실패 문제 상태 결정.
- 승인 시 Gate Snapshot과 필수 PASS Gate 검증.
- WARNING 승인용 선택적 관리자 사유.
- 단위·서비스·API 계약 테스트.

### 명시적 제외 범위

- Material을 슬라이드 단위로 변환하는 작업.
- `material_id`, `slide_id`, `knowledge_unit_id` 신규 원장.
- `gate_results` 신규 Sheet와 Gate 실행 이력 테이블.
- 관리자 Gate 상세 패널과 재실행 버튼.
- 문제 본문 편집 UI.
- 시험세트, 응시, 채점, 결과 저장 변경.
- `question_bank` 신규 열과 Migration.

현재 시스템은 슬라이드 ID와 KnowledgeUnit을 제공하지 않는다. 따라서 V02는 생성에 실제 사용된 `material_text`와 그 SHA-256 digest를 근거로 평가한다. 존재하지 않는 출처 ID를 임의 생성하지 않는다. 향후 출처 모델이 도입되면 `GateContext`에 선택적 `source_refs`를 추가하고 Gate 결과 계약은 유지한다.

---

## 4. 최종 Gate 결과 계약

`run_gates()`의 반환값은 기존 필드를 유지하면서 다음 필드를 추가한다.

```python
{
    "pass": False,
    "failed": ["V02_GROUNDING_UNSUPPORTED", "V07_PHONE_DETECTED"],
    "flags": {
        "warning": False,
        "security_hold": True,
    },
    "overall_status": "HARD_FAIL",
    "gate_version": "mcq-7gate-v1",
    "question_fingerprint": "sha256:...",
    "source_digest": "sha256:...",
    "gates": {
        "V01": {
            "status": "PASS",
            "code": "V01_OK",
            "reason": "객관식 단일정답 Schema가 유효합니다.",
            "details": {},
        },
        "V02": {
            "status": "HARD_FAIL",
            "code": "V02_GROUNDING_UNSUPPORTED",
            "reason": "교육자료에서 질문과 정답의 근거를 확인할 수 없습니다.",
            "details": {"verdict": "UNSUPPORTED"},
        },
        "V03": {},
        "V04": {},
        "V05": {},
        "V06": {},
        "V07": {},
    },
}
```

허용 상태는 네 개로 고정한다.

```text
PASS
WARNING
REVIEW_REQUIRED
HARD_FAIL
```

전체 상태 우선순위는 다음과 같다.

```text
HARD_FAIL > REVIEW_REQUIRED > WARNING > PASS
```

`pass`는 Legacy 호환 필드다. `overall_status`가 `PASS` 또는 `WARNING`이고 V01·V02·V03·V07이 모두 PASS일 때만 `True`다. 의미 검증기가 실패했거나 응답을 파싱하지 못하면 `False`다.

`failed`에는 사람용 장문 메시지 대신 안정적인 오류 코드를 넣는다. 화면이나 로그용 설명은 각 Gate의 `reason`에 둔다. 기존 화면에서 문자열 목록을 그대로 보여도 의미가 통하도록 코드는 `V02_GROUNDING_UNSUPPORTED`처럼 작성한다.

---

## 5. Gate Context와 의미 검증기 계약

`backend/services/generation/gate_service.py`에 다음 계약을 만든다.

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GateContext:
    material_text: str
    team_code: str
    pool_key: str
    category_label: str
    approved_questions: tuple[dict, ...]
    flagged_question_ids: frozenset[str]


class SemanticGateVerifier(Protocol):
    def verify(self, question: dict, context: GateContext) -> dict:
        ...
```

Production 구현은 `ai_engine/gate_verifier.py`의 `ProviderSemanticGateVerifier` 하나로 고정한다.

```python
class ProviderSemanticGateVerifier:
    def __init__(self, provider: str):
        self.provider = provider

    def verify(self, question: dict, context: GateContext) -> dict:
        ...
```

`ai_engine/router.py::get_semantic_gate_verifier()`가 현재 `AI_PROVIDER`에 맞는 `ProviderSemanticGateVerifier`를 반환한다. `gate_service.py`는 Router나 Provider 구현을 직접 import하지 않고 `SemanticGateVerifier` Protocol에만 의존한다. `admin_service.py`가 Router에서 Verifier를 얻어 `evaluate_candidate()`에 주입한다.

```python
def get_semantic_gate_verifier() -> ProviderSemanticGateVerifier:
    provider = os.getenv("AI_PROVIDER", "mock").strip().lower()
    if provider not in {"mock", "gemini", "claude"}:
        raise ValueError(f"지원하지 않는 AI_PROVIDER: {provider}")
    return ProviderSemanticGateVerifier(provider)
```

`provider="mock"` 객체의 `verify()`는 임의 PASS 결과를 만들지 않고 `SemanticVerifierUnavailable`을 발생시킨다. Gate Service가 이 예외를 잡아 V02·V03을 REVIEW_REQUIRED로 바꾼다.

순환 import를 막기 위해 `gates.py`는 `gate_service.py`를 import하지 않는다. 결정론적 Gate 함수는 `question`과 필요한 primitive 값만 인자로 받거나 `TYPE_CHECKING` 아래에서만 `GateContext`를 참조한다.

의미 검증기 반환 계약은 다음으로 고정한다.

```python
{
    "grounding": "SUPPORTED",  # SUPPORTED | PARTIAL | UNSUPPORTED
    "grounding_reason": "교육자료의 작업 인원 설명과 정답 B가 일치합니다.",
    "single_answer": "PASS",  # PASS | FAIL | UNCERTAIN
    "single_answer_reason": "B만 자료와 일치하며 나머지 보기는 명확히 틀립니다.",
    "distractor_status": "PASS",  # PASS | WARNING | REVIEW_REQUIRED | HARD_FAIL
    "distractor_reason": "보기 형식과 난이도가 균형적입니다.",
    "scope_status": "PASS",  # PASS | WARNING | REVIEW_REQUIRED | HARD_FAIL
    "scope_reason": "T2 팀별 교육 범위와 일치합니다.",
}
```

알 수 없는 Enum 값, 누락 키, 비 JSON 응답은 검증기 성공으로 처리하지 않는다. `gate_service`가 이를 `REVIEW_REQUIRED`로 변환하고 `SEMANTIC_VERIFIER_INVALID_RESPONSE` 코드를 남긴다.

AI 호출 오류 정책은 다음과 같다.

| 상황 | 결과 |
|---|---|
| API timeout | V02·V03 `REVIEW_REQUIRED` |
| 인증키 없음 | strict 모드 생성 실패 502 또는 Candidate 검증 실패 응답 |
| JSON 파싱 실패 | V02·V03 `REVIEW_REQUIRED` |
| `grounding=UNSUPPORTED` | V02 `HARD_FAIL` |
| `grounding=PARTIAL` | V02 `REVIEW_REQUIRED` |
| `single_answer=FAIL` | V03 `HARD_FAIL` |
| `single_answer=UNCERTAIN` | V03 `REVIEW_REQUIRED` |

strict 모드에서 `AI_PROVIDER=mock`이면 네트워크 호출을 하지 않는다. 테스트용 고정 Verifier를 주입하지 않은 실제 요청은 V02·V03을 `REVIEW_REQUIRED`로 처리해 승인되지 않게 한다. Mock 결과를 근거가 확인된 문제처럼 PASS시키지 않는다.

---

## 6. V01~V07 상세 판정 규칙

### V01 Schema

다음 항목을 모두 검사한다.

- `question_type`이 없으면 Legacy 객관식으로 간주해 `MULTIPLE_CHOICE_SINGLE`을 적용한다.
- 다른 `question_type` 값은 `V01_UNSUPPORTED_QUESTION_TYPE` HARD_FAIL이다.
- `question_id`, `category`, `question`, `option_a`~`option_d`, `answer`, `explanation`이 문자열이다.
- 질문과 네 보기는 trim 후 비어 있지 않다.
- 보기는 정확히 A~D 네 개다.
- 선택지의 NFKC 정규화 결과가 서로 다르다.
- 정답은 trim·대문자 변환 후 A~D 중 하나다.
- 정답이 가리키는 선택지가 존재한다.
- 난이도는 이 Gate에서 검사하지 않고 V05가 담당한다.

하나라도 실패하면 V01은 HARD_FAIL이다. V01이 HARD_FAIL이어도 나머지 결정론적 Gate는 가능한 범위에서 실행해 한 번에 오류를 보여주되 의미 검증기는 호출하지 않는다.

### V02 Grounding

다음 순서로 검사한다.

1. `GateContext.material_text.strip()`이 비어 있으면 `V02_SOURCE_MISSING` HARD_FAIL이다.
2. 자료의 SHA-256 digest를 계산해 Gate Snapshot에 기록한다.
3. 질문, 정답 선택지, 해설을 의미 검증기에 전달한다.
4. `SUPPORTED`만 PASS다.
5. `PARTIAL`은 REVIEW_REQUIRED다.
6. `UNSUPPORTED`는 HARD_FAIL이다.

의미 검증기 프롬프트에는 문제 생성에 사용된 자료만 넣고 모델의 외부 지식을 사용하지 말라고 명시한다. 출력에는 근거 문장을 300자 이하로 반환하게 하며 전화번호·이메일 등 V07 대상 문자열은 저장 전에 마스킹한다.

### V03 Single Answer Correctness

결정론적 검사와 의미 검증을 함께 적용한다.

- 정답 문자가 A~D인지 확인한다.
- 네 보기의 정규화 문자열이 모두 다른지 확인한다.
- `SequenceMatcher` 유사도가 0.92 이상인 보기 쌍이 있으면 의미상 중복 가능성으로 REVIEW_REQUIRED다.
- 의미 검증기가 `single_answer=FAIL`을 반환하면 HARD_FAIL이다.
- 의미 검증기가 `UNCERTAIN`을 반환하면 REVIEW_REQUIRED다.
- 결정론적 검사와 의미 검증이 모두 통과해야 PASS다.

V03은 정답이 맞다는 모델의 한 줄 주장만으로 PASS시키지 않는다. V02가 SUPPORTED이고 정답 하나만 자료에 의해 지지된다는 결과가 함께 있어야 한다.

### V04 Distractor Quality

다음 확정 규칙은 결정론적으로 검사한다.

```text
모두 맞다
모두 옳다
위 보기 모두
정답 없음
상황에 따라 다르다
알 수 없음
```

- 금지 문구가 있으면 기본 REVIEW_REQUIRED다.
- 정답 선택지만 다른 보기 중앙값보다 1.8배 이상 길면 WARNING이다.
- 가장 긴 보기와 가장 짧은 보기의 길이 비율이 3.0을 넘으면 WARNING이다.
- 보기의 문장부호와 종결 형식이 혼합되면 WARNING이다.
- 의미 검증기의 `distractor_status`가 더 높은 심각도이면 그 결과를 사용한다.
- 의미 검증기가 명백한 복수정답 유도나 정답 노출을 판정하면 HARD_FAIL이다.

### V05 Scope & Difficulty

- `category`는 `공통`, `팀별`, `환경안전`, `일반상식` 중 하나다.
- `context.category_label`과 문제 `category`가 다르면 HARD_FAIL이다.
- `context.pool_key`와 `team_code` 조합이 기존 `TEAM_KEY_MAP` 규칙과 다르면 HARD_FAIL이다.
- `difficulty_init` 또는 `difficulty_ai`는 `상`, `중`, `하` 중 하나다.
- AI 난이도와 의미 검증기의 범위 판단이 불명확하면 REVIEW_REQUIRED다.
- `admin_override`가 비어 있으면 생성 Gate는 WARNING으로 남긴다.
- 승인 시에는 `admin_override` 또는 명시적인 관리자 난이도 확정이 필요하다.

이번 범위에서는 공정·업무 코드가 없으므로 이를 임의 생성하지 않는다. 향후 필드가 생기면 V05 details에 추가한다.

### V06 Duplicate & Exposure

표준 라이브러리만 사용해 다음을 검사한다.

- NFKC 정규화 후 공백·문장부호를 제거한 문제가 기존 승인 문제와 완전히 같으면 HARD_FAIL이다.
- `SequenceMatcher` 유사도가 0.92 이상이면 REVIEW_REQUIRED다.
- 0.82 이상 0.92 미만이면 WARNING이다.
- 같은 `question_id`가 이미 있으면 HARD_FAIL이다.
- `flagged_question_ids`에 들어 있는 문제와 동일 ID이면 WARNING이다.
- 같은 배치 안의 Candidate끼리도 동일 기준으로 비교한다.

Gate Context에 현재 Candidate 자신이 포함되지 않도록 서비스에서 제외한다. 비교 결과에는 가장 유사한 문제 ID와 similarity를 남긴다.

### V07 Security & Media

다음 영역을 합쳐 검사한다.

```text
question
option_a
option_b
option_c
option_d
explanation
선택적으로 전달된 media metadata
```

확정 HARD_FAIL 패턴은 다음과 같다.

- 한국 전화번호 형식.
- 이메일 주소.
- `http://`, `https://` 내부·외부 URL.
- 비밀번호, 보안코드, 관리자계정, 서버접속 키워드.
- `사번`, `직번`, `employee id` 라벨 뒤의 식별자.
- media가 존재하지만 `approved=true`가 아닌 경우.
- media OCR 결과에 정답 표시 패턴이 있는 경우.

설비번호는 업무상 정상 자료일 수 있으므로 번호만으로 HARD_FAIL시키지 않는다. `equipment_identifier_detected` WARNING을 남기고 관리자가 확인하게 한다. 실명 판정도 한국어 일반 명사와 혼동 가능성이 있어 명시적 인물 메타데이터가 없으면 REVIEW_REQUIRED로 둔다.

V07이 PASS가 아니면 승인할 수 없다. 기존처럼 `security_hold`만 세우고 `pass=true`를 반환하는 동작을 금지한다.

---

## 7. 문제 Fingerprint와 Gate Snapshot

Fingerprint는 Gate 실행 후 문제 내용이 바뀌었는지 확인하기 위해 사용한다. 다음 필드만 고정 순서 JSON으로 직렬화한다.

```text
question_type
question_id
category
question
option_a
option_b
option_c
option_d
answer
explanation
difficulty_init
difficulty_ai
admin_override
```

```python
def question_fingerprint(question: dict) -> str:
    payload = {key: question.get(key, "") for key in FINGERPRINT_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

승인 시 저장된 `gate_snapshot.question_fingerprint`와 현재 문제 fingerprint가 다르면 HTTP 409 `GATE_RESULT_STALE`을 반환한다. 내용이 바뀐 문제를 과거 Gate 결과로 승인하지 않는다.

Gate Snapshot은 기존 Sheets A:R 중 `flags` JSON 셀에 다음 형태로 저장한다.

```python
question["flags"] = {
    "warning": gate_result["overall_status"] == "WARNING",
    "security_hold": gate_result["gates"]["V07"]["status"] != "PASS",
    "gate_snapshot": gate_result,
}
question["gate_errors"] = gate_result["failed"]
```

이 방식은 이번 단계에서 Repository와 Sheets 열을 수정하지 않으면서 상세 결과를 보존한다. 장기적으로 `gate_results` Append-only 원장이 생기면 이 Snapshot은 승인 당시 결과의 호환 사본으로 유지한다.

---

## 8. 승인 정책

strict 모드 승인 조건은 모두 만족해야 한다.

```text
question.status == reviewing
gate_snapshot 존재
gate_snapshot.gate_version == mcq-7gate-v1
현재 fingerprint == snapshot fingerprint
overall_status != HARD_FAIL
overall_status != REVIEW_REQUIRED
V01 == PASS
V02 == PASS
V03 == PASS
V07 == PASS
admin_override in {상, 중, 하}
```

V04·V05·V06 중 WARNING이 있으면 `override_reason`이 trim 후 10자 이상이어야 한다. 이유 없이 승인하면 HTTP 409 `GATE_WARNING_OVERRIDE_REQUIRED`를 반환한다.

승인 API의 기존 body 없는 호출을 유지하기 위해 요청 Body는 선택값으로 추가한다.

```python
class ApproveQuestionRequest(BaseModel):
    override_reason: str = ""


@router.post("/questions/{question_id}/approve")
def approve_question(
    question_id: str,
    body: ApproveQuestionRequest | None = None,
    actor: dict = Depends(require_admin),
):
    return service_approve_question(
        question_id,
        actor=actor,
        override_reason=body.override_reason if body else "",
    )
```

현재 UI는 body 없이 호출한다. Gate가 모두 PASS인 문제는 그대로 승인된다. WARNING 문제는 이번 범위에서 UI를 바꾸지 않으므로 API 직접 호출 또는 후속 UI 작업 전까지 승인되지 않는다. 이 제한은 조용한 우회보다 안전하다.

legacy 모드에서는 기존 문제 승인 동작을 보존한다. 단, 이미 `security_hold=true`인 문제는 legacy에서도 승인하지 않도록 보안 수정은 공통 적용한다.

안정적인 오류 코드는 다음으로 고정한다.

```text
GATE_SNAPSHOT_MISSING
GATE_VERSION_UNSUPPORTED
GATE_RESULT_STALE
GATE_REQUIRED_PASS_MISSING
GATE_HARD_FAIL
GATE_REVIEW_REQUIRED
GATE_WARNING_OVERRIDE_REQUIRED
GATE_ADMIN_DIFFICULTY_REQUIRED
GATE_SECURITY_HOLD
```

---

## 9. 변경 파일 지도

### 수정 파일

| 파일 | 책임 | 수정 범위 |
|---|---|---|
| `backend/services/generation/gates.py` | 순수 Gate 규칙과 결과 조립 | 기존 함수 호환 유지, V01~V07 재정의 |
| `backend/services/admin_service.py` | 생성 Context 구성과 승인 Guard | `generate_ai_questions`, `approve_question`의 Gate 인접 구간만 수정 |
| `backend/api/admin.py` | 선택적 승인 사유와 actor 전달 | 승인 Request와 승인 Route만 수정 |
| `ai_engine/router.py` | 의미 검증 Provider 선택 | 기존 생성 Router를 유지하고 검증 함수만 추가 |

### 신규 파일

| 파일 | 책임 |
|---|---|
| `backend/services/generation/gate_service.py` | Context, semantic verifier 호출, strict/legacy 분기, Snapshot 저장 형태 조립 |
| `ai_engine/gate_verifier.py` | Gemini·Claude 검증 Prompt 호출과 응답 JSON 파싱 |
| `tests/services/generation/test_gate_rules.py` | V01·V04·V05·V06·V07 순수 규칙 테스트 |
| `tests/services/generation/test_gate_service.py` | V02·V03, 전체 상태, fingerprint, verifier 오류 테스트 |
| `tests/services/test_question_gate_integration.py` | 생성 저장 상태와 승인 Guard 테스트 |
| `tests/api/test_admin_gate_approval.py` | 기존 body 없는 승인과 선택적 override_reason API 계약 테스트 |

### 변경 금지 파일

```text
backend/repositories/base.py
backend/repositories/local_json.py
backend/repositories/sheets_repo.py
backend/repositories/__init__.py
backend/services/material_service.py
backend/services/exam_service.py
backend/api/exam.py
frontend/src/pages/Admin.jsx
frontend/src/pages/Exam.jsx
frontend/dist/**
```

구현 중 변경 금지 파일이 필요해지면 작업을 중단하고 이유, 필요한 변경, 대안, 위험을 사용자에게 보고한다.

---

## 10. Task별 TDD 구현 절차

### Task 0. 구현 브랜치 기준선 잠금

**Files**

- Read: `AGENTS.md`.
- Read: `docs/history/README.md`.
- Read: 이 계획서.
- No code changes.

**Interfaces**

- Consumes: 최신 `origin/develop`.
- Produces: 충돌 없는 Gate 전용 Feature Branch와 Baseline 보고.

- [x] **Step 1: 원격 상태를 확인한다.**

```bash
git status --short
git branch --show-current
git fetch origin
git log --oneline HEAD..origin/develop
git diff --name-only HEAD...origin/develop
```

Expected는 작업 트리가 깨끗하고 원격 변경 파일 목록이 확인되는 것이다.

- [x] **Step 2: Gate 대상 파일의 원격 변경을 보고한다.**

```text
backend/services/generation/gates.py
backend/services/admin_service.py
backend/api/admin.py
ai_engine/router.py
```

원격 변경이 있으면 함수별 diff와 통합 방안을 기록한다.

- [x] **Step 3: 최신 develop에서 격리된 Branch 또는 Worktree를 만든다.**

프로젝트의 Branch 규칙과 Codex 환경의 Worktree 기능을 따른다. 공유 Branch에서 Rebase하지 않는다.

- [x] **Step 4: Baseline 컴파일을 실행한다.**

```bash
python -m compileall backend ai_engine
```

Expected는 exit code 0이다.

### Task 1. Legacy Gate 특성 고정

**Files**

- Create: `tests/services/generation/test_gate_rules.py`.
- Modify: 없음.

**Interfaces**

- Consumes: 현재 `run_gates(question)`.
- Produces: legacy 모드에서 보존해야 할 `pass`, `failed`, `flags` 계약.

- [x] **Step 1: 테스트 패키지 디렉터리를 만든다.**

각 새 Python 소스 파일의 첫 줄에는 역할을 설명하는 한국어 주석을 넣는다. `__init__.py`가 필요하면 빈 파일로 만들지 말고 한국어 모듈 설명을 넣는다.

- [x] **Step 2: 현재 정상 문제 Fixture를 작성한다.**

```python
VALID_QUESTION = {
    "question_id": "team2-test-001",
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
    "admin_override": "",
    "status": "draft",
}
```

- [x] **Step 3: Legacy 응답 필드 테스트를 작성한다.**

```python
def test_legacy_result_keeps_required_fields(self):
    result = run_gates(dict(VALID_QUESTION))
    self.assertIn("pass", result)
    self.assertIn("failed", result)
    self.assertIn("flags", result)
    self.assertIn("warning", result["flags"])
    self.assertIn("security_hold", result["flags"])
```

- [x] **Step 4: 테스트를 실행해 현재 Baseline을 확인한다.**

```bash
python -m unittest tests.services.generation.test_gate_rules -v
```

Expected는 Legacy 특성 테스트가 PASS하는 것이다. 기존 코드가 이미 기대와 다르면 계획을 임의 변경하지 말고 차이를 기록한다.

- [x] **Step 5: Commit한다.**

```bash
git add tests/services/generation
git commit -m "test: 현재 7-Gate 호환 계약 고정"
```

### Task 2. 상태 모델과 결정론적 Gate 구현

**Files**

- Modify: `backend/services/generation/gates.py`.
- Modify: `tests/services/generation/test_gate_rules.py`.

**Interfaces**

- Produces: `normalize_text`, `question_fingerprint`, V01·V04·V05·V06·V07 판정 함수.
- Produces: Gate 상태 우선순위와 dual result.

- [x] **Step 1: 실패 테스트를 추가한다.**

최소 다음 Case를 각각 독립 테스트로 만든다.

```text
question_type이 MULTIPLE_CHOICE_SINGLE이 아님
빈 문제
빈 보기
NFKC 정규화 후 중복 보기
정답 E
금지 문구 모두 맞다
정답 보기만 과도하게 김
카테고리 오류
난이도 오류
기존 문제와 완전 중복
기존 문제와 0.92 이상 유사
전화번호
이메일
URL
보안 키워드
미승인 media
설비번호만 존재
```

예시 테스트는 다음과 같다.

```python
def test_v07_phone_is_hard_fail(self):
    question = {**VALID_QUESTION, "explanation": "문의 010-1234-5678"}
    result = run_deterministic_gates(question, self.context)
    self.assertEqual(result["gates"]["V07"]["status"], "HARD_FAIL")
    self.assertEqual(result["gates"]["V07"]["code"], "V07_PHONE_DETECTED")
```

- [x] **Step 2: 테스트가 실패하는지 확인한다.**

```bash
python -m unittest tests.services.generation.test_gate_rules -v
```

Expected는 새 함수가 없거나 새 판정이 구현되지 않아 FAIL하는 것이다.

- [x] **Step 3: Gate 상태 상수와 결과 생성기를 구현한다.**

```python
GATE_STATUSES = {"PASS", "WARNING", "REVIEW_REQUIRED", "HARD_FAIL"}
STATUS_PRIORITY = {
    "PASS": 0,
    "WARNING": 1,
    "REVIEW_REQUIRED": 2,
    "HARD_FAIL": 3,
}


def gate_result(status: str, code: str, reason: str, details: dict | None = None) -> dict:
    if status not in GATE_STATUSES:
        raise ValueError(f"지원하지 않는 Gate 상태: {status}")
    return {
        "status": status,
        "code": code,
        "reason": reason,
        "details": details or {},
    }
```

- [x] **Step 4: 정규화와 fingerprint를 구현한다.**

정규화는 NFKC, trim, 소문자화, 연속 공백 축소를 적용한다. 중복 비교용 정규화는 문장부호와 공백도 제거하되 원문 저장값은 바꾸지 않는다.

- [x] **Step 5: V01·V04·V05·V06·V07을 구현한다.**

각 Gate는 다른 Gate의 전역 상태를 수정하지 않고 자신의 결과 dict만 반환한다. `run_deterministic_gates()`가 결과를 조립한다.

- [x] **Step 6: 전체 상태 우선순위 테스트를 추가한다.**

```python
def test_overall_status_uses_highest_severity(self):
    self.assertEqual(overall_status(["PASS", "WARNING"]), "WARNING")
    self.assertEqual(overall_status(["WARNING", "REVIEW_REQUIRED"]), "REVIEW_REQUIRED")
    self.assertEqual(overall_status(["PASS", "HARD_FAIL"]), "HARD_FAIL")
```

- [x] **Step 7: 테스트를 재실행한다.**

```bash
python -m unittest tests.services.generation.test_gate_rules -v
```

Expected는 모든 결정론적 Gate 테스트 PASS다.

- [x] **Step 8: Commit한다.**

```bash
git add backend/services/generation/gates.py tests/services/generation/test_gate_rules.py
git commit -m "feat: 객관식 결정론적 Gate 검증 강화"
```

### Task 3. 의미 검증기와 V02·V03 구현

**Files**

- Create: `ai_engine/gate_verifier.py`.
- Modify: `ai_engine/router.py`.
- Create: `backend/services/generation/gate_service.py`.
- Create: `tests/services/generation/test_gate_service.py`.

**Interfaces**

- Produces: `GateContext`.
- Produces: `SemanticGateVerifier` Protocol.
- Produces: `ProviderSemanticGateVerifier.verify(question, context) -> dict`.
- Produces: `get_semantic_gate_verifier() -> SemanticGateVerifier`.
- Produces: `evaluate_candidate(question, context, verifier, mode) -> dict`.

- [x] **Step 1: Fake Verifier 기반 실패 테스트를 작성한다.**

```python
class FakeVerifier:
    def __init__(self, result):
        self.result = result

    def verify(self, question, context):
        return self.result


def test_v02_unsupported_is_hard_fail(self):
    verifier = FakeVerifier({
        "grounding": "UNSUPPORTED",
        "grounding_reason": "자료에 제조사 정보가 없습니다.",
        "single_answer": "PASS",
        "single_answer_reason": "정답은 하나입니다.",
        "distractor_status": "PASS",
        "distractor_reason": "보기 품질이 적절합니다.",
        "scope_status": "PASS",
        "scope_reason": "범위가 일치합니다.",
    })
    result = evaluate_candidate(VALID_QUESTION, CONTEXT, verifier, mode="strict")
    self.assertEqual(result["gates"]["V02"]["status"], "HARD_FAIL")
```

- [x] **Step 2: 다음 의미 검증 Case를 작성한다.**

```text
SUPPORTED → V02 PASS
PARTIAL → V02 REVIEW_REQUIRED
UNSUPPORTED → V02 HARD_FAIL
single_answer PASS → V03 PASS
single_answer FAIL → V03 HARD_FAIL
single_answer UNCERTAIN → V03 REVIEW_REQUIRED
Verifier timeout → V02·V03 REVIEW_REQUIRED
Verifier 비 JSON → REVIEW_REQUIRED
Verifier 필수 키 누락 → REVIEW_REQUIRED
V01 HARD_FAIL이면 Verifier 호출 0회
material_text 빈 값이면 Verifier 호출 0회, V02 HARD_FAIL
```

- [x] **Step 3: 테스트 실패를 확인한다.**

```bash
python -m unittest tests.services.generation.test_gate_service -v
```

Expected는 Gate Service가 없어 FAIL하는 것이다.

- [x] **Step 4: `GateContext`와 Protocol을 구현한다.**

Context는 불변 dataclass를 사용하고 기본 mutable 값을 두지 않는다. 승인 문제 목록은 tuple, 플래그 ID는 frozenset으로 받는다.

- [x] **Step 5: `evaluate_candidate()`를 구현한다.**

실행 순서는 V01 → source 존재 검사 → 의미 검증기 → V02·V03 → V04·V05 보정 → V06 → V07 → 전체 결과 조립이다.

- [x] **Step 6: AI 검증 Prompt와 파서를 구현한다.**

Prompt는 다음 규칙을 포함한다.

```text
제공된 교육자료만 사용한다.
외부 지식으로 정답을 보완하지 않는다.
정답 선택지가 자료로 직접 또는 명확히 증명되는지 확인한다.
오답 세 개가 모두 명확히 틀리는지 확인한다.
응답은 지정된 JSON Object 하나만 반환한다.
판단이 불가능하면 PASS 대신 PARTIAL 또는 UNCERTAIN을 반환한다.
```

`ai_engine/gate_verifier.py`는 기존 Gemini·Claude `_call_api`를 호출하되 API 키를 로그에 출력하지 않는다. Provider별 응답을 동일 dict 계약으로 파싱한다.

- [x] **Step 7: Router에 Verifier Factory만 추가한다.**

기존 `generate_questions_from_material()`을 수정하거나 이름을 바꾸지 않는다. 새 공개 함수는 `get_semantic_gate_verifier()` 하나로 제한한다. `admin_service.py`는 이 Factory가 반환한 객체를 Gate Service에 주입한다.

- [x] **Step 8: 테스트를 재실행한다.**

```bash
python -m unittest tests.services.generation.test_gate_service -v
```

Expected는 네트워크 호출 없이 Fake Verifier 테스트가 모두 PASS하는 것이다.

- [x] **Step 9: Compile을 실행한다.**

```bash
python -m compileall backend/services/generation ai_engine
```

Expected는 exit code 0이다.

- [x] **Step 10: Commit한다.**

```bash
git add ai_engine/gate_verifier.py ai_engine/router.py backend/services/generation/gate_service.py tests/services/generation/test_gate_service.py
git commit -m "feat: 교육자료 기반 Gate 의미 검증 추가"
```

### Task 4. 문제 생성 흐름에 strict Gate 통합

**Files**

- Modify: `backend/services/admin_service.py`.
- Create: `tests/services/test_question_gate_integration.py`.

**Interfaces**

- Consumes: `evaluate_candidate()`.
- Produces: legacy/strict 생성 분기.
- Produces: 기존 `flags` JSON 안의 `gate_snapshot`.

- [x] **Step 1: Repository Fake를 사용한 실패 테스트를 작성한다.**

최소 다음 Case를 검증한다.

```text
OJT_GATE_MODE 미설정 → legacy
OJT_GATE_MODE=legacy → 기존 pass/failed 저장 동작 유지
OJT_GATE_MODE=strict + PASS → status=reviewing
strict + WARNING, 필수 Gate PASS → status=reviewing
strict + REVIEW_REQUIRED → status=draft
strict + HARD_FAIL → status=draft
strict에서 draft도 question_repo에 한 번 저장
flags.gate_snapshot 존재
gate_errors에 안정적인 코드 존재
같은 Candidate 중복 저장 없음
검증기 오류를 PASS로 바꾸지 않음
```

- [x] **Step 2: 테스트 실패를 확인한다.**

```bash
python -m unittest tests.services.test_question_gate_integration -v
```

- [x] **Step 3: `OJT_GATE_MODE` 파서를 추가한다.**

허용값은 `legacy`, `strict` 두 개다. 미설정 기본값은 `legacy`다. 잘못된 값은 서버 시작 또는 요청 시 명시적 오류로 처리하고 임의로 legacy에 폴백하지 않는다.

- [x] **Step 4: Gate Context를 구성한다.**

기존 로직이 이미 읽는 다음 데이터를 재사용한다.

```text
material_text
team_code
pool_key category
category_label
question_repo.get_all_questions()
question_stats_repo.list_flagged()
```

추가 Repository 호출을 반복하지 않도록 전체 문제은행과 통계를 한 번만 읽고 배치의 모든 Candidate에 공유한다.

- [x] **Step 5: strict 결과를 문제 dict에 저장한다.**

strict 모드에서는 PASS 여부와 관계없이 모든 생성 Candidate를 현재 `question_repo`에 정확히 한 번 저장한다. HARD_FAIL·REVIEW_REQUIRED는 `draft`, 검토 가능한 PASS·WARNING은 `reviewing`이다.

legacy 모드에서는 기존 동작을 byte-level까지 요구하지 않지만 응답 필드, 저장 대상, status 의미를 동일하게 유지한다.

- [x] **Step 6: API 응답에 additive Gate 필드를 넣는다.**

기존 `questions` 배열과 기존 필드를 제거하지 않는다. 각 문제에 다음만 추가한다.

```python
{
    "overall_gate_status": q["flags"]["gate_snapshot"]["overall_status"],
    "gates": q["flags"]["gate_snapshot"]["gates"],
}
```

legacy 모드에서는 필드를 생략하거나 Legacy 결과를 변환해 넣되 기존 클라이언트가 깨지지 않아야 한다.

- [x] **Step 7: 테스트를 재실행한다.**

```bash
python -m unittest tests.services.test_question_gate_integration -v
```

Expected는 모든 생성 통합 테스트 PASS다.

- [x] **Step 8: Commit한다.**

```bash
git add backend/services/admin_service.py tests/services/test_question_gate_integration.py
git commit -m "feat: 문제 생성에 강화 Gate 결과 통합"
```

### Task 5. 승인 Guard 구현

**Files**

- Modify: `backend/services/admin_service.py`.
- Modify: `backend/api/admin.py`.
- Modify: `tests/services/test_question_gate_integration.py`.
- Create: `tests/api/test_admin_gate_approval.py`.

**Interfaces**

- Produces: `approve_question(question_id, actor, override_reason="")`.
- Preserves: 기존 승인 API 경로와 body 없는 호출.

- [x] **Step 1: 서비스 승인 실패 테스트를 작성한다.**

```text
문제 없음 → 404
strict에서 status=draft → 409
snapshot 없음 → 409 GATE_SNAPSHOT_MISSING
지원하지 않는 gate_version → 409
fingerprint 불일치 → 409 GATE_RESULT_STALE
overall HARD_FAIL → 409
overall REVIEW_REQUIRED → 409
V01 미통과 → 409
V02 미통과 → 409
V03 미통과 → 409
V07 미통과 → 409
admin_override 없음 → 409
V04 WARNING + 사유 없음 → 409
V04 WARNING + 10자 이상 사유 → 승인
모든 Gate PASS → body 없이 승인
security_hold=true → legacy에서도 승인 차단
```

예시 테스트는 다음과 같다.

```python
def test_approval_rejects_stale_gate_snapshot(self):
    question = make_reviewing_question_with_pass_snapshot()
    question["question"] = "Gate 이후 수정된 문제"
    repo = FakeQuestionRepository(question)
    with patch_repositories(repo):
        with self.assertRaises(HTTPException) as raised:
            approve_question(question["question_id"], actor=ADMIN_ACTOR)
    self.assertEqual(raised.exception.status_code, 409)
    self.assertEqual(raised.exception.detail["code"], "GATE_RESULT_STALE")
```

- [x] **Step 2: API 하위호환 테스트를 작성한다.**

```text
POST approve, body 없음, all PASS → 200
POST approve, {override_reason: ...} → 서비스로 전달
일반 사용자 JWT → 403
토큰 없음 → 401
```

- [x] **Step 3: 실패를 확인한다.**

```bash
python -m unittest tests.services.test_question_gate_integration tests.api.test_admin_gate_approval -v
```

- [x] **Step 4: 승인 Guard를 구현한다.**

검사 순서는 존재 → 상태 → 보안 hold → 모드 → snapshot → version → fingerprint → overall → 필수 Gate → 관리자 난이도 → WARNING 사유 순서다. 첫 실패에서 안정적인 오류 코드와 현재 상태를 반환한다. Gate 전체 원문이나 교육자료 전문을 HTTP 오류에 포함하지 않는다.

- [x] **Step 5: actor와 승인 사유를 저장한다.**

기존 Schema 변경 없이 `flags` 안에 다음 감사 정보를 추가한다.

```python
flags["gate_approval"] = {
    "approved_by": actor.get("sub", ""),
    "override_reason": override_reason.strip(),
    "gate_version": snapshot["gate_version"],
    "question_fingerprint": snapshot["question_fingerprint"],
}
```

승인 시 `status="approved"`와 갱신된 `flags`를 한 번의 `update_question()` 호출로 저장한다.

- [x] **Step 6: 테스트를 재실행한다.**

```bash
python -m unittest tests.services.test_question_gate_integration tests.api.test_admin_gate_approval -v
```

Expected는 모든 승인 Guard 테스트 PASS다.

- [x] **Step 7: Commit한다.**

```bash
git add backend/services/admin_service.py backend/api/admin.py tests/services/test_question_gate_integration.py tests/api/test_admin_gate_approval.py
git commit -m "fix: Gate 미통과 문제 승인 차단"
```

### Task 6. 전체 Gate 회귀와 실패 폐쇄 검증

**Files**

- Modify: Gate 관련 테스트 파일만 필요 시 수정.
- Production code changes are not expected.

**Interfaces**

- Produces: 구현 완료 증거.

- [x] **Step 1: 전체 Gate 테스트를 실행한다.**

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected는 0 failures, 0 errors다.

- [x] **Step 2: Backend compile을 실행한다.**

```bash
python -m compileall backend ai_engine
```

Expected는 exit code 0이다.

- [x] **Step 3: Legacy 모드 회귀를 실행한다.**

```powershell
$env:OJT_GATE_MODE='legacy'
python -m unittest tests.services.test_question_gate_integration -v
```

Expected는 기존 생성 응답과 저장 상태 테스트 PASS다.

- [x] **Step 4: strict 모드 Golden Case를 실행한다.**

```powershell
$env:OJT_GATE_MODE='strict'
python -m unittest tests.services.generation.test_gate_service tests.services.test_question_gate_integration -v
```

Expected는 정상 Baffle 문제 PASS, 무출처·복수정답·전화번호·중복 문제 차단이다.

- [x] **Step 5: 프론트 변경이 없는지 확인한다.**

```bash
git diff --name-only origin/develop...HEAD
```

Expected에 `frontend/`, `backend/repositories/`, `backend/services/exam_service.py`, `backend/api/exam.py`가 없어야 한다.

- [x] **Step 6: 금지 구조를 확인한다.**

```bash
rg -n "question_bank_v2|exam_papers|/api/v2" backend frontend tests
```

Expected는 이번 구현으로 추가된 결과가 없는 것이다.

- [x] **Step 7: 최종 Commit이 필요한 경우 테스트 문서만 Commit한다.**

```bash
git add tests
git commit -m "test: 강화된 7-Gate 회귀 검증 보강"
```

변경 사항이 없으면 빈 Commit을 만들지 않는다.

---

## 11. 필수 테스트 매트릭스

| Gate | PASS Case | 실패·경고 Case | 기대 상태 |
|---|---|---|---|
| V01 | 4개 고유 보기, A~D 정답 | 빈 필드, 중복 보기, unsupported type | HARD_FAIL |
| V02 | 자료가 질문과 정답을 직접 지지 | source 없음, PARTIAL, UNSUPPORTED | HARD_FAIL 또는 REVIEW_REQUIRED |
| V03 | 정답 하나, 오답 세 개 | 유사 보기, 복수정답, 불확실 | HARD_FAIL 또는 REVIEW_REQUIRED |
| V04 | 균형 잡힌 오답 | 모두 맞다, 정답만 긴 보기, 황당한 보기 | WARNING 이상 |
| V05 | 팀·카테고리·난이도 일치 | category 오류, 난이도 오류, admin 미확정 | HARD_FAIL 또는 WARNING |
| V06 | 신규 문제 | exact duplicate, 0.92 유사, 과다 출제 | HARD_FAIL, REVIEW_REQUIRED, WARNING |
| V07 | 개인정보·미디어 없음 | 전화번호, 이메일, URL, 미승인 이미지 | HARD_FAIL |

추가 통합 테스트는 다음을 반드시 포함한다.

- strict 모드에서 semantic verifier가 호출되지 않아야 하는 V01 실패.
- verifier timeout이 PASS로 변하지 않는지 확인.
- Gate Snapshot을 저장한 뒤 문제 본문을 변경하면 승인 차단.
- 다른 문제의 Gate Snapshot을 복사해도 fingerprint로 차단.
- V07 security_hold 문제를 legacy 승인 경로로 우회할 수 없음.
- body 없는 기존 승인 API가 all PASS 문제에서 계속 동작.
- strict 모드 draft 문제가 `question_repo`에 한 번만 저장됨.
- Gate 결과에 API 키, 전체 자료 전문, 개인정보 원문이 포함되지 않음.

---

## 12. 오류 처리와 로그 정책

- 사용자 입력이나 Gate 판정 실패는 `logging.warning` 이하로 기록한다.
- 의미 검증기 API 장애는 Provider 이름, 오류 유형, Candidate ID만 기록한다.
- API 키와 Prompt 전체 원문을 로그에 남기지 않는다.
- `material_text` 전체를 Gate Snapshot이나 오류 응답에 저장하지 않는다.
- 의미 검증 근거 발췌는 300자로 제한하고 V07 패턴을 마스킹한다.
- 예상하지 못한 예외를 `pass=True`로 바꾸지 않는다.
- strict 모드에서 검증을 완료하지 못하면 Candidate는 `draft`이고 승인 불가다.

권장 HTTP 상태는 다음과 같다.

| 상황 | 상태 |
|---|---|
| 문제 없음 | 404 |
| 승인 상태·Gate 조건 충돌 | 409 |
| 잘못된 승인 Body | 422 |
| 의미 검증 Provider 실패 | 생성 요청 502 또는 Candidate REVIEW_REQUIRED |
| 관리자 권한 없음 | 401 또는 403 |

---

## 13. Feature Flag와 Rollout

환경변수는 하나만 추가한다.

```env
OJT_GATE_MODE=legacy
```

허용값은 `legacy`, `strict`다.

권장 적용 순서는 다음과 같다.

1. 코드와 테스트를 배포하고 `legacy`로 유지한다.
2. 로컬 Fake Verifier Golden Case를 검증한다.
3. `admin001` 환경에서 strict 생성만 확인한다.
4. strict 생성 결과의 V01~V07과 승인 차단을 확인한다.
5. Gate 오탐과 의미 검증 비용을 확인한다.
6. 문제가 없을 때 strict를 유지한다.

Rollback은 `OJT_GATE_MODE=legacy`로 되돌리고 서버를 재시작하는 것이다. 저장된 `flags.gate_snapshot`은 삭제하지 않는다. Gate Snapshot이 있는 문제를 legacy 모드에서 읽어도 기존 필드가 유지되어야 한다.

---

## 14. 완료 기준

다음 조건을 모두 만족하기 전에는 7-Gate 고도화 완료를 주장하지 않는다.

- [x] V01~V07 각각의 독립 결과가 존재한다.
- [x] 모든 Gate 결과에 status, code, reason, details가 존재한다.
- [x] V01 Schema 실패가 HARD_FAIL이다.
- [x] V02 SUPPORTED만 PASS다.
- [x] V03 정답 단일성이 불명확하면 PASS가 아니다.
- [x] V04 금지 보기와 길이 누출이 탐지된다.
- [x] V05 팀·카테고리·난이도 불일치가 탐지된다.
- [x] V06 exact duplicate와 고유사 문제가 구분된다.
- [x] V07 전화번호·이메일·URL·보안 Hold가 승인을 차단한다.
- [x] 의미 검증기 장애가 PASS로 변하지 않는다.
- [x] Legacy `pass`, `failed`, `flags` 응답이 유지된다.
- [x] 상세 결과가 기존 `flags.gate_snapshot`에 저장된다.
- [x] fingerprint가 Gate 이후 문제 수정을 탐지한다.
- [x] draft, HARD_FAIL, REVIEW_REQUIRED 승인이 차단된다.
- [x] WARNING 승인은 10자 이상 관리자 사유가 필요하다.
- [x] body 없는 기존 승인 API가 all PASS 문제에서 동작한다.
- [x] Repository, Sheet Schema, Admin UI, Exam UI를 수정하지 않았다.
- [x] 전체 unittest가 0 failures, 0 errors다.
- [x] Backend와 AI Engine compile이 성공한다.
- [x] legacy 모드 회귀가 통과한다.
- [x] strict Baffle Golden Case가 통과한다.

---

## 15. 구현 에이전트 최종 보고 형식

구현을 완료한 에이전트는 다음 내용을 빠짐없이 보고한다.

```text
기준 origin/develop Commit
작업 Branch
원격 변경과 충돌 분석
변경 파일 목록
신규 파일 목록
변경하지 않은 보호 파일 목록
V01~V07 판정표
Feature Flag 값
Legacy 호환 결과
승인 Guard 결과
테스트 명령과 실제 통과 수
compile 결과
외부 AI API 실제 호출 여부
Migration 실행 여부
알려진 한계
Rollback 방법
Commit 목록
```

이번 계획의 핵심은 Gate를 강하게 만들면서도 문제은행, Sheets Schema, 관리자 UI, 시험 흐름을 함께 뜯어고치지 않는 것이다. 현재 데이터가 제공하지 않는 slide·KnowledgeUnit 출처를 꾸며내지 않고, 실제 생성 자료와 의미 검증 결과를 근거로 실패 폐쇄 판정을 구현한다.
