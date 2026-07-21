import logging


def record_activity(
    activity_type: str,
    actor_name: str = "",
    target: str = "",
    detail: str = "",
    team_code: str = "",
    is_test: bool = False,
) -> None:
    """대시보드 "최근 활동 피드" 기록은 최선 노력으로만 수행한다 — 실패해도 호출한
    원본 액션(응시 제출·문제 승인·사용자 등록·시험 생성 등)을 막지 않는다."""
    from repositories import activity_log_repo
    try:
        activity_log_repo.append_activity({
            "type": activity_type,
            "actor_name": actor_name,
            "target": target,
            "detail": detail,
            "team_code": team_code,
            "is_test": is_test,
        })
    except Exception:
        logging.exception("activity log write failed for %s", activity_type)


def fetch_activity_log(page: int = 1, limit: int = 20) -> dict:
    from repositories import activity_log_repo
    page = max(1, page)
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit
    # has_more 판단을 위해 1건 더 조회한다.
    items = activity_log_repo.list_recent_activity(limit=limit + 1, offset=offset)
    has_more = len(items) > limit
    return {"items": items[:limit], "page": page, "limit": limit, "has_more": has_more}
