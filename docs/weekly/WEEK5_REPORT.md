# Week5 성과 정리 — 2026-06-20 ~ 2026-06-26

## 이번 주 완성된 작업

### 프론트엔드 — React 전환 (`frontend/src/**`, `frontend/*.html`)
- React 전환 후 버그 수정 및 dead code 제거 [브랜치: a, asan_ojt_suin, develop, feature/2-google-drive-poc, 파일: backend/main.py, frontend/src/pages/Admin.jsx, frontend/src/pages/Exam.jsx, vercel.json]
- 로그아웃 기능 추가 [브랜치: asan_ojt_suin, develop, 파일: frontend/src/App.jsx, frontend/src/api.js, frontend/src/pages/Admin.jsx, frontend/src/pages/Exam.jsx]

### Google Drive API 연동 (`backend/services/drive_service.py`, `backend/api/drive.py`, `ai_engine/`)
- Google Drive API 연결 PoC 구현 [브랜치: develop, feature/2-google-drive-poc, 파일: backend/api/drive.py, backend/services/drive_service.py, backend/credentials/.gitkeep]
- Google Drive OAuth 연동 완성 [브랜치: develop, 파일: backend/services/drive_service.py, ai_engine/drive_connector.py, backend/services/admin_service.py, frontend/src/App.jsx]

### 문서 및 프로젝트 설정 (`README.md`, `CLAUDE.md`, `.github/**`)
- README 배포·브랜치 전략 추가, CLAUDE.md 신규 작성 [브랜치: asan_ojt_suin, develop, 파일: README.md, CLAUDE.md]
- GitHub 이슈/PR 템플릿 추가 [브랜치: develop, 파일: .github/ISSUE_TEMPLATE/bug_report.md, .github/ISSUE_TEMPLATE/feature_request.md, .github/pull_request_template.md]

## 이번 주 발견된 문제

- fix: FastAPI가 정적 파일 직접 서빙하도록 구조 변경 [브랜치: asan_ojt_suin, develop]
- fix: vercel.json - builds 배열 제거, buildCommand/outputDirectory 방식으로 전환 [브랜치: asan_ojt_suin, develop]
- fix: Vercel 404 수정 - api/index.py 컨벤션으로 Python 함수 경로 변경 [브랜치: asan_ojt_suin, develop]
- fix: Vercel requirements에 google-auth 패키지 추가 (api/requirements.txt) [브랜치: develop]
- fix: 루트 requirements.txt에 google-auth 패키지 추가 (Vercel 실제 설치 경로) [브랜치: develop]
- refactor: React 전환 후 버그 수정 및 dead code 제거 [브랜치: a, asan_ojt_suin]

## 브랜치별 커밋 수

| 브랜치 | 이번 주 커밋 | 변경 파일 수 |
|--------|------------|------------|
| a | 2개 | 8개 |
| asan_ojt_suin | 7개 | 17개 |
| develop | 12개 | 25개 |
| feature/2-google-drive-poc | 4개 | 9개 |

## 다음 주 목표

[TODO: 직접 입력해주세요]

## 이번 주 결정 사항

[TODO: 직접 입력해주세요]

---
생성 시각: 2026-06-22 16:30
