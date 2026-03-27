from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from app.core.api_usage import capture_api_usage
from app.collector.categories import (
    DEFAULT_CATEGORY_SOURCE,
    get_category_queries,
    get_category_search_area,
    get_category_trend_topic,
    resolve_category_name,
)
from app.collector.naver_trend import (
    NaverTrendAuthError,
    NaverTrendCategoryNotFoundError,
    NaverTrendClient,
    NaverTrendError,
    NaverTrendOptions,
)
from app.expander.sources.naver_autocomplete import get_naver_autocomplete
from app.expander.sources.naver_related import get_naver_related_queries
from app.expander.utils.throttle import wait_for_naver_keyword_request
from app.expander.utils.tokenizer import normalize_text


_RELATED_SUFFIXES = ("추천", "후기", "가격", "비교", "정리", "방법")
_UI_STOPWORDS = {
    "광고",
    "더보기",
    "공유하기",
    "본문 바로가기",
    "메뉴 바로가기",
    "NAVER",
    "자동완성",
    "입력도구",
    "사전",
    "옵션",
    "전체",
    "모바일 메인 바로가기",
    "PC 메인 바로가기",
    "Keep 바로가기",
    "등록 안내",
    "광고가 표시되는 이유",
}
_SEARCH_HOST = "https://search.naver.com/search.naver"


@dataclass(frozen=True)
class CollectorOptions:
    collect_related: bool
    collect_autocomplete: bool
    collect_bulk: bool

    @classmethod
    def from_dict(cls, raw: Any) -> "CollectorOptions":
        if not isinstance(raw, dict):
            raw = {}

        return cls(
            collect_related=bool(raw.get("collect_related", True)),
            collect_autocomplete=bool(raw.get("collect_autocomplete", True)),
            collect_bulk=bool(raw.get("collect_bulk", True)),
        )


@dataclass(frozen=True)
class CollectorRequest:
    mode: str
    category: str
    seed_input: str
    options: CollectorOptions
    debug: bool
    category_source: str
    trend_options: NaverTrendOptions

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CollectorRequest":
        return cls(
            mode=_normalize_mode(raw.get("mode")),
            category=str(raw.get("category") or "").strip(),
            seed_input=str(raw.get("seed_input") or "").strip(),
            options=CollectorOptions.from_dict(raw.get("options")),
            debug=bool(raw.get("debug")),
            category_source=_normalize_category_source(raw.get("category_source")),
            trend_options=NaverTrendOptions.from_dict(raw.get("trend_options")),
        )


@dataclass
class CollectorDebugContext:
    mode: str
    requested_category: str | None
    requested_seed: str | None
    requested_category_source: str
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    resolved_category: str | None = None
    effective_source: str | None = None
    search_area: str | None = None
    trend_service: str | None = None
    trend_topic: str | None = None
    trend_date: str | None = None
    query_logs: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    raw_keyword_count: int = 0
    deduped_keyword_count: int = 0
    duration_ms: int = 0


