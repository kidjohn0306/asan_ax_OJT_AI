<!-- 1차 MVP 백엔드 구조 설계 정본. AI문제생성_상세설계_통합마스터.md의 §14.1(1차 MVP 필수)을 백엔드 아키텍처로 구체화한 문서 -->

# 백엔드 구조 — 1차 MVP 설계 (정본)

| 항목 | 내용 |
|---|---|
| 문서 목적 | [통합 마스터 설계](AI문제생성_상세설계_통합마스터.md) §14.1 **1차 MVP 필수 9개**를 실제 백엔드 구조로 확정 |
| 핵심 원칙 | **저장소를 추상화한다.** 지금은 `mock_data/*.json`, 나중엔 Google Drive — 서비스 코드는 안 바뀐다 |
| 적용 범위 | 1차 MVP만. 기준문항(anchor)·자동화 지표·일반상식 외부출처는 2차(범위 밖) |
| 코딩 여부 | **본 문서는 설계만.** 코드는 이 구조 승인 후 별도 진행 |

---

## 0. 한 장 요약

```
지금의 문제                        →   이 설계의 해법
─────────────────────────────────────────────────────────
인메모리 dict 3개가 콜드스타트에 소멸  →   전부 Repository로 영속화
results.json 파일쓰기 → Vercel 불가   →   JSONL append (서버리스 안전)
저장 위치가 서비스에 하드코딩          →   Repository 인터페이스로 분리
모든 문제가 무조건 출제됨              →   status=approved 필터
출제 후 정답 수정 시 과거 채점 틀어짐   →   스냅샷(보기 순서맵 포함)
```

**단 하나의 핵심 결정**: 서비스와 파일 입출력(I/O) 사이에 **Repository 계층**을 끼운다. 이 계층 하나가 들어가면 위 6개 문제가 동시에 풀리고, `mock_data → Drive → DB` 전환이 서비스 수정 없이 가능해진다.

---

