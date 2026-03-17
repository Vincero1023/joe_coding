from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text


_ASSOCIATION_BY_FUNCTION = {
    "keyword_analysis": ["분석", "트렌드"],
    "keyword_expansion": ["연관", "확장"],
    "content_guidance": ["가이드"],
}

_DEFAULT_ASSOCIATIONS = ["인기", "가이드"]


def expand_association(keyword: str, analysis_data: dict[str, Any] | None = None) -> list[dict[str, str]]:
    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    associations: list[str] = []
    for function_name in analysis_data.get("core_functions", []) if isinstance(analysis_data, dict) else []:
        associations.extend(_ASSOCIATION_BY_FUNCTION.get(str(function_name), []))

    if not associations:
        associations = list(_DEFAULT_ASSOCIATIONS)

    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for association in associations:
        if association in seen or association in base_keyword:
            continue
        seen.add(association)
        results.append(
            {
                "keyword": f"{base_keyword} {association}",
                "origin": base_keyword,
                "type": "association",
            }
        )

    return results
