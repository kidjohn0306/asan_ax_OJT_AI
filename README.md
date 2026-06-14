# OJT 평가 시스템 — (주)엑스티

AI 기반 신입사원 OJT 교육 이해도 평가 자동화 시스템

---

## 팀 분업 구조

| 팀 | 담당 폴더 | 역할 |
|---|---|---|
| A팀 (프론트엔드) | `frontend/` | React 또는 HTML/CSS/JS 응시자·관리자 화면 |
| B팀 (백엔드 API) | `backend/` | FastAPI 서버, JWT 인증, Drive 저장 |
| C팀 (AI·데이터) | `ai_engine/` | Claude API 문제 생성, 난이도 알고리즘, Drive 연동 |
| PM | 루트 | API 명세, 통합 테스트, 문서 |

---

## 프로젝트 구조

```
asan_ax_OJT_AI/
├── frontend/
│   ├── login.html       # 로그인 페이지
│   ├── exam.html        # 응시자 시험 화면
│   ├── admin.html       # 관리자 대시보드 (3패널)
│   └── assets/
├── backend/
│   ├── main.py          # FastAPI 진입점
│   ├── api/
│   │   ├── auth.py      # POST /api/auth/login|logout
│   │   ├── exam.py      # POST /api/exam/generate|submit, GET /result
│   │   └── admin.py     # GET/PATCH /api/admin/...
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── exam_service.py    # 출제·채점 로직
│   │   ├── admin_service.py
│   │   └── difficulty.py      # 난이도 판정 알고리즘
│   ├── mock_data/
│   │   ├── questions.json     # 개발용 더미 문제
│   │   └── users.json         # 개발용 더미 사용자
│   ├── requirements.txt
│   └── .env.example
└── ai_engine/
    ├── question_generator.py  # Claude API 문제 생성
    ├── drive_connector.py     # Google Drive 연동
    └── difficulty_classifier.py (TODO)
```

---

## 빠른 시작

### 백엔드

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # .env 편집 후 키 입력
USE_MOCK_DATA=true uvicorn main:app --reload
# http://localhost:8000/docs  →  Swagger UI
```

### 프론트엔드 (정적 파일)

```bash
# 브라우저에서 바로 열기 (개발용)
open frontend/login.html

# 또는 간단한 서버 실행
cd frontend
python -m http.server 3000
# http://localhost:3000/login.html
```

---

## Mock 모드 (개발 단계)

`.env`에서 `USE_MOCK_DATA=true` 설정 시:
- Claude API 호출 없음 → `mock_data/questions.json` 사용
- Google Drive API 호출 없음 → 로컬 파일 사용
- JWT는 `mock_jwt_{employee_id}` 형태의 더미 토큰 반환

실제 연동 전환 시 `.env`에서 `USE_MOCK_DATA=false`로 변경 후 각 TODO 구현.

---

## 핵심 API

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/auth/login` | 로그인 → JWT 반환 |
| POST | `/api/auth/logout` | 세션 무효화 |
| POST | `/api/exam/generate` | 팀코드 → 25문항 출제 |
| POST | `/api/exam/submit` | 답안 채점 + Drive 저장 |
| GET  | `/api/exam/result/{id}` | 결과 조회 |
| GET  | `/api/admin/logs` | 응시 이력 |
| PATCH| `/api/admin/difficulty` | 난이도 재조정 |
| POST | `/api/admin/approve-user` | 신입사원 승인 |

---

## 환경변수 (`.env`)

| 변수 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 키 (별도 결제 필요) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service Account JSON 경로 |
| `GDRIVE_QUESTION_BANK_FOLDER_ID` | 문제은행 루트 폴더 ID |
| `GDRIVE_RESULT_LOG_FOLDER_ID` | 결과로그 폴더 ID |
| `JWT_SECRET_KEY` | JWT 서명 키 |
| `USE_MOCK_DATA` | `true`=Mock 모드, `false`=실제 API |

---

## 향후 구현 (TODO)

- [ ] 실제 JWT 발급 및 검증 (`python-jose`)
- [ ] Google Drive Service Account 연동 (`drive_connector.py`)
- [ ] Claude API 문제 생성 (`question_generator.py`)
- [ ] 난이도 피드백 루프 및 자동 확정 로직
- [ ] 응시자 승인 관리 UI
- [ ] 결과 리포트 시각화 차트
