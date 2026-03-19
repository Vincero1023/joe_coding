from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.analyzer.keyword_stats import KeywordStats
from app.expander.utils.tokenizer import normalize_key, normalize_text


_BASE_URL = "https://keywordmaster.net/ajax/keywordAjax.php"
_DEFAULT_TIMEOUT = 8.0
_DEFAULT_MAX_WORKERS = 6
_DEFAULT_MAX_KEYWORDS = 60

UrlopenLike = Callable[..., Any]


class KeywordMasterBenchmarkError(RuntimeError):
    """Base exception for KeywordMaster benchmark requests."""


class KeywordMasterBenchmarkResponseError(KeywordMasterBenchmarkError):
    """Raised when KeywordMaster returns an unexpected payload."""


@dataclass(frozen=True)
class KeywordMasterBenchmarkSettings:
    enabled: bool = False
    timeout: float = _DEFAULT_TIMEOUT
    max_workers: int = _DEFAULT_MAX_WORKERS
    max_keywords: int = _DEFAULT_MAX_KEYWORDS

    @classmethod
    def from_input(cls, input_data: Any) -> "KeywordMasterBenchmarkSettings":
        root = input_data if isinstance(input_data, dict) else {}
        benchmark = (
            root.get("keywordmaster_benchmark")
            if isinstance(root.get("keywordmaster_benchmark"), dict)
            else {}
        )
        enabled = _coerce_bool(
            benchmark.get("enabled"),
            root.get("keywordmaster_benchmark_enabled"),
            default=False,
        )
        timeout = _coerce_float(
            benchmark.get("timeout"),
            default=_DEFAULT_TIMEOUT,
            minimum=1.0,
            maximum=30.0,
        )
        max_workers = _coerce_int(
            benchmark.get("max_workers"),
            default=_DEFAULT_MAX_WORKERS,
            minimum=1,
            maximum=16,
        )
        max_keywords = _coerce_int(
            benchmark.get("max_keywords"),
            default=_DEFAULT_MAX_KEYWORDS,
            minimum=1,
            maximum=500,
        )
        return cls(
            enabled=enabled,
            timeout=timeout,
            max_workers=max_workers,
            max_keywords=max_keywords,
        )


