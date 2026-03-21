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
from app.expander.main import expander_module, run_with_analysis_progress, run_with_progress


router = APIRouter()
logger = logging.getLogger(__name__)
_STREAM_HEARTBEAT_SECONDS = 5.0


@router.post("/expand", response_model=ModuleResponse)
def expand_keywords(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("expand")
    return ModuleResponse(result=expander_module.run(payload.input_data))


@router.post("/expand/stream")
def expand_keywords_stream(payload: ModuleRequest, request: Request) -> StreamingResponse:
    record_operation_start("expand_stream")
    request_id = getattr(request.state, "request_id", "")
    return _stream_expand_response(
        request=request,
        request_id=request_id,
        worker_label="Expanded stream failed",
        runner=lambda stop_event, publish: run_with_progress(
            payload.input_data,
            progress_callback=lambda progress_payload: publish({"event": "progress", "data": progress_payload}),
            stop_event=stop_event,
        ),
    )


@router.post("/expand/analyze/stream")
def expand_analyze_keywords_stream(payload: ModuleRequest, request: Request) -> StreamingResponse:
    record_operation_start("expand_analyze_stream")
    request_id = getattr(request.state, "request_id", "")
    return _stream_expand_response(
        request=request,
        request_id=request_id,
        worker_label="Expand/analyze stream failed",
        runner=lambda stop_event, publish: run_with_analysis_progress(
            payload.input_data,
            progress_callback=lambda progress_payload: publish({"event": "progress", "data": progress_payload}),
            analysis_callback=lambda analysis_payload: publish({"event": "analysis", "data": analysis_payload}),
            stop_event=stop_event,
        ),
    )


def _stream_expand_response(
    *,
    request: Request,
    request_id: str,
    worker_label: str,
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
                logger.exception(worker_label)
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
                    logger.exception("Failed to inspect stream disconnect state")
                    disconnected = False

                if disconnected:
                    stop_event.set()
                    break

                try:
                    item = await asyncio.to_thread(event_queue.get, True, 0.1)
                except Empty:
                    now = time.monotonic()
                    if now >= next_heartbeat_at:
                        yield json.dumps({"event": "heartbeat", "request_id": request_id}, ensure_ascii=False) + "\n"
                        next_heartbeat_at = now + _STREAM_HEARTBEAT_SECONDS
                    await asyncio.sleep(0.05)
                    continue

                if item is None:
                    break

                next_heartbeat_at = time.monotonic() + _STREAM_HEARTBEAT_SECONDS
                yield json.dumps(item, ensure_ascii=False) + "\n"
        except Exception as exc:  # pragma: no cover - runtime guard
            stop_event.set()
            logger.exception("Streaming response generator failed")
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
                yield json.dumps(error_payload, ensure_ascii=False) + "\n"
            except Exception:
                logger.exception("Failed to emit stream generator error payload")
        finally:
            stop_event.set()

    response = StreamingResponse(stream_lines(), media_type="application/x-ndjson")
    if request_id:
        response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response