## 1. 계층 구조 (Layered Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│  api/  (라우터 — 얇게 유지)                                   │
│  auth.py · exam.py · admin.py · drive.py                     │
│  · HTTP 요청/응답, Pydantic 검증, 권한 체크만                 │
└───────────────────────────┬─────────────────────────────────┘
                            │ 함수 호출
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  services/  (도메인 로직 — "저장 위치를 모른다")              │
│  auth_service · exam_service · admin_service                 │
│  generation/ (gates.py 규칙게이트 · generator.py 생성)        │
└───────────────────────────┬─────────────────────────────────┘
                            │ Repository 인터페이스만 의존
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  repositories/  ◄══════════ ★신규 핵심 계층★                 │
│  base.py     (인터페이스 정의)                                │
│  local_json.py  (현재: mock_data/*.json)                     │
│  drive_repo.py  (나중: Google Drive)                         │
└───────────────────────────┬─────────────────────────────────┘
                            │ 환경변수 STORAGE_BACKEND 로 스위치
            ┌───────────────┴───────────────┐
            ▼                               ▼
   ┌─────────────────┐            ┌─────────────────────┐
   │  mock_data/     │            │  Google Drive       │
   │  *.json (지금)  │            │  /OJT_Root/ (나중)   │
   └─────────────────┘            └─────────────────────┘
```

**규칙**: 화살표는 위→아래 단방향. 서비스는 `repo.get_approved_questions()`만 부르고, 그게 로컬 파일인지 Drive인지 모른다.

---

## 2. 저장소 추상화 — 이 설계의 심장

### 2.1 왜 필요한가 (현재 코드의 결함)

현재 모든 서비스가 저장 위치를 직접 알고 있다:

```python
# 지금 (services 전체에 흩어져 있음)
with open(MOCK_DIR / "questions.json") as f: ...   # exam_service
with open(MOCK_DIR / "users.json") as f: ...       # auth_service, admin_service
_exam_sessions: dict = {}                           # 인메모리 → 콜드스타트 소멸
_difficulty_overrides: dict = {}                    # 인메모리 → 콜드스타트 소멸
```

→ Drive로 바꾸려면 **모든 서비스 함수를 수정**해야 한다. 이게 전환을 막는 벽.

### 2.2 해법 — Repository 인터페이스

서비스는 아래 "약속(인터페이스)"만 본다. 실제 구현(로컬/Drive)은 갈아끼운다.

```
QuestionRepository (인터페이스)
  ├─ get_approved_questions(team, category) → list   # status=approved만
  ├─ get_question(question_id)              → dict
  ├─ update_question(question_id, fields)   → None    # 상태·난이도·내용 수정
  └─ list_by_status(status)                 → list    # 검토 큐

ResultRepository (인터페이스)
  ├─ append_result(result_record)           → None    # JSONL append
  └─ get_result(exam_id)                    → dict

SnapshotRepository (인터페이스)
  ├─ save_snapshot(exam_id, snapshots)      → None    # 출제 시점 고정
  └─ get_snapshot(exam_id)                  → list

FeedbackRepository (인터페이스)
  └─ append_feedback(feedback_record)       → None    # 난이도 수정 이력 JSONL

UserRepository (인터페이스)
  ├─ get_user(employee_id)                  → dict
  ├─ list_approved_users()                  → list
  ├─ add_user(user) / delete_user(id)       → None
```

### 2.3 구현 2종 + 스위치

```
환경변수 STORAGE_BACKEND 값에 따라 결정:

  STORAGE_BACKEND=local  →  LocalJsonRepository   (지금, 기본값)
  STORAGE_BACKEND=drive  →  DriveRepository       (나중)
```

```
services/__init__.py 또는 의존성 주입 지점에서:

  backend = os.getenv("STORAGE_BACKEND", "local")
  question_repo = LocalJsonRepo() if backend == "local" else DriveRepo()
```

→ **서비스 코드는 한 줄도 안 바뀐다.** 이게 §11 "Drive MVP → DB 전환 가능"의 코드 레벨 실현.

---

## 3. 저장소별 형식 — JSON vs JSONL

설계 §3.3·§11.3 그대로. **갱신형은 JSON, 누적형은 JSONL**.

| 저장소 | 형식 | 이유 | 지금 위치 | 나중 위치 (Drive) |
|---|---|---|---|---|
| 사용자 | JSON | 갱신형(승인/삭제) | `mock_data/users.json` | `00_Admin/users.json` |
| 문제은행 | JSON | 갱신형(상태·난이도) | `mock_data/questions.json` | `02_Question_Bank/*.json` |
| 시험 결과 | **JSONL** | 누적형·서버리스 안전 | `mock_data/results.jsonl` | `06_Exam_Results/raw_results.jsonl` |
| 시험 스냅샷 | **JSONL** | 불변 기록 | `mock_data/snapshots.jsonl` | `05_Exam_Papers/snapshots.jsonl` |
| 난이도 피드백 | **JSONL** | 이력 원본 | `mock_data/difficulty_feedback.jsonl` | `04_Feedback/*.jsonl` |
| 검증 리포트 | **JSONL** | 누적 로그 | `mock_data/validation_reports.jsonl` | `03_Validation/*.jsonl` |

> **왜 JSONL인가**: `results.json`에 매번 전체를 `open("w")` 덮어쓰면 ① Vercel 읽기전용 FS에서 실패 ② 동시 쓰기 충돌. JSONL은 한 줄씩 **append-only**라 두 문제 모두 없다.

---

## 4. 데이터 모델 — 기존 필드 유지 + 추가 (설계 §3·D1·F1)

### 4.1 문제 레코드 — 기존을 깨지 않는다

현재 `questions.json` 한 줄:
```json
{"question_id":"C-001","category":"공통","question":"...","option_a":"...","option_b":"...",
 "option_c":"...","option_d":"...","answer":"A","difficulty_init":"하","difficulty_ai":"하","admin_override":""}
```

여기에 **MVP 필수 필드만** 얹는다 (한글·기존 필드명 유지):

```jsonc
{
  // ── 기존 (그대로 유지) ──
  "question_id": "C-001", "category": "공통", "question": "...",
  "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
  "answer": "A", "difficulty_init": "하", "difficulty_ai": "하",
  "admin_override": "",          // 있으면 이게 출제 난이도 (기존 필드 재사용)

  // ── 1차 MVP 추가 ──
  "status": "approved",          // draft|reviewing|approved|rejected (출제는 approved만)
  "explanation": "",             // 해설
  "version": 1,                  // 수정 시 +1 (스냅샷 정합)
  "flags": { "warning": false, "security_hold": false, "needs_edit": false }
}
```

> 2차 필드(`is_anchor`, `scope`, `source`, `difficulty_confidence` 등)는 지금 넣지 않는다. 필요해질 때 또 얹으면 된다.

### 4.2 출제 난이도 결정 규칙 (설계 §3.2)

```text
출제 난이도 = admin_override (있으면)
            → 없으면 difficulty_ai
            → 없으면 difficulty_init

출제 대상 = status == "approved" 인 문제만
```

기존 `exam_service._pick_by_difficulty`가 이미 `difficulty_ai or difficulty_init`을 본다.
→ **`admin_override` 우선**과 **`status==approved` 필터** 두 줄만 추가하면 된다.

---

## 5. 상태 머신 (설계 §6 — 핵심 5상태 중 MVP 4개)

```
   [AI/관리자 생성]
         │
         ▼
   ┌─────────┐  규칙게이트 통과   ┌───────────┐  승인   ┌──────────┐
   │  draft  │ ────────────────▶ │ reviewing │ ──────▶ │ approved │ ──▶ 출제 가능
   └─────────┘                   └───────────┘         └──────────┘
        ▲                              │ 반려
        │ 게이트 실패                   ▼
        └──────────              ┌──────────┐
                                 │ rejected │
                                 └──────────┘
```

| 상태 | 의미 | 출제 |
|---|---|---|
| `draft` | 생성 직후 / 게이트 실패 | ✕ |
| `reviewing` | 게이트 통과, 관리자 검토 대기 | ✕ |
| `approved` | 관리자 승인 완료 | **○ (이것만)** |
| `rejected` | 반려됨 | ✕ |

> `archived`(보관)는 2차. 플래그(`warning` 등)는 출제 가능여부엔 영향 없고 검토 보조용.

---

## 6. 핵심 흐름 — 시험 응시 (스냅샷 중심)

설계 §10(F3): **출제 후 문제가 바뀌어도 과거 결과는 당시 기준으로 보존**.

```
[응시자]                [exam_service]              [Repository]
   │                         │                          │
   │  POST /exam/generate    │                          │
   ├────────────────────────▶│                          │
   │                         │ get_approved_questions() │
   │                         ├─────────────────────────▶│  status=approved만
   │                         │◀─────────────────────────┤  25문항 선별
   │                         │                          │
   │                         │ ★ 스냅샷 생성 ★           │
   │                         │  (문제 내용 + answer +    │
   │                         │   보기 순서맵 고정)        │
   │                         │ save_snapshot(exam_id) ──▶│  snapshots.jsonl
   │◀────────────────────────┤  문제만 반환(정답 제외)   │
   │                         │                          │
   │  POST /exam/submit      │                          │
   ├────────────────────────▶│                          │
   │  (answers, times)       │ get_snapshot(exam_id) ───▶│  ★스냅샷으로 채점★
   │                         │◀─────────────────────────┤  (라이브 문제 아님!)
   │                         │ 채점 → 점수               │
   │                         │ append_result() ────────▶│  results.jsonl
   │◀────────────────────────┤  점수·합불 반환           │
```

**스냅샷 한 건 구조** (보기 순서맵 필수 — 이게 빠지면 채점 틀어짐):

```json
{
  "exam_id": "exam_uuid", "question_id": "C-001", "question_version": 1,
  "snapshot": { "question": "...", "answer": "A", "difficulty": "하",
                "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "..." },
  "presentation": {
    "question_order": 7,
    "option_order_map": { "A": "C", "B": "A", "C": "D", "D": "B" }
  }
}
```

> 현재 인메모리 `_exam_sessions` dict가 하던 일을 **SnapshotRepository로 영속화**. 콜드스타트 버그(F7)가 여기서 해소됨.

---

## 7. 핵심 흐름 — 관리자 문제 검토/승인

```
[관리자]                [admin_service]             [Repository]
   │                         │                          │
   │ GET /questions          │                          │
   │   ?status=reviewing     │ list_by_status()  ──────▶│  검토 큐 조회
   │◀────────────────────────┤◀─────────────────────────┤
   │                         │                          │
   │ PATCH /difficulty       │  ★난이도 비교 기준 수정★  │
   │  (id, "중")             │  difficulty_ai vs 관리자값│  ← 현재 결함 수정
   │                         │  update_question() ─────▶│  admin_override="중"
   │                         │  append_feedback() ─────▶│  difficulty_feedback.jsonl
   │                         │                          │
   │ POST /approve           │  update_question() ─────▶│  status="approved"
   │◀────────────────────────┤                          │
```

> **현재 결함 수정 포인트**: `admin_service.override_difficulty`가 지금은 "직전 관리자값 vs 새 관리자값"을 비교(무의미). 설계대로 **`difficulty_ai`(AI 판정) vs 관리자 확정값**으로 고친다(§7.1·§14.4).

---

## 8. 규칙 게이트 (설계 §5.2 — 7개, LLM 불필요)

생성된 문제를 검토 큐(`reviewing`)에 넣기 전 **순수 규칙**으로 1차 거른다. LLM 호출 없음 → 싸고 빠르고 테스트 쉬움.

| 코드 | 검증 | 실패 시 |
|---|---|---|
| V-01 | JSON 필수필드·타입 | FAILED → draft 유지 |
| V-02 | 보기 구조 (객관식 4개, 빈 보기·중복 없음) | FAILED |
| V-03 | 정답 단일성 (`answer`가 A~D 범위 내) | FAILED |
| V-04 | 근거 존재 (내부자료 문제는 출처) | FAILED |
| V-05 | 난이도 값 (상/중/하 중 하나) | FAILED |
| V-06 | 카테고리·팀 일치 | WARNING (flags만) |
| V-07 | 보안 키워드 필터 | SECURITY_HOLD (flags만) |

```
생성 → [게이트 7개] → PASS → reviewing (관리자 검토)
                   → FAILED → draft 유지 (재생성 대상)
```

> `services/generation/gates.py`에 순수 함수로. 입력 dict → 검증 결과 dict. 외부 의존 0.

---

## 9. 디렉토리 구조 (목표)

```
backend/
├── main.py                  # FastAPI 앱 (변경 거의 없음)
├── api/                     # 라우터 (얇게)
│   ├── auth.py  exam.py  admin.py  drive.py
│
├── services/                # 도메인 로직 (저장 위치 모름)
│   ├── auth_service.py
│   ├── exam_service.py      # ← 스냅샷·approved 필터 추가
│   ├── admin_service.py     # ← 난이도 비교 기준 수정
│   ├── difficulty.py
│   └── generation/          # ★신규 (AI 생성 파트)
│       ├── gates.py         #   규칙 게이트 7개 (순수 함수)
│       └── generator.py     #   Claude API 호출 (mock/real 토글)
│
├── repositories/            # ★신규 핵심 계층★
│   ├── base.py              #   인터페이스 (Question/Result/Snapshot/Feedback/User)
│   ├── local_json.py        #   현재: mock_data/*.json + *.jsonl
│   └── drive_repo.py        #   나중: Google Drive
│
├── mock_data/               # 로컬 저장 (STORAGE_BACKEND=local)
│   ├── users.json
│   ├── questions.json       # ← status/version/explanation/flags 필드 추가
│   ├── results.jsonl        # ← .json 에서 .jsonl 로
│   ├── snapshots.jsonl      # ← 신규
│   └── difficulty_feedback.jsonl  # ← 신규
│
└── credentials/
    └── service_account.json
```

---

## 10. 지금(mock_data) → 나중(Drive) 전환 그림

```
                  STORAGE_BACKEND=local                 STORAGE_BACKEND=drive
                  ┌──────────────────┐                 ┌──────────────────────┐
   services  ───▶ │ LocalJsonRepo    │      또는    ───▶│ DriveRepo            │
   (안 바뀜)      │                  │                 │                      │
                  │ mock_data/       │                 │ /OJT_Root/           │
                  │  users.json      │                 │  00_Admin/users.json │
                  │  questions.json  │   ══전환══▶      │  02_Question_Bank/   │
                  │  results.jsonl   │                 │  06_Exam_Results/    │
                  │  snapshots.jsonl │                 │  05_Exam_Papers/     │
                  └──────────────────┘                 └──────────────────────┘
                       로컬 개발                            Vercel 운영
```

**전환 시 작업**: `DriveRepo` 클래스 하나 구현 + 환경변수 1개 변경. 서비스·라우터·프론트엔드 **무수정**.

> Drive 인증은 이미 `drive_service.py`에 **환경변수→파일 폴백**으로 구현되어 있어 그대로 재사용한다.

---

## 11. 1차 MVP 필수 9개 → 본 설계 매핑 (설계 §14.1)

| # | MVP 필수 항목 | 본 설계 위치 | 현재 대비 |
|---|---|---|---|
| 1 | Drive 파일목록/문제은행 읽기 | §2 QuestionRepository | 인터페이스화 |
| 2 | AI/mock 문제 생성(draft) | §9 `generation/generator.py` | 신규 |
| 3 | 규칙 게이트 7개 | §8 `generation/gates.py` | 신규 |
| 4 | 관리자 검토(수정·승인·반려) | §7 상태전이 + admin_service | 상태머신 추가 |
| 5 | 난이도 수정 + 사유 저장 | §7 FeedbackRepository(JSONL) | 결함 수정 + 영속화 |
| 6 | 승인 문제은행(approved) | §5 상태 머신 | status 필드 신규 |
| 7 | 승인 문제만 시험지 생성 | §4.2 출제 규칙 | approved 필터 추가 |
| 8 | 시험지 스냅샷(순서맵) | §6 SnapshotRepository | 신규 |
| 9 | 응시·자동채점·결과 저장 | §6 ResultRepository(JSONL) | 인메모리→영속화 |

---

## 12. 구현 순서 권장 (작은 것 → 큰 것)

```
1. 데이터 모델 확장      questions.json에 status/version/explanation/flags 추가
                        (기존 동작 안 깨짐, 가장 안전)
2. Repository 계층 도입   기존 파일 I/O를 LocalJsonRepo로 래핑 (동작 동일, 구조만 분리)
3. 난이도 비교 결함 수정   difficulty_ai 기준으로 (§7)
4. 인메모리 3종 영속화     _exam_sessions·_difficulty_overrides → Repository
                        (콜드스타트 버그 해소)
5. 규칙 게이트 7개         gates.py (순수 함수, 테스트 쉬움)
6. 스냅샷 + 순서맵         채점을 스냅샷 기준으로 전환
7. results.json→jsonl     ResultRepository append 방식
8. DriveRepo 구현          STORAGE_BACKEND=drive 스위치
9. AI 생성(generator)      Claude API (비용·외부의존, 마지막)
```

> 1~4번은 **기존 기능을 안 깨면서 구조만 정비**하는 단계라 가장 먼저, 가장 안전하게 할 수 있다.

---

## 13. 비범위 (1차 MVP에서 안 함 — 설계 §14.2/14.3)

```
✕ 기준문항(anchor) pool 관리        → 2차 (cold-start 때문)
✕ calibration few-shot 선별 UI      → 2차
✕ 자동 승인·자동 출제               → 영구 제외
✕ 일반상식 외부 출처 fetch          → 2차 (보안 경계)
✕ 실측 난이도 IRT/통계              → 제외 (데이터 기근)
✕ 서술형 자동채점                   → 제외
✕ DB 전환                          → 구조만 준비, 실제 전환은 나중
```

---

## 부록. 핵심 5줄

1. **Repository 계층 하나**가 이 설계의 심장 — 인메모리 소실·Vercel 쓰기·Drive 전환이 한 번에 풀린다.
2. 갱신형은 JSON, 누적형은 **JSONL append** (서버리스 안전).
3. 문제에 `status` 추가 → **approved만 출제**.
4. 채점은 라이브 문제가 아니라 **스냅샷(보기 순서맵 포함)** 기준.
5. 지금은 `mock_data`, 나중은 Drive — **환경변수 한 개**로 전환, 서비스는 무수정.
