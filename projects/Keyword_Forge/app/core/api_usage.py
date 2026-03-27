from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from threading import Lock
from typing import Any, Callable


_CURRENT_API_USAGE_COLLECTOR: ContextVar["ApiUsageCollector | None"] = ContextVar(
    "current_api_usage_collector",
    default=None,
)
_LLM_PROVIDERS = {"openai", "gemini", "vertex", "anthropic"}


class ApiUsageCollector:
    def __init__(self) -> None:
        self._lock = Lock()
        self._services: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    def record(
        self,
        *,
        stage: str = "",
        service: str = "",
        provider: str = "",
        model: str = "",
        endpoint: str = "",
        call_count: int = 1,
        success: bool = True,
        cached: bool = False,
        requested_units: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        normalized_stage = str(stage or "").strip()
        normalized_service = str(service or "").strip() or "unknown"
        normalized_provider = str(provider or "").strip()
        normalized_model = str(model or "").strip()
        normalized_endpoint = str(endpoint or "").strip()
        normalized_call_count = max(0, _coerce_int(call_count))
        normalized_requested_units = max(0, _coerce_int(requested_units))
        normalized_prompt_tokens = max(0, _coerce_int(prompt_tokens))
        normalized_completion_tokens = max(0, _coerce_int(completion_tokens))
        normalized_total_tokens = max(0, _coerce_int(total_tokens))
        if normalized_total_tokens <= 0:
            normalized_total_tokens = normalized_prompt_tokens + normalized_completion_tokens
        if normalized_call_count <= 0 and not cached:
            normalized_call_count = 1

        key = (
            normalized_stage,
            normalized_service,
            normalized_provider,
            normalized_model,
            normalized_endpoint,
        )

        with self._lock:
            entry = self._services.setdefault(
                key,
                {
                    "stage": normalized_stage,
                    "service": normalized_service,
                    "provider": normalized_provider,
                    "model": normalized_model,
                    "endpoint": normalized_endpoint,
                    "calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "cached_calls": 0,
                    "requested_units": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
            entry["calls"] += normalized_call_count
            entry["requested_units"] += normalized_requested_units
            entry["prompt_tokens"] += normalized_prompt_tokens
            entry["completion_tokens"] += normalized_completion_tokens
            entry["total_tokens"] += normalized_total_tokens
            if cached:
                entry["cached_calls"] += normalized_call_count
            elif success:
                entry["successful_calls"] += normalized_call_count
            else:
                entry["failed_calls"] += normalized_call_count

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            services = [dict(entry) for entry in self._services.values()]

        return _build_snapshot_from_services(services)


def merge_api_usage_snapshots(*snapshots: Any) -> dict[str, Any]:
    merged_services: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        services = snapshot.get("services")
        if not isinstance(services, list):
            continue
        for raw_item in services:
            if not isinstance(raw_item, dict):
                continue
            key = (
                str(raw_item.get("stage") or "").strip(),
                str(raw_item.get("service") or "").strip(),
                str(raw_item.get("provider") or "").strip(),
                str(raw_item.get("model") or "").strip(),
                str(raw_item.get("endpoint") or "").strip(),
            )
            entry = merged_services.setdefault(
                key,
                {
                    "stage": key[0],
                    "service": key[1],
                    "provider": key[2],
                    "model": key[3],
                    "endpoint": key[4],
                    "calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "cached_calls": 0,
                    "requested_units": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
            for field_name in (
                "calls",
                "successful_calls",
                "failed_calls",
                "cached_calls",
                "requested_units",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            ):
                entry[field_name] += max(0, _coerce_int(raw_item.get(field_name)))

    return _build_snapshot_from_services(list(merged_services.values()))


def _build_snapshot_from_services(services: list[dict[str, Any]]) -> dict[str, Any]:
    services.sort(
        key=lambda item: (
            -int(item.get("calls") or 0),
            -int(item.get("total_tokens") or 0),
            str(item.get("service") or ""),
            str(item.get("provider") or ""),
            str(item.get("model") or ""),
        )
    )

    summary = {
        "service_count": len(services),
        "total_calls": sum(int(item.get("calls") or 0) for item in services),
        "successful_calls": sum(int(item.get("successful_calls") or 0) for item in services),
        "failed_calls": sum(int(item.get("failed_calls") or 0) for item in services),
        "cached_calls": sum(int(item.get("cached_calls") or 0) for item in services),
        "total_requested_units": sum(int(item.get("requested_units") or 0) for item in services),
        "llm_calls": sum(
            int(item.get("calls") or 0)
            for item in services
            if str(item.get("provider") or "").strip().lower() in _LLM_PROVIDERS
        ),
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in services),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in services),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in services),
    }
    return {
        "summary": summary,
        "services": services,
    }


def get_current_api_usage_collector() -> ApiUsageCollector | None:
    return _CURRENT_API_USAGE_COLLECTOR.get()


def record_api_usage(
    *,
    stage: str = "",
    service: str = "",
    provider: str = "",
    model: str = "",
    endpoint: str = "",
    call_count: int = 1,
    success: bool = True,
    cached: bool = False,
    requested_units: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    collector = get_current_api_usage_collector()
    if collector is None:
        return
    collector.record(
        stage=stage,
        service=service,
        provider=provider,
        model=model,
        endpoint=endpoint,
        call_count=call_count,
        success=success,
        cached=cached,
        requested_units=requested_units,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


@contextmanager
def capture_api_usage() -> Any:
    collector = ApiUsageCollector()
    token = _CURRENT_API_USAGE_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _CURRENT_API_USAGE_COLLECTOR.reset(token)


def bind_current_api_usage_context(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Callable[[], Any]:
    context = copy_context()

    def runner() -> Any:
        return context.run(func, *args, **kwargs)

    return runner


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
