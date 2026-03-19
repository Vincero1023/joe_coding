from __future__ import annotations

import math
import re
from typing import Any

from app.analyzer.config import AnalyzerConfig, DEFAULT_CONFIG
from app.analyzer.keyword_stats import KeywordStats, extract_item_stats
from app.expander.utils.tokenizer import normalize_text, tokenize_text


_HIGH_VALUE_TOPICS: tuple[tuple[str, float], ...] = (
    ("보험", 24.0),
    ("대출", 24.0),
    ("카드", 22.0),
    ("법률", 20.0),
    ("변호사", 20.0),
    ("세무", 18.0),
    ("회계", 18.0),
    ("임플란트", 19.0),
    ("교정", 18.0),
    ("치과", 16.0),
    ("성형", 17.0),
    ("필러", 16.0),
    ("보톡스", 16.0),
    ("다이어트", 14.0),
    ("렌트카", 15.0),
    ("이사", 15.0),
    ("필라테스", 12.0),
    ("헬스장", 12.0),
)

_COMMERCIAL_TERMS: tuple[tuple[str, float], ...] = (
    ("비교", 18.0),
    ("다이렉트", 15.0),
    ("가격", 14.0),
    ("비용", 14.0),
    ("견적", 15.0),
    ("추천", 10.0),
    ("가입", 14.0),
    ("신청", 12.0),
    ("상담", 11.0),
    ("순위", 10.0),
    ("할인", 10.0),
    ("업체", 8.0),
    ("사이트", 8.0),
)

_INFORMATION_TERMS: tuple[tuple[str, float], ...] = (
    ("뜻", -28.0),
    ("정의", -26.0),
    ("정리", -16.0),
    ("방법", -16.0),
    ("원인", -16.0),
    ("증상", -18.0),
    ("부작용", -18.0),
    ("효과", -12.0),
    ("레시피", -18.0),
    ("만들기", -18.0),
    ("칼로리", -18.0),
    ("후기", -6.0),
    ("리뷰", -8.0),
)

_OFFICIAL_HINTS: tuple[str, ...] = (
    "수강신청",
    "보수교육",
    "연수원",
    "로그인",
    "홈페이지",
    "고객센터",
    "민원",
    "조회",
    "공단",
    "협회",
    "공사",
)

_LOCAL_HINTS: tuple[str, ...] = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "제주",
    "강남",
    "서초",
    "송파",
    "분당",
    "판교",
    "수원",
    "용인",
    "성남",
    "일산",
    "부천",
    "평택",
    "천안",
    "청주",
    "전주",
    "순천",
    "여수",
    "목포",
    "창원",
    "김해",
    "해운대",
    "압구정",
    "청담",
    "잠실",
)

_BRAND_HINTS: tuple[str, ...] = (
    "kb",
    "db",
    "axa",
    "현대해상",
    "삼성화재",
    "메리츠",
    "한화",
    "교보",
    "롯데",
    "신한",
    "우리",
    "카카오",
    "네이버",
)

_MODIFIER_TERMS: tuple[str, ...] = (
    "비교",
    "다이렉트",
    "가격",
    "비용",
    "견적",
    "추천",
    "가입",
    "신청",
    "사이트",
    "후기",
    "리뷰",
    "조회",
)


def calculate_profit(top_bid: float, estimated_clicks: float) -> float:
    if top_bid <= 0 or estimated_clicks <= 0:
        return 0.0
    return round((top_bid * estimated_clicks) / 1000.0, 2)


def calculate_opportunity(search_volume: float, competition_base: float) -> float:
    if search_volume <= 0:
        return 0.0
    return round(search_volume / max(competition_base, 1.0), 4)


def calculate_final_score(
    monetization_score: float,
    volume_score: float,
    rarity_score: float,
    config: AnalyzerConfig = DEFAULT_CONFIG,
) -> float:
    weighted_score = (
        (monetization_score * config.monetization_weight)
        + (volume_score * config.volume_weight)
        + (rarity_score * config.rarity_weight)
    )
    return float(math.floor(weighted_score + 0.5))


