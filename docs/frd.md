# OJT 관리자 페이지 고도화 최종 FRD

> 문서 상태: 최종 설계 기준안
>
> 문서 버전: v1.0
>
> 작성일: 2026-07-15
>
> 대상 시스템: AI 기반 OJT 문제 생성·시험·평가 관리 시스템
>
> 구현 기준: 기존 FastAPI + React 18 + Vite 애플리케이션의 단계적 확장
>
> 중요 제한: 본 문서는 구현 승인이 아니며, 별도 코딩 지시 전에는 제품 코드를 변경하지 않는다.

## 1. 문서 목적

이 문서는 현재 운영 중인 OJT 시스템의 Google Sheets 구조와 관리자 UI를 무중단으로 고도화하기 위한 최종 기능 요구사항을 정의한다.

목표는 다음과 같다.

- 현재 8개 운영 Sheet와 기존 데이터를 보존한다.
- 최종 55개 Sheet 구조를 기준으로 출처, 검수, 시험 버전, 배정, 답안, 감사 이력을 정규화한다.
- 신규 구조를 한 번에 전환하지 않고 `legacy → dual → v2` 순으로 활성화한다.
- 생성 문제의 우회 사용, 확정 시험 변경, 사용자 신원 위조, 중복 제출, 무응답 누락을 서버에서 차단한다.
- 관리자 UI를 업무 흐름과 URL 중심의 React 화면으로 재구성한다.
- 사원용 로그인·시험 응시·제출·결과 UI는 현재 화면을 유지한다.

## 2. 확정 결정사항

| 항목 | 결정 |
|---|---|
| 최종 스키마 기준 | 최종 Excel의 실제 55개 Sheet와 실제 Header를 기준으로 한다. |
| 내부 문서 불일치 | `schema_catalog`, `sheet_ranges`, `data_dictionary`는 실제 Header에 맞춰 정정한다. |
| 운영 적용 방식 | 운영 Sheet를 직접 변경하지 않고 전체 복사본에서 먼저 검증한다. |
| UI 범위 | 관리자 UI만 개편한다. 사원용 UI는 유지한다. |
| Schema 구성 | 복사본에 55개 Sheet와 확장 Header를 먼저 구성한다. |
| 신규 기능 초기 상태 | 모든 신규 Feature Flag를 `OFF`로 둔다. |
| 전환 방식 | 호환 계층 기반 단계 전환을 사용한다. |
| 저장 실패 정책 | 검증·운영 환경에서 Sheets 저장 실패 시 요청도 실패 처리한다. |
| Local fallback | 로컬 개발 환경에서만 허용한다. |
| 관리자 URL | `/admin/*`를 공식 URL로 사용한다. |
| 기존 관리자 URL | `/xt-hq-2b7f`는 일정 기간 `/admin/dashboard`로 리다이렉트한다. |
| 별도 시스템 | 별도 관리자 앱, 별도 로그인, 병렬 문제은행을 만들지 않는다. |

## 3. 범위

### 3.1 포함 범위

- 현재 및 최종 Google Sheets 스키마 정합성 확보
- 호환 Reader, V2 Reader, Dual Writer, Migration Guard
- 문제 생성 작업, Candidate, Gate, 검수, 문제은행, 변경 이력
- 시험 초안, 확정 버전, 문항 Snapshot, 사용자별 배정
- 시험 상황, 응시 세션, 운영 이벤트, 제출 오류 처리
- 결과 요약, 문제별 답안, 통계, 재교육 기록
- Google Drive 자료, 문서 버전, 파싱, 청크, 색인, 충돌
- 행동 중심 관리자 대시보드
- 감사 로그, 운영 알림, 시스템 상태
- `/admin/*` 관리자 라우팅과 화면 모듈화
- 기존 사원 API의 시트 호환성·신원·제출 무결성 강화
- 단계별 회귀 테스트, Canary, Rollback

### 3.2 제외 범위

