from __future__ import annotations

from typing import Any

from app.expander.sources.naver_related import get_naver_related_queries
from app.expander.utils.tokenizer import normalize_text


def expand_related_engine(
    keyword: str,
    strategy: dict[str, Any] | None = None,
    collected_item: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    del strategy
    del collected_item

    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    return [
        {
            "keyword": suggestion,
            "origin": base_keyword,
            "type": "related",
        }
        for suggestion in get_naver_related_queries(base_keyword)
        if normalize_text(suggestion)
    ]
