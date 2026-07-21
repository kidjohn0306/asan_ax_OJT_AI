# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Phase 3 문제 생성·검토 Dual Write 운영 계약

Phase 3는 기존 `question_bank` 동작을 유지하면서 명시적으로 활성화된 경우에만
`generation_jobs`, `question_candidates`, `gate_results`, `question_reviews`,
`question_history`에 정규화 레코드를 함께 저장한다.

기본값은 항상 Legacy-only다.

```env
OJT_SHEETS_SCHEMA_MODE=legacy
OJT_USE_CANDIDATE_TAB=false
OJT_USE_GATE_RESULTS_TAB=false
```

활성화 전 조건:

- 운영본이 아닌 Google Sheets 복사본에 Phase 2 스키마를 적용한다.
- `migrate_schema_v2.py` Dry-run의 Header blocking issue와 Primary Key issue가 모두 0인지 확인한다.
- `question_candidates`, `generation_jobs`, `question_reviews`, `question_history`의 실제 Header가 canonical manifest와 일치하는지 확인한다.
- Gate 기록까지 켜려면 `gate_results` Header도 일치해야 한다.

권장 활성화 순서:

```env
# 1단계: Candidate/Job/Review/History 이중 기록
OJT_SHEETS_SCHEMA_MODE=dual
OJT_USE_CANDIDATE_TAB=true
OJT_USE_GATE_RESULTS_TAB=false

# 2단계: V01~V07 결과까지 이중 기록
OJT_USE_GATE_RESULTS_TAB=true
```

- 생성 요청에는 재시도 중복을 막기 위해 `idempotency_key`를 전달한다.
- 정규화 저장 실패 전에는 Legacy 문제를 저장하지 않으며 API는 `503`을 반환한다.
- 정규화 저장 후 Legacy 저장이 실패하면 API는 `503`, 생성 Job은 가능한 경우 `PARTIAL_FAILED`가 된다.
- 승인·반려는 `question_reviews`와 `question_history`, Candidate 상태를 먼저 기록한 다음 Legacy 상태를 변경한다.
- `review_id`, `history_id`, `candidate_id`, `gate_result_id`는 재시도 시 같은 행을 가리키도록 안정적으로 생성한다.

롤백은 데이터 삭제나 Sheet 제거 없이 플래그만 내린다.

```env
OJT_USE_GATE_RESULTS_TAB=false
OJT_USE_CANDIDATE_TAB=false
OJT_SHEETS_SCHEMA_MODE=legacy
```

롤백 후에도 이미 기록된 정규화 행은 보존한다. 운영본에 직접 Migration을 적용하거나
정규화 행을 자동 삭제하지 않는다. V2 Read/UI 전환은 후속 Canary 단계 전까지 활성화하지 않는다.

## Phase 4 시험·배정 Dual Write 운영 계약

Phase 4는 기존 `exam_sets.question_ids`, `exam_sets.assigned_users`를 계속 사용하면서
명시적으로 활성화된 경우에만 `exam_versions`, `exam_set_items`, `assignments`에도
정규화 레코드를 함께 저장한다. 기존 `exam_sets`가 Canary 전까지 조회 원장이다.

기본값은 항상 Legacy-only다.

```env
OJT_SHEETS_SCHEMA_MODE=legacy
OJT_USE_FROZEN_EXAM=false
OJT_USE_ASSIGNMENTS_TAB=false
```

활성화 전 조건:

- 운영본이 아닌 Google Sheets 복사본에 Phase 2 스키마를 적용한다.
- `exam_sets`, `exam_versions`, `exam_set_items`, `assignments`의 실제 Header가 canonical manifest와 일치하는지 확인한다.
- Header, Primary Key, 참조 무결성 검사와 전체 회귀 테스트를 통과한다.
- 기존 `evaluation_type`이 비어 있는 시험은 안전을 위해 `official`로 취급한다.

활성화는 시험 동결과 배정을 분리해 다음 순서로 진행한다.

```env
# 1단계: 확정 시험 버전과 문항 Snapshot만 이중 기록
OJT_SHEETS_SCHEMA_MODE=dual
OJT_USE_FROZEN_EXAM=true
OJT_USE_ASSIGNMENTS_TAB=false

# 2단계: 정합성 확인 후 사용자 배정도 이중 기록
OJT_USE_ASSIGNMENTS_TAB=true
```

