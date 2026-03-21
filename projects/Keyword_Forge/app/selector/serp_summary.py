from __future__ import annotations

from collections import Counter
from typing import Any, Callable
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from app.expander.utils.throttle import wait_for_naver_keyword_request
from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text


_SEARCH_ENDPOINT = "https://search.naver.com/search.naver"
_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
_TITLE_SELECTORS = (
    "a.title_link[href]",
    ".title_area a[href]",
    "a.api_txt_lines.total_tit[href]",
    "a.total_tit[href]",
    "a.link_tit[href]",
    "a.userapi_txt_tit[href]",
    "a.news_tit[href]",
)
_INTENT_TERMS: dict[str, tuple[str, ...]] = {
    "commercial": ("추천", "비교", "가격", "비용", "견적", "순위", "선택"),
    "info": ("뜻", "정리", "방법", "가이드", "설명", "사용법", "체크리스트"),
    "review": ("후기", "리뷰", "평판", "체험", "경험"),
    "action": ("예약", "신청", "등록", "조회", "발급"),
    "location": ("위치", "코스", "루트", "근처", "동선"),
    "policy": ("조건", "기준", "정책", "지원", "기한"),
}
_INTENT_TOKEN_MAP = {
    normalize_key(term): intent_key
    for intent_key, terms in _INTENT_TERMS.items()
    for term in terms
    if normalize_key(term)
}
_STOPWORD_KEYS = {
    normalize_key(term)
    for terms in _INTENT_TERMS.values()
    for term in terms
    if normalize_key(term)
}
_STOPWORD_KEYS.update(
    {
        normalize_key(term)
        for term in ("완벽", "핵심", "총정리", "포인트", "확인")
        if normalize_key(term)
    }
)


