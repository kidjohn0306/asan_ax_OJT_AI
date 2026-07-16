import os
from collections.abc import Mapping


def is_strict_sheets_storage(env: Mapping[str, str] | None = None) -> bool:
    """Return whether Sheets failures must be surfaced instead of hidden."""
    source = os.environ if env is None else env
    raw = source.get("OJT_STRICT_SHEETS_STORAGE", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise ValueError(
            "OJT_STRICT_SHEETS_STORAGE must be either 'true' or 'false'"
        )
    return raw == "true"


def should_fallback_to_local(env: Mapping[str, str] | None = None) -> bool:
    """Allow Local fallback only when strict Sheets storage is disabled."""
    return not is_strict_sheets_storage(env)
