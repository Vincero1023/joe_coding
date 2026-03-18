from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any, Callable


_NAVER_COOKIE_NAMES = ("NID_AUT", "NID_SES", "NID_JKL", "NNB")
_NAVER_DOMAINS = ("naver.com", ".naver.com", "creator-advisor.naver.com", "nid.naver.com")
_BROWSER_ORDER = ("edge", "chrome", "firefox")


@dataclass(frozen=True)
class BrowserAttempt:
    browser: str
    status: str
    detail: str
    hint: str | None = None


class LocalBrowserCookieError(RuntimeError):
    """Raised when browser cookies cannot be loaded from the local machine."""

    def __init__(
        self,
        message: str,
        *,
        attempts: list[BrowserAttempt] | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts or []
        self.hint = hint

    def to_detail(self) -> dict[str, Any]:
        return {
            "attempts": [
                {
                    "browser": attempt.browser,
                    "status": attempt.status,
                    "detail": attempt.detail,
                    "hint": attempt.hint,
                }
                for attempt in self.attempts
            ],
            "hint": self.hint,
        }


BrowserLoader = Callable[[str, str], CookieJar]


class LocalNaverSessionService:
    def __init__(self, browser_loader: BrowserLoader | None = None) -> None:
        self._browser_loader = browser_loader or _load_browser_cookiejar

    def load_session(self, browser: str = "auto") -> dict[str, Any]:
        requested_browser = _normalize_browser(browser)
        attempts: list[BrowserAttempt] = []

        for candidate in _resolve_browser_order(requested_browser):
            try:
                cookiejar = self._browser_loader(candidate, ".naver.com")
                cookie_pairs = _extract_cookie_pairs(cookiejar)
            except Exception as exc:
                detail, hint = _classify_cookie_error(exc)
                attempts.append(
                    BrowserAttempt(
                        browser=candidate,
                        status="error",
                        detail=detail,
                        hint=hint,
                    )
                )
                continue

            if not cookie_pairs:
                attempts.append(
                    BrowserAttempt(
                        browser=candidate,
                        status="empty",
                        detail="네이버 로그인 쿠키를 찾지 못했습니다.",
                        hint="브라우저에서 네이버 로그인 후 Creator Advisor 탭을 한 번 연 다음 다시 시도해 보세요.",
                    )
                )
                continue

            return {
                "browser": candidate,
                "cookie_header": "; ".join(f"{name}={value}" for name, value in cookie_pairs),
                "cookie_names": [name for name, _ in cookie_pairs],
                "cookie_count": len(cookie_pairs),
                "attempts": [
                    {
                        "browser": attempt.browser,
                        "status": attempt.status,
                        "detail": attempt.detail,
                        "hint": attempt.hint,
                    }
                    for attempt in attempts
                ]
                + [{"browser": candidate, "status": "success", "detail": "Loaded.", "hint": None}],
            }

        raise LocalBrowserCookieError(
            "로컬 브라우저에서 Creator Advisor용 네이버 로그인 쿠키를 찾지 못했습니다.",
            attempts=attempts,
            hint=_build_global_hint(attempts),
        )


def _load_browser_cookiejar(browser: str, domain_name: str) -> CookieJar:
    try:
        import browser_cookie3  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise LocalBrowserCookieError(
            "browser-cookie3가 설치되어 있지 않습니다.",
            hint="`pip install -r requirements.txt`를 먼저 실행해 주세요.",
        ) from exc

    browser_map = {
        "edge": browser_cookie3.edge,
        "chrome": browser_cookie3.chrome,
        "firefox": browser_cookie3.firefox,
    }
    loader = browser_map.get(browser)
    if loader is None:
        raise LocalBrowserCookieError(f"지원하지 않는 브라우저입니다: {browser}")

    return loader(domain_name=domain_name)


def _extract_cookie_pairs(cookiejar: CookieJar) -> list[tuple[str, str]]:
    candidates: dict[str, str] = {}
    for cookie in _iter_cookies(cookiejar):
        domain = str(getattr(cookie, "domain", "") or "").lower()
        name = str(getattr(cookie, "name", "") or "").strip()
        value = str(getattr(cookie, "value", "") or "")
        if not name or not value:
            continue
        if name not in _NAVER_COOKIE_NAMES:
            continue
        if not any(allowed in domain for allowed in _NAVER_DOMAINS):
            continue
        candidates[name] = value

    return [(name, candidates[name]) for name in _NAVER_COOKIE_NAMES if name in candidates]


def _iter_cookies(cookiejar: CookieJar) -> Iterable[Any]:
    try:
        return list(cookiejar)
    except TypeError:  # pragma: no cover - defensive only
        return []


def _normalize_browser(browser: str) -> str:
    normalized = str(browser or "").strip().lower()
    allowed = {"auto", *_BROWSER_ORDER}
    return normalized if normalized in allowed else "auto"


def _resolve_browser_order(browser: str) -> tuple[str, ...]:
    if browser == "auto":
        return _BROWSER_ORDER
    return (browser,)


def _classify_cookie_error(exc: Exception) -> tuple[str, str | None]:
    message = str(exc).strip() or exc.__class__.__name__
    normalized = message.lower()

    if "requires admin" in normalized or "permission denied" in normalized:
        return (
            message,
            "브라우저 창을 모두 완전히 종료한 뒤 다시 시도하거나, 필요하면 이 앱을 관리자 권한으로 실행해 보세요.",
        )
    if "could not find firefox profile directory" in normalized:
        return (
            message,
            "이 PC에서 Firefox 프로필을 찾지 못했습니다. Edge나 Chrome을 선택해 보세요.",
        )
    if "install" in normalized and "browser-cookie3" in normalized:
        return (
            message,
            "`pip install -r requirements.txt`로 의존성을 먼저 설치해 주세요.",
        )

    return (message, None)


def _build_global_hint(attempts: list[BrowserAttempt]) -> str:
    if any(attempt.hint and "관리자" in attempt.hint for attempt in attempts):
        return "현재는 브라우저 쿠키 DB 접근 권한 때문에 막히고 있습니다. Edge/Chrome 창을 모두 끈 뒤 다시 시도해 보세요."
    if any(attempt.browser in {"edge", "chrome"} for attempt in attempts):
        return "네이버 로그인은 되어 있어도 브라우저 쿠키 파일이 잠겨 있으면 읽을 수 없습니다. 브라우저 완전 종료 후 다시 시도해 보세요."
    return "브라우저 로그인 상태와 Creator Advisor 접속 여부를 다시 확인해 주세요."