def summarize_serp_competition(
    input_data: dict[str, Any],
    *,
    fetch_html: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    selected_items = [
        item
        for item in input_data.get("selected_keywords", [])
        if isinstance(item, dict) and normalize_text(item.get("keyword"))
    ]
    longtail_suggestions = [
        item
        for item in input_data.get("longtail_suggestions", [])
        if isinstance(item, dict) and normalize_text(item.get("longtail_keyword"))
    ]
    limit = _coerce_limit(input_data.get("limit"))
    queries = _pick_serp_queries(selected_items, longtail_suggestions, limit=limit)

    if not queries:
        return {
            "serp_competition_summary": {
                "summary": {
                    "query_count": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "high_competition_count": 0,
                    "medium_competition_count": 0,
                    "low_competition_count": 0,
                },
                "queries": [],
            }
        }

    fetcher = fetch_html or fetch_naver_serp_html
    query_summaries = [_summarize_single_query(query, fetcher=fetcher) for query in queries]
    summary = {
        "query_count": len(query_summaries),
        "success_count": sum(1 for item in query_summaries if item.get("status") == "success"),
        "error_count": sum(1 for item in query_summaries if item.get("status") != "success"),
        "high_competition_count": sum(
            1 for item in query_summaries if item.get("competition_level") == "high"
        ),
        "medium_competition_count": sum(
            1 for item in query_summaries if item.get("competition_level") == "medium"
        ),
        "low_competition_count": sum(
            1 for item in query_summaries if item.get("competition_level") == "low"
        ),
    }
    return {
        "serp_competition_summary": {
            "summary": summary,
            "queries": query_summaries,
        }
    }


def fetch_naver_serp_html(keyword: str) -> str:
    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        return ""

    wait_for_naver_keyword_request()
    request = Request(
        url=build_search_url(normalized_keyword),
        headers={**_SEARCH_HEADERS, "Referer": "https://search.naver.com/"},
        method="GET",
    )
    with urlopen(request, timeout=6.0) as response:
        return response.read().decode("utf-8", errors="ignore")


def build_search_url(keyword: str) -> str:
    return f"{_SEARCH_ENDPOINT}?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(normalize_text(keyword))}"


def parse_serp_titles(html: str) -> list[dict[str, Any]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for selector in _TITLE_SELECTORS:
        for anchor in soup.select(selector):
            title = normalize_text(anchor.get_text(" ", strip=True))
            href = normalize_text(anchor.get("href"))
            if not title or not href:
                continue
            domain = _extract_domain(href)
            if not domain or domain in {"search.naver.com", "m.search.naver.com"}:
                continue

            key = (normalize_key(title), href)
            if not key[0] or key in seen:
                continue
            seen.add(key)

            results.append(
                {
                    "rank": len(results) + 1,
                    "title": title,
                    "url": href,
                    "domain": domain,
                    "source_bucket": _resolve_source_bucket(domain),
                    "intent_key": _resolve_intent_key(title),
                }
            )
            if len(results) >= 5:
                return results
    return results


def _pick_serp_queries(
    selected_items: list[dict[str, Any]],
    longtail_suggestions: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in sorted(selected_items, key=lambda item: -_coerce_float(item.get("score"))):
        keyword = normalize_text(item.get("keyword"))
        if keyword:
            candidates.append(
                {
                    "query": keyword,
                    "candidate_type": "selected",
                    "score": _coerce_float(item.get("score")),
                }
            )

    for item in sorted(longtail_suggestions, key=_longtail_sort_key):
        keyword = normalize_text(item.get("longtail_keyword"))
        if not keyword:
            continue
        status = str(item.get("verification_status") or "pending").strip().lower()
        if status in {"fail", "error"}:
            continue
        candidates.append(
            {
                "query": keyword,
                "candidate_type": "longtail",
                "score": _coerce_float(item.get("verified_score", item.get("projected_score"))),
            }
        )

    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        query_key = normalize_key(candidate["query"])
        if not query_key or query_key in seen:
            continue
        seen.add(query_key)
        picked.append(candidate)
        if len(picked) >= limit:
            break
    return picked


def _summarize_single_query(
    query: dict[str, Any],
    *,
    fetcher: Callable[[str], str],
) -> dict[str, Any]:
    keyword = normalize_text(query.get("query"))
    search_url = build_search_url(keyword)

    try:
        html = fetcher(keyword)
        titles = parse_serp_titles(html)
    except Exception as exc:
        return {
            "query": keyword,
            "candidate_type": query.get("candidate_type") or "selected",
            "status": "error",
            "search_url": search_url,
            "error": str(exc),
            "top_titles": [],
            "competition_level": "low",
            "competition_score": 0,
            "dominant_intents": [],
            "common_terms": [],
            "source_mix": {},
            "top_domains": [],
        }

    if not titles:
        return {
            "query": keyword,
            "candidate_type": query.get("candidate_type") or "selected",
            "status": "error",
            "search_url": search_url,
            "error": "no_results",
            "top_titles": [],
            "competition_level": "low",
            "competition_score": 0,
            "dominant_intents": [],
            "common_terms": [],
            "source_mix": {},
            "top_domains": [],
        }

    intent_counts = Counter(title["intent_key"] for title in titles if title.get("intent_key"))
    domain_counts = Counter(title["domain"] for title in titles if title.get("domain"))
    source_counts = Counter(title["source_bucket"] for title in titles if title.get("source_bucket"))
    common_terms = _extract_common_terms(keyword, titles)
    competition_score = _calculate_competition_score(
        title_count=len(titles),
        intent_counts=intent_counts,
        common_terms=common_terms,
        domain_counts=domain_counts,
    )
    if competition_score >= 70:
        competition_level = "high"
    elif competition_score >= 45:
        competition_level = "medium"
    else:
        competition_level = "low"

    return {
        "query": keyword,
        "candidate_type": query.get("candidate_type") or "selected",
        "status": "success",
        "search_url": search_url,
        "top_titles": titles,
        "competition_level": competition_level,
        "competition_score": competition_score,
        "dominant_intents": [
            {"intent_key": intent_key, "count": count}
            for intent_key, count in intent_counts.most_common(3)
        ],
        "common_terms": common_terms,
        "source_mix": dict(source_counts),
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in domain_counts.most_common(3)
        ],
    }


def _extract_common_terms(keyword: str, titles: list[dict[str, Any]]) -> list[str]:
    keyword_tokens = {
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
    }
    counter: Counter[str] = Counter()
    for item in titles:
        title_tokens = {
            normalize_key(token)
            for token in tokenize_text(item.get("title"))
            if normalize_key(token)
        }
        for token in title_tokens:
            if token in keyword_tokens or token in _STOPWORD_KEYS or len(token) <= 1:
                continue
            counter[token] += 1
    return [token for token, count in counter.most_common(4) if count >= 2]


def _calculate_competition_score(
    *,
    title_count: int,
    intent_counts: Counter[str],
    common_terms: list[str],
    domain_counts: Counter[str],
) -> int:
    if title_count <= 0:
        return 0
    dominant_ratio = (max(intent_counts.values()) / title_count) if intent_counts else 0.0
    term_ratio = min(1.0, len(common_terms) / 3)
    domain_ratio = (max(domain_counts.values()) / title_count) if domain_counts else 0.0
    return int(round(dominant_ratio * 55 + term_ratio * 25 + domain_ratio * 20))


def _resolve_intent_key(title: str) -> str:
    title_key = normalize_key(title)
    for token_key, intent_key in _INTENT_TOKEN_MAP.items():
        if token_key and token_key in title_key:
            return intent_key
    return "general"


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _resolve_source_bucket(domain: str) -> str:
    safe_domain = str(domain or "").lower()
    if any(token in safe_domain for token in ("blog.", "post.", "cafe.", "tistory.", "brunch.")):
        return "blog"
    if any(token in safe_domain for token in ("go.kr", "or.kr", "ac.kr", "terms.naver.com", "kin.naver.com")):
        return "official"
    if any(token in safe_domain for token in ("shopping", "store", "smartstore", "coupang", "11st", "gmarket", "auction")):
        return "commerce"
    if "news" in safe_domain:
        return "news"
    return "external"


def _longtail_sort_key(item: dict[str, Any]) -> tuple[int, float]:
    status = str(item.get("verification_status") or "pending").strip().lower()
    status_rank = {"pass": 0, "review": 1, "pending": 2}.get(status, 3)
    return (
        status_rank,
        -_coerce_float(item.get("verified_score", item.get("projected_score"))),
    )


def _coerce_limit(value: Any) -> int:
    try:
        limit = int(value or 3)
    except (TypeError, ValueError):
        limit = 3
    return max(1, min(5, limit))


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