def classify_priority(score: float, config: AnalyzerConfig = DEFAULT_CONFIG) -> str:
    if score >= config.high_priority_threshold:
        return "high"
    if score >= config.medium_priority_threshold:
        return "medium"
    return "low"


def classify_grade(score: float) -> str:
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C"
    if score >= 25:
        return "D"
    return "F"


def analyze_items(
    items: list[dict[str, Any]],
    *,
    stats_index: dict[str, KeywordStats] | None = None,
    config: AnalyzerConfig = DEFAULT_CONFIG,
) -> list[dict[str, Any]]:
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

        scored_item = _score_item(item, stats_index=stats_index, config=config)
        if scored_item is None:
            continue
        if scored_item["analysis_mode"] != "search_metrics" and scored_item["score"] < config.minimum_score:
            continue

        analyzed.append(scored_item)

    analyzed.sort(key=lambda item: item["score"], reverse=True)
    return analyzed


def _score_item(
    item: dict[str, Any],
    *,
    stats_index: dict[str, KeywordStats] | None,
    config: AnalyzerConfig,
) -> dict[str, Any] | None:
    keyword = normalize_text(item.get("keyword"))
    if not keyword:
        return None

    heuristic_metrics = _estimate_heuristic_metrics(keyword)
    keyword_stats = extract_item_stats(item, stats_index)

    if keyword_stats is not None and (
        keyword_stats.resolved_total_searches() > 0
        or keyword_stats.resolved_primary_bid() > 0
        or (keyword_stats.blog_results or 0) > 0
    ):
        analysis_mode = "search_metrics"
        confidence = _derive_stats_confidence(keyword_stats)
        metrics = _build_metrics_from_stats(keyword_stats, fallback=heuristic_metrics)
    else:
        analysis_mode = "heuristic"
        confidence = 0.35
        metrics = heuristic_metrics

    score = calculate_final_score(
        metrics["monetization_score"],
        metrics["volume_score"],
        metrics["rarity_score"],
        config,
    )

    metrics = {
        **metrics,
        "confidence": round(confidence, 2),
    }

    return {
        "keyword": keyword,
        "origin": normalize_text(item.get("origin")) or normalize_text(item.get("root_origin")) or keyword,
        "type": normalize_text(item.get("type")) or "manual_input",
        "score": score,
        "priority": classify_priority(score, config),
        "grade": classify_grade(score),
        "analysis_mode": analysis_mode,
        "confidence": round(confidence, 2),
        "metrics": metrics,
    }


