from __future__ import annotations

import asyncio
import json
import logging
import time
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ModuleRequest, ModuleResponse
from app.core.runtime_settings import record_operation_start
from app.title.main import run_with_progress
from app.title_gen.main import title_generator_module


router = APIRouter()
logger = logging.getLogger(__name__)
_STREAM_HEARTBEAT_SECONDS = 5.0


@router.post("/generate-title", response_model=ModuleResponse)
def generate_title(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("generate_title")
    return ModuleResponse(result=title_generator_module.run(_with_default_title_export(payload.input_data)))


@router.post("/generate-title/stream")
def generate_title_stream(payload: ModuleRequest, request: Request) -> StreamingResponse:
    record_operation_start("generate_title_stream")
    request_id = getattr(request.state, "request_id", "")
    input_data = _with_default_title_export(payload.input_data)
    return _stream_title_response(
        request=request,
        request_id=request_id,
        runner=lambda stop_event, publish: run_with_progress(
            input_data,
            progress_callback=lambda progress_payload: publish({"event": "progress", "data": progress_payload}),
            stop_event=stop_event,
        ),
    )


def _with_default_title_export(input_data: Any) -> Any:
    if not isinstance(input_data, dict):
        return input_data

    merged = dict(input_data)
    raw_export = merged.get("title_export") if isinstance(merged.get("title_export"), dict) else {}
    merged["title_export"] = {
        **raw_export,
        "enabled": _coerce_boolish(raw_export.get("enabled"), default=True),
    }
    return merged


def _coerce_boolish(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _stream_title_response(
    *,
    request: Request,
    request_id: str,
    runner: Callable[[Event, Callable[[dict[str, Any]], None]], dict[str, Any]],
) -> StreamingResponse:
    stop_event = Event()

    async def stream_lines():
        event_queue: Queue[dict[str, Any] | None] = Queue()
        next_heartbeat_at = time.monotonic() + _STREAM_HEARTBEAT_SECONDS

        def publish(envelope: dict[str, Any]) -> None:
            if not stop_event.is_set():
                event_queue.put(envelope)

        def worker() -> None:
            try:
                result = runner(stop_event, publish)
                if not stop_event.is_set():
                    event_queue.put({"event": "completed", "result": result})
            except Exception as exc:  # pragma: no cover - exercised via API tests
                if stop_event.is_set():
                    return
                logger.exception("Title stream failed")
                event_queue.put(
                    {
                        "event": "error",
                        "error": {
                            "code": "internal_error",
                            "message": str(exc) or "Unhandled server error.",
                            "detail": {"type": exc.__class__.__name__},
                            "request_id": request_id,
                            "path": request.url.path,
                        },
                    }
                )
            finally:
                event_queue.put(None)

        Thread(target=worker, daemon=True).start()

        try:
            while True:
                try:
                    disconnected = await request.is_disconnected()
                except Exception:  # pragma: no cover - runtime guard
                    logger.exception("Failed to inspect title stream disconnect state")
                    disconnected = False

                if disconnected:
                    stop_event.set()
                    break

                try:
                    item = await asyncio.to_thread(event_queue.get, True, 0.1)
                except Empty:
                    now = time.monotonic()
                    if now >= next_heartbeat_at:
                        yield json.dumps(
                            {"event": "heartbeat", "request_id": request_id},
                            ensure_ascii=False,
                            default=str,
                        ) + "\n"
                        next_heartbeat_at = now + _STREAM_HEARTBEAT_SECONDS
                    await asyncio.sleep(0.05)
                    continue

                if item is None:
                    break

                next_heartbeat_at = time.monotonic() + _STREAM_HEARTBEAT_SECONDS
                yield json.dumps(item, ensure_ascii=False, default=str) + "\n"
        except Exception as exc:  # pragma: no cover - runtime guard
            stop_event.set()
            logger.exception("Title streaming response generator failed")
            error_payload = {
                "event": "error",
                "error": {
                    "code": "stream_generator_error",
                    "message": str(exc) or "Streaming response failed.",
                    "detail": {"type": exc.__class__.__name__},
                    "request_id": request_id,
                    "path": request.url.path,
                },
            }
            try:
                yield json.dumps(error_payload, ensure_ascii=False, default=str) + "\n"
            except Exception:
                logger.exception("Failed to emit title stream generator error payload")
        finally:
            stop_event.set()

    response = StreamingResponse(stream_lines(), media_type="application/x-ndjson")
    if request_id:
        response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response