- 사원 로그인 UI 재설계
- 사원 시험 안내 및 응시 UI 재설계
- 사원용 자동 저장·제출·결과 화면 재설계
- 별도 인증 시스템
- 별도 관리자 애플리케이션
- `question_bank_v2`, `exam_papers` 등 병렬 원장
- 현재 MVP에서 빈칸형·단답형·서술형 문제 지원
- 1차 구현의 WebSocket 의존
- 검증 전 운영 Google Sheet 직접 변경

## 4. 사용자와 권한

### 4.1 관리자

- 단일 관리자 권한 체계를 사용한다.
- 관리자는 문제 생성·검수, 시험 생성·배정·운영, 결과 조회, 자료 관리, 사용자·팀 관리, 시스템 상태 확인을 수행한다.
- 모든 주요 변경은 JWT의 관리자 식별자를 `actor_id`로 감사 로그에 기록한다.
- 위험한 작업은 확인 절차, 사유, 멱등키를 요구한다.

### 4.2 응시자

- 기존 사원 화면을 그대로 사용한다.
- 서버는 요청 Body의 `employee_id`, `team_code`, `name`을 신뢰 원장으로 사용하지 않는다.
- 서버는 JWT의 `sub`, `team`, `name`을 사용한다.
- 다른 사용자의 시험·결과에 대한 접근은 거부한다.

## 5. 목표 아키텍처

```text
기존 React 사원 화면 ─────────────┐
                                 ├─ 기존 FastAPI 애플리케이션
신규 React 관리자 화면 /admin ───┘
                                      │
                           서비스·도메인 검증 계층
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
              Legacy Reader                       V2 Reader
              기존 8개 탭                        신규 정규화 탭
                    │                                   │
                    └──────────── Dual Writer ──────────┘
                                      │
                           Google Sheets 복사본/운영본
```

### 5.1 구성요소 책임

#### Legacy Reader

- 현재 8개 Sheet와 기존 열을 읽는다.
- 기존 열 이름과 순서를 유지한다.
- `snapshots`의 B/C 혼재 행을 내용 기반으로 판별한다.
- 기존 소문자 상태값을 지원한다.

#### V2 Reader

- 신규 정규화 Sheet와 확장 열을 읽는다.
- 관련 Feature Flag가 활성화된 기능에서만 사용한다.
- 정의되지 않은 자동 fallback을 허용하지 않는다.

#### Dual Writer

- 전환 기간에 Legacy 구조와 V2 구조를 함께 기록한다.
- 작업 ID와 멱등키로 재시도 중복을 방지한다.
- 한쪽만 성공하면 성공으로 응답하지 않는다.
- 부분 실패는 복구 가능한 상태와 오류 정보를 남긴다.

#### Migration Guard

- Sheet 존재 여부, Header Hash, 필수 열 순서, PK 중복을 검사한다.
- 검사 실패 시 Write를 차단한다.
- 기본 실행 모드는 Dry-run이다.
- 적용 전후 행 수와 핵심 집계를 비교한다.

#### Feature Flag Router

- 기능별 Reader와 Writer 경로를 선택한다.
- `legacy`, `dual`, `v2` 모드를 지원한다.
- Rollback은 Sheet 삭제가 아니라 Flag 하향으로 수행한다.

## 6. 데이터 원장

| 데이터 | 최종 원장 | 전환 중 Legacy |
|---|---|---|
| 승인 문제 | `question_bank` | 동일 탭 기존 열 |
| 승인 전 문제 | `question_candidates` | `question_bank`의 draft/reviewing 행 |
| Gate 결과 | `gate_results` | `flags.gate_snapshot` |
| 문제 검수 | `question_reviews` | 기존 상태·반려 사유 |
| 문제 변경 이력 | `question_history` | 기존 version |
| 시험 기본정보 | `exam_sets` | 동일 탭 기존 열 |
| 확정 시험 버전 | `exam_versions` | 없음 |
| 확정 시험 문항 | `exam_set_items` | `exam_sets.question_ids` |
| 사용자별 배정 | `assignments` | `exam_sets.assigned_users` |
| 응시 세션 | `exam_attempts` | Snapshot과 결과의 간접 상태 |
| 운영 이벤트 | `exam_events` | 없음 |
| 결과 요약 | `results` | 동일 탭 기존 열 |
| 문제별 답안 | `result_answers` | `results.results` JSON |
| 자료 원본 정보 | `materials` | `material_cache` |
| 문서 버전 | `document_versions` | 없음 |
| 자료 청크 | `document_chunks` | 없음 |
| 관리자 작업 | `audit_logs` | 결과 기반 로그 |
| 운영 이상 | `operational_alerts` | 없음 |

