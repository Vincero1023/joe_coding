from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text


_DEFAULT_RELATED_TERMS = ["연관", "추천", "비교"]


def expand_related_engine(
    keyword: str,
    strategy: dict[str, Any] | None = None,
    collected_item: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    related_terms = []
    if isinstance(strategy, dict):
        related_terms = [normalize_text(item) for item in strategy.get("related_terms", []) if normalize_text(item)]

    if not related_terms:
        related_terms = list(_DEFAULT_RELATED_TERMS)

    category = normalize_text(collected_item.get("category")) if isinstance(collected_item, dict) else ""
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for term in related_terms:
        if term in seen or term in base_keyword:
            continue
        seen.add(term)
        results.append(
            {
                "keyword": f"{base_keyword} {term}",
                "origin": base_keyword,
                "type": "related",
            }
        )

    if category and category not in base_keyword:
        results.append(
            {
                "keyword": f"{base_keyword} {category}",
                "origin": base_keyword,
                "type": "related",
            }
        )

    return results
