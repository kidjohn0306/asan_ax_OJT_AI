# OJT 평가 시스템 — (주)엑스티

AI 기반 신입사원 OJT 교육 이해도 평가 자동화 시스템

---

## 팀 분업 구조

| 팀 | 담당 폴더 | 역할 |
|---|---|---|
| A팀 (프론트엔드) | `frontend/` | React SPA 응시자·관리자 화면 |
| B팀 (백엔드 API) | `backend/` | FastAPI 서버, JWT 인증, Drive 연동 |
| C팀 (AI·데이터) | `ai_engine/` | Claude API 문제 생성, 난이도 알고리즘 |
| PM | 루트 | API 명세, 통합 테스트, 문서 |

---

## 프로젝트 구조

```
asan_ax_OJT_AI/
├── api/
│   └── index.py              # Vercel 진입점 — backend/main.py의 app을 임포트
├── backend/
│   ├── main.py               # FastAPI 앱, frontend/dist/ StaticFiles 마운트
│   ├── api/
│   │   ├── auth.py           # POST /api/auth/login|logout
│   │   ├── exam.py           # POST /api/exam/generate|submit, GET /result/{id}
│   │   ├── admin.py          # GET/PATCH/POST /api/admin/... (JWT 보호)
│   │   └── drive.py          # GET/POST /api/drive/status|files|download
│   ├── services/
│   │   ├── auth_service.py   # JWT 발급·검증, bcrypt 비밀번호 확인
│   │   ├── exam_service.py   # 출제·채점·스냅샷 저장 (Repository 패턴)
│   │   ├── admin_service.py  # 이력조회, 문제관리, AI 생성·gate 검증, 사용자승인
│   │   ├── drive_service.py  # Google Drive 서비스 계정 인증·파일 목록·업로드·다운로드
│   │   ├── difficulty.py     # 난이도 판정 알고리즘 (정답률·응답시간·백분위)
│   │   └── generation/
│   │       └── gates.py      # AI 생성 문제 7-gate 검증 (V-01~V-07)
│   ├── api/
│   │   ├── deps.py           # 공유 의존성 — require_admin() JWT 검증
│   │   ├── auth.py, exam.py, admin.py, drive.py
│   ├── repositories/         # 저장소 추상화 레이어
│   │   ├── base.py           # 추상 인터페이스 (Question/Result/Snapshot/Feedback)
│   │   ├── local_json.py     # 로컬 JSON 파일 기반 구현체
│   │   ├── drive_repo.py     # Google Drive 기반 구현체
│   │   ├── sheets_repo.py    # Google Sheets 기반 구현체 ✅
│   │   └── __init__.py       # STORAGE_BACKEND 환경변수로 구현체 선택
│   ├── credentials/          # service_account.json (gitignore됨 — 로컬에 직접 생성)
│   ├── mock_data/
│   │   ├── questions.json    # 공통5 + 팀별10×3 + 안전5 + 일반5 = 40문항
│   │   ├── users.json        # 개발용 더미 사용자 (approved_users + admins)
│   │   └── results.jsonl     # 채점 결과 로컬 저장 (STORAGE_BACKEND=local 시)
│   └── requirements.txt
├── ai_engine/                # AI 문제 생성 엔진 (루트 위치)
│   ├── router.py             # AI_PROVIDER 환경변수로 생성기 선택
│   ├── _shared.py            # gemini/claude 생성기 공통 로직 (프롬프트 생성·응답 파싱·자료 절단)
│   ├── gemini_generator.py   # Gemini REST API (gemini-2.5-flash) ✅
│   └── question_generator.py # Claude API (완전 구현) + _mock_generate() ✅
├── frontend/
│   ├── src/              # React 소스 (수정 시 반드시 빌드 후 커밋)
│   └── dist/             # 빌드 결과물 (git 포함 — Vercel이 이 파일을 서빙)
├── vercel.json           # 모든 요청 → api/index.py → FastAPI
└── requirements.txt      # Vercel 빌드 시 실제 설치되는 파일 (가장 중요)
```

---

## 빠른 시작

### 백엔드

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# http://localhost:8000/docs  →  Swagger UI
```

로컬에서 Google Drive 연동 시 `backend/credentials/service_account.json` 파일 필요.

### 프론트엔드 (개발 서버)

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

백엔드 서버(`localhost:8000`)도 함께 실행해야 API 호출 가능.

### 접속 URL

| 경로 | 설명 |
|---|---|
| `http://localhost:8000/` | 로그인 페이지 (React SPA) |
| `http://localhost:5173/` | 프론트 개발 서버 (HMR) |
| `http://localhost:8000/docs` | FastAPI Swagger UI |

