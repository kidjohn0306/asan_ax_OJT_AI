# 7-Gate 고도화 구현 효과 정리와 원격 충돌 재확인

## 기록 정보

- 기록 시각은 2026-07-11 17:39 KST다.
- 작업 브랜치는 `feature/mcq-seven-gate-hardening`이며, 이 기록 시점 HEAD는 `e8e6b20`이다.
- 직전 기록은 `docs/history/2026-07-11_1733_mcq-seven-gate-hardening-구현완료.md`(구현 완료 보고)다. 이 기록은 그 이후 사용자 질문에 답하며 다시 확인한 원격 상태와, 구현으로 실제로 무엇이 해결됐는지를 정리한 것이다.
- 이번 기록부터 파일명에 시:분(HHMM)을 반드시 포함해 같은 날짜에 여러 기록이 남아도 파일명이 충돌하지 않게 한다(`docs/history/README.md`의 `YYYY-MM-DD_HHMM_<짧은-주제>.md` 규칙을 다시 준수). 기존 `docs/history/2026-07-11-mcq-seven-gate-hardening.md`(계획서 원본, Codex가 만든 파일)는 시각이 빠진 이름이라 이 규칙과 다르지만, 이미 존재하는 계획서 파일이라 되짚어 고치지 않고 이후 기록부터 규칙을 지킨다.

## 요청과 대화의 핵심 요약

사용자가 두 가지를 요청했다.
1. 이번 7-Gate 고도화 구현으로 실제로 무엇이 해결됐는지(전후 차이, 좋아진 점)를 설명해 달라.
2. 다시 Git 상태를 확인해 원격과 충돌이 없는지 재점검해 달라.

## 확인한 실제 근거

`git fetch` 결과 `origin/develop`이 이전 기록(`2026-07-11_1733`) 이후 다시 4개 커밋(`2bad837`) 앞서 나가 있었다 — PR #77(출제 횟수 초과 문제 제외 기능), PR #74(시험세트 삭제 버튼). merge-base(`3106150~1` = 작업 시작 시점의 `origin/develop`)를 기준으로 `git diff`를 다시 떠서 다음을 확인했다.

- `backend/services/admin_service.py`, `backend/services/generation/gates.py`, `ai_engine/router.py` — 원격에서 전혀 변경되지 않음.
- `backend/api/admin.py` — 원격에서 변경됐지만, 실제 diff는 `PreviewExamRequest`/`preview_exam`(시험 미리보기, `max_exam_count` 필드 추가)이고 이번 작업이 건드린 곳은 `ApproveQuestionRequest`/`approve_question`(승인 API) — 같은 파일이지만 줄 단위로 겹치지 않는다.
- `backend/services/exam_service.py`도 원격에서 변경됐지만 이번 7-Gate 작업 대상이 아니다.
- `git status --short` — 작업 트리는 깨끗함(커밋 안 된 변경 없음).

## 판단

merge 시 실제 충돌(같은 줄을 양쪽에서 수정)은 없을 것으로 판단했다. 다만 파일 자체(`admin.py`)가 원격에서 계속 바뀌고 있어, 실제 PR 생성·병합 직전에는 반드시 다시 `git fetch`로 재확인해야 한다고 판단했다 — 이 판단은 이전 기록에도 이미 남겨둔 내용과 같다.

## 이번 구현으로 해결된 것 (전후 비교 요약)

사용자에게 아래 내용을 답변으로 전달했다. 사실 확인은 코드(특히 `backend/services/generation/gates.py`, `gate_service.py`, `admin_service.approve_question`)를 근거로 했다.

1. **Gate가 형식만 보고 실제 내용을 못 걸렀던 문제** — 기존 `run_gates()`는 V01(필수 필드 존재), V02(보기 중복, 사실상 이름과 역할이 어긋나 있었음), V03(정답 A~D 범위)처럼 형식 검사만 했다. 강화 후(`OJT_GATE_MODE=strict`)에는 V02가 실제로 교육자료 원문 대비 근거(Grounding)를 AI로 확인하고, V03이 보기 유사도 + AI의 정답 단일성 판단을 함께 본다. V04(금지 오답 문구·비정상 길이), V06(기존 문제와 완전/고유사 중복)은 이전에 아예 없던 검사다.
2. **가장 큰 문제 — V07 보안 검사가 실패해도 승인을 막지 못했음** — 기존 코드는 `security_hold=True`만 세우고 `pass=True`를 반환해, 전화번호·이메일 등이 포함된 문제도 관리자가 승인 버튼만 누르면 그대로 통과됐다. 이번 수정으로 `approve_question()` 서비스 함수 자체가 `security_hold`가 있으면 **legacy/strict 모드 관계없이** 409로 승인을 차단한다.
3. **Gate 판정 이후 문제 내용이 바뀌어도 예전 통과 기록으로 승인되던 위험** — strict 모드는 `question_fingerprint`(문제 내용의 SHA-256 지문)를 승인 시점에 다시 계산해 Gate 판정 당시와 다르면 `GATE_RESULT_STALE`로 막는다.
4. **Gate 실패 문제가 새로고침하면 사라졌던 문제** — 기존엔 실패한 생성 후보를 저장하지 않아 관리자가 다시 볼 수 없었다. strict 모드는 통과 여부와 무관하게 모든 후보를 정확히 한 번 저장한다.
5. **호환성** — `OJT_GATE_MODE` 기본값은 `legacy`라서 이 강화 로직은 켜기 전까지 기존 동작에 전혀 영향을 주지 않는다. 실제 롤아웃 여부는 별도 결정 사항으로 남아 있다.

## 발견한 문제와 위험

새로 발견한 위험은 없다 — 직전 기록(`2026-07-11_1733`)에 남긴 위험(로컬 `python` 별칭 문제, 테스트 실행에 필요한 패키지 사전 설치, `unittest discover`에 `-t .` 필요, WARNING 승인 UI 부재, 실제 AI Provider 미검증)이 여전히 유효하다.

## 완료한 작업과 변경 파일

이번 기록 작업은 코드 변경 없이 다음만 수행했다.

- Git 상태·원격 diff 재확인(파일 변경 없음).
- 이 기록 파일 추가: `docs/history/2026-07-11_1739_mcq-seven-gate-hardening-효과정리및충돌재확인.md`.

## 아직 하지 않은 작업

- (이전 기록과 동일, 변경 없음) 실제 Gemini/Claude API로 근거 검증 품질 확인, 관리자 화면 WARNING 승인 사유 입력 UI, 브랜치 Push 및 PR 생성.

## 다음 작업자가 먼저 할 일

1. `docs/history/README.md`와 가장 최신 기록(이 파일과 `2026-07-11_1733` 기록)을 순서대로 읽는다.
2. 실제 작업 전에 `git fetch origin && git log --oneline HEAD..origin/develop`으로 원격이 또 앞서 나갔는지 다시 확인한다 — 특히 `backend/api/admin.py`, `backend/services/admin_service.py`는 다른 팀원이 자주 수정하므로 매번 diff까지 확인할 것.
3. Push·PR 생성 여부는 아직 사용자 승인을 받지 않았다 — 임의로 진행하지 않는다.

## 원격 변경 및 충돌 가능성

이 기록 시점 `origin/develop`은 `2bad837`이다. 이후 다시 갱신될 수 있으므로, Push·PR 전 반드시 재확인이 필요하다.
