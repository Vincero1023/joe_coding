from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_LOGIN_TARGET_URL = "https://creator-advisor.naver.com/naver_blog/goodbuy40/trends"
_COOKIE_NAMES = ("NID_AUT", "NID_SES", "NID_JKL", "NNB")
_SESSION_DIR = Path(".local") / "naver_playwright"
_SESSION_CACHE_FILE = _SESSION_DIR / "naver_creator_session.json"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LoginBrowserAttempt:
    browser: str
    status: str
    detail: str
    hint: str | None = None


class LocalLoginBrowserError(RuntimeError):
    """Raised when the dedicated local login browser flow fails."""

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        attempts: list[LoginBrowserAttempt] | None = None,
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.attempts = attempts or []

    def to_detail(self) -> dict[str, Any]:
        return {
            "hint": self.hint,
            "attempts": [
                {
                    "browser": attempt.browser,
                    "status": attempt.status,
                    "detail": attempt.detail,
                    "hint": attempt.hint,
                }
                for attempt in self.attempts
            ],
        }


class LocalNaverLoginBrowserService:
    def open_and_capture_session(
        self,
        *,
        browser: str = "edge",
        timeout_seconds: int = 300,
        allow_subprocess_fallback: bool = True,
    ) -> dict[str, Any]:
        channels = _resolve_channel_order(browser)
        attempts: list[LoginBrowserAttempt] = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise LocalLoginBrowserError(
                "playwright가 설치되어 있지 않습니다.",
                hint="`pip install -r requirements.txt`를 실행한 뒤 다시 시도해 주세요.",
            ) from exc

        try:
            with sync_playwright() as playwright:
                for channel in channels:
                    try:
                        cookie_pairs = self._launch_and_capture(
                            playwright=playwright,
                            channel=channel,
                            timeout_seconds=timeout_seconds,
                        )
                    except LocalLoginBrowserError as exc:
                        exc.attempts = attempts + exc.attempts
                        raise exc
                    except Exception as exc:  # pragma: no cover - browser runtime dependent
                        detail, hint = _classify_launch_error(channel, exc)
                        attempts.append(
                            LoginBrowserAttempt(
                                browser=channel,
                                status="error",
                                detail=detail,
                                hint=hint,
                            )
                        )
                        continue

                    cookie_header = "; ".join(f"{name}={value}" for name, value in cookie_pairs)
                    payload = {
                        "browser": channel,
                        "cookie_header": cookie_header,
                        "cookie_names": [name for name, _ in cookie_pairs],
                        "cookie_count": len(cookie_pairs),
                        "target_url": _LOGIN_TARGET_URL,
                        "profile_dir": str(_profile_dir_for_channel(channel)),
                        "saved_at": int(time.time()),
                        "attempts": [
                            {
                                "browser": attempt.browser,
                                "status": attempt.status,
                                "detail": attempt.detail,
                                "hint": attempt.hint,
                            }
                            for attempt in attempts
                        ]
                        + [{"browser": channel, "status": "success", "detail": "Loaded.", "hint": None}],
                    }
                    _SESSION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    _SESSION_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    return payload

                raise LocalLoginBrowserError(
                    "전용 로그인 브라우저를 실행하지 못했습니다.",
                    hint="Edge가 안 되면 Chrome을 선택해 다시 시도하고, 둘 다 안 되면 `python -m playwright install chromium`를 실행해 주세요.",
                    attempts=attempts,
                )
        except LocalLoginBrowserError:
            raise
        except Exception as exc:  # pragma: no cover - depends on local browser/runtime
            detail, hint = _classify_playwright_startup_error(exc)
            attempts.append(
                LoginBrowserAttempt(
                    browser="playwright",
                    status="error",
                    detail=detail,
                    hint=hint,
                )
            )
            if allow_subprocess_fallback:
                return self._capture_session_in_subprocess(
                    browser=browser,
                    timeout_seconds=timeout_seconds,
                    prior_attempts=attempts,
                )
            raise LocalLoginBrowserError(
                "전용 로그인 브라우저를 초기화하지 못했습니다.",
                hint=hint
                or "`python -m playwright install chromium`를 실행한 뒤 서버를 다시 시작해 주세요.",
                attempts=attempts,
            ) from exc

    def _capture_session_in_subprocess(
        self,
        *,
        browser: str,
        timeout_seconds: int,
        prior_attempts: list[LoginBrowserAttempt],
    ) -> dict[str, Any]:
        command = [
            sys.executable,
            "-m",
            "app.local.naver_login_worker",
            "--browser",
            browser,
            "--timeout-seconds",
            str(timeout_seconds),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                cwd=str(_PROJECT_ROOT),
                timeout=max(120, timeout_seconds + 30),
            )
        except subprocess.TimeoutExpired as exc:
            raise LocalLoginBrowserError(
                "전용 로그인 브라우저 보조 프로세스가 제한 시간 안에 끝나지 않았습니다.",
                hint="열린 브라우저 창에서 로그인 중이라면 조금 더 기다린 뒤 다시 시도해 주세요.",
                attempts=prior_attempts
                + [
                    LoginBrowserAttempt(
                        browser="subprocess",
                        status="timeout",
                        detail=f"Timed out after {int(exc.timeout or timeout_seconds)} seconds.",
                        hint="보조 프로세스가 응답을 마칠 때까지 시간이 더 필요했습니다.",
                    )
                ],
            ) from exc

        payload = _try_parse_json_payload(_decode_subprocess_output(completed.stdout))
        subprocess_attempts = _deserialize_attempts(payload.get("attempts") if isinstance(payload, dict) else None)

        if completed.returncode == 0 and isinstance(payload, dict):
            payload["attempts"] = _serialize_attempts(prior_attempts + subprocess_attempts)
            return payload

        stderr_message = _decode_subprocess_output(completed.stderr)
        attempts = prior_attempts + subprocess_attempts
        if stderr_message:
            attempts.append(
                LoginBrowserAttempt(
                    browser="subprocess",
                    status="error",
                    detail=stderr_message.splitlines()[-1],
                    hint="보조 프로세스 표준 오류 로그를 확인해 주세요.",
                )
            )

        detail_message = payload.get("message") if isinstance(payload, dict) else ""
        detail_hint = payload.get("hint") if isinstance(payload, dict) else None
        raise LocalLoginBrowserError(
            detail_message or "전용 로그인 브라우저 보조 프로세스를 실행하지 못했습니다.",
            hint=detail_hint
            or "직접 Python에서 Playwright를 띄우기 어려운 환경이라 보조 프로세스로 재시도했지만 실패했습니다.",
            attempts=attempts,
        )

    def _launch_and_capture(
        self,
        *,
        playwright: Any,
        channel: str,
        timeout_seconds: int,
    ) -> list[tuple[str, str]]:
        profile_dir = _profile_dir_for_channel(channel)
        profile_dir.mkdir(parents=True, exist_ok=True)

        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(profile_dir),
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if channel != "chromium":
            launch_kwargs["channel"] = channel

        context = playwright.chromium.launch_persistent_context(**launch_kwargs)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(_LOGIN_TARGET_URL, wait_until="domcontentloaded")
            page.bring_to_front()
            return self._wait_for_naver_session(
                context=context,
                timeout_seconds=timeout_seconds,
                channel=channel,
            )
        finally:
            context.close()

    def _wait_for_naver_session(
        self,
        *,
        context: Any,
        timeout_seconds: int,
        channel: str,
    ) -> list[tuple[str, str]]:
        deadline = time.time() + max(30, timeout_seconds)

        while time.time() < deadline:
            cookies = context.cookies(
                [
                    "https://naver.com",
                    "https://nid.naver.com",
                    "https://creator-advisor.naver.com",
                ]
            )
            cookie_map = {
                str(item.get("name")): str(item.get("value"))
                for item in cookies
                if item.get("name") in _COOKIE_NAMES and item.get("value")
            }
            if "NID_AUT" in cookie_map and "NID_SES" in cookie_map:
                return [(name, cookie_map[name]) for name in _COOKIE_NAMES if name in cookie_map]

            time.sleep(1.0)

        raise LocalLoginBrowserError(
            f"{channel} 전용 로그인 브라우저에서 제한 시간 안에 네이버 세션 쿠키를 확인하지 못했습니다.",
            hint="열린 브라우저 창에서 네이버 로그인과 Creator Advisor 접속을 완료한 뒤, 창이 유지된 상태로 기다려 주세요.",
            attempts=[
                LoginBrowserAttempt(
                    browser=channel,
                    status="timeout",
                    detail="Timed out waiting for Naver session cookies.",
                    hint="로그인 후 Creator Advisor 페이지가 실제로 열린 상태인지 확인해 주세요.",
                )
            ],
        )


