from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text, tokenize_text


_DEFAULT_MODIFIERS = ["추천", "정리"]


def expand_combinator(keyword: str, analysis_data: dict[str, Any] | None = None) -> list[dict[str, str]]:
    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    tokens = tokenize_text(base_keyword)
    results: list[dict[str, str]] = []

    if len(tokens) >= 2:
        compact_keyword = "".join(tokens)
        if compact_keyword != base_keyword:
            results.append(
                {
                    "keyword": compact_keyword,
                    "origin": base_keyword,
                    "type": "combinator",
                }
            )

        pair_keyword = " ".join(tokens[:2])
        if pair_keyword != base_keyword:
            results.append(
                {
                    "keyword": pair_keyword,
                    "origin": base_keyword,
                    "type": "combinator",
                }
            )

        tail_keyword = " ".join(tokens[-2:])
        if tail_keyword != base_keyword and tail_keyword != pair_keyword:
            results.append(
                {
                    "keyword": tail_keyword,
                    "origin": base_keyword,
                    "type": "combinator",
                }
            )

        return results

    modifiers = _extract_modifiers(analysis_data)
    for modifier in modifiers:
        results.append(
            {
                "keyword": f"{base_keyword} {modifier}",
                "origin": base_keyword,
                "type": "combinator",
            }
        )

    return results


def _extract_modifiers(analysis_data: dict[str, Any] | None) -> list[str]:
    modifiers: list[str] = []
    if isinstance(analysis_data, dict):
        for value in analysis_data.get("important_keywords", []):
            text = normalize_text(value)
            if not text or len(text) > 6:
                continue
            if text.isascii():
                continue
            modifiers.append(text)

    if not modifiers:
        modifiers = list(_DEFAULT_MODIFIERS)

    return list(dict.fromkeys(modifiers[:2]))
