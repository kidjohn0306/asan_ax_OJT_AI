"""Gate Context 구성과 의미 검증(V02·V03) 결과 결합.
services.generation.gates의 결정론적 판정(V01·V04·V05·V06·V07)과 의미 검증기 응답을 합쳐
최종 7-Gate 결과(overall_status, gate_version, question_fingerprint 포함)를 조립한다.
Router나 Provider 구현을 직접 import하지 않고 SemanticGateVerifier Protocol에만 의존해
순환 import와 ai_engine에 대한 결합을 피한다."""
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Protocol

from services.generation.gates import (
    GATE_STATUSES,
    STATUS_PRIORITY,
    gate_result,
    overall_status,
    question_fingerprint,
    run_deterministic_gates,
    v03_option_similarity_gate,
)

GATE_VERSION = "mcq-7gate-v1"

_VALID_GROUNDING = {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}
_VALID_SINGLE_ANSWER = {"PASS", "FAIL", "UNCERTAIN"}
_REQUIRED_PASS_GATES = ("V01", "V02", "V03", "V07")
_ALL_GATE_KEYS = ("V01", "V02", "V03", "V04", "V05", "V06", "V07")


@dataclass(frozen=True)
class GateContext:
    material_text: str
    team_code: str
    pool_key: str
    category_label: str
    approved_questions: tuple = field(default_factory=tuple)
    flagged_question_ids: frozenset = field(default_factory=frozenset)


class SemanticGateVerifier(Protocol):
    def verify(self, question: dict, context: GateContext) -> dict:
        ...


def _source_digest(material_text: str) -> str:
    return "sha256:" + hashlib.sha256((material_text or "").encode("utf-8")).hexdigest()


def _validate_semantic_response(raw) -> dict | None:
    """알 수 없는 Enum 값, 누락 키, 비 JSON 응답은 검증기 성공으로 처리하지 않는다."""
    if not isinstance(raw, dict):
        return None
    required_keys = ("grounding", "single_answer", "distractor_status", "scope_status")
    if any(key not in raw for key in required_keys):
        return None
    if raw["grounding"] not in _VALID_GROUNDING:
        return None
    if raw["single_answer"] not in _VALID_SINGLE_ANSWER:
        return None
    if raw["distractor_status"] not in GATE_STATUSES:
        return None
    if raw["scope_status"] not in GATE_STATUSES:
        return None
    return raw


def _map_grounding(validated: dict) -> dict:
    grounding = validated["grounding"]
    reason = validated.get("grounding_reason") or ""
    if grounding == "SUPPORTED":
        return gate_result("PASS", "V02_OK", reason or "교육자료가 질문과 정답을 뒷받침합니다.", {})
    if grounding == "PARTIAL":
        return gate_result("REVIEW_REQUIRED", "V02_GROUNDING_PARTIAL",
                            reason or "근거가 부분적으로만 확인됩니다.", {})
    return gate_result("HARD_FAIL", "V02_GROUNDING_UNSUPPORTED",
                        reason or "교육자료에서 근거를 확인할 수 없습니다.", {})


def _map_single_answer(validated: dict) -> dict:
    single_answer = validated["single_answer"]
    reason = validated.get("single_answer_reason") or ""
    if single_answer == "PASS":
        return gate_result("PASS", "V03_OK", reason or "정답이 하나로 확인됩니다.", {})
    if single_answer == "UNCERTAIN":
        return gate_result("REVIEW_REQUIRED", "V03_SINGLE_ANSWER_UNCERTAIN",
                            reason or "정답 단일성이 불확실합니다.", {})
    return gate_result("HARD_FAIL", "V03_SINGLE_ANSWER_FAIL",
                        reason or "정답이 하나로 확정되지 않습니다.", {})


def _harsher(a: dict, b: dict) -> dict:
    return a if STATUS_PRIORITY[a["status"]] >= STATUS_PRIORITY[b["status"]] else b


