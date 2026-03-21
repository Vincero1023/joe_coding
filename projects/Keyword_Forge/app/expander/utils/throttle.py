from __future__ import annotations

import os
import threading
import time

from app.core.runtime_settings import before_naver_request, get_runtime_operation_settings


# Use a conservative default because unattended scheduled runs are now a first-class use case.
_DEFAULT_NAVER_REQUEST_GAP_SECONDS = 2.0
_NAVER_REQUEST_GAP_ENV = "KEYWORD_FORGE_NAVER_REQUEST_GAP_SECONDS"
_NAVER_REQUEST_BUCKET = "naver_keyword_sources"


class RequestThrottle:
    def __init__(self, default_min_interval_seconds: float) -> None:
        self._default_min_interval_seconds = max(0.0, float(default_min_interval_seconds))
        self._lock = threading.Lock()
        self._next_allowed_at: dict[str, float] = {}

    def wait(self, bucket: str, min_interval_seconds: float | None = None) -> None:
        interval = self._resolve_interval(min_interval_seconds)
        if interval <= 0:
            return

        now = time.monotonic()
        with self._lock:
            next_allowed_at = self._next_allowed_at.get(bucket, now)
            scheduled_at = max(now, next_allowed_at)
            self._next_allowed_at[bucket] = scheduled_at + interval

        delay = scheduled_at - now
        if delay > 0:
            time.sleep(delay)

    def _resolve_interval(self, min_interval_seconds: float | None) -> float:
        if min_interval_seconds is None:
            return self._default_min_interval_seconds
        return max(0.0, float(min_interval_seconds))


def get_naver_request_gap_seconds() -> float:
    runtime_gap = get_runtime_operation_settings().naver_request_gap_seconds
    raw_value = os.getenv(_NAVER_REQUEST_GAP_ENV, "").strip()
    if not raw_value:
        return runtime_gap if runtime_gap >= 0 else _DEFAULT_NAVER_REQUEST_GAP_SECONDS

    try:
        parsed = float(raw_value)
    except ValueError:
        return runtime_gap if runtime_gap >= 0 else _DEFAULT_NAVER_REQUEST_GAP_SECONDS

    return parsed if parsed >= 0 else (runtime_gap if runtime_gap >= 0 else _DEFAULT_NAVER_REQUEST_GAP_SECONDS)


_GLOBAL_THROTTLE = RequestThrottle(default_min_interval_seconds=_DEFAULT_NAVER_REQUEST_GAP_SECONDS)


def wait_for_naver_keyword_request() -> None:
    before_naver_request()
    _GLOBAL_THROTTLE.wait(
        bucket=_NAVER_REQUEST_BUCKET,
        min_interval_seconds=get_naver_request_gap_seconds(),
    )
