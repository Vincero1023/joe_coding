from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, quote, unquote_plus, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from app.core.api_usage import record_api_usage
from app.expander.utils.throttle import wait_for_naver_keyword_request
from app.expander.utils.tokenizer import normalize_key, normalize_text


_SEARCH_ENDPOINT = "https://search.naver.com/search.naver"
_QRA_API_URL_PATTERN = re.compile(
    r'(?:\"apiURL\"|apiURL)\s*:\s*("https://s\.search\.naver\.com/p/qra/1/search\.naver\?[^"]+")'
)
_CACHE: dict[str, list[str]] = {}
_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="135", "Not-A.Brand";v="8", "Google Chrome";v="135"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def get_naver_related_queries(keyword: str) -> list[str]:
    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        return []

    cache_key = normalized_keyword.lower()
    if cache_key in _CACHE:
        return list(_CACHE[cache_key])

    wait_for_naver_keyword_request()
    search_url = f"{_SEARCH_ENDPOINT}?where=nexearch&query={quote(normalized_keyword)}"

    request = Request(
        url=search_url,
        headers={**_SEARCH_HEADERS, "Referer": "https://search.naver.com/"},
        method="GET",
    )

    try:
        with urlopen(request, timeout=5.0) as response:
            html = response.read().decode("utf-8", errors="ignore")
        record_api_usage(
            stage="expander",
            service="naver_related_search",
            provider="naver",
            endpoint="/search.naver",
            requested_units=1,
            success=True,
        )
        related_queries = _fetch_qra_related_queries(
            html=html,
            keyword=normalized_keyword,
            referer_url=search_url,
        )
        if not related_queries:
            related_queries = _extract_related_queries(html, normalized_keyword)
    except Exception:
        record_api_usage(
            stage="expander",
            service="naver_related_search",
            provider="naver",
            endpoint="/search.naver",
            requested_units=1,
            success=False,
        )
        related_queries = []

    _CACHE[cache_key] = related_queries
    return list(related_queries)


def _fetch_qra_related_queries(*, html: str, keyword: str, referer_url: str) -> list[str]:
    api_url = _extract_qra_api_url(html)
    if not api_url:
        return []

    wait_for_naver_keyword_request()
    request = Request(
        url=api_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": referer_url,
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=5.0) as response:
            body = response.read().decode("utf-8", errors="ignore")
        record_api_usage(
            stage="expander",
            service="naver_related_qra",
            provider="naver",
            endpoint="/p/qra/1/search.naver",
            requested_units=1,
            success=True,
        )
    except Exception:
        record_api_usage(
            stage="expander",
            service="naver_related_qra",
            provider="naver",
            endpoint="/p/qra/1/search.naver",
            requested_units=1,
            success=False,
        )
        return []

    return _extract_related_queries_from_qra_response(body, keyword)


def _extract_qra_api_url(html: str) -> str | None:
    if not html:
        return None

    match = _QRA_API_URL_PATTERN.search(html)
    if match is None:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _extract_related_queries_from_qra_response(body: str, keyword: str) -> list[str]:
    if not body:
        return []

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return []

    contents = parsed.get("result", {}).get("contents")
    if not isinstance(contents, list):
        return []

    results: list[str] = []
    seen: set[str] = set()
    keyword_key = normalize_key(keyword)

    for item in contents:
        if not isinstance(item, dict):
            continue

        related_keyword = normalize_text(item.get("query"))
        related_key = normalize_key(related_keyword)
        if not related_key or related_key == keyword_key or related_key in seen:
            continue

        seen.add(related_key)
        results.append(related_keyword)

    return results


def _extract_related_queries(html: str, keyword: str) -> list[str]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    related_section = soup.select_one("#nx_right_related_keywords")
    if related_section is None:
        return []

    results: list[str] = []
    seen: set[str] = set()
    keyword_key = normalize_key(keyword)

    for anchor in related_section.select("a.keyword[href]"):
        related_keyword = _extract_anchor_keyword(anchor)
        if not related_keyword:
            continue

        related_key = normalize_key(related_keyword)
        if not related_key or related_key == keyword_key or related_key in seen:
            continue

        seen.add(related_key)
        results.append(related_keyword)

    return results


def _extract_anchor_keyword(anchor) -> str:
    title_node = anchor.select_one(".tit")
    if title_node is not None:
        title_text = normalize_text(title_node.get_text(" ", strip=True))
        if title_text:
            return title_text

    href = str(anchor.get("href") or "").strip()
    if href:
        parsed = urlparse(href)
        query_values = parse_qs(parsed.query).get("query", [])
        if query_values:
            return normalize_text(unquote_plus(query_values[0]))

    return normalize_text(anchor.get_text(" ", strip=True))