def evaluate_candidate(
    question: dict,
    context: GateContext,
    verifier: SemanticGateVerifier,
    mode: str = "strict",
) -> dict:
    """V01·V04·V05·V06·V07(결정론적) + V02·V03(의미 검증)을 합쳐 최종 Gate 결과를 조립한다.
    verifier 호출 실패·비정상 응답은 어떤 mode에서도 PASS로 바뀌지 않고 REVIEW_REQUIRED로 처리한다."""
    deterministic_gates = run_deterministic_gates(
        question,
        category_label=context.category_label,
        pool_key=context.pool_key,
        team_code=context.team_code,
        approved_questions=context.approved_questions,
        flagged_question_ids=context.flagged_question_ids,
    )["gates"]

    gates = dict(deterministic_gates)
    option_similarity = v03_option_similarity_gate(question)
    semantic_v04 = None
    semantic_v05 = None

    if gates["V01"]["status"] == "HARD_FAIL":
        v02_result = gate_result("REVIEW_REQUIRED", "V02_NOT_EVALUATED",
                                  "V01 Schema 실패로 의미 검증을 수행하지 않았습니다.", {})
        v03_semantic = gate_result("REVIEW_REQUIRED", "V03_NOT_EVALUATED",
                                    "V01 Schema 실패로 의미 검증을 수행하지 않았습니다.", {})
    elif not (context.material_text or "").strip():
        v02_result = gate_result("HARD_FAIL", "V02_SOURCE_MISSING",
                                  "생성에 사용된 교육자료가 없습니다.", {})
        v03_semantic = gate_result("REVIEW_REQUIRED", "V03_NOT_EVALUATED",
                                    "근거 자료가 없어 정답 단일성을 검증할 수 없습니다.", {})
    else:
        try:
            raw_response = verifier.verify(question, context)
        except Exception as exc:
            logging.warning(
                "Gate 의미 검증기 호출 실패 (provider=%s): %s: %s",
                getattr(verifier, "provider", "unknown"), type(exc).__name__, exc,
            )
            v02_result = gate_result("REVIEW_REQUIRED", "V02_VERIFIER_ERROR",
                                      "의미 검증기 호출에 실패해 검토가 필요합니다.", {})
            v03_semantic = gate_result("REVIEW_REQUIRED", "V03_VERIFIER_ERROR",
                                        "의미 검증기 호출에 실패해 검토가 필요합니다.", {})
        else:
            validated = _validate_semantic_response(raw_response)
            if validated is None:
                v02_result = gate_result("REVIEW_REQUIRED", "SEMANTIC_VERIFIER_INVALID_RESPONSE",
                                          "의미 검증기 응답을 해석할 수 없습니다.", {})
                v03_semantic = gate_result("REVIEW_REQUIRED", "SEMANTIC_VERIFIER_INVALID_RESPONSE",
                                            "의미 검증기 응답을 해석할 수 없습니다.", {})
            else:
                v02_result = _map_grounding(validated)
                v03_semantic = _map_single_answer(validated)
                semantic_v04 = gate_result(
                    validated["distractor_status"], f"V04_SEMANTIC_{validated['distractor_status']}",
                    validated.get("distractor_reason") or "", {},
                )
                semantic_v05 = gate_result(
                    validated["scope_status"], f"V05_SEMANTIC_{validated['scope_status']}",
                    validated.get("scope_reason") or "", {},
                )

    gates["V02"] = v02_result
    gates["V03"] = _harsher(option_similarity, v03_semantic)
    if semantic_v04 is not None:
        gates["V04"] = _harsher(gates["V04"], semantic_v04)
    if semantic_v05 is not None:
        gates["V05"] = _harsher(gates["V05"], semantic_v05)

    overall = overall_status([gates[key]["status"] for key in _ALL_GATE_KEYS])
    required_pass = all(gates[key]["status"] == "PASS" for key in _REQUIRED_PASS_GATES)
    legacy_pass = overall in ("PASS", "WARNING") and required_pass
    failed = [gates[key]["code"] for key in _ALL_GATE_KEYS
              if gates[key]["status"] in ("HARD_FAIL", "REVIEW_REQUIRED")]

    return {
        "pass": legacy_pass,
        "failed": failed,
        "flags": {
            "warning": overall == "WARNING",
            "security_hold": gates["V07"]["status"] != "PASS",
        },
        "overall_status": overall,
        "gate_version": GATE_VERSION,
        "question_fingerprint": question_fingerprint(question),
        "source_digest": _source_digest(context.material_text),
        "gates": gates,
    }