## 7. Sheet 구성 원칙

### 7.1 기존 운영 호환 Sheet

다음 Sheet는 삭제하거나 이름을 변경하지 않는다.

```text
results
snapshots
question_stats
exam_sets
teams
users
question_bank
material_cache
```

- 기존 열은 삭제, 이동, 중간 삽입하지 않는다.
- 신규 열은 기존 열의 오른쪽에만 추가한다.
- 기존 Reader가 사용하는 접두 Header의 순서를 유지한다.
- 신규 필수 필드는 Feature Flag 전환 전까지 기존 행에서 비어 있을 수 있다.

### 7.2 정규화 및 관리자 운영 Sheet

```text
schema_meta
materials
material_slides
knowledge_units
generation_jobs
question_candidates
gate_results
question_history
exam_set_items
assignments
result_answers
difficulty_feedback
generation_presets
document_versions
document_chunks
sync_runs
sync_conflicts
question_reviews
exam_versions
exam_attempts
exam_events
admin_tasks
operational_alerts
audit_logs
system_status_checks
export_jobs
reeducation_records
```

### 7.3 문서·검증 Sheet

최종 Excel에 포함된 README, 데이터 사전, 관계도, Dry-run 결과, UI/API/상태 모델 Sheet는 운영 원장이 아니다. 구현 시 실제 Header와 동기화된 문서 및 검증 근거로 사용한다.

```text
00_README
01_상세설명
02_적용체크리스트
03_관리자기능_v3_요약
schema_catalog
data_dictionary
migration_plan
relation_map
enum_values
feature_flags
sheet_ranges
dry_snapshot
dry_category
dry_question
dry_result
sample_rows
ui_routes_v3
api_contracts_v3
state_models_v3
feature_matrix_v3
```

기존 운영 호환 8개, 정규화·관리자 운영 27개, 문서·검증 20개를 합쳐 총 55개 Sheet로 구성한다.

## 8. 기능 요구사항

### 8.1 대시보드

#### FR-DASH-001 오늘 할 일

- `admin_tasks`에서 P0, P1, P2 작업을 조회한다.
- P0, 마감 임박 P1, P2 순서로 정렬한다.
- 완료 작업은 기본적으로 접힌 영역에 표시한다.

#### FR-DASH-002 운영 이상

- 시험 시작 불가, 승인되지 않은 문제 포함, 답안 저장 실패, 제출 실패, Drive 동기화 실패, 파싱·색인 실패를 표시한다.
- 각 알림은 대상 화면으로 이동할 수 있어야 한다.

#### FR-DASH-003 오늘 시험 요약

- 배정, 미입장, 입장, 응시 중, 제출, 오류 수를 요약한다.
- 위험한 시험 제어 기능은 대시보드에서 제공하지 않는다.

#### FR-DASH-004 최근 관리자 작업

- `audit_logs`를 읽기 쉬운 문장으로 표시한다.

### 8.2 문제 생성

#### FR-QGEN-001 생성 조건

- 평가 유형, 팀, 근무형태, 공정, 업무, 총 문항 수, 난이도·카테고리 분포, 재사용 정책을 입력한다.
- 합계 불일치와 문제 부족을 실행 전에 검증한다.

#### FR-QGEN-002 자료 사용 조건

- 보안 승인 및 색인 완료 자료만 문제 생성에 사용할 수 있다.
- 문서 버전과 근거 위치를 Candidate에 연결한다.

#### FR-QGEN-003 생성 작업

- 생성 요청은 `generation_jobs` 한 행으로 관리한다.
- 진행률, 완료 수, 검토 필요 수, 실패 수, 부분 실패를 표시한다.
- 작업과 생성 결과는 별도 URL을 사용한다.

#### FR-QGEN-004 Candidate 보존