- 현재 시험 생성 API 호출은 즉시 확정으로 처리한다. 별도 초안/확정 UI는 Phase 6에서 도입한다.
- 시험은 승인된 문제만 사용하며 최대 100문항이다.
- `question_scores`를 생략하면 총 100점을 양의 정수로 균등 배분하고 나머지는 앞 문항부터 1점씩 더한다.
- 배점을 지정하면 문항 ID가 정확히 일치하고 모든 점수가 양의 정수이며 합계가 정확히 100이어야 한다.
- 생성·회차 생성 재시도에는 같은 `idempotency_key`를 사용한다. 같은 키에 다른 불변 입력을 보내면 `409`를 반환한다.
- `official` 시험은 사용자당 활성 배정 하나만 허용한다. 새 정식 시험 배정은 이전 정식 배정을 `cancelled`로 바꾸되 삭제하지 않는다.
- `practice` 시험은 사용자당 여러 개를 동시에 배정할 수 있으며 정식 시험 및 다른 연습 시험 배정을 취소하지 않는다.
- 승인된 사용자만 배정할 수 있고, 정규화 배정이 켜진 경우 확정된 시험 버전이 반드시 존재해야 한다.
- 정규화 저장을 먼저 수행한다. 정규화 저장 실패 시 Legacy를 변경하지 않고 `503`을 반환한다.
- 정규화 저장 후 Legacy 저장이 실패해도 성공으로 응답하지 않으며 `503`을 반환한다.
- 배정·취소 행에는 JWT 관리자의 `sub`를 기록하고 재시도는 동일한 `assignment_id`를 갱신한다.

롤백은 정규화 데이터를 삭제하지 않고 플래그만 역순으로 내린다.

```env
OJT_USE_ASSIGNMENTS_TAB=false
OJT_USE_FROZEN_EXAM=false
OJT_SHEETS_SCHEMA_MODE=legacy
```

롤백 후에도 `exam_versions`, `exam_set_items`, `assignments`의 기존 행은 보존한다.
Sheet나 정규화 행을 삭제하지 않으며, 운영본 적용과 V2 Read 전환은 별도 승인된 Canary 단계에서만 수행한다.

## Phase 5 결과 Dual Write 운영 계약

Phase 5는 확정되어 사용자에게 배정된 시험에만 적용한다. 기존 동적 Legacy 시험은 기존 Snapshot 채점과
`results` 저장 경로를 그대로 사용한다. 확정 시험은 배정된 `exam_version_id`와 `exam_set_items`의
문항 Snapshot 및 문항별 점수를 기준으로 전체 문항을 채점한다.

기본값은 항상 비활성 상태다.

```env
OJT_SHEETS_SCHEMA_MODE=legacy
OJT_USE_FROZEN_EXAM=false
OJT_USE_ASSIGNMENTS_TAB=false
OJT_USE_RESULT_ANSWERS=false
```

운영본이 아닌 Google Sheets 복사본에서 Header, Primary Key, 기존 기능 회귀 테스트를 확인한 후 다음
순서로 활성화한다.

```env
# 1단계: 확정 시험과 배정까지만 활성화
OJT_SHEETS_SCHEMA_MODE=dual
OJT_USE_FROZEN_EXAM=true
OJT_USE_ASSIGNMENTS_TAB=true
OJT_USE_RESULT_ANSWERS=false

# 2단계: 문항별 답안과 최소 응시 상태 이중 기록 활성화
OJT_USE_RESULT_ANSWERS=true
```

- 제출 API의 `submission_idempotency_key`는 선택값이며, 비어 있으면 `result_id`를 사용한다.
- 같은 키와 같은 답안의 재시도는 기존 결과를 반환하고 행을 중복 기록하지 않는다.
- 같은 키에 다른 답안을 보내거나 완료된 결과에 다른 키를 보내면 `409`를 반환한다.
- 무응답 문항도 전체 문항 채점에 포함하고 `selected_choice`는 빈 값, 점수는 0점으로 기록한다.
- 저장 순서는 `result_answers` → `exam_attempts(submitting)` → Legacy `results` →
  `exam_attempts(submitted)` → `assignments.attempts_used`다.
- 정규화 답안 저장이 실패하면 Legacy 결과를 저장하지 않는다. 이후 단계가 실패하면 `503`을 반환하며,
  같은 요청 재시도로 이미 완료된 단계를 중복 기록하지 않고 남은 단계만 마친다.
- 재시험은 새 배정과 새 응시 ID를 사용하며 완료된 결과를 덮어쓰지 않는다.

문제가 발생하면 데이터나 Sheet를 삭제하지 않고 결과 플래그만 먼저 내린다.

```env
OJT_USE_RESULT_ANSWERS=false
```

이 상태에서는 기존 Legacy 결과 조회·저장을 유지한다. 추가 롤백이 필요할 때만 Phase 4 순서에 따라
`OJT_USE_ASSIGNMENTS_TAB`, `OJT_USE_FROZEN_EXAM`, `OJT_SHEETS_SCHEMA_MODE`를 역순으로 내린다.
이미 기록된 `result_answers`, `exam_attempts`, 확장 `results` 행은 감사와 복구를 위해 보존한다.

## Phase 6A 관리자 UI 전환 운영 계약

Phase 6A는 기존 관리자 기능을 `/admin/*` 업무 URL로 옮기는 호환 전환이다. 최신 `main`의 대시보드,
Admin App Shell, 색상, 버튼과 카드 스타일을 기준으로 유지하며 사원용 `/exam` 흐름은 변경하지 않는다.

- 좌측 `시험 관리` 메뉴는 `시험지 생성관리`, `시험 생성관리`, `응시 현황` 3개만 둔다.
- 시험지 생성관리는 `/admin/exam-papers?tab=setup|list`를 사용한다. 목록 상태는 `q`, `team`, `usage`,
  `page`, 상세는 `selected`, 수정본 원본은 `source` query로 보존한다.
