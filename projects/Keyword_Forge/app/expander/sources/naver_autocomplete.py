from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.api_usage import record_api_usage
from app.expander.utils.throttle import wait_for_naver_keyword_request
from app.expander.utils.tokenizer import normalize_text


_ENDPOINT = "https://ac.search.naver.com/nx/ac"
_CACHE: dict[str, list[str]] = {}


def get_naver_autocomplete(keyword: str) -> list[str]:
    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        return []

    cache_key = normalized_keyword.lower()
    if cache_key in _CACHE:
        return list(_CACHE[cache_key])

    wait_for_naver_keyword_request()

    params = urlencode(
        {
            "q": normalized_keyword,
            "con": 0,
            "frm": "nv",
            "ans": 2,
        }
    )
    request = Request(
        url=f"{_ENDPOINT}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=3.0) as response:
            body = response.read().decode("utf-8", errors="ignore")
        data = _parse_response_body(body)
        suggestions = _extract_suggestions(data.get("items"))
        record_api_usage(
            stage="expander",
            service="naver_autocomplete",
            provider="naver",
            endpoint="/nx/ac",
            requested_units=1,
            success=True,
        )
    except Exception:
        record_api_usage(
            stage="expander",
            service="naver_autocomplete",
            provider="naver",
            endpoint="/nx/ac",
            requested_units=1,
            success=False,
        )
        suggestions = []

    _CACHE[cache_key] = suggestions
    return list(suggestions)


def _parse_response_body(body: str) -> dict[str, Any]:
    payload = body.strip()
    if not payload:
        return {}

    callback_start = payload.find("(")
    callback_end = payload.rfind(")")
    if payload.endswith(")") and callback_start != -1 and callback_end > callback_start:
        payload = payload[callback_start + 1 : callback_end]

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _extract_suggestions(items: Any) -> list[str]:
    suggestions: list[str] = []
    if not isinstance(items, list):
        return suggestions

    for group in items:
        if not isinstance(group, list):
            continue
        for item in group:
            suggestion = _extract_keyword(item)
            if suggestion:
                suggestions.append(suggestion)

    return list(dict.fromkeys(suggestions))


def _extract_keyword(item: Any) -> str | None:
    if isinstance(item, str):
        return normalize_text(item) or None
    if isinstance(item, list) and item:
        if isinstance(item[0], str):
            return normalize_text(item[0]) or None
        if isinstance(item[0], dict):
            return _extract_keyword(item[0])
    if isinstance(item, dict):
        for key in ("keyword", "query", "text", "value"):
            if key in item:
                return normalize_text(item.get(key)) or None
    return None
