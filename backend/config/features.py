import os
from collections.abc import Mapping


SCHEMA_MODE_ENV = "OJT_SHEETS_SCHEMA_MODE"
SCHEMA_MODES = ("legacy", "dual", "v2")

NORMALIZED_FEATURE_FLAGS = (
    "OJT_USE_NORMALIZED_MATERIALS",
    "OJT_USE_KNOWLEDGE_UNITS",
    "OJT_USE_CANDIDATE_TAB",
    "OJT_USE_GATE_RESULTS_TAB",
    "OJT_USE_FROZEN_EXAM",
    "OJT_USE_ASSIGNMENTS_TAB",
    "OJT_USE_RESULT_ANSWERS",
)


def _source(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def get_schema_mode(env: Mapping[str, str] | None = None) -> str:
    raw = _source(env).get(SCHEMA_MODE_ENV, "legacy").strip().lower()
    if raw not in SCHEMA_MODES:
        allowed = ", ".join(SCHEMA_MODES)
        raise ValueError(f"{SCHEMA_MODE_ENV} must be one of: {allowed}")
    return raw


def is_feature_enabled(
    flag: str,
    env: Mapping[str, str] | None = None,
) -> bool:
    if flag not in NORMALIZED_FEATURE_FLAGS:
        raise KeyError(f"unknown OJT feature flag: {flag}")
    raw = _source(env).get(flag, "false").strip().lower()
    if raw not in {"true", "false"}:
        raise ValueError(f"{flag} must be either 'true' or 'false'")
    return raw == "true"


def get_feature_flags(
    env: Mapping[str, str] | None = None,
) -> dict[str, bool]:
    return {
        flag: is_feature_enabled(flag, env)
        for flag in NORMALIZED_FEATURE_FLAGS
    }
