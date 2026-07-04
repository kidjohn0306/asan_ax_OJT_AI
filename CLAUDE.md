# OJT 평가 시스템 — Claude Code 가이드

## 프로젝트 개요
AI 기반 신입사원 OJT 교육 이해도 평가 시스템. FastAPI 백엔드 + Vite React 프론트엔드.
현재 단계: **Google Sheets 저장소 백엔드 완성 + 코드 품질 리팩토링 완료**

## 아키텍처

```
asan_ax_OJT_AI/
├── api/index.py              # Vercel 진입점 — backend/main.py의 app을 임포트
├── ai_engine/                # AI 문제 생성 엔진 (루트 위치 — sys.path에 의해 임포트됨)
│   ├── router.py             # AI_PROVIDER 환경변수로 생성기 선택
│   ├── gemini_generator.py   # Gemini REST API (gemini-2.5-flash) — _build_prompt/_call_api/_parse_response
│   ├── mock_generator.py     # 목업 문제 (AI_PROVIDER=mock)
│   └── question_generator.py # Claude API 스텁 (미구현)
├── backend/
│   ├── main.py               # FastAPI 앱, frontend/dist/ StaticFiles 마운트, load_dotenv(override=True)
│   ├── api/                  # 라우터
│   │   ├── deps.py           # 공유 의존성 — require_admin() (JWT 검증 + 역할 확인)
│   │   ├── auth.py, exam.py, admin.py, drive.py
│   ├── services/             # 비즈니스 로직
│   │   ├── exam_service.py   # 출제·채점·스냅샷 저장 (PASS_SCORE=70, SCORE_PER_QUESTION=4)
│   │   ├── admin_service.py  # 문제관리, 사용자승인, AI 생성 연결
│   │   ├── drive_service.py  # Google Drive 서비스 계정 인증
│   │   └── generation/       # run_gates (7개 검증 규칙)
│   ├── repositories/         # 저장소 추상화 레이어
│   │   ├── base.py           # 추상 인터페이스 (Question/Result/Snapshot/Feedback)
│   │   ├── local_json.py     # 로컬 JSON 파일 기반 (로컬 개발용)
│   │   ├── drive_repo.py     # Google Drive 기반 (STORAGE_BACKEND=drive)
│   │   ├── sheets_repo.py    # Google Sheets 기반 (STORAGE_BACKEND=sheets) ✅
│   │   └── __init__.py       # STORAGE_BACKEND 환경변수로 구현체 선택
│   ├── credentials/          # 서비스 계정 파일 (gitignore됨)
│   └── mock_data/            # 더미 JSON (users, questions, results)
├── frontend/
│   ├── src/                  # React 소스 (수정 대상)
│   └── dist/                 # 빌드 결과물 (git 포함 — 수정 후 반드시 재빌드)
└── vercel.json               # 모든 요청 → api/index.py → FastAPI
```

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
- `claude` — Claude API 스텁 (미구현, `ANTHROPIC_API_KEY` 필요)

### 저장소 백엔드 선택 (`STORAGE_BACKEND`)
- `local` (기본값) — `mock_data/*.json` 파일에 저장. Vercel 재배포 시 초기화됨
- `sheets` — Google Sheets에 저장. `GOOGLE_SHEETS_ID` 필요 ✅ **권장 (Drive 할당량 이슈 해결)**
  - 시험결과(`results` 탭) + 스냅샷(`snapshots` 탭) + 문제세트(`exam_sets` 탭) 자동 생성
  - 서비스 계정에 스프레드시트 편집자 권한 필요
- `drive` — Google Drive에 저장. `DRIVE_RESULTS_FOLDER_ID` 필요
  - ⚠️ 개인 구글 계정 연결 서비스 계정은 Drive 쓰기 할당량 0 → `storageQuotaExceeded` 발생

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
```

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
