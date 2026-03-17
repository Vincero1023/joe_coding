from __future__ import annotations

from app.analyzer.rules import (
    HIGH_BID_PATTERNS,
    HIGH_CPC_PATTERNS,
    LOW_BID_PATTERNS,
    LOW_CPC_PATTERNS,
    MEDIUM_BID_PATTERNS,
    MEDIUM_CPC_PATTERNS,
)
from app.expander.utils.tokenizer import normalize_text, tokenize_text


def get_cpc_score(keyword: str) -> float:
    normalized = normalize_text(keyword)
    if _contains_any(normalized, HIGH_CPC_PATTERNS):
        return 1.0
    if _contains_any(normalized, MEDIUM_CPC_PATTERNS):
        return 0.7
    if _contains_any(normalized, LOW_CPC_PATTERNS):
        return 0.3
    return 0.5


def get_bid_score(keyword: str) -> float:
    normalized = normalize_text(keyword)
    if _contains_any(normalized, HIGH_BID_PATTERNS):
        return 1.0
    if _contains_any(normalized, MEDIUM_BID_PATTERNS):
        return 0.6
    if _contains_any(normalized, LOW_BID_PATTERNS):
        return 0.3
    return 0.5


def get_volume_score(keyword: str) -> float:
    token_count = len(tokenize_text(keyword))
    if token_count <= 2:
        return 1.0
    if token_count <= 4:
        return 0.7
    return 0.4


def get_competition_score(keyword: str) -> float:
    token_count = len(tokenize_text(keyword))
    if token_count <= 2:
        return 1.0
    if token_count <= 4:
        return 0.7
    return 0.4


def _contains_any(keyword: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in keyword for pattern in patterns)
