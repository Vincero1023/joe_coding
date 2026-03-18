from __future__ import annotations

import json
import logging
from queue import Queue
from threading import Thread
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ModuleRequest, ModuleResponse
from app.expander.main import expander_module, run_with_progress


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/expand", response_model=ModuleResponse)
def expand_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=expander_module.run(payload.input_data))


@router.post("/expand/stream")
def expand_keywords_stream(payload: ModuleRequest, request: Request) -> StreamingResponse:
    request_id = getattr(request.state, "request_id", "")

    def stream_lines():
        event_queue: Queue[dict[str, Any] | None] = Queue()

        def publish(progress_payload: dict[str, Any]) -> None:
            event_queue.put({"event": "progress", "data": progress_payload})

        def worker() -> None:
            try:
                result = run_with_progress(payload.input_data, progress_callback=publish)
                event_queue.put({"event": "completed", "result": result})
            except Exception as exc:  # pragma: no cover - exercised via API tests
                logger.exception("Expanded stream failed")
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

        while True:
            item = event_queue.get()
            if item is None:
                break
            yield json.dumps(item, ensure_ascii=False) + "\n"

    response = StreamingResponse(stream_lines(), media_type="application/x-ndjson")
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


