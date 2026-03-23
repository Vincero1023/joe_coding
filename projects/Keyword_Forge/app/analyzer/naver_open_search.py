from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.analyzer.keyword_stats import KeywordStats
from app.core.config import get_settings
from app.expander.utils.tokenizer import normalize_key, normalize_text
from app.analyzer.naver_searchad import _normalize_keyword_tool_hint


_BASE_URL = "https://openapi.naver.com"
_BLOG_SEARCH_URI = "/v1/search/blog.json"
_DEFAULT_TIMEOUT = 8.0
_DEFAULT_MAX_WORKERS = 6
_DEFAULT_CREDENTIALS_PATH = Path(".local") / "credentials" / "naver_search.credentials.json"
_LEGACY_CREDENTIALS_PATH = Path("naver_search.credentials.json")

UrlopenLike = Callable[..., Any]


class NaverOpenSearchError(RuntimeError):
    """Base exception for Naver Open Search requests."""


class NaverOpenSearchAuthError(NaverOpenSearchError):
    """Raised when Naver Open Search credentials are missing or rejected."""


class NaverOpenSearchResponseError(NaverOpenSearchError):
    """Raised when Naver Open Search returns an unexpected payload."""


@dataclass(frozen=True)
class NaverOpenSearchCredentials:
    client_id: str
    client_secret: str

    @classmethod
    def from_input(cls, input_data: Any) -> "NaverOpenSearchCredentials | None":
        root = input_data if isinstance(input_data, dict) else {}
        search_api = root.get("naver_search_api") if isinstance(root.get("naver_search_api"), dict) else {}
        settings = get_settings()
        file_values = _load_search_credentials_file(
            normalize_text(search_api.get("credentials_path"))
            or normalize_text(root.get("naver_search_credentials_path"))
        )

        client_id = (
            normalize_text(search_api.get("client_id"))
            or normalize_text(root.get("naver_search_client_id"))
            or normalize_text(file_values.get("client_id"))
            or normalize_text(settings.naver_search_client_id)
        )
        client_secret = (
            normalize_text(search_api.get("client_secret"))
            or normalize_text(root.get("naver_search_client_secret"))
            or normalize_text(file_values.get("client_secret"))
            or normalize_text(settings.naver_search_client_secret)
        )
        if not client_id or not client_secret:
            return None

        return cls(
            client_id=client_id,
            client_secret=client_secret,
        )


@dataclass(frozen=True)
class NaverOpenSearchSettings:
    enabled: bool = False
    timeout: float = _DEFAULT_TIMEOUT
    max_workers: int = _DEFAULT_MAX_WORKERS

    @classmethod
    def from_input(cls, input_data: Any) -> "NaverOpenSearchSettings":
        root = input_data if isinstance(input_data, dict) else {}
        search_api = root.get("naver_search_api") if isinstance(root.get("naver_search_api"), dict) else {}
        credentials = NaverOpenSearchCredentials.from_input(root)
        default_enabled = credentials is not None
        enabled = _coerce_bool(
            search_api.get("enabled"),
            root.get("naver_search_api_enabled"),
            default=default_enabled,
        )
        timeout = _coerce_float(
            search_api.get("timeout"),
            default=_DEFAULT_TIMEOUT,
            minimum=1.0,
            maximum=30.0,
        )
        max_workers = _coerce_int(
            search_api.get("max_workers"),
            default=_DEFAULT_MAX_WORKERS,
            minimum=1,
            maximum=12,
        )
        return cls(
            enabled=enabled,
            timeout=timeout,
            max_workers=max_workers,
        )


