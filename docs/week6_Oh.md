# Week 6 작업 보고서 — Oh 

> **작업 기간**: 2026-06-27  
> **대상 브랜치**: `feature/mvp-backend-redesign` (예정)  
> **연관 문서**: [`백엔드_구조_MVP설계.md`](백엔드_구조_MVP설계.md) · [`UI변경점.md`](UI변경점.md)  
> **참조 설계**: `AI문제생성_상세설계_통합마스터.md`

---

## 1. 이번 주 작업 요약

| 구분 | 작업 내용 | 산출물 | 상태 |
|---|---|---|---|
| 분석 | 현재 백엔드 코드 구조 진단 — 설계서 대비 격차 파악 | (이 문서) | ✅ |
| 설계 | 1차 MVP 백엔드 아키텍처 설계 | `docs/백엔드_구조_MVP설계.md` | ✅ |
| 명세 | MVP 적용에 따른 프론트엔드 UI 변경 명세 | `docs/UI변경점.md` | ✅ |
| 백엔드 구현 | Repository 계층 신설, 서비스 리팩토링, 규칙 게이트 | 아래 상세 참고 | ✅ |
| 프론트 구현 | 상태 뱃지·승인/반려 UI, 통계 카드, 경고 문구 제거 | `Admin.jsx`, `Exam.jsx` | ✅ |
| 빌드 | `npm run build` → `dist/` 재생성 | `frontend/dist/` | ✅ |

---

## 2. 문제 정의 — 현재 코드의 무엇이 문제였나

### 2-1. 콜드스타트(Cold Start) 데이터 소멸 버그

**원인**: 서비스 파일 상단 모듈 레벨 변수 3개가 Vercel 재기동 시 초기화됨.

```python
# 수정 전 — 인메모리라 콜드스타트에 소멸
_exam_sessions: dict = {}
_difficulty_overrides: dict = {}
_difficulty_error_logs: dict = {}
```

**해결**: 전부 Repository로 영속화 — `snapshots.jsonl`, `questions.json(admin_override 필드)`, `difficulty_feedback.jsonl`

---

### 2-2. Vercel에서 results.json 저장 불가

**원인**: `open("w")`로 파일 전체를 덮어쓰는 방식 → Vercel 읽기전용 FS에서 실패.

**해결**: `results.jsonl` JSONL append-only 방식으로 전환. `LocalResultRepository.append_result()` 사용.

---

### 2-3. 모든 문제가 무조건 출제됨

**원인**: `questions.json`에 `status` 필드가 없어 초안 문제도 출제 대상.

**해결**: 전체 문제에 `status` 필드 추가. `exam_service`에서 `approved` 문제만 선별.

---

### 2-4. 채점이 "라이브 문제" 기준

**원인**: 채점 시 `questions.json` 현재 값을 읽어 채점 → 출제 후 수정 시 채점 오류.

**해결**: 출제 시점에 스냅샷 저장(`snapshots.jsonl`), 채점은 스냅샷 기준으로 전환.

---

### 2-5. 난이도 비교 기준 버그

**원인**: `override_difficulty()`가 "이전 관리자값 vs 새 관리자값" 비교 → 무의미.

**해결**: 설계 §7.1대로 `difficulty_ai` vs 관리자 확정값 비교로 수정.

---

### 2-6. 저장 위치 하드코딩 — Drive 전환 불가

**원인**: 모든 서비스가 `mock_data/` 경로를 직접 참조.

**해결**: Repository 계층 도입. `STORAGE_BACKEND` 환경변수로 `local` ↔ `drive` 전환 가능.

---

## 3. 구현된 파일 목록

### 3-1. 신규 파일

| 파일 | 설명 |
|---|---|
| `backend/repositories/__init__.py` | `STORAGE_BACKEND` 환경변수로 구현체 선택 |
| `backend/repositories/base.py` | Repository 인터페이스 4종 (Question·Result·Snapshot·Feedback) |
| `backend/repositories/local_json.py` | LocalJson 구현체 — `mock_data/*.json` + `*.jsonl` |
| `backend/services/generation/__init__.py` | 패키지 초기화 |
| `backend/services/generation/gates.py` | 규칙 게이트 V-01~V-07 (순수 함수) |
| `backend/mock_data/snapshots.jsonl` | 시험 스냅샷 저장소 (출제 시 자동 생성) |
| `backend/mock_data/difficulty_feedback.jsonl` | 난이도 수정 이력 저장소 (수정 시 자동 생성) |
| `backend/mock_data/results.jsonl` | 채점 결과 저장소 (results.json 대체) |
| `docs/백엔드_구조_MVP설계.md` | MVP 백엔드 아키텍처 설계 정본 |
| `docs/UI변경점.md` | UI 변경 명세 |
| `docs/week6_Oh.md` | 이 문서 |

### 3-2. 수정된 파일

| 파일 | 주요 변경 내용 |
|---|---|
| `backend/mock_data/questions.json` | `status`, `version`, `explanation`, `flags` 필드 추가 (전체 45문제) |
| `backend/services/exam_service.py` | approved 필터, 스냅샷 저장/채점, JSONL 저장, 인메모리 제거 |
| `backend/services/admin_service.py` | Repository 사용, 난이도 비교 버그 수정, approve/reject 함수 추가, 인메모리 3종 제거 |
| `backend/api/admin.py` | `POST /questions/{id}/approve`, `POST /questions/{id}/reject`, `GET /approved-question-count`, `GET /reviewing-question-count`, `status` 쿼리 파라미터 추가 |
| `frontend/src/pages/Admin.jsx` | 상태 필터 탭, StatusBadge, 승인/반려 버튼, 대시보드 통계 카드 교체, Settings TODO 업데이트, ExamCreate 복합 생성 모드 |
| `frontend/src/pages/Exam.jsx` | 시험 응시 화면 난이도 뱃지 제거, 결과 화면 경고 문구 → 저장 완료 문구 |
| `frontend/dist/` | `npm run build` 재빌드 완료 |