**Mock 모드 테스트 계정**

| 사원번호 | 역할 | 비밀번호 |
|---|---|---|
| `admin001` | 관리자 | 아무 값 |
| `2024001` | 응시자 (T1) | 아무 값 |
| `2024002` | 응시자 (T2) | 아무 값 |

---

## 구현 현황

### 프론트엔드

| 파일 | 상태 | 설명 |
|---|---|---|
| `src/pages/Login.jsx` | ✅ 완료 | `POST /api/auth/login` 연동, role에 따라 admin/exam 분기 |
| `src/pages/Exam.jsx` | ✅ 완료 | API로 문제 수신, 제출 후 채점 결과 반영 |
| `src/pages/Admin.jsx` | ✅ 완료 | SPA 멀티뷰 — 사이드바 8개 뷰 |

**Admin 뷰 목록**

| 뷰 | 상태 | 설명 |
|---|---|---|
| 대시보드 | ✅ | 4개 통계 카드(문제수/시험세트/응시예정/전체인원) + 더미 데이터 주입 버튼 |
| 시험 생성 | ✅ | 팀·난이도 선택 → AI 생성 또는 mock 미리보기 |
| 검토·수정 | ✅ | 생성된 문항 탭별 검토, gate 오류 표시 |
| 응시 이력 | ⚠️ 더미 데이터 | 실 응시 데이터 없으면 하드코딩 5건 반환 |
| 문제 관리 | ✅ | 난이도 드롭다운 즉시 반영 (`PATCH /api/admin/difficulty`) |
| 사용자 승인 | ✅ | 신입사원 등록 폼 + CSV 대량 업로드 카드 |
| 결과 분석 | ⚠️ 더미 데이터 | 통계·차트 하드코딩 (실데이터 부족) |
| 설정 | ✅ | 외부 연동 현황 실시간 표시 |
| 팀 관리 | ✅ | 팀 추가·팀명 수정·삭제 (Sheets `teams` 탭 연동) |

### 백엔드

| 파일 | 상태 | 설명 |
|---|---|---|
| `auth_service.py` | ✅ 완료 | JWT 발급·검증, bcrypt 비밀번호 확인 |
| `exam_service.py` | ✅ 완료 | 출제·채점·스냅샷 저장 (Repository 패턴). 스냅샷 없으면 HTTP 410 |
| `admin_service.py` | ✅ 완료 | 이력 조회·사용자 승인·난이도 override·AI 생성·팀CRUD·CSV업로드·대시보드통계 |
| `drive_service.py` | ✅ 완료 | 서비스 계정 인증, 파일 목록·다운로드·업로드 구현 |
| `material_service.py` | ✅ 완료 | Drive 교육자료(PDF/PPTX) 스캔·텍스트추출·캐싱, AI 문제 생성에 자동 반영 |
| `difficulty.py` | ✅ 완료 | 정답률(50%)·응답시간(30%)·백분위(20%) 규칙 기반, admin override 연결 |
| `api/admin.py` | ✅ 완료 | 모든 라우트 `require_admin` JWT 의존성으로 보호 |
| `repositories/` | ✅ 완료 | Repository 패턴. `STORAGE_BACKEND=local\|sheets\|drive` 선택 |
| `repositories/sheets_repo.py` | ✅ 완료 | Sheets 백엔드 — results/snapshots/exam_sets/teams/question_stats 탭 |
| `api/deps.py` | ✅ 완료 | `require_admin()` 공유 의존성 — admin/drive 중복 제거 |
| `ai_engine/gemini_generator.py` | ✅ 완료 | Gemini REST API 문제 생성, 함수 분리 + 예외처리 강화 |
| `services/generation/gates.py` | ✅ 완료 | AI 생성 문제 7-gate 검증 후 reviewing 상태 저장 |
| `ai_engine/question_generator.py` | ✅ 완료 | Claude API (anthropic SDK) 문제 생성 + mock 생성기 |

---

## 채점 기준

- **25문항 × 4점 = 100점 만점**
- **70점 이상 합격** (`pass: true`)
- 난이도 배분: 상 7 · 중 10 · 하 8

---

## 핵심 API