def read_cached_session_summary(session_cache_file: Path | None = None) -> dict[str, Any]:
    target_file = session_cache_file or _SESSION_CACHE_FILE
    empty_summary = {
        "available": False,
        "browser": "",
        "cookie_count": 0,
        "cookie_names": [],
        "saved_at": 0,
        "target_url": "",
        "profile_dir": "",
    }

    if not target_file.exists():
        return empty_summary

    try:
        payload = json.loads(target_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_summary

    cookie_header = str(payload.get("cookie_header") or "").strip()
    cookie_names = payload.get("cookie_names")
    if not isinstance(cookie_names, list):
        cookie_names = []

    try:
        cookie_count = int(payload.get("cookie_count") or 0)
    except (TypeError, ValueError):
        cookie_count = 0
    if cookie_count <= 0 and cookie_header:
        cookie_count = max(1, len(cookie_names))

    try:
        saved_at = int(payload.get("saved_at") or 0)
    except (TypeError, ValueError):
        saved_at = 0

    return {
        "available": bool(cookie_header),
        "browser": str(payload.get("browser") or "").strip(),
        "cookie_count": cookie_count,
        "cookie_names": [str(name).strip() for name in cookie_names if str(name).strip()],
        "saved_at": saved_at,
        "target_url": str(payload.get("target_url") or "").strip(),
        "profile_dir": str(payload.get("profile_dir") or "").strip(),
    }


def _profile_dir_for_channel(channel: str) -> Path:
    return _SESSION_DIR / channel.replace("-", "_")


def _resolve_channel_order(browser: str) -> tuple[str, ...]:
    normalized = str(browser or "").strip().lower()
    if normalized in {"edge", "msedge", "auto", ""}:
        return ("msedge", "chrome", "chromium")
    if normalized == "chrome":
        return ("chrome", "msedge", "chromium")
    raise LocalLoginBrowserError(
        f"지원하지 않는 전용 로그인 브라우저입니다: {browser}",
        hint="현재는 Edge 또는 Chrome만 지원합니다.",
    )


def _classify_launch_error(channel: str, exc: Exception) -> tuple[str, str | None]:
    message = str(exc).strip() or exc.__class__.__name__
    normalized = message.lower()

    if isinstance(exc, NotImplementedError):
        return (
            message,
            f"{channel} 채널 실행이 이 환경에서 지원되지 않아 다음 브라우저로 자동 재시도합니다.",
        )
    if "executable doesn't exist" in normalized or "browserType.launch".lower() in normalized:
        return (
            message,
            f"{channel} 브라우저 실행 파일을 찾지 못했습니다. 설치 여부를 확인하거나 `python -m playwright install chromium`를 실행해 주세요.",
        )
    if "target page, context or browser has been closed" in normalized:
        return (
            message,
            "브라우저가 바로 종료되었습니다. 다른 Chromium 계열 브라우저로 다시 시도합니다.",
        )

    return (message, None)


def _classify_playwright_startup_error(exc: Exception) -> tuple[str, str | None]:
    message = str(exc).strip() or exc.__class__.__name__
    normalized = message.lower()

    if isinstance(exc, NotImplementedError):
        return (
            message,
            "Playwright 초기화가 바로 실패했습니다. 서버를 다시 시작하고, 계속 같으면 관리자 권한 실행이나 `python -m playwright install chromium`를 시도해 주세요.",
        )
    if "driver" in normalized or "playwright" in normalized or "node" in normalized:
        return (
            message,
            "`python -m playwright install chromium`를 실행한 뒤 서버를 다시 시작해 주세요.",
        )

    return (message, None)


def _try_parse_json_payload(raw_text: str | None) -> dict[str, Any] | None:
    if not raw_text:
        return None

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict):
        return payload
    return None