- 생성 성공·실패·Gate 실패 후보를 삭제하지 않는다.
- 모든 후보는 전역적으로 고유한 `candidate_id`를 가진다.

### 8.3 Gate 및 검수

#### FR-QREV-001 Gate 기록

- V01~V07을 Gate별 한 행으로 `gate_results`에 기록한다.
- `HARD_FAIL`은 서버에서 승인을 차단한다.

#### FR-QREV-002 변경 후 재검사

- 문제 본문, 보기, 정답, 해설, 근거가 변경되면 기존 Gate 판정을 만료시킨다.
- 재검사 완료 전 승인할 수 없다.

#### FR-QREV-003 승인·반려

- 승인과 반려는 체크리스트와 사유를 `question_reviews`에 기록한다.
- 승인된 Candidate만 `question_bank`에 등록한다.
- WARNING 승인에는 최소 사유 길이를 적용한다.

#### FR-QREV-004 문제 변경 이력

- 승인 문제 수정 시 기존 행을 조용히 덮어쓰지 않는다.
- 변경 전후 Snapshot을 `question_history`에 기록한다.
- 이미 확정된 시험의 문항에는 변경을 반영하지 않는다.

### 8.4 시험 생성·확정

#### FR-EXAM-001 승인 문제 강제

- 시험 저장 API는 모든 문제의 존재 여부와 `approved` 상태를 검사한다.
- draft, reviewing, rejected, archived 문제를 거부한다.

#### FR-EXAM-002 시험 초안

- 초안 단계에서는 문항 추가, 삭제, 순서, 배점을 수정할 수 있다.
- 총점, 문항 수, 분포, 중복, 보관 문제를 검증한다.

#### FR-EXAM-003 시험 확정

- 확정 시 `exam_versions`와 `exam_set_items`를 생성한다.
- 문항 본문, 보기, 정답, 해설, 문제 버전, 배점의 Snapshot을 저장한다.
- 확정 버전은 수정하지 않는다.
- 변경이 필요하면 새 시험 버전을 만든다.

### 8.5 시험 배정·상황

#### FR-ASGN-001 사용자별 배정

- 확정된 시험만 배정할 수 있다.
- 사용자별 배정은 `assignments` 한 행으로 관리한다.
- 과거 배정 행을 삭제하지 않고 상태를 변경한다.

#### FR-ASGN-002 응시 조건

- 응시 가능 기간, 최대 시도 횟수, 추가 시간, 재입장 정책을 서버에서 검사한다.
- 승인·활성 사용자만 배정할 수 있다.

#### FR-LIVE-001 응시 상태

- 미입장, 입장, 응시 중, 일시 이탈, 제출 중, 제출 완료, 제출 실패, 강제 종료를 구분한다.
- 1차 구현은 5~10초 폴링을 사용한다.

#### FR-LIVE-002 운영 제어

- 시험 시작, 시간 연장, 입장 마감, 시험 종료는 멱등키를 요구한다.
- 모든 운영 제어는 `exam_events`와 `audit_logs`에 기록한다.
- 위험한 작업은 확인과 사유를 요구한다.

### 8.6 제출·채점·결과

#### FR-RSLT-001 신원 강제

- 시험 생성·제출·결과 조회는 JWT 사용자 신원을 기준으로 처리한다.
- 다른 사용자의 식별자를 Body에 전달해도 적용하지 않는다.

#### FR-RSLT-002 멱등 제출

- 제출은 고유 멱등키를 사용한다.
- 동일 제출 재요청은 결과를 중복 저장하지 않는다.

#### FR-RSLT-003 전체 문항 채점

- 제출된 답안 목록이 아니라 확정 시험 전체 문항을 기준으로 채점한다.
- 무응답은 `selected_choice=null`, `is_correct=false`, `score=0`으로 저장한다.
- 문항 점수는 `exam_set_items.score`를 사용한다.

#### FR-RSLT-004 결과 저장

- 요약은 `results`, 문항별 상세는 `result_answers`에 저장한다.
- 두 구조의 저장 상태를 추적한다.
- 부분 실패 상태에서는 성공 응답을 반환하지 않는다.

