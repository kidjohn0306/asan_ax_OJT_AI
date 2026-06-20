# OJT 평가 시스템 — Claude Code 가이드

## 프로젝트 개요
AI 기반 신입사원 OJT 교육 이해도 평가 시스템. FastAPI 백엔드 + Vite React 프론트엔드.
현재 단계: **더미데이터 기반 Mock MVP** (Google Drive·Claude API 연동 전)

## 아키텍처

```
asan_ax_OJT_AI/
├── api/index.py          # Vercel 진입점 — backend/main.py의 app을 임포트
├── backend/
│   ├── main.py           # FastAPI 앱, frontend/dist/ StaticFiles 마운트
│   ├── api/              # 라우터 (auth, exam, admin)
│   ├── services/         # 비즈니스 로직
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
(Drive 연동 완료 전 임시 구조)

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
