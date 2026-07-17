# OJT 관리자 고도화 구현 로드맵

**기준 문서:** `docs/frd.md`

## 분할 원칙

FRD는 저장소 호환성, 문제 관리, 시험·결과, 자료·연동, 관리자 UI라는 독립 하위 시스템을 포함한다. 각 단계는 단독으로 테스트·배포·롤백할 수 있어야 하므로 다음 여섯 개 구현 계획으로 분리한다.

| 순서 | 구현 계획 | 독립 산출물 | 다음 단계 진입 조건 |
|---|---|---|---|
| 1 | P0 호환성·보안 기반 | Strict Sheets, Snapshot 혼합 Reader, 안전한 Migration, JWT 신원, 승인 문제 Guard | 기존 전체 테스트와 신규 P0 테스트 통과 |
| 2 | 55-Sheet Schema·Migration Guard | 실제 Header 기준 Schema Catalog, Header Hash, Dry-run 생성·검증 | 복사본에서 기존 기능 회귀 통과 |
| 3 | 문제 생성·검수 Dual Write | generation_jobs, candidates, gate_results, reviews, history | Legacy/V2 문제 데이터 대조 통과 |
| 4 | 시험 버전·배정·결과 Dual Write | exam_versions, items, assignments, attempts, result_answers | 불변성·멱등 제출·무응답 테스트 통과 |
| 5 | 자료·대시보드·운영 데이터 | materials, versions, chunks, sync, alerts, tasks, audit | Drive 충돌·실패 복구 테스트 통과 |
| 6 | `/admin/*` React UI·Canary | URL 기반 관리자 UI, API 연결, 폴링, Rollback | E2E·접근성·Canary 대조 통과 |

## 공통 배포 흐름

각 계획은 다음 순서를 따른다.

```text
실패 테스트 작성
→ 최소 구현
→ 단위·통합 테스트
→ 복사본 Dry-run
→ Legacy 회귀 테스트
→ Feature Flag OFF 배포
→ Canary 활성화
→ Legacy/V2 대조
→ 범위 확대 또는 Flag Rollback
```

## 현재 실행 대상

첫 실행 대상은 `2026-07-15-phase-1-compatibility-security.md`다. 이 단계에서는 55개 Sheet를 생성하거나 관리자 UI를 변경하지 않는다.
