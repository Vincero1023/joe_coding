from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text


_DEFAULT_SUFFIXES = [
    "추천",
    "후기",
    "가격",
    "정리",
    "비교",
    "리뷰",
]


def expand_suffix(keyword: str, analysis_data: dict[str, Any] | None = None) -> list[dict[str, str]]:
    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    results: list[dict[str, str]] = []
    for suffix in _DEFAULT_SUFFIXES:
        if base_keyword.endswith(suffix):
            continue
        results.append(
            {
                "keyword": f"{base_keyword} {suffix}",
                "origin": base_keyword,
                "type": "suffix",
            }
        )

    return results
