"""
규칙 게이트 7개 (V-01 ~ V-07) — 순수 함수, 외부 의존 없음
생성된 문제 dict를 입력받아 검증 결과 dict를 반환한다.

`run_gates()`는 기존 호출자(admin_service.generate_ai_questions legacy 경로)와의 호환을 위해
원래 동작 그대로 유지한다. 강화된 판정은 `run_deterministic_gates()`가 V01·V04·V05·V06·V07을 담당하고,
`services.generation.gate_service.evaluate_candidate()`가 의미 검증(V02·V03) 결과와 합쳐
최종 Gate 결과(overall_status, gate_version, question_fingerprint 포함)를 조립한다.
"""
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher

REQUIRED_FIELDS = ["question_id", "category", "question",
                   "option_a", "option_b", "option_c", "option_d", "answer"]
VALID_DIFFICULTIES = {"상", "중", "하"}
VALID_ANSWERS = {"A", "B", "C", "D"}
VALID_CATEGORIES = {"공통", "팀별", "환경안전", "일반상식"}
SECURITY_KEYWORDS = ["비밀번호", "개인정보", "급여", "인사기록", "보안코드", "서버접속", "관리자계정"]


def _v01_required_fields(q: dict) -> tuple[bool, str]:
    for field in REQUIRED_FIELDS:
        if field not in q or q[field] is None or q[field] == "":
            return False, f"V-01: 필수 필드 누락 — {field}"
    return True, ""


def _v02_option_structure(q: dict) -> tuple[bool, str]:
    opts = [q.get("option_a",""), q.get("option_b",""), q.get("option_c",""), q.get("option_d","")]
    if any(o == "" for o in opts):
        return False, "V-02: 빈 보기 존재"
    if len(set(opts)) < 4:
        return False, "V-02: 중복 보기 존재"
    return True, ""


def _v03_answer_single(q: dict) -> tuple[bool, str]:
    ans = str(q.get("answer", "")).strip().upper()
    if ans not in VALID_ANSWERS:
        return False, f"V-03: 정답값 범위 초과 — {ans!r} (A~D만 허용)"
    return True, ""


def _v04_source_exists(q: dict) -> tuple[bool, str]:
    if q.get("category") in ("공통", "팀별", "환경안전"):
        if not q.get("explanation", "").strip():
            return False, "V-04: 내부자료 기반 문제에 해설(근거) 없음"
    return True, ""


def _v05_difficulty_value(q: dict) -> tuple[bool, str]:
    d = q.get("difficulty_init") or q.get("difficulty_ai", "")
    if d not in VALID_DIFFICULTIES:
        return False, f"V-05: 난이도 값 오류 — {d!r} (상/중/하만 허용)"
    return True, ""


def _v06_category_team_match(q: dict) -> tuple[bool, str]:
    cat = q.get("category", "")
    if cat not in VALID_CATEGORIES:
        return False, f"V-06: 카테고리 불일치 — {cat!r}"
    return True, ""


def _v07_security_keywords(q: dict) -> tuple[bool, str]:
    text = " ".join([
        q.get("question", ""),
        q.get("option_a", ""), q.get("option_b", ""),
        q.get("option_c", ""), q.get("option_d", ""),
        q.get("explanation", ""),
    ])
    for kw in SECURITY_KEYWORDS:
        if kw in text:
            return False, f"V-07: 보안 키워드 감지 — {kw!r}"
    return True, ""


