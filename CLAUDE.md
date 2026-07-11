# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
AI 기반 신입사원 OJT 교육 이해도 평가 시스템. FastAPI 백엔드 + Vite React 프론트엔드.
현재 단계: **팀 관리·출제횟수 트래킹·CSV 업로드·대시보드 통계 구현 완료**

## 아키텍처

```
asan_ax_OJT_AI/
├── api/index.py              # Vercel 진입점 — backend/main.py의 app을 임포트
├── ai_engine/                # AI 문제 생성 엔진 (루트 위치 — sys.path에 의해 임포트됨)
│   ├── router.py             # AI_PROVIDER 환경변수로 생성기 선택
│   ├── gemini_generator.py   # Gemini REST API (gemini-2.5-flash) — _build_prompt/_call_api/_parse_response
│   └── question_generator.py # Claude API (claude-sonnet-5, anthropic SDK) + mock 생성기(_mock_generate) 겸용
├── backend/
│   ├── main.py               # FastAPI 앱, frontend/dist/ StaticFiles 마운트, load_dotenv(override=True)
│   ├── api/                  # 라우터
│   │   ├── deps.py           # 공유 의존성 — require_admin() (JWT 검증 + 역할 확인)
│   │   ├── auth.py, exam.py, admin.py, drive.py
│   ├── services/             # 비즈니스 로직
│   │   ├── exam_service.py   # 출제·채점·스냅샷 저장 (PASS_SCORE=70) + 출제횟수 increment_batch
│   │   ├── admin_service.py  # 문제관리, 사용자승인, AI 생성, 팀CRUD, CSV업로드, 대시보드통계
│   │   ├── drive_service.py  # Google Drive 서비스 계정 인증
│   │   └── generation/       # gates.py — run_gates (V-01~V-07 순수 함수 검증 규칙)
│   ├── repositories/         # 저장소 추상화 레이어
│   │   ├── base.py           # 추상 인터페이스 (Question/Result/Snapshot/Feedback/ExamSet/Team/QuestionStats)
│   │   ├── local_json.py     # 로컬 JSON 파일 기반 (로컬 개발용)
│   │   ├── drive_repo.py     # Google Drive 기반 (STORAGE_BACKEND=drive)
│   │   ├── sheets_repo.py    # Google Sheets 기반 (STORAGE_BACKEND=sheets) ✅
│   │   └── __init__.py       # 백엔드 선택 로직 (아래 "저장소 백엔드 선택" 참고)
│   ├── credentials/          # 서비스 계정 파일 (gitignore됨)
│   └── mock_data/            # 더미 JSON (users, questions, results)
├── frontend/
│   ├── src/                  # React 소스 (수정 대상)
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
`frontend/src/` 수정 후 반드시 빌드하고 dist도 커밋:
```bash
cd frontend && npm run build
git add frontend/src/ frontend/dist/
```

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
  - `results` + `snapshots` + `exam_sets` + `teams` + `question_stats` + `question_bank` 탭 자동 생성
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
- 새/변경 파일 발견 시 즉시 반영하지 않고 관리자 화면(`시험 생성`)에 알림 배너를 띄우며, 관리자가 "지금 스캔하기"를 눌러야 스캔·캐시 갱신됨
  (`GET /api/admin/materials/status?team_code=`, `POST /api/admin/materials/scan`)
- 관리자가 "교육자료 추가 입력" textarea에 직접 붙여넣은 텍스트는 Drive 캐시 텍스트 뒤에 보충 내용으로 덧붙여짐 (둘 다 유지, 어느 한쪽도 덮어쓰지 않음)
- 텍스트 추출 라이브러리: `pypdf`, `python-pptx` (세 requirements.txt 모두에 추가됨)
- 파일당 20,000자·카테고리당 40,000자로 텍스트를 잘라 저장 (Sheets 셀 5만자 한도 방지 + 프롬프트 폭주 방지)
- 파일 크기가 `DRIVE_MATERIAL_MAX_FILE_SIZE_MB`(기본 25MB)를 넘으면 다운로드를 건너뛰고 스캔 응답의 `skipped`에 사유와 함께 표시됨 (실제 교육용 PPTX에 영상·고해상도 이미지가 포함되면 수십~수백 MB로 커질 수 있어, 필요 시 이 값을 올려서 재스캔할 것)
- `team_code`는 Drive 쿼리에 그대로 들어가므로 `[a-zA-Z0-9_-]+` 패턴만 허용 (쿼리 인젝션 방지)

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

이 저장소에는 자동화된 테스트 스위트와 린터 설정이 없다 (pytest/eslint 설정 파일 없음).
변경 검증은 위 로컬 실행 방법으로 실제 플로우(로그인 → 시험 생성/응시 → 채점, 관리자 화면)를 직접 확인하는 방식에 의존한다.

## 주의사항
- API 키·시크릿을 코드에 하드코딩하지 말 것
- `frontend/dist/`는 빌드 후 소스와 함께 커밋할 것
- `api/index.py`는 수정 불필요 — Vercel 진입점 역할만 함
- Repository 구현체 추가 시 `base.py` 추상 메서드 모두 구현할 것

### 패키지 의존성 관리
`requirements.txt`가 세 곳에 있고 역할이 다름:
- `requirements.txt` (루트) — **Vercel 빌드 시 실제로 설치됨** (가장 중요)
- `api/requirements.txt` — Vercel api/ 함수용 (루트와 동기화 유지)
- `backend/requirements.txt` — 로컬 개발용

**패키지 추가·변경 시 세 파일 모두 수정할 것.** 루트 `requirements.txt` 누락 시 Vercel에서 ModuleNotFoundError 발생.
