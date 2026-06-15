# OJT 평가 시스템 — (주)엑스티

AI 기반 신입사원 OJT 교육 이해도 평가 자동화 시스템

---

## 팀 분업 구조

| 팀 | 담당 폴더 | 역할 |
|---|---|---|
| A팀 (프론트엔드) | `frontend/` | HTML/CSS/JS 응시자·관리자 화면 |
| B팀 (백엔드 API) | `backend/` | FastAPI 서버, JWT 인증, Drive 저장 |
| C팀 (AI·데이터) | `ai_engine/` | Claude API 문제 생성, 난이도 알고리즘, Drive 연동 |
| PM | 루트 | API 명세, 통합 테스트, 문서 |

---

## 프로젝트 구조

```
asan_ax_OJT_AI/
├── frontend/
│   ├── index.html       # 진입점 — /login.html 으로 자동 이동
│   ├── login.html       # 로그인 — fetch() API 연동, sessionStorage 토큰 저장
│   ├── exam.html        # 응시자 시험 화면 — API 연동 + mock fallback
│   └── admin.html       # 관리자 SPA — 사이드바 8개 뷰 (대시보드·시험생성 등)
├── backend/
│   ├── main.py          # FastAPI 진입점, CORS 설정
│   ├── api/
│   │   ├── auth.py      # POST /api/auth/login|logout
│   │   ├── exam.py      # POST /api/exam/generate|submit, GET /result/{id}
│   │   └── admin.py     # GET/PATCH/POST /api/admin/... (JWT 보호)
│   ├── services/
│   │   ├── auth_service.py    # JWT 발급·검증, bcrypt 비밀번호 확인
│   │   ├── exam_service.py    # 출제·채점, results.json 저장
│   │   ├── admin_service.py   # 이력조회, 문제관리, 사용자승인, 난이도 override
│   │   └── difficulty.py      # 난이도 판정 알고리즘 (정답률·응답시간·백분위)
│   ├── mock_data/
│   │   ├── questions.json     # 공통5 + 팀별10×3 + 안전5 + 일반5 = 40문항
│   │   ├── users.json         # 개발용 더미 사용자 (approved_users + admins)
│   │   └── results.json       # 채점 결과 로컬 저장 (Drive 연동 전 임시)
│   ├── requirements.txt
│   └── .env.example
└── ai_engine/
    ├── question_generator.py  # Claude API 문제 생성 (TODO)
    └── drive_connector.py     # Google Drive 연동 (TODO)
```

---

## 빠른 시작

### 백엔드

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 필요 시 키 입력 (Mock 모드는 불필요)
uvicorn main:app --reload
# http://localhost:8000/docs  →  Swagger UI
```

### 프론트엔드

백엔드 서버가 프론트를 함께 서빙합니다. 별도 서버 불필요.

```
http://localhost:8000/login.html   # 로그인
http://localhost:8000/exam.html    # 응시자 시험
http://localhost:8000/admin.html   # 관리자
```

**Mock 모드 테스트 계정**

| 사원번호 | 역할 | 비밀번호 |
|---|---|---|
| `admin001` | 관리자 | 아무 값 |
| `2024ㄴ001` | 응시자 (T1) | 아무 값 |
| `2024002` | 응시자 (T2) | 아무 값 |

---

## 구현 현황

### 프론트엔드

| 파일 | 상태 | 설명 |
|---|---|---|
| `login.html` | ✅ 완료 | `POST /api/auth/login` 연동, role에 따라 admin/exam 분기 |
| `exam.html` | ✅ 완료 | API로 문제 수신, 제출 후 채점 결과 반영. API 실패 시 mock fallback |
| `admin.html` | ✅ 완료 | SPA 멀티뷰 — 사이드바 네비게이션, 8개 독립 뷰 |

**admin.html 뷰 목록**

| 뷰 | 설명 |
|---|---|
| 대시보드 | KPI 카드, 빠른 실행, 최근 이력, 시스템 상태 |
| 시험 생성 | 팀·난이도·문항수 선택 → AI 미리보기 (`POST /api/admin/preview-exam`) |
| 검토·수정 | 생성된 문항 탭별 검토, 승인/수정요청 |
| 응시 이력 | 팀·날짜 필터, 이름 검색 (`GET /api/admin/logs`) |
| 문제 관리 | 문제 목록, 난이도 드롭다운 즉시 반영 (`PATCH /api/admin/difficulty`) |
| 사용자 승인 | 신입사원 등록 폼 → users.json 저장 (`POST /api/admin/approve-user`) |
| 결과 분석 | 응시자 목록, 부서별 점수 차트, AI 분석 요약 |
| 설정 | Mock/Live 모드 상태, 외부 연동 현황, TODO 목록 |

### 백엔드

| 파일 | 상태 | 설명 |
|---|---|---|
| `auth_service.py` | ✅ 완료 | python-jose JWT 발급·검증, bcrypt 비밀번호 확인 |
| `exam_service.py` | ✅ 완료 | 25문항 출제, 자동 채점, results.json 저장 |
| `admin_service.py` | ✅ 완료 | 이력 조회, 문제 목록, 난이도 override(즉시 반영 + 시험 출제에도 적용), 사용자 승인 |
| `difficulty.py` | ✅ 연결 | 정답률(50%)·응답시간(30%)·백분위(20%) 규칙 기반 판정, admin override에 연결 |
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
| POST | `/api/auth/logout` | Bearer | 세션 무효화 |
| POST | `/api/exam/generate` | 없음 | 팀코드 → 25문항 출제 |
| POST | `/api/exam/submit` | 없음 | 답안 채점 + 결과 저장 |
| GET  | `/api/exam/result/{id}` | 없음 | 결과 조회 |
| GET  | `/api/admin/logs` | Admin JWT | 응시 이력 (팀·날짜 필터) |
| GET  | `/api/admin/questions` | Admin JWT | 문제 목록 (team·카테고리 필터) |
| PATCH| `/api/admin/difficulty` | Admin JWT | 난이도 재조정 (시험 출제에도 즉시 반영) |
| POST | `/api/admin/preview-exam` | Admin JWT | 시험지 미리보기 |
| GET  | `/api/admin/users` | Admin JWT | 승인된 응시자 목록 |
| POST | `/api/admin/approve-user` | Admin JWT | 신입사원 승인 등록 |
| DELETE| `/api/admin/users/{id}` | Admin JWT | 응시자 삭제 |
| GET  | `/api/admin/user-count` | Admin JWT | 승인된 응시자 수 (대시보드용) |
| GET  | `/api/admin/exam-count` | Admin JWT | 총 응시 완료 수 (대시보드용) |

---

## Mock 모드

`USE_MOCK_DATA=true`(기본값)일 때:

- Claude API 호출 없음 → `mock_data/questions.json` 문제 사용
- Google Drive 없음 → `mock_data/results.json`에 로컬 저장
- 비밀번호 `mock_hash` 계정은 아무 값으로 로그인 가능 (개발 편의)
- 실제 전환: `.env`에서 `USE_MOCK_DATA=false` 후 Drive·Claude 연동 구현

---

## 환경변수 (`.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `USE_MOCK_DATA` | `true` | `true`=Mock, `false`=실제 API |
| `JWT_SECRET_KEY` | `ojt-dev-secret-...` | JWT 서명 키 (운영 시 반드시 교체) |
| `ANTHROPIC_API_KEY` | — | Claude API 키 (문제 생성용) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | — | Service Account JSON 경로 |
| `GDRIVE_QUESTION_BANK_FOLDER_ID` | — | 문제은행 루트 폴더 ID |
| `GDRIVE_RESULT_LOG_FOLDER_ID` | — | 결과로그 폴더 ID |