def _build_metrics_from_stats(stats: KeywordStats, *, fallback: dict[str, float]) -> dict[str, float]:
    total_searches = stats.resolved_total_searches()
    if total_searches <= 0:
        total_searches = 0.0

    blog_results = _coerce_non_negative(stats.blog_results, default=0.0)
    primary_bid = stats.resolved_primary_bid()
    if primary_bid <= 0:
        primary_bid = 0.0

    average_bid = stats.resolved_average_bid()
    if average_bid <= 0:
        average_bid = 0.0

    total_clicks = stats.resolved_total_clicks()
    if total_clicks <= 0:
        total_clicks = 0.0

    volume_score = _scale_search_volume(total_searches)
    monetization_score = _scale_bid_value(average_bid)
    opportunity_ratio = calculate_opportunity(total_searches, blog_results)
    rarity_score = _scale_blog_rarity(blog_results)
    competition_ratio = round(blog_results / max(total_searches, 1.0), 4)
    profit = calculate_profit(average_bid, total_clicks)

    return {
        "volume": round(total_searches, 4),
        "competition": competition_ratio,
        "cpc": round(average_bid, 4),
        "bid": round(primary_bid, 4),
        "profit": profit,
        "opportunity": opportunity_ratio,
        "volume_score": volume_score,
        "search_volume_score": volume_score,
        "monetization_score": monetization_score,
        "cpc_score": monetization_score,
        "rarity_score": rarity_score,
        "pc_searches": round(_coerce_non_negative(stats.pc_searches, default=0.0), 4),
        "mobile_searches": round(_coerce_non_negative(stats.mobile_searches, default=0.0), 4),
        "blog_results": round(blog_results, 4),
        "pc_clicks": round(_coerce_non_negative(stats.pc_clicks, default=0.0), 4),
        "mobile_clicks": round(_coerce_non_negative(stats.mobile_clicks, default=0.0), 4),
        "total_clicks": round(total_clicks, 4),
        "bid_1": round(_coerce_non_negative(stats.bid_1, default=primary_bid), 4),
        "bid_2": round(_coerce_non_negative(stats.bid_2, default=0.0), 4),
        "bid_3": round(_coerce_non_negative(stats.bid_3, default=0.0), 4),
        "bid_4": round(_coerce_non_negative(stats.bid_4, default=0.0), 4),
        "bid_5": round(_coerce_non_negative(stats.bid_5, default=0.0), 4),
        "bid_6": round(_coerce_non_negative(stats.bid_6, default=0.0), 4),
        "bid_7": round(_coerce_non_negative(stats.bid_7, default=0.0), 4),
        "bid_8": round(_coerce_non_negative(stats.bid_8, default=0.0), 4),
        "bid_9": round(_coerce_non_negative(stats.bid_9, default=0.0), 4),
        "bid_10": round(_coerce_non_negative(stats.bid_10, default=0.0), 4),
        "mobile_bid_1": round(_coerce_non_negative(stats.mobile_bid_1, default=0.0), 4),
        "mobile_bid_2": round(_coerce_non_negative(stats.mobile_bid_2, default=0.0), 4),
        "mobile_bid_3": round(_coerce_non_negative(stats.mobile_bid_3, default=0.0), 4),
        "mobile_bid_4": round(_coerce_non_negative(stats.mobile_bid_4, default=0.0), 4),
        "mobile_bid_5": round(_coerce_non_negative(stats.mobile_bid_5, default=0.0), 4),
    }


