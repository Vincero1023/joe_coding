from __future__ import annotations

import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


def install_error_handlers(app: FastAPI, *, app_env: str) -> None:
    include_traceback = app_env.lower() != "production"

    @app.middleware("http")
    async def attach_request_context(request: Request, call_next):  # type: ignore[override]
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        payload = _build_error_payload(
            request=request,
            code=f"http_{exc.status_code}",
            message=_extract_http_message(exc.detail),
            detail=_normalize_detail(exc.detail),
        )
        response = JSONResponse(status_code=exc.status_code, content=payload)
        response.headers["X-Request-ID"] = payload["error"]["request_id"]
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        payload = _build_error_payload(
            request=request,
            code="validation_error",
            message="Request validation failed.",
            detail={"errors": exc.errors()},
        )
        response = JSONResponse(status_code=422, content=payload)
        response.headers["X-Request-ID"] = payload["error"]["request_id"]
        return response

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error")

        detail: dict[str, Any] = {"type": exc.__class__.__name__}
        if include_traceback:
            detail["traceback"] = traceback.format_exception(type(exc), exc, exc.__traceback__)

        payload = _build_error_payload(
            request=request,
            code="internal_error",
            message=str(exc) or "Unhandled server error.",
            detail=detail,
        )
        response = JSONResponse(status_code=500, content=payload)
        response.headers["X-Request-ID"] = payload["error"]["request_id"]
        return response


def _build_error_payload(
    *,
    request: Request,
    code: str,
    message: str,
    detail: Any,
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


def _extract_http_message(detail: Any) -> str:
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    if isinstance(detail, str) and detail.strip():
        return detail.strip()

    return "Request failed."


def _normalize_detail(detail: Any) -> Any:
    if detail is None:
        return {}
    return detail