def _decode_subprocess_output(raw_output: bytes | str | None) -> str:
    if raw_output is None:
        return ""
    if isinstance(raw_output, str):
        return raw_output.strip()
    if not raw_output:
        return ""

    for encoding in ("utf-8", "cp949", sys.getdefaultencoding()):
        try:
            return raw_output.decode(encoding).strip()
        except UnicodeDecodeError:
            continue

    return raw_output.decode("utf-8", errors="replace").strip()


def _serialize_attempts(attempts: list[LoginBrowserAttempt]) -> list[dict[str, Any]]:
    return [
        {
            "browser": attempt.browser,
            "status": attempt.status,
            "detail": attempt.detail,
            "hint": attempt.hint,
        }
        for attempt in attempts
    ]


def _deserialize_attempts(raw_attempts: Any) -> list[LoginBrowserAttempt]:
    if not isinstance(raw_attempts, list):
        return []

    attempts: list[LoginBrowserAttempt] = []
    for item in raw_attempts:
        if not isinstance(item, dict):
            continue
        attempts.append(
            LoginBrowserAttempt(
                browser=str(item.get("browser") or "unknown"),
                status=str(item.get("status") or "error"),
                detail=str(item.get("detail") or ""),
                hint=str(item.get("hint")) if item.get("hint") is not None else None,
            )
        )
    return attempts
