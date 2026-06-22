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
│   └── index.py          # Vercel 진입점 — backend/main.py의 app을 임포트
├── backend/
│   ├── main.py           # FastAPI 앱, frontend/dist/ StaticFiles 마운트
│   ├── api/
│   │   ├── auth.py       # POST /api/auth/login|logout
│   │   ├── exam.py       # POST /api/exam/generate|submit, GET /result/{id}
│   │   ├── admin.py      # GET/PATCH/POST /api/admin/... (JWT 보호)
│   │   └── drive.py      # GET/POST /api/drive/status|files|download|upload-test-result
│   ├── services/
│   │   ├── auth_service.py    # JWT 발급·검증, bcrypt 비밀번호 확인
│   │   ├── exam_service.py    # 출제·채점, results.json 저장 (Drive 저장 미구현)
│   │   ├── admin_service.py   # 이력조회, 문제관리, 사용자승인, 난이도 override
│   │   ├── drive_service.py   # Google Drive 서비스 계정 인증·파일 목록·업로드·다운로드
│   │   └── difficulty.py      # 난이도 판정 알고리즘 (정답률·응답시간·백분위)
│   ├── credentials/           # service_account.json (gitignore됨 — 로컬에 직접 생성)
│   ├── mock_data/
│   │   ├── questions.json     # 공통5 + 팀별10×3 + 안전5 + 일반5 = 40문항
│   │   ├── users.json         # 개발용 더미 사용자 (approved_users + admins)
│   │   └── results.json       # 채점 결과 로컬 저장 (Drive 결과 저장 미구현 동안 임시)
│   └── requirements.txt
├── frontend/
│   ├── src/              # React 소스 (수정 시 반드시 빌드 후 커밋)
│   └── dist/             # 빌드 결과물 (git 포함 — Vercel이 이 파일을 서빙)
├── ai_engine/
│   └── question_generator.py  # Claude API 문제 생성 (미구현)
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
| 대시보드 | ✅ | KPI, 시스템 상태 (Drive·API 실시간 표시) |
| 시험 생성 | ✅ | 팀·난이도 선택 → mock 미리보기 |
| 검토·수정 | ✅ | 생성된 문항 탭별 검토 |
| 응시 이력 | ⚠️ 더미 데이터 | `fetch_logs()` 하드코딩 5건 반환 중 |
| 문제 관리 | ✅ | 난이도 드롭다운 즉시 반영 (`PATCH /api/admin/difficulty`) |
| 사용자 승인 | ✅ | 신입사원 등록 폼 → users.json 저장 |
| 결과 분석 | ⚠️ 더미 데이터 | 통계·차트 하드코딩 (실데이터 부족) |
| 설정 | ✅ | 외부 연동 현황 실시간 표시 |

### 백엔드

| 파일 | 상태 | 설명 |
|---|---|---|
| `auth_service.py` | ✅ 완료 | JWT 발급·검증, bcrypt 비밀번호 확인 |
| `exam_service.py` | ⚠️ 부분 | 출제·채점 완료. `USE_MOCK_DATA=false` 시 Drive 저장 로직 미구현 |
| `admin_service.py` | ⚠️ 부분 | 이력 조회·사용자 승인·난이도 override 완료. `fetch_logs()` 더미 반환, 난이도 로그 Drive 미저장 |
| `drive_service.py` | ✅ 완료 | 서비스 계정 인증, 파일 목록·다운로드·업로드 구현 |
| `difficulty.py` | ✅ 완료 | 정답률(50%)·응답시간(30%)·백분위(20%) 규칙 기반, admin override 연결 |
| `api/admin.py` | ✅ 완료 | 모든 라우트 `require_admin` JWT 의존성으로 보호 |

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
| GET  | `/api/admin/user-count` | Admin JWT | 승인된 응시자 수 (대시보드용) |
| GET  | `/api/admin/exam-count` | Admin JWT | 총 응시 완료 수 (대시보드용) |
| GET  | `/api/drive/status` | 없음 | Google Drive 연결 상태 확인 |
| GET  | `/api/drive/files?folder_id={id}` | 없음 | 폴더 내 파일 목록 조회 |
| POST | `/api/drive/download` | 없음 | Drive 파일 다운로드 |
| POST | `/api/drive/upload-test-result` | 없음 | JSON 결과 파일 업로드 테스트 |

---

## Mock 모드

`USE_MOCK_DATA=true`(기본값, `exam_service.py`에서 참조)일 때:

