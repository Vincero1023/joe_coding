from __future__ import annotations

import asyncio
import json
import logging
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ModuleRequest, ModuleResponse
from app.expander.main import expander_module, run_with_analysis_progress, run_with_progress


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/expand", response_model=ModuleResponse)
def expand_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=expander_module.run(payload.input_data))


@router.post("/expand/stream")
def expand_keywords_stream(payload: ModuleRequest, request: Request) -> StreamingResponse:
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
                if await request.is_disconnected():
                    stop_event.set()
                    break
                try:
                    item = await asyncio.to_thread(event_queue.get, True, 0.1)
                except Empty:
                    await asyncio.sleep(0.05)
                    continue
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + "\n"
        finally:
            stop_event.set()

    response = StreamingResponse(stream_lines(), media_type="application/x-ndjson")
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