#### FR-RSLT-005 결과 분석

- 평균 점수, 합격률, 팀·공정·카테고리별 비교, 문제별 정답률, 응답시간을 제공한다.
- AI 난이도와 실제 정답률의 차이를 계산한다.
- 재검토 문제와 재교육 대상을 추천한다.

### 8.7 자료·연동

#### FR-MAT-001 자료 원장

- Google Drive 파일 한 개를 `materials` 한 행으로 관리한다.
- Drive 파일 ID, Hash, 보안 상태, 파싱·색인 상태, 현재 버전을 기록한다.

#### FR-MAT-002 문서 버전

- Drive 변경을 기존 시스템 버전에 자동 덮어쓰지 않는다.
- 변경 파일은 `document_versions`에 새 버전으로 기록한다.

#### FR-MAT-003 파싱·청크·색인

- 슬라이드·페이지는 `material_slides`, 검색·생성 단위는 `document_chunks`로 관리한다.
- 실패 원인과 재시도 상태를 기록한다.

#### FR-MAT-004 충돌

- Drive와 시스템 버전 충돌을 `sync_conflicts`에 기록한다.
- 자동 덮어쓰기를 금지한다.
- 관리자의 해결 선택과 사유를 감사 로그에 남긴다.

### 8.8 사용자·팀·시스템

#### FR-SYS-001 사용자 관리

- 사번, 이름, 팀, 근무형태, 공정, 업무, 활성 상태를 관리한다.
- 삭제 대신 비활성화를 기본으로 사용한다.

#### FR-SYS-002 팀 관리

- 팀 코드는 생성 후 변경하지 않는다.
- 사용 이력이 있는 팀은 삭제 대신 보관한다.

#### FR-SYS-003 시스템 상태

- Backend, Sheets, Drive, AI, 파싱·색인의 실제 상태와 지연시간을 표시한다.
- 하드코딩된 정상 상태를 사용하지 않는다.

#### FR-SYS-004 감사 로그

- 생성, 수정, 승인, 반려, 확정, 배정, 시험 제어, 충돌 해결, 재채점을 기록한다.
- actor, action, target, 변경 전후, 사유, request ID, 시각을 포함한다.

## 9. 관리자 UI와 URL

### 9.1 공통

| 화면 | URL |
|---|---|
| 관리자 기본 진입 | `/admin` |
| 대시보드 | `/admin/dashboard` |

### 9.2 문제 관리

| 화면 | URL |
|---|---|
| 생성 준비 | `/admin/questions/generate/setup` |
| 생성 작업 목록 | `/admin/questions/generate/runs` |
| 생성 결과 | `/admin/questions/generate/runs/:runId` |
| 검수 대기 | `/admin/questions/review` |
| 문제은행 | `/admin/questions/bank` |
| 문제 상세 | `/admin/questions/:questionId` |
| 변경 이력 | `/admin/questions/:questionId/history` |

### 9.3 시험 운영

| 화면 | URL |
|---|---|
| 시험 목록 | `/admin/exams` |
| 시험 생성 | `/admin/exams/create` |
| 시험 상세 | `/admin/exams/:examId` |
| 시험 편집 | `/admin/exams/:examId/edit` |
| 시험 배정 | `/admin/exams/:examId/assign` |
| 전체 시험 상황 | `/admin/exams/live` |
| 시험별 실시간 상세 | `/admin/exams/:examId/live` |
| 운영 이력 | `/admin/exams/history` |

### 9.4 결과·시스템 관리

| 화면 | URL |
|---|---|
| 응시 결과 | `/admin/results` |
| 결과 상세 | `/admin/results/:resultId` |
| 결과 통계·분석 | `/admin/analytics` |
| 응시자 관리 | `/admin/employees` |
| 팀 관리 | `/admin/teams` |
| 자료·연동 | `/admin/materials` |
| 문서 상세 | `/admin/materials/:documentId` |
| 동기화 작업 | `/admin/materials/sync-runs` |
| 충돌 관리 | `/admin/materials/conflicts` |
| 시스템 상태 | `/admin/system/status` |
| 감사 로그 | `/admin/system/audit-logs` |

