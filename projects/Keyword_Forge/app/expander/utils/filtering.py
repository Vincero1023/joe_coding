from __future__ import annotations

import re
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text


_REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{2,}")


def filter_expansions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for item in items:
        keyword = normalize_text(item.get("keyword"))
        origin = normalize_text(item.get("origin"))
        expansion_type = normalize_text(item.get("type"))
        if not keyword or not origin or not expansion_type:
            continue
        if normalize_key(keyword) == normalize_key(origin):
            continue
        if len(keyword) > 30:
            continue

        tokens = tokenize_text(keyword)
        if len(tokens) < 1 or len(tokens) > 6:
            continue
        if _is_noisy_keyword(keyword, tokens):
            continue
        if expansion_type != "related":
            if not is_relevant(keyword, origin):
                continue
            if similarity(keyword, origin) < 0.3 and normalize_key(origin) not in normalize_key(keyword):
                continue

        filtered.append(
            {
                "keyword": keyword,
                "origin": origin,
                "type": expansion_type,
            }
        )

    return filtered


def apply_seed_filter(items: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    normalized_seed = normalize_key(seed)
    if not normalized_seed:
        return items

    return [
        item
        for item in items
        if normalized_seed in normalize_key(item.get("keyword"))
        or is_relevant(item.get("keyword"), seed)
    ]


def limit_expansions_per_origin(items: list[dict[str, Any]], max_per_origin: int = 20) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    limited: list[dict[str, Any]] = []

    for item in items:
        origin_key = normalize_key(item.get("origin"))
        if not origin_key:
            continue

        current_count = counts.get(origin_key, 0)
        if current_count >= max_per_origin:
            continue

        counts[origin_key] = current_count + 1
        limited.append(item)

    return limited


def limit_total_expansions(
    items: list[dict[str, Any]],
    totals: dict[str, int],
    max_total_per_origin: int = 50,
) -> list[dict[str, Any]]:
    limited: list[dict[str, Any]] = []

    for item in items:
        origin_key = normalize_key(item.get("origin"))
        if not origin_key:
            continue

        current_total = totals.get(origin_key, 0)
        if current_total >= max_total_per_origin:
            continue

        totals[origin_key] = current_total + 1
        limited.append(item)

    return limited


def is_relevant(keyword: Any, origin: Any) -> bool:
    keyword_tokens = set(tokenize_text(keyword))
    origin_tokens = set(tokenize_text(origin))
    return len(keyword_tokens & origin_tokens) >= 1


def similarity(a: Any, b: Any) -> float:
    tokens_a = set(tokenize_text(a))
    tokens_b = set(tokenize_text(b))
    if not tokens_a:
        return 0.0
    common_tokens = tokens_a & tokens_b
    return len(common_tokens) / len(tokens_a)


def _is_noisy_keyword(keyword: str, tokens: list[str]) -> bool:
    lowered_tokens = [token.lower() for token in tokens]
    token_counts: dict[str, int] = {}
    for token in lowered_tokens:
        token_counts[token] = token_counts.get(token, 0) + 1

    if any(count > 2 for count in token_counts.values()):
        return True
    if len(lowered_tokens) != len(set(lowered_tokens)):
        return True
    if any(lowered_tokens[index] == lowered_tokens[index - 1] for index in range(1, len(lowered_tokens))):
        return True
    if _REPEATED_CHAR_PATTERN.search(keyword.replace(" ", "")):
        return True
    if any(_looks_weird(token) for token in tokens):
        return True
    return False


def _looks_weird(token: str) -> bool:
    compact = token.strip()
    if len(compact) == 1:
        return True
    if compact.isdigit():
        return True
    return False