def run_gates(q: dict) -> dict:
    """
    반환값:
      {
        "pass": bool,          # True = reviewing으로 진행 가능
        "failed": [str],       # FAILED 게이트 메시지 (pass=False 원인)
        "flags": {
          "warning": bool,     # V-06 실패
          "security_hold": bool  # V-07 실패
        }
      }
    """
    failed = []
    flags = {"warning": False, "security_hold": False}

    # V-01 ~ V-05: FAILED → draft 유지
    for fn in [_v01_required_fields, _v02_option_structure,
               _v03_answer_single, _v04_source_exists, _v05_difficulty_value]:
        ok, msg = fn(q)
        if not ok:
            failed.append(msg)

    # V-06: WARNING 플래그만
    ok, _ = _v06_category_team_match(q)
    if not ok:
        flags["warning"] = True

    # V-07: SECURITY_HOLD 플래그만
    ok, _ = _v07_security_keywords(q)
    if not ok:
        flags["security_hold"] = True

    return {
        "pass": len(failed) == 0,
        "failed": failed,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# 강화된 7-Gate 상태 모델 (mcq-7gate-v1)
# ---------------------------------------------------------------------------

GATE_STATUSES = {"PASS", "WARNING", "REVIEW_REQUIRED", "HARD_FAIL"}
STATUS_PRIORITY = {"PASS": 0, "WARNING": 1, "REVIEW_REQUIRED": 2, "HARD_FAIL": 3}

QUESTION_TYPE_MCQ_SINGLE = "MULTIPLE_CHOICE_SINGLE"

FINGERPRINT_FIELDS = [
    "question_type", "question_id", "category", "question",
    "option_a", "option_b", "option_c", "option_d",
    "answer", "explanation", "difficulty_init", "difficulty_ai", "admin_override",
]


def gate_result(status: str, code: str, reason: str, details: dict | None = None) -> dict:
    if status not in GATE_STATUSES:
        raise ValueError(f"지원하지 않는 Gate 상태: {status}")
    return {
        "status": status,
        "code": code,
        "reason": reason,
        "details": details or {},
    }


def overall_status(statuses) -> str:
    """여러 Gate 상태 중 가장 심각한 상태를 반환한다. 빈 목록은 PASS로 취급한다."""
    if not statuses:
        return "PASS"
    return max(statuses, key=lambda s: STATUS_PRIORITY[s])


def normalize_text(text: str) -> str:
    """NFKC 정규화 + trim. 보기 중복 비교 등 표시값 그대로의 비교에 사용."""
    return unicodedata.normalize("NFKC", (text or "").strip())


def _normalize_for_dedup(text: str) -> str:
    """NFKC 정규화 후 공백·문장부호를 제거한다. 중복·유사도 비교 전용."""
    normalized = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"[\s\W_]+", "", normalized, flags=re.UNICODE)