### 9.5 UI 원칙

- 기존 `BrowserRouter`를 유지한다.
- 메뉴별 URL, 새로고침 복원, 뒤로가기, 직접 링크를 지원한다.
- 목록 필터와 페이지 정보는 query string과 동기화한다.
- 관리자 단일 대형 컴포넌트를 업무 영역별 페이지·컴포넌트로 분리한다.
- 프로토타입의 레이아웃과 디자인은 재사용하되 Mock 데이터 계층은 실제 API 계층으로 교체한다.
- 문제·자료 화면은 고밀도 목록·상세 분할 구조를 사용한다.
- 색상만으로 상태를 전달하지 않는다.
- 이모티콘은 사용하지 않는다.

## 10. API 원칙

- 기존 API는 전환 기간 동안 유지한다.
- 신규 관리자 API는 `/api/admin/*` 하위에 추가한다.
- API는 Sheet 열 위치를 직접 알지 않고 Repository와 서비스 계층을 사용한다.
- 상태 전이와 업무 규칙은 UI가 아니라 서버에서 최종 검증한다.
- 목록 API는 서버 페이지네이션, 정렬, 필터를 지원한다.
- 모든 쓰기 API는 request ID를 기록한다.
- 재시도 가능한 작업은 멱등키를 지원한다.
- 충돌은 `409`, 인증 실패는 `401`, 권한 부족은 `403`, 미존재는 `404`, 만료 세션은 `410`, 외부 연동 실패는 명확한 `5xx`로 구분한다.
- 검증·운영 환경에서는 Sheets 오류를 Local 성공으로 변환하지 않는다.

## 11. 상태 모델

### 11.1 문제

```text
GENERATED → EDITING → REVIEW_REQUESTED → IN_REVIEW → APPROVED → ARCHIVED
                                             └──────→ REJECTED
```

### 11.2 시험

```text
DRAFT → READY_FOR_REVIEW → CONFIRMED → ASSIGNING → SCHEDULED
      → LIVE → CLOSING → CLOSED → ARCHIVED
```

### 11.3 응시

```text
NOT_ENTERED → ENTERED → IN_PROGRESS → SUBMITTING → SUBMITTED
                              ├──────→ TEMPORARILY_DISCONNECTED
                              ├──────→ SUBMISSION_FAILED
                              └──────→ FORCE_CLOSED
```

### 11.4 자료

```text
UPLOADED → SECURITY_REVIEW → APPROVED → PARSING → INDEXING → AVAILABLE
```

상태 전이는 서버에서 허용 목록으로 검증하며 임의의 역전이나 건너뛰기를 허용하지 않는다.

## 12. 오류 처리와 복구

### 12.1 Sheets 오류

- 검증·운영에서는 요청을 실패 처리한다.
- 오류 코드, 대상 Sheet, 작업 ID, 재시도 가능 여부를 기록한다.
- 사용자에게 Local 저장 성공으로 표시하지 않는다.

### 12.2 Dual Write 부분 실패

- 작업 상태를 `PARTIAL_FAILED`로 기록한다.
- 성공한 쪽의 레코드 ID와 실패한 쪽의 오류를 저장한다.
- 동일 멱등키로 실패한 부분만 재시도한다.
- 전체 정합성이 확인된 후 완료 처리한다.

### 12.3 동시 수정

- `row_version`으로 낙관적 잠금을 적용한다.
- 버전이 다르면 최신 데이터를 다시 불러오도록 `409`를 반환한다.
- 관리자 변경을 조용히 덮어쓰지 않는다.

### 12.4 외부 작업

- AI 생성, Drive 동기화, 파싱, 색인, 내보내기는 작업 상태와 오류를 저장한다.
- 부분 완료 데이터를 삭제하지 않는다.
- 재시도 횟수와 최종 실패를 구분한다.

## 13. 보안 요구사항

