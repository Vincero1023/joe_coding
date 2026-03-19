from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.analyzer.keyword_stats import KeywordStats, merge_keyword_stats
from app.core.config import get_settings
from app.expander.utils.tokenizer import normalize_key, normalize_text


_BASE_URL = "https://api.searchad.naver.com"
_AVERAGE_POSITION_URI = "/estimate/average-position-bid/keyword"
_KEYWORD_TOOL_URI = "/keywordstool"
_DEFAULT_TIMEOUT = 8.0
_DEFAULT_BID_KEYWORD_BATCH_SIZE = 50
_DEFAULT_KEYWORD_TOOL_BATCH_SIZE = 1
_DEFAULT_CREDENTIALS_PATH = "searchad.credentials.json"
_PC_TOP_POSITIONS = tuple(range(1, 11))
_MOBILE_TOP_POSITIONS = tuple(range(1, 6))

UrlopenLike = Callable[..., Any]


class NaverSearchAdError(RuntimeError):
    """Base exception for SearchAd estimate requests."""


class NaverSearchAdAuthError(NaverSearchAdError):
    """Raised when SearchAd credentials are missing or rejected."""


class NaverSearchAdResponseError(NaverSearchAdError):
    """Raised when SearchAd returns an unexpected payload."""


@dataclass(frozen=True)
class NaverSearchAdCredentials:
    api_key: str
    secret_key: str
    customer_id: str

    @classmethod
    def from_input(cls, input_data: Any) -> "NaverSearchAdCredentials | None":
        root = input_data if isinstance(input_data, dict) else {}
        searchad = root.get("searchad") if isinstance(root.get("searchad"), dict) else {}
        settings = get_settings()
        file_values = _load_searchad_credentials_file(
            normalize_text(searchad.get("credentials_path"))
            or normalize_text(root.get("searchad_credentials_path"))
        )

        api_key = (
            normalize_text(searchad.get("api_key"))
            or normalize_text(searchad.get("access_license"))
            or normalize_text(root.get("naver_ads_api_key"))
            or normalize_text(root.get("naver_ads_access_license"))
            or normalize_text(file_values.get("api_key"))
            or normalize_text(file_values.get("access_license"))
            or normalize_text(settings.naver_ads_access_license)
        )
        secret_key = (
            normalize_text(searchad.get("secret_key"))
            or normalize_text(root.get("naver_ads_secret_key"))
            or normalize_text(file_values.get("secret_key"))
            or normalize_text(settings.naver_ads_secret_key)
        )
        customer_id = (
            normalize_text(searchad.get("customer_id"))
            or normalize_text(root.get("naver_ads_customer_id"))
            or normalize_text(file_values.get("customer_id"))
            or normalize_text(settings.naver_ads_customer_id)
        )

        if not api_key or not secret_key or not customer_id:
            return None

        return cls(
            api_key=api_key,
            secret_key=secret_key,
            customer_id=customer_id,
        )


def _load_searchad_credentials_file(path_value: str | None) -> dict[str, Any]:
    candidate_paths: list[Path] = []
    if path_value:
        candidate_paths.append(Path(path_value.strip()))

    default_path = Path(_DEFAULT_CREDENTIALS_PATH)
    if default_path.exists():
        candidate_paths.append(default_path)

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
            nested = payload.get("searchad")
            if isinstance(nested, dict):
                return nested
            return payload

    return {}


@dataclass(frozen=True)
class SearchAdBidSettings:
    enabled: bool = False
    timeout: float = _DEFAULT_TIMEOUT
    bid_keyword_batch_size: int = _DEFAULT_BID_KEYWORD_BATCH_SIZE
    keyword_tool_batch_size: int = _DEFAULT_KEYWORD_TOOL_BATCH_SIZE

    @classmethod
    def from_input(cls, input_data: Any) -> "SearchAdBidSettings":
        root = input_data if isinstance(input_data, dict) else {}
        searchad = root.get("searchad") if isinstance(root.get("searchad"), dict) else {}
        has_available_credentials = NaverSearchAdCredentials.from_input(root) is not None
        enabled = _coerce_bool(searchad.get("enabled"), root.get("searchad_enabled"), default=has_available_credentials)
        timeout = _coerce_float(searchad.get("timeout"), default=_DEFAULT_TIMEOUT, minimum=1.0, maximum=30.0)
        bid_keyword_batch_size = _coerce_int(
            searchad.get("bid_keyword_batch_size") or searchad.get("keyword_batch_size"),
            default=_DEFAULT_BID_KEYWORD_BATCH_SIZE,
            minimum=1,
            maximum=100,
        )
        keyword_tool_batch_size = _coerce_int(
            searchad.get("keyword_tool_batch_size"),
            default=_DEFAULT_KEYWORD_TOOL_BATCH_SIZE,
            minimum=1,
            maximum=20,
        )
        return cls(
            enabled=enabled,
            timeout=timeout,
            bid_keyword_batch_size=bid_keyword_batch_size,
            keyword_tool_batch_size=keyword_tool_batch_size,
        )


