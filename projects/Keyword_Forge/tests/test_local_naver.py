import sys
import json
from http.cookiejar import Cookie, CookieJar
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.local.naver_login_browser import (
    LocalLoginBrowserError,
    LocalNaverLoginBrowserService,
    read_cached_session_summary,
)
from app.local.naver_session import LocalBrowserCookieError, LocalNaverSessionService
from app.main import app


client = TestClient(app)


def _build_cookie(name: str, value: str, domain: str = ".naver.com") -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=domain.startswith("."),
        path="/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def test_local_naver_session_service_uses_first_browser_with_valid_cookies() -> None:
    def fake_loader(browser: str, domain_name: str) -> CookieJar:
        jar = CookieJar()
        if browser == "chrome":
            jar.set_cookie(_build_cookie("NID_AUT", "aut-token"))
            jar.set_cookie(_build_cookie("NID_SES", "ses-token"))
        return jar

    service = LocalNaverSessionService(browser_loader=fake_loader)
    result = service.load_session(browser="auto")

    assert result["browser"] == "chrome"
    assert result["cookie_count"] == 2
    assert "NID_AUT=aut-token" in result["cookie_header"]
    assert "NID_SES=ses-token" in result["cookie_header"]


def test_local_naver_session_endpoint_returns_loaded_cookie_header() -> None:
    with patch(
        "app.api.routes.local_naver.service.load_session",
        return_value={
            "browser": "edge",
            "cookie_header": "NID_AUT=test; NID_SES=session",
            "cookie_names": ["NID_AUT", "NID_SES"],
            "cookie_count": 2,
            "attempts": [{"browser": "edge", "status": "success", "detail": "Loaded."}],
        },
    ):
        response = client.post("/local/naver-session", json={"input_data": {"browser": "edge"}})

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["browser"] == "edge"
    assert result["cookie_count"] == 2
    assert "NID_AUT=test" in result["cookie_header"]


def test_local_naver_session_endpoint_returns_attempts_on_failure() -> None:
    with patch(
        "app.api.routes.local_naver.service.load_session",
        side_effect=LocalBrowserCookieError(
            "로컬 브라우저에서 Creator Advisor용 네이버 로그인 쿠키를 찾지 못했습니다.",
            attempts=[],
            hint="브라우저를 모두 종료한 뒤 다시 시도해 보세요.",
        ),
    ):
        response = client.post("/local/naver-session", json={"input_data": {"browser": "edge"}})

    assert response.status_code == 400
    payload = response.json()["error"]
    assert payload["message"] == "로컬 브라우저에서 Creator Advisor용 네이버 로그인 쿠키를 찾지 못했습니다."
    assert payload["detail"]["hint"] == "브라우저를 모두 종료한 뒤 다시 시도해 보세요."


def test_local_naver_login_browser_endpoint_returns_cookie_header() -> None:
    with patch(
        "app.api.routes.local_naver.login_browser_service.open_and_capture_session",
        return_value={
            "browser": "msedge",
            "cookie_header": "NID_AUT=test; NID_SES=session",
            "cookie_names": ["NID_AUT", "NID_SES"],
            "cookie_count": 2,
            "target_url": "https://creator-advisor.naver.com/naver_blog/goodbuy40/trends",
        },
    ):
        response = client.post("/local/naver-login-browser", json={"input_data": {"browser": "edge"}})

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["browser"] == "msedge"
    assert "NID_SES=session" in result["cookie_header"]


def test_local_naver_login_browser_endpoint_preserves_error_hint() -> None:
    with patch(
        "app.api.routes.local_naver.login_browser_service.open_and_capture_session",
        side_effect=LocalLoginBrowserError(
            "msedge 전용 로그인 브라우저에서 제한 시간 안에 네이버 세션 쿠키를 확인하지 못했습니다.",
            hint="열린 브라우저 창에서 네이버 로그인과 Creator Advisor 접속을 완료한 뒤 기다려 주세요.",
        ),
    ):
        response = client.post("/local/naver-login-browser", json={"input_data": {"browser": "edge"}})

    assert response.status_code == 400
    payload = response.json()["error"]
    assert payload["message"] == "msedge 전용 로그인 브라우저에서 제한 시간 안에 네이버 세션 쿠키를 확인하지 못했습니다."
    assert payload["detail"]["hint"] == "열린 브라우저 창에서 네이버 로그인과 Creator Advisor 접속을 완료한 뒤 기다려 주세요."