def question_fingerprint(question: dict) -> str:
    """Gate 실행 시점의 문제 내용을 나타내는 안정적인 지문. 이후 문제 수정 여부를 감지하는 데 사용한다."""
    payload = {key: question.get(key, "") for key in FINGERPRINT_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --- V01 Schema --------------------------------------------------------------

_SCHEMA_STRING_FIELDS = [
    "question_id", "category", "question",
    "option_a", "option_b", "option_c", "option_d",
    "answer", "explanation",
]
_SCHEMA_NON_EMPTY_FIELDS = [
    "question_id", "category", "question",
    "option_a", "option_b", "option_c", "option_d", "answer",
]


def _schema_gate(q: dict) -> dict:
    question_type = q.get("question_type") or QUESTION_TYPE_MCQ_SINGLE
    if question_type != QUESTION_TYPE_MCQ_SINGLE:
        return gate_result(
            "HARD_FAIL", "V01_UNSUPPORTED_QUESTION_TYPE",
            f"지원하지 않는 문제 유형입니다 — {question_type!r}",
            {"question_type": question_type},
        )

    for field in _SCHEMA_STRING_FIELDS:
        value = q.get(field)
        if value is None:
            return gate_result("HARD_FAIL", "V01_FIELD_MISSING",
                                f"필수 필드 누락 — {field}", {"field": field})
        if not isinstance(value, str):
            return gate_result("HARD_FAIL", "V01_FIELD_TYPE_INVALID",
                                f"필드 타입이 문자열이 아닙니다 — {field}", {"field": field})

    for field in _SCHEMA_NON_EMPTY_FIELDS:
        if not q[field].strip():
            return gate_result("HARD_FAIL", "V01_FIELD_EMPTY",
                                f"필드 값이 비어 있습니다 — {field}", {"field": field})

    options = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
    normalized_options = [normalize_text(o) for o in options]
    if len(set(normalized_options)) < 4:
        return gate_result("HARD_FAIL", "V01_DUPLICATE_OPTIONS",
                            "정규화 후 중복된 보기가 있습니다.", {})

    answer = q["answer"].strip().upper()
    if answer not in VALID_ANSWERS:
        return gate_result("HARD_FAIL", "V01_ANSWER_OUT_OF_RANGE",
                            f"정답값 범위 초과 — {answer!r} (A~D만 허용)", {"answer": answer})

    return gate_result("PASS", "V01_OK", "객관식 단일정답 Schema가 유효합니다.", {})


# --- V03 Single Answer (결정론적 부분: 보기 간 중복 가능성) -------------------------

_OPTION_SIMILARITY_REVIEW_THRESHOLD = 0.92


def v03_option_similarity_gate(q: dict) -> dict:
    """네 보기 사이에 의미상 거의 동일한 쌍이 있으면 정답 단일성이 흔들릴 수 있다고 보고 REVIEW_REQUIRED로 표시한다.
    정답 근거(교육자료 대비 Grounding) 확인은 gate_service.evaluate_candidate()의 의미 검증기가 담당한다."""
    options = [q.get(k, "") for k in ("option_a", "option_b", "option_c", "option_d")]
    normalized = [_normalize_for_dedup(o) for o in options]
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            if not normalized[i] or not normalized[j]:
                continue
            similarity = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if similarity >= _OPTION_SIMILARITY_REVIEW_THRESHOLD:
                return gate_result("REVIEW_REQUIRED", "V03_OPTIONS_TOO_SIMILAR",
                                    "두 보기 문장이 의미상 중복될 가능성이 있습니다.",
                                    {"option_pair": [i, j], "similarity": round(similarity, 4)})
    return gate_result("PASS", "V03_OK", "보기 간 중복 가능성이 낮습니다.", {})


# --- V04 Distractor Quality ---------------------------------------------------

FORBIDDEN_DISTRACTOR_PHRASES = [
    "모두 맞다", "모두 옳다", "위 보기 모두", "정답 없음", "상황에 따라 다르다", "알 수 없음",
]
_ANSWER_LENGTH_OUTLIER_RATIO = 1.8
_LENGTH_RATIO_LIMIT = 3.0


def _distractor_quality_gate(q: dict) -> dict:
    options = {k: (q.get(k) or "") for k in ("option_a", "option_b", "option_c", "option_d")}

    for key, text in options.items():
        if any(phrase in text for phrase in FORBIDDEN_DISTRACTOR_PHRASES):
            return gate_result("REVIEW_REQUIRED", "V04_FORBIDDEN_DISTRACTOR_PHRASE",
                                f"금지된 보기 문구가 있습니다 — {key}", {"field": key})

    lengths = {k: len(v.strip()) for k, v in options.items()}
    answer = str(q.get("answer", "")).strip().upper()
    answer_key = f"option_{answer.lower()}" if answer in VALID_ANSWERS else None

    if answer_key and lengths.get(answer_key, 0) > 0:
        other_lengths = sorted(v for k, v in lengths.items() if k != answer_key)
        if other_lengths:
            median_other = other_lengths[len(other_lengths) // 2]
            if median_other > 0 and lengths[answer_key] >= _ANSWER_LENGTH_OUTLIER_RATIO * median_other:
                return gate_result("WARNING", "V04_ANSWER_LENGTH_OUTLIER",
                                    "정답 보기가 다른 보기보다 지나치게 깁니다.", {"lengths": lengths})

    nonzero_lengths = [v for v in lengths.values() if v > 0]
    if nonzero_lengths and min(nonzero_lengths) > 0:
        if max(nonzero_lengths) / min(nonzero_lengths) > _LENGTH_RATIO_LIMIT:
            return gate_result("WARNING", "V04_LENGTH_RATIO_EXCESSIVE",
                                "보기 길이 편차가 과도합니다.", {"lengths": lengths})

    endings = {k: v.strip()[-1] for k, v in options.items() if v.strip()}
    terminal_flags = {k: (v in ".!?") for k, v in endings.items()}
    if len(set(terminal_flags.values())) > 1:
        return gate_result("WARNING", "V04_INCONSISTENT_OPTION_FORMAT",
                            "보기의 문장부호·종결 형식이 혼합되어 있습니다.", {})

    return gate_result("PASS", "V04_OK", "오답 보기 품질이 적절합니다.", {})


# --- V05 Scope & Difficulty ---------------------------------------------------

# admin_service.TEAM_KEY_MAP과 동일하게 유지해야 하는 검증용 사본.
# gates.py는 "외부 의존 없음" 원칙을 지키기 위해 admin_service를 import하지 않는다.
_TEAM_KEY_MAP = {"T1": "team1", "T2": "team2", "T3": "team3"}


def _scope_difficulty_gate(q: dict, category_label: str = "", pool_key: str = "", team_code: str = "") -> dict:
    category = q.get("category", "")
    if category not in VALID_CATEGORIES:
        return gate_result("HARD_FAIL", "V05_CATEGORY_INVALID",
                            f"카테고리 값이 유효하지 않습니다 — {category!r}", {"category": category})

    if category_label and category != category_label:
        return gate_result("HARD_FAIL", "V05_CATEGORY_LABEL_MISMATCH",
                            f"생성 요청 카테고리 라벨과 문제의 category가 다릅니다 — {category!r} != {category_label!r}",
                            {"category": category, "category_label": category_label})

    if team_code:
        expected_pool_key = _TEAM_KEY_MAP.get(team_code, team_code)
        if pool_key and pool_key != expected_pool_key:
            return gate_result("HARD_FAIL", "V05_TEAM_POOL_MISMATCH",
                                f"team_code와 pool_key 조합이 일치하지 않습니다 — {team_code!r} -> {pool_key!r}",
                                {"team_code": team_code, "pool_key": pool_key, "expected_pool_key": expected_pool_key})

    difficulty = q.get("difficulty_init") or q.get("difficulty_ai") or ""
    if difficulty not in VALID_DIFFICULTIES:
        return gate_result("HARD_FAIL", "V05_DIFFICULTY_INVALID",
                            f"난이도 값이 유효하지 않습니다 — {difficulty!r}", {"difficulty": difficulty})

    if not (q.get("admin_override") or "").strip():
        return gate_result("WARNING", "V05_ADMIN_DIFFICULTY_PENDING",
                            "관리자 난이도 확정이 아직 없습니다.", {})

    return gate_result("PASS", "V05_OK", "팀·카테고리·난이도가 유효합니다.", {})


# --- V06 Duplicate & Exposure --------------------------------------------------

_HIGH_SIMILARITY_THRESHOLD = 0.92
_MODERATE_SIMILARITY_THRESHOLD = 0.82


def _duplicate_exposure_gate(q: dict, approved_questions=(), flagged_question_ids=frozenset()) -> dict:
    question_id = q.get("question_id", "")
    normalized_self = _normalize_for_dedup(q.get("question", ""))

    best_match_id = ""
    best_similarity = 0.0
    for other in approved_questions:
        if question_id and other.get("question_id") == question_id:
            return gate_result("HARD_FAIL", "V06_DUPLICATE_ID",
                                f"이미 존재하는 문제 ID입니다 — {question_id!r}", {"question_id": question_id})

        normalized_other = _normalize_for_dedup(other.get("question", ""))
        if normalized_self and normalized_other and normalized_self == normalized_other:
            return gate_result("HARD_FAIL", "V06_EXACT_DUPLICATE",
                                "기존 승인 문제와 완전히 동일합니다.",
                                {"matched_question_id": other.get("question_id", "")})

        if normalized_self and normalized_other:
            similarity = SequenceMatcher(None, normalized_self, normalized_other).ratio()
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = other.get("question_id", "")

    if best_similarity >= _HIGH_SIMILARITY_THRESHOLD:
        return gate_result("REVIEW_REQUIRED", "V06_HIGH_SIMILARITY",
                            "기존 승인 문제와 매우 유사합니다.",
                            {"matched_question_id": best_match_id, "similarity": round(best_similarity, 4)})

    if question_id and question_id in flagged_question_ids:
        return gate_result("WARNING", "V06_FREQUENTLY_ISSUED",
                            "자주 출제된 문제로 플래그된 ID입니다.", {"question_id": question_id})

    if best_similarity >= _MODERATE_SIMILARITY_THRESHOLD:
        return gate_result("WARNING", "V06_MODERATE_SIMILARITY",
                            "기존 승인 문제와 유사도가 다소 높습니다.",
                            {"matched_question_id": best_match_id, "similarity": round(best_similarity, 4)})

    return gate_result("PASS", "V06_OK", "신규 문제이며 중복이 발견되지 않았습니다.",
                        {"matched_question_id": best_match_id, "similarity": round(best_similarity, 4)})


# --- V07 Security & Media -----------------------------------------------------

_PHONE_PATTERN = re.compile(r"01[016789]-?\d{3,4}-?\d{4}")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_PATTERN = re.compile(r"https?://\S+")
_EMPLOYEE_ID_PATTERN = re.compile(r"(?:사번|직번|employee\s*id)\s*[:\-]?\s*\S+", re.IGNORECASE)
_EQUIPMENT_ID_PATTERN = re.compile(r"(?:설비\s*번호|설비\s*id|equipment\s*id)\s*[:\-]?\s*\S+", re.IGNORECASE)


def _security_media_gate(q: dict, media: dict | None = None) -> dict:
    text = " ".join([
        q.get("question", ""),
        q.get("option_a", ""), q.get("option_b", ""),
        q.get("option_c", ""), q.get("option_d", ""),
        q.get("explanation", ""),
    ])

    if _PHONE_PATTERN.search(text):
        return gate_result("HARD_FAIL", "V07_PHONE_DETECTED",
                            "전화번호로 추정되는 문자열이 감지되었습니다.", {})
    if _EMAIL_PATTERN.search(text):
        return gate_result("HARD_FAIL", "V07_EMAIL_DETECTED",
                            "이메일 주소가 감지되었습니다.", {})
    if _URL_PATTERN.search(text):
        return gate_result("HARD_FAIL", "V07_URL_DETECTED",
                            "URL이 감지되었습니다.", {})
    for kw in SECURITY_KEYWORDS:
        if kw in text:
            return gate_result("HARD_FAIL", "V07_SECURITY_KEYWORD_DETECTED",
                                f"보안 키워드가 감지되었습니다 — {kw!r}", {"keyword": kw})
    if _EMPLOYEE_ID_PATTERN.search(text):
        return gate_result("HARD_FAIL", "V07_EMPLOYEE_ID_EXPOSED",
                            "사번·직번으로 추정되는 식별자가 감지되었습니다.", {})

    if media:
        if media.get("present") and not media.get("approved"):
            return gate_result("HARD_FAIL", "V07_MEDIA_NOT_APPROVED",
                                "승인되지 않은 미디어가 포함되어 있습니다.", {})
        if media.get("ocr_detected_answer_pattern"):
            return gate_result("HARD_FAIL", "V07_MEDIA_ANSWER_LEAK",
                                "미디어 OCR 결과에서 정답 노출 패턴이 감지되었습니다.", {})

    if _EQUIPMENT_ID_PATTERN.search(text):
        return gate_result("WARNING", "V07_EQUIPMENT_IDENTIFIER_DETECTED",
                            "설비번호로 추정되는 식별자가 감지되었습니다 — 관리자 확인이 필요합니다.", {})

    return gate_result("PASS", "V07_OK", "개인정보·보안·미디어 문제가 발견되지 않았습니다.", {})


def run_deterministic_gates(
    question: dict,
    *,
    category_label: str = "",
    pool_key: str = "",
    team_code: str = "",
    approved_questions=(),
    flagged_question_ids=frozenset(),
    media: dict | None = None,
) -> dict:
    """외부 I/O 없이 판정 가능한 V01·V04·V05·V06·V07 결과만 조립한다.
    V02·V03(의미 검증)은 services.generation.gate_service.evaluate_candidate()가 담당한다.
    V01이 HARD_FAIL이어도 나머지 결정론적 Gate는 best-effort로 계속 실행한다."""
    return {
        "gates": {
            "V01": _schema_gate(question),
            "V04": _distractor_quality_gate(question),
            "V05": _scope_difficulty_gate(question, category_label, pool_key, team_code),
            "V06": _duplicate_exposure_gate(question, approved_questions, flagged_question_ids),
            "V07": _security_media_gate(question, media),
        }
    }
