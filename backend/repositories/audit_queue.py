import logging
import threading
import uuid
from datetime import datetime, timezone


class QueuedAuditRepository:
    """감사 로그를 이벤트마다 즉시 쓰지 않고 메모리 큐에 모았다가 주기적으로 배치 기록한다.
    Google Sheets 쓰기 API는 분당 호출 횟수 한도가 있어, 승인·반려·수정 등이 몰리면
    이벤트당 1회 append로는 한도를 빠르게 소진한다 — 여러 건을 모아 한 번의 append 호출로
    내보내 호출 수를 줄인다. sink는 record_batch(rows)와 list_logs(limit)를 제공해야 한다."""

    def __init__(self, sink, flush_interval: float = 20.0, max_queue_size: int = 25):
        self._sink = sink
        self._flush_interval = flush_interval
        self._max_queue_size = max_queue_size
        self._lock = threading.Lock()
        self._queue: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._flush_interval):
            self._safe_flush()

    def _safe_flush(self) -> None:
        try:
            self.flush()
        except Exception:
            logging.exception("audit log batch flush failed; will retry next interval")

    def record(self, actor_id: str, actor_role: str, action_type: str, target_type: str,
               target_id: str, before: dict | None = None, after: dict | None = None,
               reason: str = "") -> None:
        row = {
            "audit_id": "audit-" + uuid.uuid4().hex,
            "actor_id": actor_id or "",
            "actor_role": actor_role or "",
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "before_json": before or {},
            "after_json": after or {},
            "reason": reason or "",
            "request_id": "",
            "ip_address": "",
            "user_agent": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._queue.append(row)
            should_flush = len(self._queue) >= self._max_queue_size
        if should_flush:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            if not self._queue:
                return
            pending = self._queue
            self._queue = []
        try:
            self._sink.record_batch(pending)
        except Exception:
            # 실패하면 다음 주기에 재시도할 수 있도록 큐에 되돌린다(먼저 쌓인 순서 유지).
            with self._lock:
                self._queue = pending + self._queue
            raise

    def list_logs(self, limit: int = 200) -> list:
        with self._lock:
            pending = list(self._queue)
        stored = self._sink.list_logs(limit=limit)
        combined = pending + stored
        combined.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return combined[:limit]
