from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_key


def deduplicate_expansions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduplicated: list[dict[str, Any]] = []

    for item in items:
        keyword_key = normalize_key(item.get("keyword"))
        origin_key = normalize_key(item.get("origin"))
        identity = (origin_key, keyword_key)
        if not keyword_key or not origin_key or identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(item)

    return deduplicated
