from __future__ import annotations

from typing import Any

from app.expander.sources.naver_autocomplete import get_naver_autocomplete
from app.expander.utils.tokenizer import normalize_text


def expand_autocomplete_engine(keyword: str, strategy: dict[str, Any] | None = None) -> list[dict[str, str]]:
    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    suggestions = get_naver_autocomplete(base_keyword)
    return [
        {
            "keyword": suggestion,
            "origin": base_keyword,
            "type": "autocomplete",
        }
        for suggestion in suggestions
        if normalize_text(suggestion)
    ]