| Method | Endpoint | 인증 | 설명 |
|---|---|---|---|
| POST | `/api/auth/login` | 없음 | 로그인 → JWT 반환 |
| POST | `/api/auth/logout` | Bearer | 세션 무효화 (클라이언트 측만 처리) |
| POST | `/api/exam/generate` | 없음 | 팀코드 → 25문항 출제 |
| POST | `/api/exam/submit` | 없음 | 답안 채점 + 결과 저장 |
| GET  | `/api/exam/result/{id}` | 없음 | 결과 조회 |
| GET  | `/api/admin/logs` | Admin JWT | 응시 이력 (팀·날짜 필터) — 현재 더미 반환 |
| GET  | `/api/admin/questions` | Admin JWT | 문제 목록 (team·카테고리 필터) |
| PATCH| `/api/admin/difficulty` | Admin JWT | 난이도 재조정 (시험 출제에도 즉시 반영) |
| POST | `/api/admin/preview-exam` | Admin JWT | 시험지 미리보기 |
| GET  | `/api/admin/users` | Admin JWT | 승인된 응시자 목록 |
| POST | `/api/admin/approve-user` | Admin JWT | 신입사원 승인 등록 |
| DELETE| `/api/admin/users/{id}` | Admin JWT | 응시자 삭제 |
| GET  | `/api/admin/stats` | Admin JWT | 대시보드 4개 집계 (문제수/시험세트/응시예정/전체인원) |
| GET  | `/api/admin/teams` | Admin JWT | 팀 목록 조회 |
| POST | `/api/admin/teams` | Admin JWT | 팀 추가 |
| PATCH| `/api/admin/teams/{id}` | Admin JWT | 팀명 수정 |
| DELETE| `/api/admin/teams/{id}` | Admin JWT | 팀 삭제 |
| POST | `/api/admin/upload-users` | Admin JWT | CSV 대량 사원 업로드 (multipart) |
| GET  | `/api/admin/question-stats` | Admin JWT | 전체 문제 출제 횟수 조회 |
| GET  | `/api/admin/question-stats/flagged` | Admin JWT | 자주 출제 문제 목록 (exam_count≥5) |
| POST | `/api/admin/seed-mock-data` | Admin JWT | 더미 사용자 주입 (테스트용) |
| GET  | `/api/admin/system-status` | Admin JWT | 실제 운영 모드(AI_PROVIDER 등)·API 키 설정 여부 조회 |
| GET  | `/api/admin/materials/status` | Admin JWT | 교육자료 폴더의 신규/변경 파일 감지 (team_code 쿼리) |
| POST | `/api/admin/materials/scan` | Admin JWT | 감지된 신규 파일 다운로드·텍스트추출·캐싱 실행 |
| GET  | `/api/drive/status` | 없음 | Google Drive 연결 상태 확인 |
| GET  | `/api/drive/files?folder_id={id}` | 없음 | 폴더 내 파일 목록 조회 |
| POST | `/api/drive/download` | 없음 | Drive 파일 다운로드 |
| POST | `/api/drive/upload-test-result` | 없음 | JSON 결과 파일 업로드 테스트 |

---

## Mock 모드

`AI_PROVIDER=mock`(기본값)일 때:

- AI API 호출 없음 → `mock_data/questions.json` 문제 사용
- `STORAGE_BACKEND=local`이면 채점 결과는 `mock_data/results.jsonl`에 로컬 저장
- 비밀번호 `mock_hash` 계정은 아무 값으로 로그인 가능 (개발 편의)
- Gemini 전환: `AI_PROVIDER=gemini` + `GEMINI_API_KEY` 설정
- Sheets 저장 전환: `STORAGE_BACKEND=sheets` + `GOOGLE_SHEETS_ID` 설정 ✅ **권장**
- Drive 저장 전환: `STORAGE_BACKEND=drive` + `DRIVE_RESULTS_FOLDER_ID` 설정 (할당량 이슈 주의)

---

