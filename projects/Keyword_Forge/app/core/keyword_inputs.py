from __future__ import annotations

import re
from typing import Any

from app.expander.utils.tokenizer import normalize_text


_KEYWORD_SPLIT_PATTERN = re.compile(r"[\r\n,;]+")


def parse_keyword_text(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []

    tokens = [normalize_text(item) for item in _KEYWORD_SPLIT_PATTERN.split(value)]
    return _unique_keywords(tokens)


def extract_keyword_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return parse_keyword_text(value)

    if not isinstance(value, list):
        return []

    results: list[str] = []
    for item in value:
        if isinstance(item, str):
            results.extend(parse_keyword_text(item))
            continue

        if isinstance(item, dict):
            keyword = normalize_text(item.get("keyword"))
            if keyword:
                results.append(keyword)

    return _unique_keywords(results)


def coerce_collected_keyword_items(
    input_data: dict[str, Any],
    *,
    default_category: str | None = None,
    default_source: str = "manual_input",
) -> list[dict[str, Any]]:
    raw_items = input_data.get("collected_keywords")
    normalized_items = _normalize_existing_collected_items(raw_items)
    if normalized_items:
        return normalized_items

    keywords = _extract_manual_keywords(input_data)
    category = normalize_text(input_data.get("category")) or default_category
    source = normalize_text(input_data.get("source")) or default_source

    return [
        {
            "keyword": keyword,
            "category": category,
            "source": source,
            "raw": keyword,
        }
        for keyword in keywords
    ]


def coerce_expanded_keyword_items(
    input_data: Any,
    *,
    default_type: str = "manual_input",
) -> list[dict[str, Any]]:
    if isinstance(input_data, list):
        normalized = _normalize_existing_expanded_items(input_data)
        if normalized:
            return normalized

        keywords = extract_keyword_strings(input_data)
        return [_build_expanded_item(keyword, default_type=default_type) for keyword in keywords]

    if not isinstance(input_data, dict):
        return []

    raw_items = input_data.get("expanded_keywords")
    normalized_items = _normalize_existing_expanded_items(raw_items)
    if normalized_items:
        return normalized_items

    keywords = _extract_manual_keywords(input_data)
    return [_build_expanded_item(keyword, default_type=default_type) for keyword in keywords]


def _extract_manual_keywords(input_data: dict[str, Any]) -> list[str]:
    manual_keywords: list[str] = []
    manual_keywords.extend(parse_keyword_text(input_data.get("keywords_text")))
    manual_keywords.extend(extract_keyword_strings(input_data.get("keywords")))
    manual_keywords.extend(extract_keyword_strings(input_data.get("seed_keywords")))
    return _unique_keywords(manual_keywords)


def _normalize_existing_collected_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []

    normalized_items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue

        normalized_items.append(
            {
                "keyword": keyword,
                "category": normalize_text(item.get("category")) or None,
                "source": normalize_text(item.get("source")) or "manual_input",
                "raw": normalize_text(item.get("raw")) or keyword,
            }
        )

    return normalized_items


def _normalize_existing_expanded_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []

    normalized_items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue

        normalized_items.append(
            {
                "keyword": keyword,
                "origin": normalize_text(item.get("origin")) or normalize_text(item.get("root_origin")) or keyword,
                "type": normalize_text(item.get("type")) or "manual_input",
            }
        )

    return normalized_items


def _build_expanded_item(keyword: str, *, default_type: str) -> dict[str, Any]:
    return {
        "keyword": keyword,
        "origin": keyword,
        "type": default_type,
    }


def _unique_keywords(items: list[str]) -> list[str]:
    unique_items: list[str] = []
    seen: set[str] = set()
    for item in items:
        keyword = normalize_text(item)
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        unique_items.append(keyword)
    return unique_items