class KeywordMasterBenchmarkClient:
    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        opener: UrlopenLike | None = None,
    ) -> None:
        self._timeout = timeout
        self._opener = opener or urlopen
        self._cache: dict[str, KeywordStats] = {}
        self._lock = Lock()

    def fetch_keyword_stats(
        self,
        keywords: list[str],
        *,
        max_workers: int = _DEFAULT_MAX_WORKERS,
    ) -> dict[str, KeywordStats]:
        results: dict[str, KeywordStats] = {}
        pending_keywords: list[str] = []

        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            key = normalize_key(normalized_keyword)
            if not key or key in results:
                continue

            cached = self._get_cached(key)
            if cached is not None:
                results[key] = cached.with_keyword(normalized_keyword)
                continue

            pending_keywords.append(normalized_keyword)

        if not pending_keywords:
            return results

        worker_count = max(1, min(max_workers, len(pending_keywords)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(self._fetch_keyword_stat, keyword): keyword
                for keyword in pending_keywords
            }
            for future in as_completed(future_map):
                keyword = future_map[future]
                try:
                    item = future.result()
                except KeywordMasterBenchmarkError:
                    continue
                if item is None:
                    continue
                results[normalize_key(keyword)] = item.with_keyword(keyword)

        return results

    def _fetch_keyword_stat(self, keyword: str) -> KeywordStats | None:
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            return None

        request = Request(
            url=f"{_BASE_URL}?keyword={quote(normalized_keyword)}",
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 KeywordForge/1.0",
            },
            method="GET",
        )
        payload = self._execute_json(request)
        parsed = parse_keywordmaster_keyword_response(payload, request_keyword=normalized_keyword)
        if parsed is None:
            return None

        self._set_cached(normalize_key(normalized_keyword), parsed)
        return parsed

    def _execute_json(self, request: Request) -> dict[str, Any]:
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw_text = response.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            raw_text = exc.read().decode("utf-8", errors="ignore")
            raise KeywordMasterBenchmarkResponseError(raw_text or str(exc.reason)) from exc
        except URLError as exc:
            raise KeywordMasterBenchmarkResponseError(str(exc.reason)) from exc
        except Exception as exc:  # pragma: no cover - runtime guard
            raise KeywordMasterBenchmarkResponseError(str(exc)) from exc

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise KeywordMasterBenchmarkResponseError("KeywordMaster returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise KeywordMasterBenchmarkResponseError("KeywordMaster returned an unexpected payload.")
        return parsed

    def _get_cached(self, key: str) -> KeywordStats | None:
        with self._lock:
            return self._cache.get(key)

    def _set_cached(self, key: str, item: KeywordStats) -> None:
        with self._lock:
            self._cache[key] = item


def build_keywordmaster_benchmark_index(
    input_data: Any,
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
    client: KeywordMasterBenchmarkClient | Any | None = None,
) -> dict[str, KeywordStats]:
    settings = KeywordMasterBenchmarkSettings.from_input(input_data)
    if not settings.enabled:
        return {}

    pending_keywords = build_keywordmaster_benchmark_requests(
        keywords,
        stats_index=stats_index,
        max_keywords=settings.max_keywords,
    )
    if not pending_keywords:
        return {}

    resolved_client = client or KeywordMasterBenchmarkClient(timeout=settings.timeout)
    try:
        return resolved_client.fetch_keyword_stats(
            pending_keywords,
            max_workers=settings.max_workers,
        )
    except KeywordMasterBenchmarkError:
        return {}


def build_keywordmaster_benchmark_requests(
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
    max_keywords: int = _DEFAULT_MAX_KEYWORDS,
) -> list[str]:
    requests: list[str] = []
    seen: set[str] = set()

    for keyword in _extract_keywords(keywords):
        key = normalize_key(keyword)
        if not key or key in seen:
            continue
        seen.add(key)

        existing = stats_index.get(key) if stats_index else None
        if not _should_request_keywordmaster(existing):
            continue

        requests.append(keyword)
        if len(requests) >= max(1, max_keywords):
            break

    return requests


def parse_keywordmaster_keyword_response(payload: Any, *, request_keyword: str) -> KeywordStats | None:
    if not isinstance(payload, dict):
        raise KeywordMasterBenchmarkResponseError("KeywordMaster response must be an object.")

    main = payload.get("main")
    if not isinstance(main, dict):
        raise KeywordMasterBenchmarkResponseError("KeywordMaster response is missing main data.")

    keyword = normalize_text(request_keyword)
    if not keyword:
        return None

    pc_bids = _coerce_number_list(main.get("pcBids"), limit=10)
    mobile_bids = _coerce_number_list(main.get("moBids"), limit=5)

    return KeywordStats(
        keyword=keyword,
        pc_searches=_coerce_optional_float(main.get("pcSearch")),
        mobile_searches=_coerce_optional_float(main.get("moSearch")),
        blog_results=_coerce_optional_float(main.get("blogPosts")),
        pc_clicks=_coerce_optional_float(main.get("pcClick")),
        mobile_clicks=_coerce_optional_float(main.get("moClick")),
        bid_1=pc_bids[0] if len(pc_bids) > 0 else None,
        bid_2=pc_bids[1] if len(pc_bids) > 1 else None,
        bid_3=pc_bids[2] if len(pc_bids) > 2 else None,
        bid_4=pc_bids[3] if len(pc_bids) > 3 else None,
        bid_5=pc_bids[4] if len(pc_bids) > 4 else None,
        bid_6=pc_bids[5] if len(pc_bids) > 5 else None,
        bid_7=pc_bids[6] if len(pc_bids) > 6 else None,
        bid_8=pc_bids[7] if len(pc_bids) > 7 else None,
        bid_9=pc_bids[8] if len(pc_bids) > 8 else None,
        bid_10=pc_bids[9] if len(pc_bids) > 9 else None,
        mobile_bid_1=mobile_bids[0] if len(mobile_bids) > 0 else None,
        mobile_bid_2=mobile_bids[1] if len(mobile_bids) > 1 else None,
        mobile_bid_3=mobile_bids[2] if len(mobile_bids) > 2 else None,
        mobile_bid_4=mobile_bids[3] if len(mobile_bids) > 3 else None,
        mobile_bid_5=mobile_bids[4] if len(mobile_bids) > 4 else None,
        source="keywordmaster_benchmark",
    )


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


def _should_request_keywordmaster(existing: KeywordStats | None) -> bool:
    if existing is None:
        return True

    blog_results = existing.blog_results or 0.0
    average_bid = existing.resolved_average_bid()
    top_bids = existing.resolved_pc_bids(limit=3)

    if blog_results <= 0:
        return True
    if not top_bids:
        return True

    # SearchAd often collapses uncertain bids to a flat 70원 ladder.
    if average_bid <= 70.0 and all(bid <= 70.0 for bid in top_bids):
        return True

    return False


def _coerce_bool(*values: Any, default: bool) -> bool:
    for value in values:
        if value is None:
            continue
        return bool(value)
    return default


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _coerce_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _coerce_optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_number_list(value: Any, *, limit: int) -> list[float | None]:
    if not isinstance(value, list):
        return []

    results: list[float | None] = []
    for raw_item in value[: max(0, limit)]:
        results.append(_coerce_optional_float(raw_item))
    return results