- 확정 시험지를 직접 수정하지 않는다. 수정은 원본 문항·순서·배점을 새 작성 폼에 채운 뒤 새 ID로
  저장하는 Copy-on-Write이며, API 요청에 원본 ID를 새 시험의 식별자로 재사용하지 않는다.
- 시험지 목록·상세·시험 관리·응시 현황은 실제 API만 사용한다. 실패를 Mock 데이터, 빈 성공 결과,
  임의 집계로 대체하지 않는다.
- 시험 생성관리는 `/admin/exams`와 `/admin/exams/:examId`를 선택 상태의 기준으로 삼는다. 정식 시험은
  사용자당 활성 1개라서 새 배정 시 기존 정식만 자동 해제하고, 연습 시험은 여러 개의 활성 배정을 허용한다.
- 문자열 `detail`과 객체형 `detail.message` 백엔드 오류를 보존해 표시한다. URL 선택이 바뀐 뒤 도착한
  이전 시험·응시자 응답은 현재 상태를 덮어쓰지 않아야 한다.
- 응시 현황은 `/admin/exams/live`, `/admin/exams/:examId/live`에서 10초 폴링한다. 요청을 중첩하지 않고,
  최초 실패는 오류 화면으로, 후속 실패는 마지막 정상 Snapshot을 유지한 채 갱신 실패로 표시한다.
- 전체 집계는 고유 배정자, 고유 제출자, 배정자 중 미제출자, 오류 상태의 고유 대상을 서로 구분한다.
  시험별 상세는 배정자와 사번별 최신 결과를 합치며 결과만 있는 미배정 제출도 숨기지 않는다.
- 현재 API에 없는 입장·이탈은 `정보 없음`, 잔여시간은 `집계 준비 중`, 해석 불가능한 일정은 `일정 미정`으로
  표시한다. Phase 6A UI에는 강제 종료와 시간 연장을 구현하지 않는다.
- 계획 URL에 API나 화면이 없으면 준비 중·사용 불가 상태를 정직하게 표시하고 가짜 기능을 만들지 않는다.

## 프로젝트 개요
AI 기반 신입사원 OJT 교육 이해도 평가 시스템. FastAPI 백엔드 + Vite React 프론트엔드.
현재 단계: **팀 관리·출제횟수 트래킹·CSV 업로드·시험 시간제한·결과 분석 대시보드(박스플롯·정오표·CSV/Excel/PDF 내보내기) 구현 완료. 이어서 Phase 1~5 호환·Dual Write 기반과 Phase 6A 관리자 UI 호환 전환 구현 완료. `main`(관리자 UI 전면 개편·Sheets v2 슬림 스키마·XT 브랜딩)을 `develop`에 병합하고, 병합 부작용(미사용 import·죽은 코드·PDF/HTML 생성 로직 중복·레거시 인라인 컴포넌트) 정리 완료. 이어서 프로덕션 버그 3건(레거시 유령 시험 목록·삭제 오류, 응시 화면 시험시간 하드코딩, 감사 로그 이탈 이벤트 미구현) 수정 + 전체 점검으로 AI 문제 생성 카테고리·난이도 분포 무시, 응시 화면 무음 폴백·거짓 저장 안내, 관리자 헤더 하드코딩, 죽은 API 정리 완료**

## 아키텍처