- 운영 환경에서 기본 개발 JWT Secret 사용을 금지한다.
- `mock_hash` 비밀번호 검증 생략은 로컬 개발 환경에서만 허용한다.
- 관리자 API는 관리자 JWT를 요구한다.
- 응시 API는 JWT의 사용자 신원과 대상 리소스 소유권을 검사한다.
- 보안 미승인 자료는 문제 생성에 사용할 수 없다.
- 보안 Hold 문제는 승인할 수 없다.
- 위험한 운영 제어는 관리자 ID, 사유, 시각을 기록한다.
- 민감 정보와 비밀번호 Hash를 API 응답, 로그, 감사 로그에 노출하지 않는다.

## 14. Feature Flag

초기값은 다음과 같다.

```env
OJT_SHEETS_SCHEMA_MODE=legacy
OJT_STRICT_SHEETS_STORAGE=true

OJT_USE_NORMALIZED_MATERIALS=false
OJT_USE_KNOWLEDGE_UNITS=false
OJT_USE_CANDIDATE_TAB=false
OJT_USE_GATE_RESULTS_TAB=false
OJT_USE_FROZEN_EXAM=false
OJT_USE_ASSIGNMENTS_TAB=false
OJT_USE_RESULT_ANSWERS=false
```

- 검증·운영에서 Strict 저장을 기본으로 한다.
- 로컬 개발에서만 명시적으로 fallback을 허용할 수 있다.
- Flag 전환과 Rollback은 감사 가능한 배포 설정 변경으로 관리한다.

## 15. 마이그레이션 단계

### Phase 0 — 기준 확정과 백업

- 실제 55개 Sheet Header를 기준으로 데이터 사전과 범위 문서를 정정한다.
- 운영 Sheet 전체 복사본, Excel 백업, Git Commit Hash, Header Hash를 기록한다.
- 모든 마이그레이션은 복사본만 대상으로 한다.

### Phase 1 — 기존 오류와 보안 수정

- Snapshot B/C 혼재 호환 Reader
- `exam_id` 백필 열 오류 수정
- 문제 이관 중복 방지 및 Dry-run
- JWT 신원 강제
- 검증·운영 Silent Local fallback 차단
- 승인 문제 시험 사용 강제

### Phase 2 — Schema 생성

- 기존 열 오른쪽에 확장 Header 추가
- 신규 Sheet Header 생성
- 모든 신규 Flag `OFF`
- 기존 기능 전체 회귀 테스트

### Phase 3 — 자료·문제 Dual Write

- `material_cache`와 신규 자료 구조 병행
- 기존 Candidate 구조와 `question_candidates`, `gate_results` 병행
- 승인·반려·이력 검증

### Phase 4 — 시험·배정 Dual Write

- `question_ids`와 `exam_versions`, `exam_set_items` 병행
- `assigned_users`와 `assignments` 병행
- 확정 시험 불변성 및 배정 정합성 검증

### Phase 5 — 결과 Dual Write

- `results.results` JSON과 `result_answers` 병행
- 무응답, 중복 제출, 부분 실패 검증

### Phase 6 — 관리자 UI 전환

- `/admin/*` 라우팅과 Admin App Shell
- 대시보드
- 문제 생성·검수·문제은행
- 시험 목록·생성·배정·상황
- 결과·분석
- 자료·연동
- 시스템 상태·감사 로그

### Phase 7 — V2 Read Canary

- 관리자 테스트 계정 또는 지정 팀부터 V2 Reader를 사용한다.
- Legacy와 V2 조회 결과를 비교한다.
- 차이가 없을 때 적용 범위를 확대한다.

### Phase 8 — 운영 전환

- 복사본 검증 결과와 승인 기록을 확인한다.
- 운영본 백업 후 동일 마이그레이션을 Dry-run한다.
- 승인된 변경만 운영본에 적용한다.
- Legacy 열과 Sheet는 안정화 전 삭제하지 않는다.

## 16. 테스트 및 인수 기준

### 16.1 Schema 검증

- 55개 Sheet의 이름과 Header Hash가 기준과 일치한다.
- 기존 8개 Sheet의 기존 열 순서가 변하지 않는다.
- PK 중복과 필수 참조 누락이 없다.
- Schema 추가 전후 기존 데이터 행 수와 핵심 집계가 일치한다.

### 16.2 기존 기능 회귀

