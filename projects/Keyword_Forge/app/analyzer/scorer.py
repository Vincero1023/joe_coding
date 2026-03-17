from __future__ import annotations

from typing import Any

from app.analyzer.config import AnalyzerConfig, DEFAULT_CONFIG
from app.analyzer.metrics import (
    get_bid_score,
    get_competition_score,
    get_cpc_score,
    get_volume_score,
)
from app.expander.utils.tokenizer import normalize_text, tokenize_text


def calculate_profit(cpc: float, bid: float) -> float:
    return round(cpc * bid, 4)


def calculate_opportunity(volume: float, competition: float) -> float:
    if competition <= 0:
        return 0.0
    return round(volume / competition, 4)


def calculate_final_score(
    profit: float,
    opportunity: float,
    config: AnalyzerConfig = DEFAULT_CONFIG,
) -> float:
    return round(
        (profit * config.profit_weight)
        + (opportunity * config.opportunity_weight),
        4,
    )


def classify_priority(score: float, config: AnalyzerConfig = DEFAULT_CONFIG) -> str:
    if score >= config.high_priority_threshold:
        return "high"
    if score >= config.medium_priority_threshold:
        return "medium"
    return "low"


def score_keyword(keyword: str, config: AnalyzerConfig = DEFAULT_CONFIG) -> tuple[float, dict[str, float]]:
    cpc = get_cpc_score(keyword)
    bid = get_bid_score(keyword)
    volume = get_volume_score(keyword)
    competition = get_competition_score(keyword)
    profit = calculate_profit(cpc, bid)
    opportunity = calculate_opportunity(volume, competition)
    final_score = calculate_final_score(profit, opportunity, config)

    metrics = {
        "volume": volume,
        "cpc": cpc,
        "competition": competition,
        "bid": bid,
        "profit": profit,
        "opportunity": opportunity,
    }
    return final_score, metrics


def analyze_items(items: list[dict[str, Any]], config: AnalyzerConfig = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    analyzed: list[dict[str, Any]] = []

    for item in items:
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue

        tokens = tokenize_text(keyword)
        if len(tokens) > config.max_tokens:
            continue
        if _is_meaningless_keyword(tokens):
            continue

        score, metrics = score_keyword(keyword, config)
        if score < config.minimum_score:
            continue

        analyzed.append(
            {
                "keyword": keyword,
                "score": score,
                "priority": classify_priority(score, config),
                "metrics": metrics,
            }
        )

    analyzed.sort(key=lambda item: item["score"], reverse=True)
    return analyzed


def _is_meaningless_keyword(tokens: list[str]) -> bool:
    if not tokens:
        return True

    lowered_tokens = [token.lower() for token in tokens]
    if len(set(lowered_tokens)) == 1 and len(lowered_tokens) > 1:
        return True

    for index in range(1, len(lowered_tokens)):
        if lowered_tokens[index] == lowered_tokens[index - 1]:
            return True

    counts: dict[str, int] = {}
    for token in lowered_tokens:
        counts[token] = counts.get(token, 0) + 1
        if counts[token] > 2:
            return True

    return False