```
asan_ax_OJT_AI/
├── api/index.py              # Vercel 진입점 — backend/main.py의 app을 임포트
├── ai_engine/                # AI 문제 생성 엔진 (루트 위치 — sys.path에 의해 임포트됨)
│   ├── router.py             # AI_PROVIDER 환경변수로 생성기 선택
│   ├── _shared.py            # gemini/claude 생성기 공통 로직 — truncate_material/build_prompt/parse_response
│   ├── gemini_generator.py   # Gemini REST API (gemini-2.5-flash) — _call_api만 자체 구현, 나머지는 _shared 사용
│   └── question_generator.py # Claude API (claude-sonnet-5, anthropic SDK) + mock 생성기(_mock_generate) 겸용
├── backend/
│   ├── main.py               # FastAPI 앱, frontend/dist/ StaticFiles 마운트, load_dotenv(override=True)
│   ├── api/                  # 라우터
│   │   ├── deps.py           # 공유 의존성 — require_admin()/require_auth() (JWT 검증 + 역할 확인)
│   │   ├── auth.py, exam.py, admin.py, drive.py
│   ├── config/                # Phase 1~6A dual-write 기능 플래그·저장소 정책
│   │   ├── features.py        # OJT_SHEETS_SCHEMA_MODE 등 env 플래그 파싱
│   │   └── storage.py         # should_fallback_to_local() — strict/폴백 정책 단일 소스
│   ├── schema/
│   │   └── sheets_v2.py       # 55-Sheet(슬림 18/19탭) canonical 헤더 manifest
│   ├── services/             # 비즈니스 로직
│   │   ├── exam_service.py   # 출제·채점·스냅샷 저장 (PASS_SCORE=70) + 출제횟수 increment_batch
│   │   ├── admin_service.py  # 문제관리, 사용자승인, AI 생성, 팀CRUD, CSV업로드, 대시보드통계, 시스템 상태 조회
│   │   ├── drive_service.py  # Google Drive 서비스 계정 인증
│   │   ├── material_service.py # Drive 교육자료 스캔·캐싱 (아래 "교육자료 자동 스캔" 참고)
│   │   ├── schema_service.py # Sheets v2 스키마 검증·마이그레이션 지원
│   │   ├── generation/       # gates.py — run_gates (V-01~V-07), dual_write.py — Phase 3 정규화 이중 기록
│   │   ├── exams/dual_write.py   # Phase 4 — exam_versions/exam_set_items/assignments 이중 기록
│   │   └── results/dual_write.py # Phase 5 — result_answers/exam_attempts 이중 기록
│   ├── repositories/         # 저장소 추상화 레이어
│   │   ├── base.py           # 추상 인터페이스 (Question/Result/Snapshot/Feedback/ExamSet/Team/QuestionStats)
│   │   ├── local_json.py     # 로컬 JSON 파일 기반 (로컬 개발용)
│   │   ├── drive_repo.py     # Google Drive 기반 (STORAGE_BACKEND=drive)
│   │   ├── sheets_repo.py    # Google Sheets 기반 (STORAGE_BACKEND=sheets) ✅ — 8종 저장소 모두 `_fallback_or_raise()`로 폴백 정책 통일
│   │   ├── generation_v2.py / exam_v2.py / result_v2.py / audit_v2.py  # Phase 3~5 정규화 저장소 (기본 비활성, Local 폴백 없음)
│   │   └── __init__.py       # 백엔드 선택 로직 (아래 "저장소 백엔드 선택" 참고)
│   ├── scripts/               # Migration 스크립트 (기본 Dry-run)
│   ├── credentials/          # 서비스 계정 파일 (gitignore됨)
│   └── mock_data/            # 더미 JSON (users, questions, results, question_stats)
├── frontend/
│   ├── src/
│   │   ├── pages/             # Login.jsx, Exam.jsx, Admin.jsx (뷰 스위치 + 공용 헬퍼, 아래 참고)
│   │   └── admin/             # `/admin/*` 업무 URL 라우트 구조 (Phase 6A)
│   │       ├── components/    # AdminLayout, AdminHeader, AdminSidebar
│   │       ├── config/navigation.js  # 좌측 메뉴 정의
│   │       └── pages/         # exam-papers/, exams/, questions/, results/, system/
│   └── dist/                 # 빌드 결과물 (git 포함 — 수정 후 반드시 재빌드)
└── vercel.json               # 모든 요청 → api/index.py → FastAPI
```

### 모듈 임포트 경로 (sys.path)
FastAPI 앱은 `backend/` 안에서 `from api import ...`, `from repositories import ...`처럼 절대 임포트를 쓰기 때문에
sys.path에 두 경로가 순서대로 추가돼야 정상 동작한다:
1. `api/index.py`가 `backend/` 디렉터리를 sys.path에 추가 (Vercel 진입 시)
2. `backend/main.py`가 리포 루트(`backend/`의 부모)를 sys.path에 추가 — 루트에 있는 `ai_engine` 임포트용

로컬에서 `cd backend && uvicorn main:app --reload`로 실행하는 경우도 `main.py`가 루트를 sys.path에 넣어주므로 동일하게 동작한다.
이 구조 때문에 `backend/` 하위 모듈을 리포 루트 기준 상대경로로 옮기거나 독립 실행하면 임포트가 깨지니 주의.

## 핵심 규칙

### 프론트엔드 수정 시
`frontend/src/` 수정 후 자동 테스트를 통과시키고, 모든 병렬 소스 작업이 끝난 최종 상태에서 일반 빌드를
한 번 실행해 `dist`도 함께 커밋한다. 병렬 작업 중 격리 경로에 만든 검증용 빌드 산출물은 커밋하지 않는다.

```powershell
cd frontend
npm test
npm run build
git add frontend/src frontend/dist
```

해시가 붙은 번들 파일은 이전 파일 삭제, 새 파일 추가, `frontend/dist/index.html` 참조 변경을 한 세트로
검토한다. 최종 빌드 전의 중간 `dist`를 부분적으로 스테이징하지 않는다.

### 환경변수
`.env` 파일은 gitignore됨. 로컬 개발 시 `backend/.env` 생성:
```
JWT_SECRET_KEY=로컬개발용아무값
STORAGE_BACKEND=local
AI_PROVIDER=mock
```
Vercel 배포용 키는 Vercel 대시보드 Environment Variables에서 설정 (코드에 직접 쓰지 말 것).

### AI 제공자 선택 (`AI_PROVIDER`)
- `mock` (기본값) — `mock_data/questions.json` 문제 사용, API 호출 없음
- `gemini` — Gemini REST API (`gemini-2.5-flash`) 문제 생성. `GEMINI_API_KEY` 필요
- `claude` — Claude API (`claude-sonnet-5`, anthropic SDK) 문제 생성. `CLAUDE_API_KEY` 필요
- 두 제공자 모두 자주 출제된 문제(`question_stats`의 `flagged_frequent`)를 프롬프트에 회피 목록으로 전달해 중복 출제를 줄임

### 저장소 백엔드 선택 (`STORAGE_BACKEND`)
- `local` (기본값) — `mock_data/*.json` 파일에 저장. Vercel 재배포 시 초기화됨
- `sheets` — Google Sheets에 저장. `GOOGLE_SHEETS_ID` 필요 ✅ **권장 (Drive 할당량 이슈 해결)**
  - `results` + `snapshots` + `exam_sets` + `teams` + `question_stats` + `question_bank` + `difficulty_feedback` 탭 자동 생성
  - `question_bank`: 문제은행 데이터(공통/팀별/환경안전/일반상식 문제 전체). 기존 `mock_data/questions.json` 데이터는
    `backend/scripts/migrate_questions_to_sheets.py`로 1회 이관 가능
  - 서비스 계정에 스프레드시트 편집자 권한 필요
- `drive` — Google Drive에 저장. `DRIVE_RESULTS_FOLDER_ID` 필요
  - ⚠️ 개인 구글 계정 연결 서비스 계정은 Drive 쓰기 할당량 0 → `storageQuotaExceeded` 발생

`backend/repositories/__init__.py`가 실제 구현체를 고르는 세부 규칙 (`STORAGE_BACKEND` 값 하나로 단순 결정되지 않음):
- `exam_set_repo`는 별도로 `EXAM_SET_STORAGE` 환경변수가 있으면 그 값을 우선하고, 없으면 `STORAGE_BACKEND=sheets`이거나
  `GOOGLE_SERVICE_ACCOUNT_JSON`이 설정돼 있으면(=프로덕션으로 간주) Sheets를 자동 선택한다.
- `team_repo`, `question_stats_repo`, `question_repo`(drive 백엔드 제외)는 Sheets 사용 조건일 때 우선 Sheets로 초기화를 시도하고,
  초기화 예외 발생 시 각각 Local 구현체로 자동 폴백한다 (경고 로그만 남기고 요청은 계속 처리됨).
- 즉 Sheets 관련 문제(권한 누락, API 오류 등)가 있어도 앱 전체가 죽지 않고 조용히 로컬 저장으로 전환될 수 있으니,
  "분명 Sheets로 설정했는데 데이터가 로컬에만 남는다" 같은 버그를 조사할 때는 서버 로그의 폴백 경고부터 확인할 것.

### 스냅샷 시스템
시험 생성 시 문제·정답을 스냅샷으로 저장 → 채점 시 스냅샷 기준으로 채점.
스냅샷 없으면 HTTP 410 반환 (문제 변경·세션 만료 대응).
- `local` 모드: `/tmp/snapshots.jsonl` (Vercel 인스턴스 재사용 시 유효, 신규 인스턴스면 손실)
- `sheets` 모드: Sheets `snapshots` 탭에 영구 저장 → 인스턴스 교체에도 안전 ✅
- `drive` 모드: Drive `snapshots/` 폴더 저장 (할당량 문제로 미작동)

### 테스트 계정 (Mock 모드)
- `admin001` (관리자), `2024001` (응시자 T1), `2024002` (응시자 T2)
- 비밀번호: 아무 값이나 입력 가능 (`mock_hash` 방식)

### Google Drive 인증
서비스 계정 방식으로 연동됨. 브라우저 로그인 불필요.
- 로컬: `backend/credentials/service_account.json` (gitignore됨 — 직접 생성 필요)
- Vercel: `GOOGLE_SERVICE_ACCOUNT_JSON` 환경변수에 JSON 전체 내용 입력
- 서비스 계정 이메일: `asan-ojt-drive@asanteam4-500207.iam.gserviceaccount.com`
- Drive 폴더 접근 시 해당 이메일로 폴더 공유 필요

### 교육자료 자동 스캔 (Drive → AI 문제 생성)
`DRIVE_EDUCATION_MATERIALS_FOLDER_ID` 환경변수에 Drive 폴더 ID를 설정하면, 그 하위의
`common`/`team1`/`team2`/`team3`(팀별 카테고리명과 동일 — `admin_service.TEAM_KEY_MAP` 참고) 폴더에서
PDF/PPTX 교육자료를 스캔해 텍스트를 추출하고, AI 문제 생성(`generate_ai_questions`) 시 자동으로 포함한다.
- `backend/services/material_service.py` — Drive 목록 조회, 파일 id+modifiedTime 기준 변경 감지, 텍스트 추출(pypdf/python-pptx)
- 변경되지 않은 파일은 재다운로드·재추출하지 않고 캐시된 텍스트를 재사용 (Drive 호출·추출 비용 절감이 목적)
- 캐시는 `repositories.material_repo`(Sheets `material_cache` 탭 또는 로컬 JSON, Sheets 초기화 실패 시 자동 Local 폴백)에 저장
- 새/변경 파일 발견 시 즉시 반영하지 않고, `GET /api/admin/materials/list` 응답에서 해당 파일 상태를 `new`로 표시해
  "문제 생성" 화면의 자료 선택 목록에 "신규 반영 대기"로 보여준다. 관리자가 "자료·연동" 화면에서 "새 자료 스캔" 버튼을 눌러야
  실제 스캔·캐시 갱신됨(`POST /api/admin/materials/scan`)
- 관리자가 "교육자료 추가 입력" textarea에 직접 붙여넣은 텍스트는 Drive 캐시 텍스트 뒤에 보충 내용으로 덧붙여짐 (둘 다 유지, 어느 한쪽도 덮어쓰지 않음)
- 텍스트 추출 라이브러리: `pypdf`, `python-pptx` (세 requirements.txt 모두에 추가됨)
- 파일당 20,000자·카테고리당 40,000자로 텍스트를 잘라 저장 (Sheets 셀 5만자 한도 방지 + 프롬프트 폭주 방지)
- 파일 크기가 `DRIVE_MATERIAL_MAX_FILE_SIZE_MB`(기본 25MB)를 넘으면 다운로드를 건너뛰고 스캔 응답의 `skipped`에 사유와 함께 표시됨 (실제 교육용 PPTX에 영상·고해상도 이미지가 포함되면 수십~수백 MB로 커질 수 있어, 필요 시 이 값을 올려서 재스캔할 것)
- `team_code`는 Drive 쿼리에 그대로 들어가므로 `[a-zA-Z0-9_-]+` 패턴만 허용 (쿼리 인젝션 방지)

### 시스템 상태 실제 체크 (`GET /api/admin/system-status`)
관리자 화면(대시보드/설정)의 "운영 모드"·"Claude API" 표시는 하드코딩이 아니라 이 엔드포인트가 반환하는
`AI_PROVIDER`/`STORAGE_BACKEND`/`CLAUDE_API_KEY`·`GEMINI_API_KEY` 설정 여부를 그대로 보여준다.
Google Drive 상태는 기존 `GET /api/drive/status`(실제 연결 시도)를 그대로 사용 — 이 엔드포인트에서 중복 확인하지 않음.

### AI 생성 문제의 category 필드 — pool_key와 혼동 주의
`admin_service.generate_ai_questions`에서 `category`(예: `"team1"`, `add_question`의 저장 위치 키)와
문제의 `category` 필드에 실제로 들어가야 하는 한글 라벨(`"공통"/"팀별"/"환경안전"/"일반상식"` —
`gates.py`의 `VALID_CATEGORIES`, 프론트 카테고리 필터가 기준으로 삼는 값)은 다른 개념이다.
`_category_label_for_pool()`로 변환해서 AI 생성기에는 라벨을, `q_repo.add_question()`에는 pool_key를 각각 전달해야 한다
(예전에 이 둘을 같은 변수로 섞어 쓰다가 게이트 검증(V-04)이 무력화되고 프론트 필터에서 AI 생성 문제가 누락되는 버그가 있었음).

### 시험 시간(duration_min)
시험세트마다 응시 제한시간(분, 기본 60)을 가진다. 회차 생성 시 커트라인(`pass_score`)·일시(`exam_datetime`)와
함께 즉시 지정 가능하고, 이후 `PATCH /api/admin/exam-sets/{exam_id}/duration`으로 개별 변경할 수 있다.
Sheets `exam_sets` 탭은 이 필드 때문에 `A:L`(12열)까지 사용하므로, 헤더 순서를 바꾸거나 열을 추가할 때는
`sheets_repo.py`의 `HEADERS`·`_row_to_dict`·`_dict_to_row`·읽기 range(`A:L`)를 모두 같이 맞출 것.

### 시험 응시 API의 employee_id 신뢰 금지 (보안)
`POST /api/exam/generate`, `POST /api/exam/submit`, `GET /api/exam/result/{id}`, `GET /api/exam/assigned-name`,
`POST /api/exam/exit-event`는 클라이언트가 body·query로 보낸 employee_id·name을 절대 신뢰하지 않는다 — 전부
`require_auth`로 검증한 JWT의 `sub`/`name` 클레임만 사용한다. `get_result`도 응답 전 결과의 `employee_id`가
토큰 본인 것인지(또는 role이 admin인지) 확인 후 아니면 403을 반환한다. (과거엔 body의 employee_id를 그대로
써서 타인 사칭 제출과 타인 결과 조회(IDOR)가 가능했던 취약점이 있었음 — 이 라우터에 엔드포인트를 추가할 때
이 패턴을 반복하지 말 것.)

### 레거시 exam_sets의 exam_id 없는 유령 레코드 필터링
Google Sheets `exam_sets` 탭에서 행 전체가 아니라 셀 내용만 지워지면(행 자체는 남아있음) 모든 컬럼이 빈
문자열인 레코드가 남는데, `sheets_repo.py`/`local_json.py`의 `SheetsExamSetRepository.list_exam_sets()`,
`LocalExamSetRepository.list_exam_sets()`는 이런 `exam_id`가 빈 레코드를 응답에서 걸러낸다(teams/questions/
materials 저장소와 동일한 관례). 이 필터를 제거하면 관리자 "시험 생성관리" 화면에 exam_id 없는 유령 시험이
클릭 가능한 항목으로 다시 노출되고, "문제 목록 보기"는 `GET .../exam-sets//questions`(빈 경로 → SPA
catch-all이 응답해 `Unexpected token '<'` JSON 파싱 에러), "시험 삭제"는 `DELETE .../exam-sets/`(id 없음 →
405 Method Not Allowed)로 깨진다. 프론트 `Admin.jsx`의 `ExamAssign`도 `validSets()`로 같은 방어를 이중으로
하고 있으니, 새로 `setSets(...)`를 호출하는 곳을 추가할 때 이 필터를 거치지 않고 원본 배열을 그대로 쓰지 말 것.

### 응시 전 화면(`GET /api/exam/assigned-name`)은 이름뿐 아니라 시험시간·문항수도 반환해야 함
`exam_service.get_assigned_exam_preview()`는 로그인 직후~"시험 시작하기" 클릭 전 화면(`Exam.jsx`의
`IdentityScreen`)에 보여줄 `name`/`duration_min`/`question_count`를 응시 세션을 시작하지 않고 조회만 한다
(과거엔 `name`만 반환해서 시작 전 화면에 실제 배정 시간과 무관하게 `'60분 · 25문항'`이 하드코딩되어 있었고,
관리자가 시간을 바꿔도 시작 전 화면에는 반영이 안 됐음 — 시험 시작 후 타이머는 `POST /api/exam/generate`가
별도로 `duration_min`을 내려줘서 항상 맞았음). 이 API를 수정할 때 `duration_min`/`question_count` 필드를
빠뜨리지 말 것.

### 레거시 결과 재제출은 재채점하지 말고 기존 결과를 그대로 반환할 것
`exam_service._legacy_score_and_save()`는 `skip_save`가 아닐 때 채점 전에 반드시 `r_repo.get_result(result_id)`로
기존 결과가 있는지 먼저 확인하고, 있으면 재채점·재저장 없이 그대로 반환한다. 이 early-return을 제거하면
매 호출마다 `submitted_at`이 새로 생성돼 `result_data`가 이전 저장값과 달라지고, Sheets(`sheets_repo.py`의
`append_result`)와 Local(`local_json.py`의 `save_result`) 둘 다 불변 결과 저장소라서 `ResultConflict`(500)를
던진다 — 네트워크 오류로 응답만 유실된 뒤 사용자가 "다시 제출하기"를 누르면 재시도할수록 영원히 결과 화면에
도달하지 못하는 버그로 이어진다. frozen(Phase 5) 경로 `_score_frozen_submission`도 동일하게 `existing_result`를
재사용하는 패턴을 쓰고 있으니 일관성을 유지할 것.

### 시험지 PDF/HTML 생성 — 중복 템플릿 재도입 금지
`frontend/src/pages/Admin.jsx`의 `buildExamPdfHtml({docTitle, heading, teamLabel, questions})`가
시험지 A4 인쇄용 HTML을 만드는 유일한 템플릿이다. `openExamPdf(...)`(새 창 인쇄)와 `ExamSheet`의
`buildExamHtml()`(`handleHtmlSave`의 Blob 다운로드용 원본 문자열 필요) 둘 다 이 함수를 호출해서
결과물을 만든다. 과거 이 두 흐름이 각자 똑같은 HTML 템플릿을 들고 있다가 병합 과정에서 중복으로
남았던 적이 있음 — 시험지 인쇄·저장 관련 기능을 추가할 때 새 템플릿을 만들지 말고 이 헬퍼를 재사용할 것.

### 저장소 폴백 정책 — `_fallback_or_raise()` 재사용
`backend/repositories/__init__.py`의 Sheets 기반 저장소(exam_set/result/snapshot/feedback/team/
question_stats/question/material/user, 총 8종)는 모두 `_fallback_or_raise(error, local_factory, label)`
헬퍼로 폴백 여부를 결정한다 — `should_fallback_to_local()`이 `False`(기본, `OJT_STRICT_SHEETS_STORAGE=true`)면
예외를 그대로 올려 API 실패로 노출하고, `True`면 Local 구현체로 조용히 전환한다. 새 Sheets 저장소를
추가할 때 이 헬퍼를 거치지 않고 자체적인 `try/except: fallback` 블록을 새로 만들지 말 것 — 과거
`feedback_repo`만 이 정책을 따르지 않고 항상 조용히 폴백하다가 strict 모드에서도 Sheets 오류가
숨겨지는 버그가 있었음(수정됨).

### 결과 분석 대시보드 (`Results`, `frontend/src/pages/Admin.jsx`)
시험 클릭 시 점수 분포(평균·중앙값·박스플롯 + 합격 커트라인 점선), 응시자 클릭 시 문제 영역별 정답 수와
"정오표"(O/X) 상세를 보여준다. 중앙값·박스플롯 5수 요약·등수는 모두 `/api/admin/results-analysis` 원본
데이터(`admin_service.fetch_results_analysis`)를 프론트에서 그대로 계산한 것 — 백엔드는 집계된 통계를
내려주지 않는다. 응시자 목록은 CSV(BOM 포함)·Excel·PDF로 내보낼 수 있는데, Excel은 `xlsx` npm 패키지 대신
SpreadsheetML XML을 직접 문자열로 생성한다 (`xlsx`는 패치되지 않은 고위험 CVE — Prototype Pollution, ReDoS —
가 있어 의도적으로 배제함. 다시 추가하지 말 것). PDF는 `ExamSheet`의 시험지 PDF와 동일하게 새 창에
HTML을 렌더링해 `window.print()`로 저장하는 방식이다.

## PR/커밋 규칙

### 커밋 메시지
`type: 설명` 형식을 반드시 사용:
- `feat` — 새 기능
- `fix` — 버그 수정
- `docs` — 문서 변경
- `chore` — 빌드·설정 변경
- `refactor` — 리팩토링

### PR 생성 시
- 반드시 `.github/pull_request_template.md` 형식 사용
- 이슈 생성 시 `.github/ISSUE_TEMPLATE/` 템플릿 사용
- `feature/xxx` → `develop` 으로 PR, `develop` → `main` 은 통합 완료 후 PR

## 브랜치 전략
- `main` → Vercel 자동 배포
- `develop` → PR 머지 대상
- `feature/xxx` → 개인 작업

## 로컬 실행
```bash
# 백엔드 (http://localhost:8000)
cd backend && pip install -r requirements.txt
uvicorn main:app --reload

# 프론트 개발 서버 HMR (http://localhost:5173)
cd frontend && npm install && npm run dev

# 프론트 빌드 결과물 로컬 미리보기
cd frontend && npm run preview
```

프론트엔드 단위·컴포넌트 테스트는 `frontend`에서 `npm test`로 실행한다. 백엔드 회귀 테스트는 저장소
루트에서 `PYTHONPATH`에 `backend`와 루트를 포함한 뒤 `python -m unittest discover -s tests -t . -q`로
실행한다. 자동 테스트와 빌드 성공 후에도 로그인, 시험지 생성·복사, 시험 배정, 응시 현황, 사원 응시
흐름을 직접 확인하고 브라우저 콘솔 오류가 없는지 검증한다.

## 주의사항
- API 키·시크릿을 코드에 하드코딩하지 말 것
- `frontend/dist/`는 빌드 후 소스와 함께 커밋할 것
- `api/index.py`는 수정 불필요 — Vercel 진입점 역할만 함
- Repository 구현체 추가 시 `base.py` 추상 메서드 모두 구현할 것
- `password_hash == "mock_hash"`인 계정은 비밀번호 검증이 생략된다(Mock 모드 설계, `auth_service.authenticate_user`
  참고) — 사번만 알면 비밀번호는 아무거나 입력해도 로그인된다. 실사용자 데이터로 이관하기 전 반드시 실제
  해시로 교체할 것
- `JWT_SECRET_KEY` 미설정 시 소스에 하드코딩된 기본값(`ojt-dev-secret-change-in-prod-2026`)이 그대로 쓰인다
  (`auth_service.py`) — 운영 Vercel 프로젝트 환경변수에 반드시 별도 값으로 설정할 것. 안 하면 이 값을 아는
  누구나 admin 권한 JWT를 위조할 수 있음

### 패키지 의존성 관리
`requirements.txt`가 세 곳에 있고 역할이 다름:
- `requirements.txt` (루트) — **Vercel 빌드 시 실제로 설치됨** (가장 중요)
- `api/requirements.txt` — Vercel api/ 함수용 (루트와 동기화 유지)
- `backend/requirements.txt` — 로컬 개발용

**패키지 추가·변경 시 세 파일 모두 수정할 것.** 루트 `requirements.txt` 누락 시 Vercel에서 ModuleNotFoundError 발생.

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

### Phase 1 운영 안전 계약

- 검증·운영: `OJT_STRICT_SHEETS_STORAGE=true`; Sheets 오류는 API 실패로 노출한다.
- 로컬 개발: fallback이 필요할 때만 `OJT_STRICT_SHEETS_STORAGE=false`를 명시한다.
- Migration은 기본 Dry-run이며 `--apply` 없이는 외부 Write를 수행하지 않는다.
- 응시자 식별자는 JWT `sub`, `team`, `name`을 사용한다.
- 시험 세트에는 `approved` 문제만 저장할 수 있다.

### Phase 2 — 55-Sheet Schema 검증

- 실제 기준은 `OJT_최종_Google_Sheets_관리자기능_통합설계.xlsx`의 55개 Sheet 행 1 Header다.
- `schema_catalog`, `sheet_ranges`, `data_dictionary`가 실제 Header와 다르면 실제 Header를 따른다.
- 기본 모드는 `OJT_SHEETS_SCHEMA_MODE=legacy`이며 신규 기능 Flag 7개는 모두 `false`다.
- Schema Migration은 운영본에 적용할 수 없다. 명시적인 복사본 ID와 `--target-kind copy`가 필요하다.
- Dry-run:

```powershell
cd backend
python scripts/migrate_schema_v2.py --spreadsheet-id COPY_SPREADSHEET_ID
```

- Dry-run 결과의 blocking issue가 0건일 때만 복사본에 Header를 적용한다.

```powershell
python scripts/migrate_schema_v2.py --spreadsheet-id COPY_SPREADSHEET_ID --apply --target-kind copy
```
