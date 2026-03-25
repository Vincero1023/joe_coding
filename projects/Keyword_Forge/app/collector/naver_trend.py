from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.core.runtime_settings import report_naver_auth_error
from app.expander.utils.throttle import wait_for_naver_keyword_request


_API_BASE = "https://creator-advisor.naver.com/api/v6"
_DEFAULT_TIMEOUT = 8.0
_KST = ZoneInfo("Asia/Seoul")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_SESSION_CACHE_FILE = _PROJECT_ROOT / ".local" / "naver_playwright" / "naver_creator_session.json"


class NaverTrendError(RuntimeError):
    """Base exception for Creator Advisor trend collection errors."""


class NaverTrendAuthError(NaverTrendError):
    """Raised when Creator Advisor authentication is missing or invalid."""


class NaverTrendCategoryNotFoundError(NaverTrendError):
    """Raised when the requested trend topic cannot be mapped to a category id."""


class NaverTrendResponseError(NaverTrendError):
    """Raised when Creator Advisor returns an unexpected response."""


@dataclass(frozen=True)
class NaverTrendOptions:
    service: str = "naver_blog"
    content_type: str = "text"
    date: str = ""
    auth_cookie: str = ""
    limit: int = 20
    fallback_to_preset_search: bool = True

    @classmethod
    def from_dict(cls, raw: Any) -> "NaverTrendOptions":
        if not isinstance(raw, dict):
            raw = {}

        limit = raw.get("limit", 20)
        try:
            normalized_limit = max(1, min(50, int(limit)))
        except (TypeError, ValueError):
            normalized_limit = 20

        return cls(
            service=str(raw.get("service") or "naver_blog").strip() or "naver_blog",
            content_type=str(raw.get("content_type") or "text").strip() or "text",
            date=str(raw.get("date") or "").strip(),
            auth_cookie=str(raw.get("auth_cookie") or raw.get("cookie") or "").strip(),
            limit=normalized_limit,
            fallback_to_preset_search=bool(raw.get("fallback_to_preset_search", False)),
        )

    @property
    def resolved_date(self) -> str:
        return resolve_trend_date(self.date)


@dataclass(frozen=True)
class NaverTrendKeyword:
    query: str
    rank: int | None
    rank_change: int | str | None


@dataclass(frozen=True)
class NaverTrendCategoryResult:
    topic_name: str
    topic_id: str
    service: str
    content_type: str
    date: str
    keywords: tuple[NaverTrendKeyword, ...]


JsonFetcher = Callable[[str, dict[str, Any], str], Any]


class NaverTrendClient:
    def __init__(
        self,
        *,
        json_fetcher: JsonFetcher | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._json_fetcher = json_fetcher or self._fetch_json
        self._timeout = timeout

    def collect_category_keywords(
        self,
        *,
        topic_name: str,
        options: NaverTrendOptions,
    ) -> NaverTrendCategoryResult:
        auth_candidates = _build_auth_cookie_candidates(options.auth_cookie)
        if not auth_candidates:
            raise NaverTrendAuthError("Creator Advisor 인증 쿠키가 필요합니다.")

        last_auth_error: NaverTrendAuthError | None = None

        for auth_cookie in auth_candidates:
            try:
                category_payload = self._json_fetcher(
                    f"/accounts/preferred-category/{options.service}",
                    {"contentType": options.content_type},
                    auth_cookie,
                )
                topic_id = _resolve_topic_id(category_payload, topic_name)

                trend_date = options.resolved_date
                keywords: tuple[NaverTrendKeyword, ...] = ()
                for candidate_date in _iter_trend_date_candidates(trend_date):
                    trend_payload = self._json_fetcher(
                        "/trend/category",
                        {
                            "service": options.service,
                            "categories": topic_id,
                            "contentType": options.content_type,
                            "interval": "day",
                            "date": candidate_date,
                            "hasRankChange": "true",
                            "limit": options.limit,
                        },
                        auth_cookie,
                    )
                    keywords = _extract_keywords(trend_payload, topic_id)
                    if keywords:
                        trend_date = candidate_date
                        break
            except NaverTrendAuthError as exc:
                last_auth_error = exc
                continue

            return NaverTrendCategoryResult(
                topic_name=topic_name,
                topic_id=topic_id,
                service=options.service,
                content_type=options.content_type,
                date=trend_date,
                keywords=keywords,
            )

        if last_auth_error is not None:
            raise last_auth_error
        raise NaverTrendAuthError("Creator Advisor 인증 쿠키가 필요합니다.")

    def _fetch_json(
        self,
        endpoint: str,
        params: dict[str, Any],
        auth_cookie: str,
    ) -> Any:
        query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
        url = f"{_API_BASE}{endpoint}"
        if query:
            url = f"{url}?{query}"

        wait_for_naver_keyword_request()
        request = Request(
            url=url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Cookie": auth_cookie,
                "Referer": "https://creator-advisor.naver.com/naver_blog/goodbuy40/trends",
                "Origin": "https://creator-advisor.naver.com",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/145.0.0.0 Safari/537.36"
                ),
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = response.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="ignore")
            message = _extract_error_message(payload) or _default_http_error_message(exc.code)
            if exc.code in {401, 403}:
                report_naver_auth_error(message)
                raise NaverTrendAuthError(message) from exc
            raise NaverTrendResponseError(message) from exc
        except URLError as exc:
            raise NaverTrendResponseError(f"Creator Advisor 연결에 실패했습니다: {exc.reason}") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise NaverTrendResponseError("Creator Advisor 응답을 JSON으로 해석하지 못했습니다.") from exc