@dataclass(frozen=True)
class SearchAdBidRequest:
    keyword: str
    positions: tuple[int, ...]
    device: str = "PC"


class NaverSearchAdClient:
    def __init__(
        self,
        credentials: NaverSearchAdCredentials,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        opener: UrlopenLike | None = None,
    ) -> None:
        self._credentials = credentials
        self._timeout = timeout
        self._opener = opener or urlopen

    def fetch_average_position_bid_stats(
        self,
        requests: list[SearchAdBidRequest],
        *,
        keyword_batch_size: int = _DEFAULT_BID_KEYWORD_BATCH_SIZE,
    ) -> dict[str, KeywordStats]:
        if not requests:
            return {}

        results: dict[str, KeywordStats] = {}
        for chunk in _chunked_requests(requests, keyword_batch_size):
            for device in ("PC", "MOBILE"):
                device_requests = [request for request in chunk if request.device == device]
                if not device_requests:
                    continue

                request_items = [
                    {
                        "key": request.keyword,
                        "query_key": _normalize_keyword_tool_hint(request.keyword),
                        "position": position,
                        "device": device,
                    }
                    for request in device_requests
                    for position in request.positions
                ]
                payload = {
                    "device": device,
                    "items": [{"key": item["query_key"], "position": item["position"]} for item in request_items],
                }
                chunk_stats = parse_average_position_bid_response(
                    self._post_json(_AVERAGE_POSITION_URI, payload),
                    request_items=request_items,
                    device=device,
                )
                for key, item in chunk_stats.items():
                    existing = results.get(key)
                    results[key] = item if existing is None else merge_keyword_stats(existing, item)
        return results

    def fetch_keyword_tool_stats(
        self,
        keywords: list[str],
        *,
        keyword_batch_size: int = _DEFAULT_KEYWORD_TOOL_BATCH_SIZE,
    ) -> dict[str, KeywordStats]:
        if not keywords:
            return {}

        results: dict[str, KeywordStats] = {}
        for chunk in _chunked_keywords(keywords, keyword_batch_size):
            normalized_hints = [_normalize_keyword_tool_hint(keyword) for keyword in chunk]
            payload = self._get_json(
                _KEYWORD_TOOL_URI,
                query_params={
                    "hintKeywords": ",".join(normalized_hints),
                    "showDetail": "1",
                },
            )
            chunk_stats = parse_keyword_tool_response(
                payload,
                request_keywords=chunk,
            )
            for key, item in chunk_stats.items():
                existing = results.get(key)
                results[key] = item if existing is None else merge_keyword_stats(existing, item)
        return results

    def _post_json(self, uri: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            url=f"{_BASE_URL}{uri}",
            headers=self._build_headers("POST", uri),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        return self._execute_json(request)

    def _get_json(self, uri: str, *, query_params: dict[str, str]) -> dict[str, Any]:
        from urllib.parse import urlencode

        query = urlencode(query_params)
        request = Request(
            url=f"{_BASE_URL}{uri}?{query}",
            headers=self._build_headers("GET", uri),
            method="GET",
        )
        return self._execute_json(request)

    def _execute_json(self, request: Request) -> dict[str, Any]:
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw_text = response.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            raw_text = exc.read().decode("utf-8", errors="ignore")
            detail = _extract_error_message(raw_text) or raw_text or str(exc.reason)
            if exc.code in {401, 403}:
                raise NaverSearchAdAuthError(detail) from exc
            raise NaverSearchAdResponseError(f"{exc.code} {detail}") from exc
        except URLError as exc:
            raise NaverSearchAdResponseError(str(exc.reason)) from exc
        except Exception as exc:  # pragma: no cover - runtime guard
            raise NaverSearchAdResponseError(str(exc)) from exc

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise NaverSearchAdResponseError("SearchAd returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise NaverSearchAdResponseError("SearchAd returned an unexpected payload.")
        return parsed

    def _build_headers(self, method: str, uri: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        signature = generate_signature(timestamp, method, uri, self._credentials.secret_key)
        return {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": self._credentials.api_key,
            "X-Customer": self._credentials.customer_id,
            "X-Signature": signature,
        }


def build_searchad_bid_index(
    input_data: Any,
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
    client: NaverSearchAdClient | Any | None = None,
) -> dict[str, KeywordStats]:
    settings = SearchAdBidSettings.from_input(input_data)
    if not settings.enabled:
        return {}

    credentials = NaverSearchAdCredentials.from_input(input_data)
    if credentials is None:
        return {}

    pending_requests = build_searchad_bid_requests(keywords, stats_index=stats_index)
    if not pending_requests:
        return {}

    resolved_client = client or NaverSearchAdClient(credentials, timeout=settings.timeout)
    try:
        return resolved_client.fetch_average_position_bid_stats(
            pending_requests,
            keyword_batch_size=settings.bid_keyword_batch_size,
        )
    except NaverSearchAdError:
        return {}


def build_searchad_keyword_tool_index(
    input_data: Any,
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
    client: NaverSearchAdClient | Any | None = None,
) -> dict[str, KeywordStats]:
    settings = SearchAdBidSettings.from_input(input_data)
    if not settings.enabled:
        return {}

    credentials = NaverSearchAdCredentials.from_input(input_data)
    if credentials is None:
        return {}

    pending_keywords = build_searchad_keyword_tool_requests(keywords, stats_index=stats_index)
    if not pending_keywords:
        return {}

    resolved_client = client or NaverSearchAdClient(credentials, timeout=settings.timeout)
    try:
        return resolved_client.fetch_keyword_tool_stats(
            pending_keywords,
            keyword_batch_size=settings.keyword_tool_batch_size,
        )
    except NaverSearchAdError:
        return {}


def build_searchad_bid_requests(
    keywords: list[dict[str, Any]] | list[str],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
) -> list[SearchAdBidRequest]:
    requests: list[SearchAdBidRequest] = []
    seen: set[str] = set()

    for keyword in _extract_keywords(keywords):
        key = normalize_key(keyword)
        if not key or key in seen:
            continue
        seen.add(key)

        existing = stats_index.get(key) if stats_index else None
        pending_pc_positions = tuple(
            position
            for position in _PC_TOP_POSITIONS
            if not _has_positive_number(getattr(existing, f"bid_{position}", None))
        )
        pending_mobile_positions = tuple(
            position
            for position in _MOBILE_TOP_POSITIONS
            if not _has_positive_number(getattr(existing, f"mobile_bid_{position}", None))
        )

        if pending_pc_positions:
            requests.append(SearchAdBidRequest(keyword=keyword, positions=pending_pc_positions, device="PC"))
        if pending_mobile_positions:
            requests.append(SearchAdBidRequest(keyword=keyword, positions=pending_mobile_positions, device="MOBILE"))

    return requests


def build_searchad_keyword_tool_requests(
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
        has_searches = existing is not None and existing.resolved_total_searches() > 0
        has_clicks = existing is not None and existing.resolved_total_clicks() > 0
        if has_searches and has_clicks:
            continue

        requests.append(keyword)

    return requests


def parse_average_position_bid_response(
    payload: Any,
    *,
    request_items: list[dict[str, Any]] | None = None,
    device: str | None = None,
) -> dict[str, KeywordStats]:
    if not isinstance(payload, dict):
        raise NaverSearchAdResponseError("SearchAd average-position response must be an object.")

    estimates = payload.get("estimate")
    if not isinstance(estimates, list):
        raise NaverSearchAdResponseError("SearchAd average-position response is missing estimate items.")

    slots: dict[str, dict[str, Any]] = {}
    response_device = normalize_text(payload.get("device") or device).upper() or "PC"
    for index, raw_item in enumerate(estimates):
        if not isinstance(raw_item, dict):
            continue

        keyword = normalize_text(raw_item.get("keyword") or raw_item.get("key"))
        fallback_keyword = ""
        fallback_device = response_device
        if request_items and index < len(request_items):
            fallback_keyword = normalize_text(request_items[index].get("key"))
            fallback_device = normalize_text(request_items[index].get("device") or fallback_device).upper()
        if not normalize_key(keyword):
            keyword = fallback_keyword

        position = _coerce_optional_int(raw_item.get("position"))
        bid = _coerce_optional_float(raw_item.get("bid"))
        field_name = _resolve_bid_field_name(fallback_device or response_device, position)
        if not keyword or not field_name or bid is None:
            continue

        key = normalize_key(keyword)
        slot = slots.setdefault(key, _create_empty_bid_slot(keyword))
        slot[field_name] = bid

    return {
        key: KeywordStats(
            keyword=slot["keyword"],
            bid_1=slot["bid_1"],
            bid_2=slot["bid_2"],
            bid_3=slot["bid_3"],
            bid_4=slot["bid_4"],
            bid_5=slot["bid_5"],
            bid_6=slot["bid_6"],
            bid_7=slot["bid_7"],
            bid_8=slot["bid_8"],
            bid_9=slot["bid_9"],
            bid_10=slot["bid_10"],
            mobile_bid_1=slot["mobile_bid_1"],
            mobile_bid_2=slot["mobile_bid_2"],
            mobile_bid_3=slot["mobile_bid_3"],
            mobile_bid_4=slot["mobile_bid_4"],
            mobile_bid_5=slot["mobile_bid_5"],
            source="naver_searchad",
        )
        for key, slot in slots.items()
    }


def parse_keyword_tool_response(
    payload: Any,
    *,
    request_keywords: list[str],
) -> dict[str, KeywordStats]:
    if not isinstance(payload, dict):
        raise NaverSearchAdResponseError("SearchAd keyword tool response must be an object.")

    rows = payload.get("keywordList")
    if not isinstance(rows, list):
        raise NaverSearchAdResponseError("SearchAd keyword tool response is missing keywordList.")

    results: dict[str, KeywordStats] = {}
    for index, request_keyword in enumerate(request_keywords):
        if index >= len(rows):
            continue
        raw_item = rows[index]
        if not isinstance(raw_item, dict):
            continue

        keyword = normalize_text(request_keyword)
        key = normalize_key(keyword)
        if not keyword or not key:
            continue

        results[key] = KeywordStats(
            keyword=keyword,
            pc_searches=_parse_keyword_tool_count(raw_item.get("monthlyPcQcCnt")),
            mobile_searches=_parse_keyword_tool_count(raw_item.get("monthlyMobileQcCnt")),
            pc_clicks=_coerce_optional_float(raw_item.get("monthlyAvePcClkCnt")),
            mobile_clicks=_coerce_optional_float(raw_item.get("monthlyAveMobileClkCnt")),
            source="naver_searchad_keywordtool",
        )
    return results


def generate_signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _chunked_requests(
    requests: list[SearchAdBidRequest],
    keyword_batch_size: int,
) -> list[list[SearchAdBidRequest]]:
    if not requests:
        return []

    batch_size = max(1, keyword_batch_size)
    return [
        requests[index : index + batch_size]
        for index in range(0, len(requests), batch_size)
    ]


def _chunked_keywords(keywords: list[str], keyword_batch_size: int) -> list[list[str]]:
    if not keywords:
        return []

    batch_size = max(1, keyword_batch_size)
    return [
        keywords[index : index + batch_size]
        for index in range(0, len(keywords), batch_size)
    ]


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


def _extract_error_message(raw_text: str) -> str:
    if not raw_text:
        return ""

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return ""

    if not isinstance(parsed, dict):
        return ""

    for key in ("message", "detail", "errorMessage"):
        message = normalize_text(parsed.get(key))
        if message:
            return message

    error = parsed.get("error")
    if isinstance(error, dict):
        for key in ("message", "detail"):
            message = normalize_text(error.get(key))
            if message:
                return message

    title = normalize_text(parsed.get("title"))
    if title:
        return title
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


def _coerce_optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_keyword_tool_count(value: Any) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    if text.startswith("<"):
        return 10.0
    return _coerce_optional_float(text.replace(",", ""))


def _normalize_keyword_tool_hint(keyword: str) -> str:
    normalized = normalize_text(keyword)
    collapsed = normalized.replace(" ", "")
    return collapsed or normalized


def _resolve_bid_field_name(device: str, position: int | None) -> str | None:
    if position is None:
        return None
    normalized_device = normalize_text(device).upper()
    if normalized_device == "MOBILE":
        if position in _MOBILE_TOP_POSITIONS:
            return f"mobile_bid_{position}"
        return None
    if position in _PC_TOP_POSITIONS:
        return f"bid_{position}"
    return None


def _create_empty_bid_slot(keyword: str) -> dict[str, Any]:
    return {
        "keyword": keyword,
        "bid_1": None,
        "bid_2": None,
        "bid_3": None,
        "bid_4": None,
        "bid_5": None,
        "bid_6": None,
        "bid_7": None,
        "bid_8": None,
        "bid_9": None,
        "bid_10": None,
        "mobile_bid_1": None,
        "mobile_bid_2": None,
        "mobile_bid_3": None,
        "mobile_bid_4": None,
        "mobile_bid_5": None,
    }


def _has_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) > 0