## 환경변수 (`.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `JWT_SECRET_KEY` | `ojt-dev-secret-...` | JWT 서명 키 (운영 시 반드시 교체) |
| `AI_PROVIDER` | `mock` | `mock` / `gemini` / `claude` |
| `STORAGE_BACKEND` | `local` | `local` / `sheets` / `drive` |
| `GOOGLE_SHEETS_ID` | — | Google Sheets 스프레드시트 ID (`STORAGE_BACKEND=sheets` 시 필요) |
| `GEMINI_API_KEY` | — | Gemini API 키 (`AI_PROVIDER=gemini` 시 필요) |
| `CLAUDE_API_KEY` | — | Claude API 키 (`AI_PROVIDER=claude` 시 필요) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | — | Service Account JSON 전체 내용 (Vercel 배포용) |
| `DRIVE_RESULTS_FOLDER_ID` | — | Drive 결과·스냅샷 저장 폴더 ID (`STORAGE_BACKEND=drive` 시 필요) |
| `DRIVE_EDUCATION_MATERIALS_FOLDER_ID` | — | 교육자료(PDF/PPTX) 루트 폴더 ID. 하위 `common`/`team1`/`team2`/`team3` 폴더를 스캔해 AI 문제 생성에 자동 반영 |
| `DRIVE_MATERIAL_MAX_FILE_SIZE_MB` | `25` | 교육자료 파일 다운로드 크기 상한 (초과 시 스캔에서 제외, 응답의 `skipped`에 표시) |

---

## 교육자료 자동 스캔 (Drive → AI 문제 생성)

`DRIVE_EDUCATION_MATERIALS_FOLDER_ID`를 설정하면 그 하위 `common`/`team1`/`team2`/`team3` 폴더의 PDF/PPTX를
스캔해 텍스트를 추출하고, AI 문제 생성 시 자동으로 포함합니다.

- 관리자가 "시험 생성" 화면에서 팀을 선택하면 새/변경된 자료가 있는지 자동 확인하고, 있으면 알림 배너를 띄웁니다.
- 배너의 "지금 스캔하기"를 눌러야만 실제로 다운로드·텍스트추출·캐시 갱신이 일어납니다 (자동 스캔 없음).
- 변경 없는 파일은 캐시된 텍스트를 그대로 재사용해 Drive 호출·추출 비용을 아낍니다.
- 관리자가 "교육자료 추가 입력" textarea에 직접 붙여넣은 텍스트는 캐시된 텍스트 뒤에 보충 내용으로 덧붙습니다.

---

## 개발 시 주의사항

### 대시보드 KPI 연동 현황

| 항목 | 상태 | 데이터 출처 |
|---|---|---|
| 문제은행 문제수 | ✅ 실시간 | `GET /api/admin/stats` |
| 활성 시험세트 수 | ✅ 실시간 | `GET /api/admin/stats` |
| 응시 예정 인원 | ✅ 실시간 | `GET /api/admin/stats` |
| 전체 등록 인원 | ✅ 실시간 | `GET /api/admin/stats` |
| Google Drive 상태 | ✅ 실시간 | `GET /api/drive/status` |
| 합격률 | ⚠️ 하드코딩 60% | 실응시 데이터 쌓인 후 연동 예정 |
| 결과 분석 뷰 | ⚠️ 하드코딩 | 실 응시 데이터 부족 |

### 알려진 한계

| 항목 | 설명 |
|---|---|
| Drive 쓰기 할당량 | 개인 Google 계정 연결 서비스 계정은 `storageQuotaExceeded` 발생. `STORAGE_BACKEND=sheets` 전환으로 해결됨 |
| Vercel 스냅샷 휘발 | `STORAGE_BACKEND=local` 시 스냅샷이 `/tmp`에 저장되어 신규 인스턴스에서 손실 가능 → HTTP 410. `sheets` 모드에서는 영구 저장 |
| `questions.json` 읽기 전용 | Vercel 파일시스템은 읽기 전용. AI 생성 문제 저장 시 `STORAGE_BACKEND=local`이면 런타임 오류 발생 |
| 응시 이력 | 실 결과 없으면 `fetch_logs()`가 더미 5건 반환 |

### 미구현 항목

| 기능 | 파일 | 비고 |
|---|---|---|
| ~~Claude API 문제 생성~~ | ~~`ai_engine/question_generator.py`~~ | ✅ 구현 완료 (anthropic SDK) |
| ~~Google Sheets 저장 백엔드~~ | ~~`repositories/`~~ | ✅ 구현 완료 (`sheets_repo.py`) |
| 응시자 JWT 검증 | `api/exam.py` | `/api/exam/*` 라우트 인증 미적용 |
| 서버 측 로그아웃 | `api/auth.py` | 클라이언트 sessionStorage 삭제만 처리 |
| 결과 리포트 PDF 내보내기 | — | 미착수 |
| 비밀번호 초기화 | — | 미착수 |

### 난이도 auto_confirmed 로직
관리자가 특정 문항을 **3회 연속 동일 난이도**로 override하면 `auto_confirmed: true` 반환.
결과는 `questions.json`의 `admin_override` 필드에 영속화됨 (`admin_service.py` → `difficulty.py`).