def _estimate_heuristic_metrics(keyword: str) -> dict[str, float]:
    normalized = normalize_text(keyword)
    token_count = max(1, len(tokenize_text(keyword)))
    modifier_count = sum(1 for term in _MODIFIER_TERMS if term in normalized)
    contains_official = _contains_any(normalized, _OFFICIAL_HINTS)
    contains_local = _contains_any(normalized, _LOCAL_HINTS)
    contains_brand = _contains_any(normalized.lower(), _BRAND_HINTS) or bool(re.search(r"[A-Za-z]{2,}", normalized))

    monetization_seed = 18.0
    volume_seed = 76.0 - ((token_count - 1) * 8.0) - (modifier_count * 7.0)
    rarity_seed = 24.0 + ((token_count - 1) * 5.0) + (modifier_count * 4.0)

    for token, weight in _HIGH_VALUE_TOPICS:
        if token in normalized:
            monetization_seed += weight
            volume_seed += 4.0
            rarity_seed -= 3.0

    for token, weight in _COMMERCIAL_TERMS:
        if token in normalized:
            monetization_seed += weight
            rarity_seed += 3.0

    for token, weight in _INFORMATION_TERMS:
        if token in normalized:
            monetization_seed += weight
            rarity_seed -= 3.0

    if contains_official:
        monetization_seed -= 30.0
        volume_seed -= 18.0
        rarity_seed -= 6.0

    if contains_local:
        monetization_seed += 5.0
        volume_seed -= 14.0
        rarity_seed += 14.0

    if contains_brand:
        monetization_seed -= 4.0
        volume_seed -= 10.0
        rarity_seed += 8.0

    if len(normalized) >= 16:
        volume_seed -= 12.0
        rarity_seed += 10.0

    volume_score = _clamp(volume_seed, 8.0, 95.0)
    raw_bid = _clamp(30.0 + (monetization_seed * 5.2), 20.0, 1200.0)
    average_bid = round(raw_bid * 0.74, 4)
    monetization_score = _clamp(average_bid / 7.0, 5.0, 100.0)
    rarity_score = _clamp(rarity_seed, 8.0, 95.0)
    estimated_volume = round(10 ** ((volume_score + 20.0) / 25.0), 4)
    opportunity_ratio = round(1.0 + (rarity_score / 40.0), 4)
    competition_ratio = round(1.0 / max(opportunity_ratio, 1.0), 4)
    estimated_blog_results = round(max(estimated_volume * competition_ratio, 1.0), 4)
    estimated_clicks = round(estimated_volume * _estimate_ctr(monetization_score, rarity_score), 4)

    return {
        "volume": estimated_volume,
        "competition": competition_ratio,
        "cpc": average_bid,
        "bid": round(raw_bid, 4),
        "profit": calculate_profit(average_bid, estimated_clicks),
        "opportunity": opportunity_ratio,
        "volume_score": volume_score,
        "search_volume_score": volume_score,
        "monetization_score": monetization_score,
        "cpc_score": monetization_score,
        "rarity_score": rarity_score,
        "pc_searches": round(estimated_volume * 0.24, 4),
        "mobile_searches": round(estimated_volume * 0.76, 4),
        "blog_results": estimated_blog_results,
        "pc_clicks": round(estimated_clicks * 0.28, 4),
        "mobile_clicks": round(estimated_clicks * 0.72, 4),
        "total_clicks": estimated_clicks,
        "bid_1": round(raw_bid, 4),
        "bid_2": round(raw_bid * 0.72, 4),
        "bid_3": round(raw_bid * 0.55, 4),
    }


def _scale_search_volume(search_volume: float) -> float:
    if search_volume <= 0:
        return 0.0
    if search_volume >= 50_000:
        return 100.0
    if search_volume >= 10_000:
        return 90.0
    if search_volume >= 1_000:
        return 60.0
    if search_volume >= 100:
        return 25.0
    return 10.0


def _scale_bid_value(top_bid: float) -> float:
    if top_bid <= 0:
        return 0.0
    if top_bid >= 50_000:
        return 100.0
    if top_bid >= 20_000:
        return 90.0
    if top_bid >= 10_000:
        return 75.0
    if top_bid >= 5_000:
        return 25.0
    return 10.0


def _scale_opportunity_ratio(opportunity_ratio: float) -> float:
    if opportunity_ratio <= 0:
        return 0.0
    if opportunity_ratio >= 20.0:
        return 100.0
    if opportunity_ratio >= 10.0:
        return 75.0
    if opportunity_ratio >= 5.0:
        return 55.0
    if opportunity_ratio >= 1.5:
        return 35.0
    return 15.0


def _scale_blog_rarity(blog_results: float) -> float:
    if blog_results <= 0:
        return 100.0
    if blog_results < 5_000:
        return 35.0
    return 15.0


def _estimate_ctr(monetization_score: float, rarity_score: float) -> float:
    return _clamp(0.0025 + (monetization_score / 10000.0) + (rarity_score / 20000.0), 0.0025, 0.03)


def _derive_stats_confidence(stats: KeywordStats) -> float:
    confidence = 0.55
    if stats.resolved_total_searches() > 0:
        confidence += 0.2
    if (stats.blog_results or 0) > 0:
        confidence += 0.1
    if stats.resolved_primary_bid() > 0:
        confidence += 0.15
    if stats.resolved_total_clicks() > 0:
        confidence += 0.05
    return _clamp(confidence, 0.0, 0.98)


def _contains_any(keyword: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in keyword for pattern in patterns)


def _coerce_non_negative(value: float | None, *, default: float) -> float:
    if value is None or value < 0:
        return default
    return float(value)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


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
