from fastapi import APIRouter, HTTPException

from app.api.schemas import ModuleRequest, ModuleResponse
from app.local.naver_login_browser import (
    LocalLoginBrowserError,
    LocalNaverLoginBrowserService,
    load_cached_session_payload,
    read_cached_session_summary,
)
from app.local.naver_session import LocalBrowserCookieError, LocalNaverSessionService


router = APIRouter()
service = LocalNaverSessionService()
login_browser_service = LocalNaverLoginBrowserService()


@router.post("/local/naver-session", response_model=ModuleResponse)
def read_local_naver_session(payload: ModuleRequest) -> ModuleResponse:
    browser = str(payload.input_data.get("browser") or "auto")
    try:
        return ModuleResponse(result=service.load_session(browser=browser))
    except LocalBrowserCookieError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                **exc.to_detail(),
            },
        ) from exc


@router.post("/local/naver-login-browser", response_model=ModuleResponse)
def open_local_naver_login_browser(payload: ModuleRequest) -> ModuleResponse:
    browser = str(payload.input_data.get("browser") or "edge")
    timeout_seconds = int(payload.input_data.get("timeout_seconds") or 300)
    try:
        return ModuleResponse(
            result=login_browser_service.open_and_capture_session(
                browser=browser,
                timeout_seconds=timeout_seconds,
            )
        )
    except LocalLoginBrowserError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                **exc.to_detail(),
            },
        ) from exc


@router.get("/local/naver-session-cache", response_model=ModuleResponse)
def read_cached_local_naver_session() -> ModuleResponse:
    return ModuleResponse(result=read_cached_session_summary())


@router.post("/local/naver-session-cache/load", response_model=ModuleResponse)
def load_cached_local_naver_session(payload: ModuleRequest) -> ModuleResponse:
    try:
        return ModuleResponse(result=load_cached_session_payload())
    except LocalLoginBrowserError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                **exc.to_detail(),
            },
        ) from exc