---

## 4. Repository 계층 구조

```
services/ (저장 위치를 모른다)
  ↓ 인터페이스만 호출
repositories/
  ├── base.py           — 인터페이스 정의
  ├── local_json.py     — 현재: mock_data/*.json + *.jsonl
  └── (drive_repo.py)   — 나중: Google Drive (STORAGE_BACKEND=drive)
```

전환 방법: `.env`에 `STORAGE_BACKEND=drive` 한 줄. 서비스·라우터·프론트 무수정.

---

## 5. 규칙 게이트 (V-01~V-07)

`backend/services/generation/gates.py` — 순수 함수, 외부 의존 없음.

| 코드 | 검증 | 실패 시 |
|---|---|---|
| V-01 | JSON 필수 필드·타입 | `draft` 유지 |
| V-02 | 보기 구조 (4개, 빈값·중복 없음) | `draft` 유지 |
| V-03 | 정답 단일성 (A~D) | `draft` 유지 |
| V-04 | 근거 존재 (내부자료 문제 해설 필수) | `draft` 유지 |
| V-05 | 난이도 값 (상/중/하) | `draft` 유지 |
| V-06 | 카테고리·팀 일치 | `flags.warning = true` |
| V-07 | 보안 키워드 필터 | `flags.security_hold = true` |

---

## 6. 데이터 구조 변경

### questions.json 추가 필드

```json
{
  "status": "approved",
  "version": 1,
  "explanation": "해설 텍스트",
  "flags": { "warning": false, "security_hold": false, "needs_edit": false }
}
```

### 저장소 형식 분리

| 파일 | 형식 | 이유 |
|---|---|---|
| `questions.json` | JSON | 갱신형 |
| `users.json` | JSON | 갱신형 |
| `results.jsonl` | **JSONL** | 누적형, Vercel 안전 |
| `snapshots.jsonl` | **JSONL** | 불변 기록 |
| `difficulty_feedback.jsonl` | **JSONL** | 이력 원본 |

---

## 7. 프론트엔드 변경 상세

### 관리자 화면 (Admin.jsx)

| 컴포넌트 | 변경 내용 |
|---|---|
| `Dashboard` | 통계 카드 3·4번 교체: 합격률(하드코딩) → 승인 문제 수 API, 평균 점수(하드코딩) → 검토 대기 수 API |
| `Questions` | 상태 필터 탭(전체/검토대기/승인/반려/초안), StatusBadge, 플래그 아이콘(⚠️🔒), 승인/반려 버튼, 반려 사유 인라인 입력 |
| `ExamCreate` | 난이도별 생성 / 복합 생성 모드 분리 탭 |
| `Settings` | TODO → 구현 현황으로 교체, 완료 항목 체크 표시 |

### 응시자 화면 (Exam.jsx)

| 화면 | 변경 내용 |
|---|---|
| `ExamScreen` | 난이도 뱃지 제거 (설계 §9.4: 사원 화면엔 난이도 숨김) |
| `ResultScreen` | `"※ 이 화면을 닫으면 모든 응시 데이터가 삭제됩니다."` 제거 → `"결과가 인사팀에 자동 전송 및 저장되었습니다."` |

---

## 8. 새로 추가된 API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/api/admin/approved-question-count` | 승인된 문제 수 |
| `GET` | `/api/admin/reviewing-question-count` | 검토 대기 문제 수 |
| `GET` | `/api/admin/questions?status=reviewing` | 상태별 문제 조회 |
| `POST` | `/api/admin/questions/{id}/approve` | 문제 승인 |
| `POST` | `/api/admin/questions/{id}/reject` | 문제 반려 (body: `{ reason }`) |
| `PATCH` | `/api/admin/difficulty` | 난이도 수정 (body에 `reason_code` 추가) |

---

## 9. 미구현 항목 (다음 단계)

| 항목 | 이유 |
|---|---|
| `DriveRepository` 구현 | `STORAGE_BACKEND=drive` 스위치 준비 완료, 실제 Drive API 연동 코드만 남음 |
| Claude API 문제 생성 (`generator.py`) | 비용·외부 의존, 마지막 단계 |
| 검토 큐 뷰 실제 API 연동 | `ExamReview` 컴포넌트 현재 Mock 뷰 유지 |
| 응시 이력 실제 results.jsonl 연동 | `fetch_logs` 데이터 없을 때 더미 반환 중 |
| calibration few-shot 선별 UI | 2차 MVP |

---

## 10. 로컬 실행 방법

```bash
# 백엔드 (반드시 backend/ 디렉터리에서)
cd backend
uvicorn main:app --reload

# 프론트 개발서버
cd frontend && npm run dev
```

**주의**: 프로젝트 루트에서 `python -m uvicorn backend.main:app` 실행 시  
루트의 `api/` 폴더 충돌로 `ImportError` 발생 — 반드시 `cd backend` 후 실행.

### 테스트 계정

| 계정 | 역할 | 비밀번호 |
|---|---|---|
| `admin001` | 관리자 | 아무 값 |
| `2024001` | 응시자 T1 | 아무 값 |
| `2024002` | 응시자 T2 | 아무 값 |

### 환경변수 (backend/.env)

```
JWT_SECRET_KEY=로컬개발용아무값
USE_MOCK_DATA=true
STORAGE_BACKEND=local
```