class NaverOpenSearchClient:
    def __init__(
        self,
        credentials: NaverOpenSearchCredentials,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        opener: UrlopenLike | None = None,
    ) -> None:
        self._credentials = credentials
        self._timeout = timeout
        self._opener = opener or urlopen

    def fetch_blog_totals(
        self,
        keywords: list[str],
        *,
        max_workers: int = _DEFAULT_MAX_WORKERS,
    ) -> dict[str, KeywordStats]:
        results: dict[str, KeywordStats] = {}
        pending_keywords: list[str] = []
        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            if not normalized_keyword:
                continue
            key = normalize_key(normalized_keyword)
            if not key or key in results:
                continue
            pending_keywords.append(normalized_keyword)

        if not pending_keywords:
            return results

        worker_count = max(1, min(max_workers, len(pending_keywords)))
        if worker_count == 1:
            for keyword in pending_keywords:
                item = self._fetch_blog_total(keyword)
                if item is not None:
                    results[normalize_key(keyword)] = item
            return results

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(self._fetch_blog_total, keyword): keyword
                for keyword in pending_keywords
            }
            for future in as_completed(future_map):
                keyword = future_map[future]
                item = future.result()
                if item is not None:
                    results[normalize_key(keyword)] = item
        return results

    def _fetch_blog_total(self, keyword: str) -> KeywordStats | None:
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            return None

        query_keyword = _normalize_keyword_tool_hint(normalized_keyword) or normalized_keyword

        payload = self._get_json(
            _BLOG_SEARCH_URI,
            query_params={
                "query": query_keyword,
                "display": "1",
                "start": "1",
                "sort": "sim",
            },
        )
        total = parse_blog_total_response(payload)
        return KeywordStats(
            keyword=normalized_keyword,
            blog_results=total,
            source="naver_blog_search",
        )

    def _get_json(self, uri: str, *, query_params: dict[str, str]) -> dict[str, Any]:
        query = urlencode(query_params)
        request = Request(
            url=f"{_BASE_URL}{uri}?{query}",
            headers={
                "Accept": "application/json",
                "X-Naver-Client-Id": self._credentials.client_id,
                "X-Naver-Client-Secret": self._credentials.client_secret,
            },
            method="GET",
        )

        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw_text = response.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            raw_text = exc.read().decode("utf-8", errors="ignore")
            detail = _extract_error_message(raw_text) or raw_text or str(exc.reason)
            if exc.code in {401, 403}:
                raise NaverOpenSearchAuthError(detail) from exc
            raise NaverOpenSearchResponseError(f"{exc.code} {detail}") from exc
        except URLError as exc:
            raise NaverOpenSearchResponseError(str(exc.reason)) from exc
        except Exception as exc:  # pragma: no cover - runtime guard
            raise NaverOpenSearchResponseError(str(exc)) from exc

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise NaverOpenSearchResponseError("Naver Open Search returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise NaverOpenSearchResponseError("Naver Open Search returned an unexpected payload.")
        return parsed


def build_blog_search_index(
    input_data: Any,
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
    client: NaverOpenSearchClient | Any | None = None,
) -> dict[str, KeywordStats]:
    settings = NaverOpenSearchSettings.from_input(input_data)
    if not settings.enabled:
        return {}

    credentials = NaverOpenSearchCredentials.from_input(input_data)
    if credentials is None:
        return {}

    pending_keywords = build_blog_search_requests(keywords, stats_index=stats_index)
    if not pending_keywords:
        return {}

    resolved_client = client or NaverOpenSearchClient(credentials, timeout=settings.timeout)
    try:
        return resolved_client.fetch_blog_totals(
            pending_keywords,
            max_workers=settings.max_workers,
        )
    except NaverOpenSearchError:
        return {}


def build_blog_search_requests(
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
) -> list[str]:
    requests: list[str] = []
    seen: set[str] = set()

    for keyword in _extract_keywords(keywords):
        key = normalize_key(keyword)
        if not key or key in seen:
            continue
        seen.add(key)

        existing = stats_index.get(key) if stats_index else None
        if existing is not None and (existing.blog_results or 0) > 0:
            continue

        requests.append(keyword)

    return requests


def parse_blog_total_response(payload: Any) -> float:
    if not isinstance(payload, dict):
        raise NaverOpenSearchResponseError("Naver blog search response must be an object.")

    try:
        return float(int(payload.get("total") or 0))
    except (TypeError, ValueError) as exc:
        raise NaverOpenSearchResponseError("Naver blog search response is missing total.") from exc


def _extract_keywords(keywords: list[dict[str, Any]] | list[str]) -> list[str]:
    results: list[str] = []
    for item in keywords:
        if isinstance(item, dict):
            keyword = normalize_text(item.get("keyword"))
        else:
            keyword = normalize_text(item)
        if keyword:
            results.append(keyword)
    return results


def _load_search_credentials_file(path_value: str | None) -> dict[str, Any]:
    candidate_paths: list[Path] = []
    if path_value:
        candidate_paths.append(Path(path_value.strip()).expanduser())
    candidate_paths.append(_DEFAULT_CREDENTIALS_PATH)
    candidate_paths.append(_LEGACY_CREDENTIALS_PATH)

    seen: set[str] = set()
    for path in candidate_paths:
        resolved = str(path.resolve()) if path.exists() else str(path)
        if resolved in seen:
            continue
        seen.add(resolved)

        if not path.exists() or not path.is_file():
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(payload, dict):
            nested = payload.get("naver_search_api")
            if isinstance(nested, dict):
                return nested
            return payload

    return {}


def _extract_error_message(raw_text: str) -> str:
    if not raw_text:
        return ""

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return ""

    if not isinstance(parsed, dict):
        return ""

    for key in ("errorMessage", "message", "detail"):
        message = normalize_text(parsed.get(key))
        if message:
            return message
    return ""


def _coerce_bool(value: Any, fallback: Any, *, default: bool) -> bool:
    for candidate in (value, fallback):
        if candidate is None:
            continue
        if isinstance(candidate, bool):
            return candidate
        normalized = normalize_text(candidate).lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return bool(candidate)
    return default


def _coerce_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