- 관리자와 응시자 로그인이 동작한다.
- 기존 승인 문제 조회와 시험 생성이 동작한다.
- 기존 사용자 배정과 시험 응시가 동작한다.
- Snapshot 기반 채점과 결과 조회가 동작한다.
- 팀·사용자·교육자료 기존 기능이 동작한다.

### 16.3 핵심 무결성

- 승인되지 않은 문제로 시험을 생성할 수 없다.
- 확정 시험은 문제은행 변경의 영향을 받지 않는다.
- 다른 사용자 ID로 시험을 생성·제출·조회할 수 없다.
- 동일 제출을 반복해도 결과가 한 번만 기록된다.
- 무응답 문항이 문제별 결과에 `null`, 0점으로 기록된다.
- Sheets 오류 시 운영 API가 성공을 반환하지 않는다.

### 16.4 Dual Write 정합성

- Legacy와 V2의 문제, 시험, 배정, 결과 핵심 값이 일치한다.
- 부분 실패 작업을 재시도해 중복 없이 완료할 수 있다.
- Flag를 `legacy`로 내리면 기존 기능으로 복귀한다.

### 16.5 관리자 UI

- 모든 메뉴를 URL로 직접 열 수 있다.
- 새로고침과 뒤로가기 후 작업 위치가 유지된다.
- 필터가 URL query string과 동기화된다.
- API 오류, 빈 상태, 로딩, 권한 부족을 명확히 표시한다.
- 고밀도 표와 상세 패널에서 저장되지 않은 변경을 경고한다.

### 16.6 운영 승인 조건

운영 적용은 다음 조건을 모두 충족해야 한다.

- 복사본 마이그레이션 성공
- Header·PK·관계 검증 성공
- 기존 기능 회귀 테스트 성공
- P0 보안·무결성 테스트 성공
- Dual Write 대조 성공
- Rollback 절차 검증
- 운영 적용 승인 기록

## 17. 우선순위

### P0 — 무결성·보안

- Snapshot 호환 Reader
- 마이그레이션 열·중복 오류 수정
- JWT 신원 강제
- Strict Sheets 저장
- 승인 문제 시험 사용 강제
- 시험 버전 동결
- 제출 멱등성·무응답 저장
- 감사 로그

### P1 — 관리자 운영

- `/admin/*` 라우팅과 화면 모듈화
- 행동 중심 대시보드
- 문제 생성 작업·검수·문제은행
- 시험 목록·생성·배정·상황
- 문서 버전·파싱·색인·충돌
- 실제 시스템 상태

### P2 — 고급 기능

- 고급 결과 분석
- 재교육·재시험 관리
- 비동기 Excel·CSV 내보내기
- 생성 프리셋
- SSE 또는 WebSocket
- 자동 문제 재검토 추천

## 18. 금지사항

```text
운영 Sheet 직접 선변경
기존 탭 이름 변경
기존 열 삭제·이동·중간 삽입
백업 없는 Migration
Dry-run 없는 Migration
question_bank_v2 또는 별도 문제 원장 생성
별도 관리자 로그인 시스템 생성
Sheets 오류를 Local 저장 성공으로 처리
승인 전 문제로 시험 생성
확정 시험 문항 수정
무응답 결과 누락
Drive 충돌 자동 덮어쓰기
감사 로그 없는 위험 작업
```

## 19. 최종 성공 정의

다음 상태를 모두 만족하면 관리자 고도화가 완료된 것으로 판단한다.

- 기존 사원 UI와 핵심 응시 흐름이 유지된다.
- 관리자 UI가 `/admin/*` 업무 구조로 동작한다.
- 실제 55개 Sheet 스키마와 코드가 일치한다.
- 승인 전 문제는 시험에 사용되지 않는다.
- 확정 시험은 불변 버전과 문항 Snapshot을 가진다.
- 사용자별 배정·시도·답안·결과가 추적 가능하다.
- Sheets 실패가 성공으로 은폐되지 않는다.
- 모든 주요 관리자 작업과 운영 오류를 감사할 수 있다.
- Feature Flag로 단계적 전환과 Rollback이 가능하다.