class CollectorService:
    def __init__(
        self,
        autocomplete_fetcher: Callable[[str], list[str]] | None = None,
        related_fetcher: Callable[[str], list[str]] | None = None,
        trend_client: NaverTrendClient | None = None,
    ) -> None:
        self._autocomplete_fetcher = autocomplete_fetcher
        self._related_fetcher = related_fetcher
        self._trend_client = trend_client or NaverTrendClient()

    def run(self, input_data: dict) -> dict:
        with capture_api_usage() as api_usage:
            request = CollectorRequest.from_dict(input_data)
            debug = self._start_debug_context(request) if request.debug else None
            started_at = time.perf_counter()

            resolved_category = resolve_category_name(request.category)
            if debug:
                debug.resolved_category = resolved_category

            if request.mode == "category":
                if not resolved_category:
                    _record_warning(
                        debug,
                        code="category_not_found",
                        message="?붿껌??移댄뀒怨좊━瑜?李얠? 紐삵뻽?듬땲??",
                        detail={"requested_category": request.category},
                    )
                    return self._build_result(
                        [],
                        debug,
                        started_at,
                        api_usage_snapshot=api_usage.snapshot(),
                    )

                raw_entries = self._collect_category_entries(
                    category=resolved_category,
                    request=request,
                    debug=debug,
                )
                return self._build_result(
                    raw_entries,
                    debug,
                    started_at,
                    api_usage_snapshot=api_usage.snapshot(),
                )

            raw_entries = self._collect_by_seed(
                seed_input=request.seed_input,
                options=request.options,
                debug=debug,
            )
            return self._build_result(
                raw_entries,
                debug,
                started_at,
                api_usage_snapshot=api_usage.snapshot(),
            )

    def _collect_category_entries(
        self,
        *,
        category: str,
        request: CollectorRequest,
        debug: CollectorDebugContext | None,
    ) -> list[dict[str, Any]]:
        if request.category_source == "naver_trend":
            trend_entries = self._collect_by_naver_trend(
                category=category,
                trend_options=request.trend_options,
                debug=debug,
            )
            if trend_entries:
                return trend_entries
            if not request.trend_options.fallback_to_preset_search:
                return []

        return self._collect_by_preset_search(
            category=category,
            options=request.options,
            debug=debug,
        )

    def _collect_by_naver_trend(
        self,
        *,
        category: str,
        trend_options: NaverTrendOptions,
        debug: CollectorDebugContext | None,
    ) -> list[dict[str, Any]]:
        topic_name = get_category_trend_topic(category)
        if debug:
            debug.effective_source = "naver_trend"
            debug.trend_service = trend_options.service
            debug.trend_topic = topic_name
            debug.trend_date = trend_options.resolved_date

        if not topic_name:
            _record_warning(
                debug,
                code="naver_trend_topic_missing",
                message="이 카테고리에 연결된 Creator Advisor 주제가 없습니다.",
                detail={"category": category},
            )
            return []

        started_at = time.perf_counter()
        try:
            result = self._trend_client.collect_category_keywords(
                topic_name=topic_name,
                options=trend_options,
            )
        except NaverTrendAuthError as exc:
            _record_warning(
                debug,
                code="naver_trend_auth_required",
                message=str(exc),
                detail={
                    "category": category,
                    "topic": topic_name,
                    "service": trend_options.service,
                },
            )
            _record_query_log(
                debug,
                query=topic_name,
                search_area=f"trend/{trend_options.service}",
                source="naver_trend",
                status="warning",
                result_count=0,
                elapsed_ms=_elapsed_ms(started_at),
                fallback_used=trend_options.fallback_to_preset_search,
                notes=["auth_required"],
            )
            return []
        except NaverTrendCategoryNotFoundError as exc:
            _record_warning(
                debug,
                code="naver_trend_topic_not_found",
                message=str(exc),
                detail={
                    "category": category,
                    "topic": topic_name,
                    "service": trend_options.service,
                },
            )
            _record_query_log(
                debug,
                query=topic_name,
                search_area=f"trend/{trend_options.service}",
                source="naver_trend",
                status="warning",
                result_count=0,
                elapsed_ms=_elapsed_ms(started_at),
                fallback_used=trend_options.fallback_to_preset_search,
                notes=["topic_not_found"],
            )
            return []
        except NaverTrendError as exc:
            _record_warning(
                debug,
                code="naver_trend_error",
                message=str(exc),
                detail={
                    "category": category,
                    "topic": topic_name,
                    "service": trend_options.service,
                },
            )
            _record_query_log(
                debug,
                query=topic_name,
                search_area=f"trend/{trend_options.service}",
                source="naver_trend",
                status="warning",
                result_count=0,
                elapsed_ms=_elapsed_ms(started_at),
                fallback_used=trend_options.fallback_to_preset_search,
                notes=["trend_error"],
            )
            return []

        if debug:
            debug.effective_source = "naver_trend"
            debug.trend_date = result.date

        if not result.keywords:
            _record_warning(
                debug,
                code="naver_trend_empty",
                message="Creator Advisor 트렌드 응답에 키워드가 없습니다.",
                detail={
                    "category": category,
                    "topic": result.topic_name,
                    "date": result.date,
                },
            )
            _record_query_log(
                debug,
                query=result.topic_name,
                search_area=f"trend/{result.service}",
                source="naver_trend",
                status="empty",
                result_count=0,
                elapsed_ms=_elapsed_ms(started_at),
                fallback_used=trend_options.fallback_to_preset_search,
                notes=["trend_empty"],
            )
            return []

        _record_query_log(
            debug,
            query=result.topic_name,
            search_area=f"trend/{result.service}",
            source="naver_trend",
            status="success",
            result_count=len(result.keywords),
            elapsed_ms=_elapsed_ms(started_at),
            fallback_used=False,
            notes=[
                f"date:{result.date}",
                *(
                    [f"requested_date:{trend_options.resolved_date}"]
                    if result.date != trend_options.resolved_date
                    else []
                ),
            ],
        )

        return [
            {
                "keyword": normalize_text(item.query),
                "category": category,
                "source": "naver_trend",
                "raw": result.topic_name,
                "rank": item.rank,
                "rank_change": item.rank_change,
            }
            for item in result.keywords
            if normalize_text(item.query)
        ]

    def _collect_by_preset_search(
        self,
        *,
        category: str,
        options: CollectorOptions,
        debug: CollectorDebugContext | None,
    ) -> list[dict[str, Any]]:
        queries = get_category_queries(category, include_all=options.collect_bulk)
        search_area = get_category_search_area(category)
        if debug:
            debug.search_area = search_area
            debug.effective_source = "preset_search"

        if not queries:
            _record_warning(
                debug,
                code="category_query_missing",
                message="카테고리에 연결된 수집 쿼리가 없습니다.",
                detail={"category": category},
            )
            return []

        query_variants = _build_query_variants(queries, options)
        return self._collect_from_queries(
            queries=query_variants,
            category=category,
            search_area=search_area,
            debug=debug,
        )

    def _collect_by_seed(
        self,
        *,
        seed_input: str,
        options: CollectorOptions,
        debug: CollectorDebugContext | None,
    ) -> list[dict[str, Any]]:
        normalized_seed = normalize_text(seed_input)
        if not normalized_seed:
            _record_warning(
                debug,
                code="seed_missing",
                message="시드 모드에는 seed_input이 필요합니다.",
                detail={"seed_input": seed_input},
            )
            return []

        if debug:
            debug.search_area = "seed_keyword_sources"
            debug.effective_source = "seed_keyword_sources"

        collected_keywords: list[dict[str, Any]] = []
        if options.collect_autocomplete:
            collected_keywords.extend(
                self._collect_seed_source(
                    query=normalized_seed,
                    source="naver_autocomplete",
                    search_area="autocomplete",
                    fetcher=self._autocomplete_fetcher or get_naver_autocomplete,
                    warning_code="autocomplete_error",
                    warning_message="네이버 자동완성 조회에 실패했습니다.",
                    empty_note="autocomplete_empty",
                    debug=debug,
                )
            )

        if options.collect_related:
            collected_keywords.extend(
                self._collect_seed_source(
                    query=normalized_seed,
                    source="naver_related",
                    search_area="related",
                    fetcher=self._related_fetcher or get_naver_related_queries,
                    warning_code="related_error",
                    warning_message="네이버 연관검색어 조회에 실패했습니다.",
                    empty_note="related_empty",
                    debug=debug,
                )
            )

        if not collected_keywords and (options.collect_autocomplete or options.collect_related):
            _record_warning(
                debug,
                code="seed_keyword_sources_empty",
                message="시드 기준 자동완성/연관검색 결과가 없습니다.",
                detail={"seed_input": normalized_seed},
            )
        if not collected_keywords:
            _record_warning(
                debug,
                code="seed_input_fallback_used",
                message="시드 원문을 직접 수집 후보로 유지합니다.",
                detail={"seed_input": normalized_seed},
            )
            collected_keywords.append(
                {
                    "keyword": normalized_seed,
                    "category": None,
                    "source": "seed_input_fallback",
                    "raw": normalized_seed,
                }
            )

        return collected_keywords

    def _collect_seed_source(
        self,
        *,
        query: str,
        source: str,
        search_area: str,
        fetcher: Callable[[str], list[str]],
        warning_code: str,
        warning_message: str,
        empty_note: str,
        debug: CollectorDebugContext | None,
    ) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        results: list[str] = []
        fetch_error: Exception | None = None

        try:
            results = fetcher(query)
        except Exception as exc:  # pragma: no cover - exercised via debug tests
            fetch_error = exc
            _record_warning(
                debug,
                code=warning_code,
                message=warning_message,
                detail={"query": query, "error": repr(exc)},
            )

        notes = [] if results else [warning_code if fetch_error else empty_note]
        status = "success" if results else "warning" if fetch_error else "empty"
        _record_query_log(
            debug,
            query=query,
            search_area=search_area,
            source=source,
            status=status,
            result_count=len(results),
            elapsed_ms=_elapsed_ms(started_at),
            fallback_used=False,
            notes=notes,
        )

        return [
            {
                "keyword": normalize_text(item),
                "category": None,
                "source": source,
                "raw": query,
            }
            for item in results
            if normalize_text(item)
        ]

    def _collect_from_queries(
        self,
        *,
        queries: Iterable[str],
        category: str | None,
        search_area: str,
        debug: CollectorDebugContext | None,
    ) -> list[dict[str, Any]]:
        collected_keywords: list[dict[str, Any]] = []

        for query in queries:
            normalized_query = normalize_text(query)
            if not normalized_query:
                continue

            source, suggestions = self._fetch_suggestions(
                query=normalized_query,
                search_area=search_area,
                debug=debug,
            )
            for suggestion in suggestions:
                keyword = normalize_text(suggestion)
                if not keyword:
                    continue

                collected_keywords.append(
                    {
                        "keyword": keyword,
                        "category": category,
                        "source": source,
                        "raw": normalized_query,
                    }
                )

        return collected_keywords

    def _fetch_suggestions(
        self,
        *,
        query: str,
        search_area: str,
        debug: CollectorDebugContext | None,
    ) -> tuple[str, list[str]]:
        started_at = time.perf_counter()
        fetcher = self._autocomplete_fetcher or get_naver_autocomplete

        autocomplete_results: list[str] = []
        autocomplete_error: Exception | None = None
        try:
            autocomplete_results = fetcher(query)
        except Exception as exc:  # pragma: no cover - exercised via debug tests
            autocomplete_error = exc
            _record_warning(
                debug,
                code="autocomplete_error",
                message="네이버 자동완성 조회에 실패했습니다.",
                detail={"query": query, "error": repr(exc)},
            )

        if autocomplete_results:
            _record_query_log(
                debug,
                query=query,
                search_area=search_area,
                source="naver_autocomplete",
                status="success",
                result_count=len(autocomplete_results),
                elapsed_ms=_elapsed_ms(started_at),
                fallback_used=False,
                notes=[],
            )
            return "naver_autocomplete", autocomplete_results

        search_results: list[str] = []
        search_error: Exception | None = None
        try:
            search_results = self._search_naver_results(query, search_area)
        except Exception as exc:
            search_error = exc
            _record_warning(
                debug,
                code="search_fallback_error",
                message="네이버 검색 결과 폴백 수집에 실패했습니다.",
                detail={"query": query, "search_area": search_area, "error": repr(exc)},
            )

        notes: list[str] = []
        if autocomplete_error is not None:
            notes.append("autocomplete_error")
        elif not autocomplete_results:
            notes.append("autocomplete_empty")

        if search_error is not None:
            notes.append("search_error")
        elif not search_results:
            notes.append("search_empty")

        status = "success" if search_results else "warning" if (autocomplete_error or search_error) else "empty"
        _record_query_log(
            debug,
            query=query,
            search_area=search_area,
            source="naver_search",
            status=status,
            result_count=len(search_results),
            elapsed_ms=_elapsed_ms(started_at),
            fallback_used=True,
            notes=notes,
        )
        return "naver_search", search_results

    def _search_naver_results(self, query: str, search_area: str) -> list[str]:
        url = f"{_SEARCH_HOST}?where={search_area}&query={quote(query)}"
        wait_for_naver_keyword_request()
        request = Request(
            url=url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            method="GET",
        )

        with urlopen(request, timeout=5.0) as response:
            html = response.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        matches: list[str] = []
        normalized_query = normalize_text(query)
        query_key = normalized_query.replace(" ", "").lower()

        for anchor in soup.find_all("a"):
            href = str(anchor.get("href") or "").strip()
            if not href.startswith("http"):
                continue
            if any(token in href for token in ("search.naver.com", "help.naver.com", "academic.naver.com")):
                continue

            text = normalize_text(anchor.get_text(" ", strip=True))
            if not text or text in _UI_STOPWORDS:
                continue
            if len(text) < 3 or len(text) > 44:
                continue
            if not re.search(r"[0-9A-Za-z가-힣]", text):
                continue
            if not _looks_related_to_query(text, query_key):
                continue
            if _looks_like_ui_text(text):
                continue

            matches.append(text)

        return list(dict.fromkeys(matches[:20]))

    def _build_result(
        self,
        raw_entries: list[dict[str, Any]],
        debug: CollectorDebugContext | None,
        started_at: float,
        *,
        api_usage_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        deduped = _dedupe_keyword_entries(raw_entries)
        result: dict[str, Any] = {"collected_keywords": deduped}
        usage_snapshot = (
            api_usage_snapshot
            if isinstance(api_usage_snapshot, dict)
            else {"summary": {}, "services": []}
        )

        if debug is None:
            result["debug"] = {
                "stage": "collector",
                "summary": usage_snapshot.get("summary", {}),
                "api_usage": usage_snapshot,
                "collector_summary": {
                    "raw_keyword_count": len(raw_entries),
                    "deduped_keyword_count": len(deduped),
                    "duration_ms": _elapsed_ms(started_at),
                },
            }
            return result

        debug.raw_keyword_count = len(raw_entries)
        debug.deduped_keyword_count = len(deduped)
        debug.duration_ms = _elapsed_ms(started_at)
        debug_payload = _build_debug_payload(debug)
        debug_payload["api_usage"] = usage_snapshot
        result["debug"] = debug_payload
        return result

    def _start_debug_context(self, request: CollectorRequest) -> CollectorDebugContext:
        return CollectorDebugContext(
            mode=request.mode,
            requested_category=normalize_text(request.category) or None,
            requested_seed=normalize_text(request.seed_input) or None,
            requested_category_source=request.category_source,
        )


def _build_query_variants(
    base_queries: Iterable[str],
    options: CollectorOptions,
) -> tuple[str, ...]:
    normalized_queries = [query for query in (normalize_text(item) for item in base_queries) if query]
    if not normalized_queries:
        return ()

    variants: list[str] = []
    for query in normalized_queries:
        if options.collect_autocomplete or not options.collect_related:
            variants.append(query)

        if options.collect_related:
            related_suffixes = _RELATED_SUFFIXES if options.collect_bulk else _RELATED_SUFFIXES[:3]
            variants.extend(f"{query} {suffix}" for suffix in related_suffixes)

    return tuple(dict.fromkeys(variants))


def _normalize_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return "category" if normalized == "category" else "seed"


def _normalize_category_source(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized == "preset_search" else DEFAULT_CATEGORY_SOURCE


def _dedupe_keyword_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[dict[str, Any]] = []

    for entry in entries:
        keyword = normalize_text(entry.get("keyword"))
        if not keyword:
            continue

        normalized_category = normalize_text(entry.get("category")) or None
        source = normalize_text(entry.get("source")) or "unknown"
        identity = (keyword, normalized_category, source)
        if identity in seen:
            continue

        seen.add(identity)
        item = {
            "keyword": keyword,
            "category": normalized_category,
            "source": source,
            "raw": normalize_text(entry.get("raw")) or keyword,
        }

        if "rank" in entry:
            item["rank"] = entry.get("rank")
        if "rank_change" in entry:
            item["rank_change"] = entry.get("rank_change")

        deduped.append(item)

    return deduped


def _build_debug_payload(debug: CollectorDebugContext) -> dict[str, Any]:
    autocomplete_hits = sum(
        1
        for item in debug.query_logs
        if item["source"] == "naver_autocomplete" and item["result_count"] > 0
    )
    related_hits = sum(
        1
        for item in debug.query_logs
        if item["source"] == "naver_related" and item["result_count"] > 0
    )
    fallback_hits = sum(
        1
        for item in debug.query_logs
        if item["source"] == "naver_search" and item["result_count"] > 0
    )
    trend_hits = sum(
        1
        for item in debug.query_logs
        if item["source"] == "naver_trend" and item["result_count"] > 0
    )
    warning_queries = sum(1 for item in debug.query_logs if item["status"] == "warning")

    return {
        "stage": "collector",
        "started_at": debug.started_at,
        "duration_ms": debug.duration_ms,
        "mode": debug.mode,
        "requested_category": debug.requested_category,
        "resolved_category": debug.resolved_category,
        "requested_seed": debug.requested_seed,
        "requested_category_source": debug.requested_category_source,
        "effective_source": debug.effective_source,
        "search_area": debug.search_area,
        "trend_service": debug.trend_service,
        "trend_topic": debug.trend_topic,
        "trend_date": debug.trend_date,
        "summary": {
            "queries_attempted": len(debug.query_logs),
            "queries_with_results": sum(1 for item in debug.query_logs if item["result_count"] > 0),
            "autocomplete_hits": autocomplete_hits,
            "related_hits": related_hits,
            "fallback_hits": fallback_hits,
            "trend_hits": trend_hits,
            "warning_queries": warning_queries,
            "raw_keyword_count": debug.raw_keyword_count,
            "deduped_keyword_count": debug.deduped_keyword_count,
            "warning_count": len(debug.warnings),
        },
        "warnings": debug.warnings,
        "query_logs": debug.query_logs,
    }


def _record_query_log(
    debug: CollectorDebugContext | None,
    *,
    query: str,
    search_area: str,
    source: str,
    status: str,
    result_count: int,
    elapsed_ms: int,
    fallback_used: bool,
    notes: list[str],
) -> None:
    if debug is None:
        return

    debug.query_logs.append(
        {
            "query": query,
            "search_area": search_area,
            "source": source,
            "status": status,
            "result_count": result_count,
            "elapsed_ms": elapsed_ms,
            "fallback_used": fallback_used,
            "notes": notes,
        }
    )


def _record_warning(
    debug: CollectorDebugContext | None,
    *,
    code: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    if debug is None:
        return

    debug.warnings.append(
        {
            "code": code,
            "message": message,
            "detail": detail,
        }
    )


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _looks_like_ui_text(text: str) -> bool:
    return any(
        token in text
        for token in (
            "서비스 보기",
            "옵션 위치기",
            "옵션 닫기",
            "바로가기",
            "초기화",
            "직접입력",
        )
    )


def _looks_related_to_query(text: str, query_key: str) -> bool:
    if not query_key:
        return True
    text_key = normalize_text(text).replace(" ", "").lower()
    return query_key in text_key
