# 객관식 문제 생성 7-Gate 고도화 구현 완료 기록

## 기록 정보

- 기록 시각은 2026-07-11 17:33 KST다.
- 작업 브랜치는 `origin/develop`(당시 최신 커밋 `ea442fb`)에서 새로 분기한 `feature/mcq-seven-gate-hardening`이다.
- 이 기록 시점 HEAD는 `27e79bf`다.
- 구현 대상 계획서는 `docs/history/2026-07-11-mcq-seven-gate-hardening.md`(및 동일 사본 `docs/superpowers/plans/2026-07-11-mcq-seven-gate-hardening.md`)이며, 이번 작업으로 문서의 Task 0~6 체크박스와 완료 기준 체크박스를 모두 `[x]`로 갱신했다.

## 요청과 대화의 핵심 요약

사용자가 위 계획서 경로를 지정하며 "이제 구현하자. 하기 전 깃 상태 확인해서 충돌 없는 경우만 시작해"라고 요청했다. 계획서에 따라 Task 0(기준선 잠금)부터 Task 6(전체 회귀·완료 기준 검증)까지 TDD로 순차 구현했다.

## 확인한 실제 코드·문서·근거

- `git fetch` 결과 `origin/develop`이 계획서 작성 시점 기준(`7d51335`)보다 한 커밋(`ea442fb`, PR #72 시험세트 삭제 기능) 더 진행되어 있었다.
- `git diff HEAD..origin/develop`로 Gate 대상 파일(`gates.py`, `ai_engine/router.py`)이 **완전히 동일**함을 확인했고, `admin_service.py`/`admin.py`는 변경되어 있었지만 실제 diff 내용은 사용자 관리 Sheets 전환·`results-summary`·시험세트 삭제 API로 `generate_ai_questions`/`approve_question`/`run_gates`와는 무관함을 직접 diff로 확인했다.
- 이 저장소에는 pytest/eslint 설정이 없어(CLAUDE.md 명시) 계획서가 지정한 `python -m unittest`로 검증했다.

## 당시 판단과 이유

- 실제 병합 충돌이 없다고 판단해 `origin/develop`에서 새 브랜치를 만들어 바로 구현을 시작했다(사용자 지시대로 "충돌 없는 경우만 시작").
- `gates.py`는 "외부 의존 없음" 원칙을 지키기 위해 `admin_service.TEAM_KEY_MAP`을 import하지 않고 3줄짜리 검증용 사본(`_TEAM_KEY_MAP`)을 별도로 두었다. admin_service의 TEAM_KEY_MAP이 바뀌면 이 사본도 함께 갱신해야 한다.
- `run_deterministic_gates()`는 계획서 예시의 `GateContext` 객체 대신 keyword 인자(category_label/pool_key/team_code/approved_questions/flagged_question_ids)를 받도록 설계해 gates.py가 gate_service.py를 몰라도 되게 했다(계획서가 허용한 두 방식 중 "primitive 값만 받는" 쪽 선택).
- 승인 Guard의 상태 검사(`GATE_STATUS_INVALID`)는 계획서의 "안정적인 오류 코드" 목록에 없지만, "이미 승인됨/반려됨" 같은 상태를 막으려면 Gate 판정만으로는 불충분해 별도 코드로 추가했다.

## 발견한 문제와 위험 (환경 이슈)

- 로컬 `python` 명령이 Windows Store 스텁 별칭으로 연결되어 있어 실제로는 아무 것도 실행하지 못했다. `C:\Users\dheod\AppData\Local\Programs\Python\Python313\python.exe`를 직접 지정해 사용했다 — 다음 작업자도 동일 증상이면 이 경로를 써야 한다.
- 이 Python 3.13 인터프리터에는 `backend/requirements.txt`에 이미 선언되어 있던 `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client`, `python-multipart`, `python-jose[cryptography]`, `passlib`, `bcrypt`가 실제로는 설치돼 있지 않아 테스트 실행 전 `pip install`로 설치했다. 코드·requirements.txt는 변경하지 않았다(원래 선언돼 있던 패키지를 실제로 설치만 함).
- `python -m unittest discover -s tests -p "test_*.py"`를 `-t .` 없이 실행하면 `tests/__init__.py`가 top-level 패키지로 인식되지 않아 sys.path 설정이 적용되지 않고 `ModuleNotFoundError`가 난다. 반드시 `-t .`(top-level-dir=저장소 루트)를 붙여야 한다 — 계획서 Section 10/11의 예시 명령에는 이 옵션이 빠져 있어 다음 작업자가 그대로 실행하면 실패한다.

## 완료한 작업과 변경 파일

Task 0~6을 전부 완료했고, 각 Task를 별도 커밋으로 나눴다(테스트 우선 작성 → 실패 확인 → 구현 → 재통과 확인 순서).

```text
3106150 test: 현재 7-Gate 호환 계약 고정
9f365aa feat: 객관식 결정론적 Gate 검증 강화
70b744a feat: 교육자료 기반 Gate 의미 검증 추가
fa1e535 feat: 문제 생성에 강화 Gate 결과 통합
27e79bf fix: Gate 미통과 문제 승인 차단
```

변경/신규 파일:

```text
backend/services/generation/gates.py       (수정 — V01~V07 결정론적 판정, 상태 모델, fingerprint)
backend/services/generation/gate_service.py (신규 — GateContext, evaluate_candidate, V02·V03 의미 검증 결합)
ai_engine/gate_verifier.py                  (신규 — Gemini/Claude 의미 검증 Provider, SemanticVerifierUnavailable)
ai_engine/router.py                         (수정 — get_semantic_gate_verifier() 추가)
backend/services/admin_service.py           (수정 — OJT_GATE_MODE 분기, strict 생성 경로, 승인 Guard)
backend/api/admin.py                        (수정 — approve 요청에 선택적 override_reason body 추가)
tests/**                                    (신규 — 65개 unittest, tests/__init__.py가 backend를 sys.path에 추가)
docs/history/2026-07-11-mcq-seven-gate-hardening.md 및 docs/superpowers 사본 (체크박스 전체 [x] 갱신)
```

Repository, Sheets Schema, `frontend/`, `backend/services/exam_service.py`, `backend/api/exam.py`는 `git diff --name-only origin/develop...HEAD`로 변경되지 않았음을 확인했다. `question_bank_v2`/`exam_papers`/`/api/v2` 문자열은 `backend`, `frontend`, `tests`, `ai_engine` 전체에서 검색해도 없다.

## 테스트·빌드 실행 여부와 결과

- `python -m compileall backend ai_engine` — exit 0.
- `python -m unittest discover -s tests -t . -p "test_*.py"` — **65 tests, 0 failures, 0 errors**.
- `OJT_GATE_MODE=legacy`로 재실행 — 20개 통합 테스트 통과(기존 pass/failed/flags 계약 유지, security_hold는 legacy에서도 승인 차단됨을 확인).
- `OJT_GATE_MODE=strict`로 재실행 — 34개 테스트 통과(Baffle 정상 문제 PASS, 무출처·복수정답·전화번호·중복·WARNING 사유 미기재 케이스 모두 차단).
- 실제 Gemini/Claude/Anthropic API는 한 번도 호출하지 않았다 — 전 구간 FakeVerifier/Fake Repository로 검증했다.
- Google Sheets Write Migration, 프론트 빌드는 이번 범위에 없어 실행하지 않았다.

## 아직 하지 않은 작업

- `OJT_GATE_MODE=strict`를 실제 `AI_PROVIDER=gemini`/`claude`와 함께 실제 API로 시험 호출하는 것(이번 구현은 Fake Verifier로만 검증했다 — 실제 Provider 프롬프트 품질·응답 형식은 미검증).
- 관리자 화면(Admin.jsx)에서 WARNING 승인 사유 입력 UI(계획서가 이번 범위에서 명시적으로 제외함 — API는 준비됐으나 UI가 없어 WARNING 문제는 API 직접 호출 전까지 승인 불가).
- `docs/history`와 `docs/superpowers/plans`의 계획서 사본을 실제로 git에 커밋하는 일(이 기록과 함께 커밋 예정).

## 다음 작업자가 먼저 확인할 내용

1. `OJT_GATE_MODE` 환경변수는 기본값이 `legacy`다 — strict를 켜기 전에는 기존 동작과 100% 동일하다.
2. strict 모드로 전환하면 Gate 통과 여부와 무관하게 모든 생성 Candidate가 `question_repo`에 저장된다(레거시는 통과한 것만 저장) — 문제은행 행 수가 늘어나는 것을 정상 동작으로 이해할 것.
3. `python` 명령이 이 머신에서 동작하지 않으면 Python313 전체 경로를 직접 써야 하고, `unittest discover`는 반드시 `-t .`를 붙여야 한다.
4. 테스트 실행에 필요한 패키지(google-auth류, python-multipart, python-jose, passlib, bcrypt)가 실제로 설치돼 있는지 먼저 확인할 것 — 이미 requirements.txt에는 선언돼 있었지만 로컬 인터프리터에 누락돼 있었다.

## 원격 변경 및 충돌 가능성

이 기록 작성 시점 이후 `origin/develop`이 다시 갱신됐을 수 있다. PR 생성 전 반드시 `git fetch origin && git log --oneline HEAD..origin/develop`으로 재확인하고, 특히 `backend/services/admin_service.py`·`backend/api/admin.py`(다른 팀원이 자주 수정하는 파일)에 새 변경이 있는지 diff로 재검토할 것.
