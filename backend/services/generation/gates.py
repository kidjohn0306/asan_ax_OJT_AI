"""
규칙 게이트 7개 (V-01 ~ V-07) — 순수 함수, 외부 의존 없음
생성된 문제 dict를 입력받아 검증 결과 dict를 반환한다.
"""

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
    ok, msg = _v06_category_team_match(q)
    if not ok:
        flags["warning"] = True

    # V-07: SECURITY_HOLD 플래그만
    ok, msg = _v07_security_keywords(q)
    if not ok:
        flags["security_hold"] = True

    return {
        "pass": len(failed) == 0,
        "failed": failed,
        "flags": flags,
    }