---

## 개발 시 주의사항

### 대시보드 KPI 연동 현황

| 항목 | 상태 | 데이터 출처 | 미연동 이유 |
|---|---|---|---|
| 승인된 응시자 | ✅ 실시간 연동 | `users.json` (`GET /api/admin/user-count`) | — |
| 총 응시 완료 | ✅ 실시간 연동 | `results.json` (`GET /api/admin/exam-count`) | — |
| 합격률 | ⏸ 하드코딩 (60%) | — | Drive 연동 후 실데이터가 쌓여야 의미 있음 |
| 평균 점수 | ⏸ 하드코딩 (80.8점) | — | 위 동일 |
| 결과 분석 뷰 전체 | ⏸ 하드코딩 | — | Mock 데이터 몇 건으로는 통계가 무의미 |

합격률·평균점수·결과 분석 뷰는 Google Drive 연동 + 실응시 데이터 확보 후 일괄 연동 예정.

### 인메모리 상태 (서버 재시작 시 초기화)
| 변수 | 위치 | 영향 |
|---|---|---|
| `_exam_sessions` | `exam_service.py` | 진행 중인 시험 세션 소멸 → 응시자가 새로고침/재시작 시 시험 재시작 불가 |
| `_difficulty_overrides` | `admin_service.py` | 관리자가 조정한 난이도 초기화 |

### 외부 리소스 부재로 미적용 항목
아래는 코드 문제가 아니라 **외부 권한/키가 없어서** 아직 연결되지 않은 기능입니다.

| 기능 | 필요한 것 | 현재 상태 |
|---|---|---|
| Google Drive 결과 저장 | Service Account JSON + 폴더 ID | `results.json` 로컬 저장으로 대체 중 |
| Google Drive 이력 조회 | 위 동일 | `fetch_logs()` 내 하드코딩 더미 데이터 반환 중 |
| Claude API 문제 생성 | `ANTHROPIC_API_KEY` | `question_generator.py` 미구현, mock 문항 사용 중 |
| 난이도 자동 확정 루프 | Drive 결과 집계 | `classify_difficulty()` 구현됨, 채점 후 자동 호출만 미연결 |

### 알려진 미구현
- `POST /api/auth/logout` — 서버 측 세션 무효화 미구현. 클라이언트의 sessionStorage 삭제로만 처리됨

### 난이도 auto_confirmed 로직
관리자가 특정 문항의 난이도를 **3회 연속 동일하게** override하면 `auto_confirmed: true` 반환.  
AI 판정이 안정적이라고 자동 인정하는 학습 루프 구조 (`admin_service.py` → `difficulty.py`).

---

## 향후 구현 (TODO)

- [ ] Google Drive Service Account 연동 (`drive_connector.py`)
- [ ] Claude API 문제 생성 JSON 파싱 (`question_generator.py`)
- [ ] Drive 문제은행 Excel 파싱
- [ ] Drive 결과로그 저장
- [ ] 난이도 AI 자동 확정 피드백 루프 (`classify_difficulty` 집계)
- [ ] 결과 리포트 PDF 내보내기
- [ ] 비밀번호 초기화 기능
- [ ] 응시자 전용 토큰 검증 (`/api/exam/*` 라우트)