def test_read_cached_session_summary_returns_saved_metadata(tmp_path) -> None:
    session_file = tmp_path / "naver_creator_session.json"
    session_file.write_text(
        json.dumps(
            {
                "browser": "chrome",
                "cookie_header": "NID_AUT=test; NID_SES=session",
                "cookie_names": ["NID_AUT", "NID_SES"],
                "cookie_count": 2,
                "saved_at": 1774101314,
                "target_url": "https://creator-advisor.naver.com/naver_blog/goodbuy40/trends",
                "profile_dir": "F:/tmp/profile",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = read_cached_session_summary(session_file)

    assert result["available"] is True
    assert result["browser"] == "chrome"
    assert result["cookie_count"] == 2
    assert result["cookie_names"] == ["NID_AUT", "NID_SES"]
    assert result["saved_at"] == 1774101314


def test_local_naver_session_cache_endpoint_returns_cached_summary() -> None:
    with patch(
        "app.api.routes.local_naver.read_cached_session_summary",
        return_value={
            "available": True,
            "browser": "chrome",
            "cookie_count": 3,
            "cookie_names": ["NID_AUT", "NID_SES", "NNB"],
            "saved_at": 1774101314,
            "target_url": "https://creator-advisor.naver.com/naver_blog/goodbuy40/trends",
            "profile_dir": "F:/tmp/profile",
        },
    ):
        response = client.get("/local/naver-session-cache")

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["available"] is True
    assert result["browser"] == "chrome"
    assert result["cookie_count"] == 3


def test_local_naver_login_browser_session_paths_use_project_root() -> None:
    from app.local import naver_login_browser

    expected_root = Path(naver_login_browser.__file__).resolve().parents[2]

    assert naver_login_browser._SESSION_DIR == expected_root / ".local" / "naver_playwright"
    assert naver_login_browser._SESSION_CACHE_FILE == expected_root / ".local" / "naver_playwright" / "naver_creator_session.json"


def test_local_naver_login_browser_service_wraps_playwright_startup_error() -> None:
    fake_module = ModuleType("playwright.sync_api")

    def failing_sync_playwright():
        raise NotImplementedError

    fake_module.sync_playwright = failing_sync_playwright  # type: ignore[attr-defined]
    service = LocalNaverLoginBrowserService()

    with patch.dict(sys.modules, {"playwright.sync_api": fake_module}):
        with pytest.raises(LocalLoginBrowserError) as exc_info:
            service.open_and_capture_session(
                browser="edge",
                timeout_seconds=1,
                allow_subprocess_fallback=False,
            )

    exc = exc_info.value
    assert str(exc) == "전용 로그인 브라우저를 초기화하지 못했습니다."
    assert exc.hint is not None
    assert exc.attempts[0].browser == "playwright"
    assert exc.attempts[0].detail == "NotImplementedError"


def test_local_naver_login_browser_service_falls_back_to_subprocess_worker() -> None:
    fake_module = ModuleType("playwright.sync_api")

    def failing_sync_playwright():
        raise NotImplementedError

    fake_module.sync_playwright = failing_sync_playwright  # type: ignore[attr-defined]
    service = LocalNaverLoginBrowserService()
    subprocess_payload = {
        "browser": "chromium",
        "cookie_header": "NID_AUT=test; NID_SES=session",
        "cookie_names": ["NID_AUT", "NID_SES"],
        "cookie_count": 2,
        "target_url": "https://creator-advisor.naver.com/naver_blog/goodbuy40/trends",
        "attempts": [{"browser": "chromium", "status": "success", "detail": "Loaded.", "hint": None}],
    }

    with patch.dict(sys.modules, {"playwright.sync_api": fake_module}):
        with patch(
            "app.local.naver_login_browser.subprocess.run",
            return_value=SimpleNamespace(
                returncode=0,
                stdout=json.dumps(subprocess_payload, ensure_ascii=False).encode("utf-8"),
                stderr=b"",
            ),
        ):
            result = service.open_and_capture_session(browser="edge", timeout_seconds=1)

    assert result["browser"] == "chromium"
    assert result["cookie_count"] == 2
    assert result["attempts"][0]["browser"] == "playwright"
    assert result["attempts"][1]["browser"] == "chromium"
