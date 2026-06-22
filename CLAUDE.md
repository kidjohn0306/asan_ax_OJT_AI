# OJT 평가 시스템 — Claude Code 가이드

## 프로젝트 개요
AI 기반 신입사원 OJT 교육 이해도 평가 시스템. FastAPI 백엔드 + Vite React 프론트엔드.
현재 단계: **Mock MVP + Google Drive 서비스 계정 연동 완료** (Claude API 연동 전)

## 아키텍처

```
asan_ax_OJT_AI/
├── api/index.py          # Vercel 진입점 — backend/main.py의 app을 임포트
├── backend/
│   ├── main.py           # FastAPI 앱, frontend/dist/ StaticFiles 마운트
│   ├── api/              # 라우터 (auth, exam, admin, drive)
│   ├── services/         # 비즈니스 로직 (drive_service.py 포함)
│   ├── credentials/      # 서비스 계정 파일 (gitignore됨)
│   └── mock_data/        # 더미 JSON (users, questions, results)
├── frontend/
│   ├── src/              # React 소스 (수정 대상)
│   └── dist/             # 빌드 결과물 (git 포함 — 수정 후 반드시 재빌드)
└── vercel.json           # 모든 요청 → api/index.py → FastAPI
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
USE_MOCK_DATA=true
```
Vercel 배포용 키는 Vercel 대시보드 Environment Variables에서 설정 (코드에 직접 쓰지 말 것).

### Mock 모드
`USE_MOCK_DATA=true`(기본값)일 때 Claude API·Drive 없이 동작.
- 비밀번호: `mock_hash` 계정은 아무 값으로 로그인 가능
- 테스트 계정: `admin001`(관리자), `2024001`(응시자 T1), `2024002`(응시자 T2)

### 데이터 유의사항
현재 `mock_data/*.json` 파일 기반 저장. Vercel 서버리스 환경에서는 재배포 시 초기화됨.
(Drive 결과 저장 연동 전 임시 구조 — Drive API 연결은 완료, 결과 저장 로직은 미구현)

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
- `backend/mock_data/results.json`은 Vercel 재배포 시 초기화됨 (알려진 한계)
- `api/index.py`는 수정 불필요 — Vercel 진입점 역할만 함

### 패키지 의존성 관리
`requirements.txt`가 세 곳에 있고 역할이 다름:
- `requirements.txt` (루트) — **Vercel 빌드 시 실제로 설치됨** (가장 중요)
- `api/requirements.txt` — Vercel api/ 함수용 (루트와 동기화 유지)
- `backend/requirements.txt` — 로컬 개발용

**패키지 추가·변경 시 세 파일 모두 수정할 것.** 루트 `requirements.txt` 누락 시 Vercel에서 ModuleNotFoundError 발생.