- Claude API 호출 없음 → `mock_data/questions.json` 문제 사용
- Drive API 자체는 연결됨 — 단, 채점 결과는 아직 `mock_data/results.json`에 로컬 저장
- 비밀번호 `mock_hash` 계정은 아무 값으로 로그인 가능 (개발 편의)
- 실제 전환: `USE_MOCK_DATA=false` 설정 후 Drive 결과 저장(`exam_service.py`) 및 Claude 문제 생성(`question_generator.py`) 구현 필요

---

## 환경변수 (`.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `USE_MOCK_DATA` | `true` | `true`=Mock, `false`=실제 API |
| `JWT_SECRET_KEY` | `ojt-dev-secret-...` | JWT 서명 키 (운영 시 반드시 교체) |
| `ANTHROPIC_API_KEY` | — | Claude API 키 (문제 생성용, 미구현) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | — | Service Account JSON 전체 내용 (Vercel 배포용) |
| `GDRIVE_QUESTION_BANK_FOLDER_ID` | — | 문제은행 루트 폴더 ID (Drive 저장 구현 시 필요) |
| `GDRIVE_RESULT_LOG_FOLDER_ID` | — | 결과로그 폴더 ID (Drive 저장 구현 시 필요) |

---

## 개발 시 주의사항

### 대시보드 KPI 연동 현황

| 항목 | 상태 | 데이터 출처 |
|---|---|---|
| 승인된 응시자 | ✅ 실시간 | `users.json` (`GET /api/admin/user-count`) |
| 총 응시 완료 | ✅ 실시간 | `results.json` (`GET /api/admin/exam-count`) |
| Google Drive 상태 | ✅ 실시간 | `GET /api/drive/status` |
| 합격률 | ⚠️ 하드코딩 60% | 실응시 데이터 쌓인 후 연동 예정 |
| 평균 점수 | ⚠️ 하드코딩 80.8점 | 위 동일 |
| 결과 분석 뷰 | ⚠️ 하드코딩 | Mock 데이터 몇 건으로는 통계 무의미 |

### 인메모리 상태 (서버 재시작 시 초기화)

| 변수 | 위치 | 영향 |
|---|---|---|
| `_exam_sessions` | `exam_service.py` | 진행 중 시험 세션 소멸 → 응시자 재시작 불가 |
| `_difficulty_overrides` | `admin_service.py` | 관리자 조정 난이도 초기화 |

### 미구현 항목

| 기능 | 파일 | 상태 |
|---|---|---|
| Drive 결과 저장 | `exam_service.py:141` | `USE_MOCK_DATA=false` 분기 TODO |
| Drive 이력 조회 | `admin_service.py:57` | `fetch_logs()` 더미 5건 반환 중 |
| Drive 난이도 로그 기록 | `admin_service.py:103` | override 시 Excel 기록 TODO |
| Claude API 문제 생성 | `ai_engine/question_generator.py` | 파일만 존재, 로직 미구현 |
| 난이도 자동 확정 루프 | `difficulty.py` | `classify_difficulty()` 구현됨, 채점 후 자동 호출 미연결 |
| 서버 측 로그아웃 | `api/auth.py` | 클라이언트 sessionStorage 삭제만 처리 |
| 응시자 JWT 검증 | `api/exam.py` | `/api/exam/*` 라우트 인증 미적용 |

### 난이도 auto_confirmed 로직
관리자가 특정 문항을 **3회 연속 동일 난이도**로 override하면 `auto_confirmed: true` 반환.
AI 판정이 안정적이라 자동 인정하는 학습 루프 구조 (`admin_service.py` → `difficulty.py`).

---

## 향후 구현 (TODO)

- [x] Google Drive 서비스 계정 인증 연동 (`drive_service.py`, Vercel 환경변수 설정)
- [x] Admin 대시보드 Drive 상태 실시간 표시
- [ ] `exam_service.py` — Drive 결과 저장 (`USE_MOCK_DATA=false` 분기)
- [ ] `admin_service.py` — Drive에서 이력 조회, 난이도 로그 저장
- [ ] Claude API 문제 생성 (`question_generator.py`)
- [ ] Drive 문제은행 Excel 파싱
- [ ] 난이도 AI 자동 확정 피드백 루프
- [ ] 결과 리포트 PDF 내보내기
- [ ] 비밀번호 초기화 기능
- [ ] 응시자 전용 JWT 검증 (`/api/exam/*`)

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
| `ANTHROPIC_API_KEY` | Claude API 키 | Claude 연동 시 |

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