---

## 향후 구현 (TODO)

- [x] Google Drive 서비스 계정 인증 연동
- [x] Admin 대시보드 Drive 상태 실시간 표시
- [x] Repository 패턴 도입 (`STORAGE_BACKEND` 환경변수로 전환)
- [x] 스냅샷 기반 채점 (문제·정답 생성 시점 고정)
- [x] Gemini API 문제 생성 연동 (`AI_PROVIDER=gemini`)
- [x] run_gates 연결 — AI 생성 문제 7-gate 검증 후 `reviewing` 저장
- [x] Google Sheets 저장 백엔드 (`STORAGE_BACKEND=sheets`, 인스턴스 교체에도 안전)
- [x] 팀 관리 CRUD (`teams` Sheets 탭 + `/api/admin/teams`)
- [x] 문제 출제 횟수 트래킹 (`question_stats` 탭, `exam_count≥5` 자동 플래그)
- [x] 대시보드 4개 통계 카드 (`GET /api/admin/stats`)
- [x] CSV 대량 사원 업로드 (`POST /api/admin/upload-users`)
- [x] AI 토큰 절약 — 교육자료 4000자 초과 시 자동 트런케이션
- [x] Claude API 문제 생성 (`question_generator.py`, anthropic SDK)
- [x] Drive 교육자료(PDF/PPTX) 자동 스캔 → AI 문제 생성 반영 (`material_service.py`)
- [x] 관리자 화면 "운영 모드"·"Claude API" 실제 상태 체크 (`GET /api/admin/system-status`)
- [ ] 응시자 전용 JWT 검증 (`/api/exam/*`)
- [ ] 난이도 AI 자동 확정 피드백 루프
- [ ] 결과 리포트 PDF 내보내기
- [ ] 비밀번호 초기화 기능

---

## 배포 (Vercel)

**배포 URL**: `https://asan-ax-ojt-ai.vercel.app/`

### 구조
모든 요청을 FastAPI(`api/index.py`)가 처리합니다.
- `/api/*` → API 라우터
- 그 외 → `frontend/dist/` 정적 파일 서빙 (React SPA)

### Vercel 환경변수 설정 (프로젝트 소유자만)
Vercel 대시보드 → 프로젝트 → **Settings → Environment Variables**

| 변수명 | 설명 | 필수 여부 |
|---|---|---|
| `JWT_SECRET_KEY` | JWT 서명 키 (랜덤 문자열로 교체 필수) | **즉시 설정** |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service Account JSON 전체 내용 | ✅ 설정 완료 |
| `CLAUDE_API_KEY` | Claude API 키 | Claude 연동 시 |

> ⚠️ `JWT_SECRET_KEY`를 설정하지 않으면 기본값(`ojt-dev-secret-change-in-prod-2026`)이 사용됩니다. 반드시 Vercel 환경변수로 덮어쓰세요.

---

## 브랜치 전략

```
main        ← 배포 브랜치 (Vercel 자동 배포)
develop     ← 통합 브랜치 (PR 머지 대상)
feature/xxx ← 팀원 개별 작업 브랜치
```

**작업 흐름**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/내작업명

# 작업 후
git push origin feature/내작업명
# GitHub에서 develop으로 PR 생성 (.github/pull_request_template.md 자동 적용)
```

**커밋 메시지 규칙**: `type: 설명`
- `feat` — 새 기능 / `fix` — 버그 수정 / `docs` — 문서 / `chore` — 설정 / `refactor` — 리팩토링

---

## 프론트엔드 빌드 규칙

`frontend/dist/`가 git에 포함되어 있습니다. **`frontend/src/`를 수정하면 반드시 빌드 후 함께 커밋해야 합니다.**

```bash
cd frontend
npm run build        # dist/ 재생성
cd ..
git add frontend/src/ frontend/dist/
git commit -m "feat: ..."
```

빌드 없이 소스만 커밋하면 배포 화면과 코드가 불일치합니다.

## 패키지 의존성 관리

`requirements.txt`가 세 곳에 있고 역할이 다름:
- `requirements.txt` (루트) — **Vercel 빌드 시 실제로 설치됨** (가장 중요)
- `api/requirements.txt` — Vercel api/ 함수용 (루트와 동기화 유지)
- `backend/requirements.txt` — 로컬 개발용

**패키지 추가·변경 시 세 파일 모두 수정할 것.** 루트 `requirements.txt` 누락 시 Vercel에서 ModuleNotFoundError 발생.