def resolve_trend_date(raw_date: str) -> str:
    normalized = str(raw_date or "").strip()
    if not normalized:
        return datetime.now(_KST).date().isoformat()

    try:
        return datetime.strptime(normalized, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise NaverTrendError("trend date는 YYYY-MM-DD 형식이어야 합니다.") from exc


def _resolve_topic_id(payload: Any, topic_name: str) -> str:
    root = _unwrap_payload(payload)
    category_tree = root.get("categoryTree")
    if not isinstance(category_tree, list):
        raise NaverTrendResponseError("Creator Advisor categoryTree 응답 형식이 올바르지 않습니다.")

    normalized_topic = _normalize_topic_key(topic_name)

    for group in category_tree:
        categories = group.get("categories")
        if not isinstance(categories, list):
            continue

        for category in categories:
            category_id = category.get("id")
            category_name = category.get("name")
            if not category_id or not category_name:
                continue
            if _normalize_topic_key(str(category_name)) == normalized_topic:
                return str(category_id)

    raise NaverTrendCategoryNotFoundError(
        f"Creator Advisor 주제 목록에서 '{topic_name}' 항목을 찾지 못했습니다."
    )


def _extract_keywords(payload: Any, topic_id: str) -> tuple[NaverTrendKeyword, ...]:
    root = _unwrap_payload(payload)
    data = root.get("data", root)
    if not isinstance(data, list):
        raise NaverTrendResponseError("Creator Advisor trend/category 응답 형식이 올바르지 않습니다.")

    matched_group: dict[str, Any] | None = None
    for item in data:
        if str(item.get("category")) == str(topic_id):
            matched_group = item
            break

    if matched_group is None and len(data) == 1 and isinstance(data[0], dict):
        matched_group = data[0]

    if matched_group is None:
        return ()

    query_list = matched_group.get("queryList")
    if not isinstance(query_list, list):
        return ()

    keywords: list[NaverTrendKeyword] = []
    for item in query_list:
        query = str(item.get("query") or "").strip()
        if not query:
            continue

        rank = item.get("rank")
        try:
            normalized_rank = int(rank) if rank is not None else None
        except (TypeError, ValueError):
            normalized_rank = None

        rank_change = item.get("rankChange")
        if isinstance(rank_change, (int, str)) or rank_change is None:
            normalized_change = rank_change
        else:
            normalized_change = None

        keywords.append(
            NaverTrendKeyword(
                query=query,
                rank=normalized_rank,
                rank_change=normalized_change,
            )
        )

    return tuple(keywords)


def _unwrap_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise NaverTrendResponseError("Creator Advisor 응답 형식이 올바르지 않습니다.")

    data = payload.get("data")
    if isinstance(data, dict) and any(key in data for key in ("categoryTree", "category")):
        return data
    return payload


def _extract_error_message(payload: str) -> str | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        message = parsed.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        error = parsed.get("error")
        if isinstance(error, dict):
            nested_message = error.get("message")
            if isinstance(nested_message, str) and nested_message.strip():
                return nested_message.strip()

    return None


def _default_http_error_message(status_code: int) -> str:
    if status_code in {401, 403}:
        return "Creator Advisor가 현재 로그인 세션을 거부했습니다. 전용 로그인 브라우저로 다시 로그인한 뒤 재시도해 주세요."
    return f"Creator Advisor 요청이 실패했습니다. ({status_code})"


def _build_auth_cookie_candidates(primary_cookie: str) -> tuple[str, ...]:
    candidates: list[str] = []
    normalized_primary = str(primary_cookie or "").strip()
    if normalized_primary:
        candidates.append(normalized_primary)

    cached_cookie = _load_cached_auth_cookie()
    if cached_cookie and cached_cookie not in candidates:
        candidates.append(cached_cookie)

    return tuple(candidates)


def _iter_trend_date_candidates(base_date: str, *, lookback_days: int = 3) -> tuple[str, ...]:
    start_date = datetime.strptime(base_date, "%Y-%m-%d").date()
    return tuple((start_date - timedelta(days=offset)).isoformat() for offset in range(max(1, lookback_days + 1)))


def _load_cached_auth_cookie() -> str:
    if not _LOCAL_SESSION_CACHE_FILE.exists():
        return ""

    try:
        payload = json.loads(_LOCAL_SESSION_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""

    cookie_header = payload.get("cookie_header")
    if not isinstance(cookie_header, str):
        return ""
    return cookie_header.strip()


def _normalize_topic_key(value: str) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())
