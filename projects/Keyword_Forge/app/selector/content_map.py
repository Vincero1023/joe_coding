from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text


_INTENT_GROUPS: dict[str, tuple[str, ...]] = {
    "commercial": ("추천", "비교", "가격", "견적", "순위", "비용", "요금", "구매", "할인"),
    "info": ("뜻", "정리", "방법", "사용법", "가이드", "팁", "종류", "기초", "설명"),
    "review": ("후기", "리뷰", "장단점", "평가", "경험"),
    "problem": ("원인", "해결", "증상", "부작용", "주의", "대처"),
    "action": ("가입", "신청", "등록", "조회", "발급", "예약", "설정"),
}

_INTENT_LABELS: dict[str, str] = {
    "commercial": "commercial",
    "info": "info",
    "review": "review",
    "problem": "problem",
    "action": "action",
    "general": "general",
}

_INTENT_TOKEN_MAP = {
    normalize_key(token): intent_key
    for intent_key, tokens in _INTENT_GROUPS.items()
    for token in tokens
    if normalize_key(token)
}
_INTENT_TOKEN_KEYS = tuple(sorted(_INTENT_TOKEN_MAP.keys(), key=len, reverse=True))


def build_content_map(items: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [_build_entry(item) for item in items if isinstance(item, dict) and normalize_text(item.get("keyword"))]
    if not entries:
        return {
            "keyword_clusters": [],
            "content_map_summary": {
                "keyword_count": 0,
                "cluster_count": 0,
                "article_count": 0,
                "split_cluster_count": 0,
            },
        }

    grouped_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped_entries[entry["core_key"]].append(entry)

    clusters = [
        _build_cluster(entries_in_cluster)
        for entries_in_cluster in grouped_entries.values()
        if entries_in_cluster
    ]
    clusters.sort(key=_cluster_sort_key, reverse=True)

    for index, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = f"cluster-{index:02d}"

    summary = {
        "keyword_count": len(entries),
        "cluster_count": len(clusters),
        "article_count": sum(int(cluster.get("recommended_article_count") or 0) for cluster in clusters),
        "split_cluster_count": sum(
            1
            for cluster in clusters
            if int(cluster.get("recommended_article_count") or 0) > 1
        ),
    }
    return {
        "keyword_clusters": clusters,
        "content_map_summary": summary,
    }


def _build_entry(item: dict[str, Any]) -> dict[str, Any]:
    keyword = normalize_text(item.get("keyword"))
    tokens = [normalize_text(token) for token in tokenize_text(keyword) if normalize_text(token)]
    normalized_tokens = [normalize_key(token) for token in tokens if normalize_key(token)]
    intent_positions = [index for index, token_key in enumerate(normalized_tokens) if token_key in _INTENT_TOKEN_MAP]
    first_intent_position = intent_positions[0] if intent_positions else None

    if first_intent_position is not None and first_intent_position > 0:
        core_terms = tokens[:first_intent_position]
        core_token_keys = normalized_tokens[:first_intent_position]
    else:
        core_terms = [token for token, token_key in zip(tokens, normalized_tokens) if token_key not in _INTENT_TOKEN_MAP]
        core_token_keys = [token_key for token_key in normalized_tokens if token_key not in _INTENT_TOKEN_MAP]

    score = _coerce_float(item.get("score"))
    confidence = _coerce_float(item.get("confidence", item.get("metrics", {}).get("confidence")))
    volume = _coerce_float(item.get("metrics", {}).get("volume"))
    cpc = _coerce_float(item.get("metrics", {}).get("cpc"))

    return {
        "item": item,
        "keyword": keyword,
        "tokens": tokens,
        "normalized_tokens": normalized_tokens,
        "core_terms": core_terms or [keyword],
        "core_key": _build_core_key(keyword, core_token_keys),
        "intent_key": _resolve_intent_key(normalized_tokens),
        "intent_label": _INTENT_LABELS[_resolve_intent_key(normalized_tokens)],
        "grade": _resolve_grade(item),
        "profitability_grade": _resolve_profitability_grade(item),
        "attackability_grade": _resolve_attackability_grade(item),
        "combo_grade": _resolve_combo_grade(item),
        "golden_bucket": _resolve_golden_bucket(item),
        "score": score,
        "confidence": confidence,
        "volume": volume,
        "cpc": cpc,
    }


def _build_core_key(keyword: str, core_token_keys: list[str]) -> str:
    if core_token_keys:
        return "".join(core_token_keys)

    keyword_key = normalize_key(keyword)
    for intent_key in _INTENT_TOKEN_KEYS:
        if keyword_key.endswith(intent_key) and len(keyword_key) > len(intent_key) + 1:
            return keyword_key[: -len(intent_key)]
    return keyword_key


def _resolve_intent_key(normalized_tokens: list[str]) -> str:
    seen: list[str] = []
    for token in normalized_tokens:
        intent_key = _INTENT_TOKEN_MAP.get(token)
        if intent_key and intent_key not in seen:
            seen.append(intent_key)
    return seen[0] if seen else "general"


def _build_cluster(entries: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_entries = sorted(entries, key=_entry_sort_key, reverse=True)
    representative = sorted_entries[0]
    article_plan = _build_article_plan(sorted_entries)
    lead_keywords = {slot["lead_keyword"] for slot in article_plan}
    all_keywords = [entry["keyword"] for entry in sorted_entries]
    supporting_keywords = [keyword for keyword in all_keywords if keyword not in lead_keywords]

    return {
        "cluster_id": "",
        "representative_keyword": representative["keyword"],
        "topic_terms": representative["core_terms"][:4],
        "keyword_count": len(sorted_entries),
        "cluster_type": "single_article" if len(article_plan) == 1 else "multi_article",
        "recommended_article_count": len(article_plan),
        "top_grade": representative["grade"],
        "top_profitability_grade": representative["profitability_grade"],
        "top_attackability_grade": representative["attackability_grade"],
        "top_combo": representative["combo_grade"],
        "top_golden_bucket": representative["golden_bucket"],
        "avg_score": round(sum(entry["score"] for entry in sorted_entries) / max(1, len(sorted_entries)), 1),
        "total_search_volume": int(round(sum(entry["volume"] for entry in sorted_entries))),
        "primary_keywords": [slot["lead_keyword"] for slot in article_plan],
        "supporting_keywords": supporting_keywords[:8],
        "all_keywords": all_keywords,
        "article_plan": article_plan,
    }


def _build_article_plan(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped_entries[entry["intent_key"]].append(entry)

    if "general" in grouped_entries and len(grouped_entries) > 1:
        general_entries = grouped_entries.pop("general")
        strongest_key = max(grouped_entries.keys(), key=lambda key: _entry_sort_key(grouped_entries[key][0]))
        grouped_entries[strongest_key].extend(general_entries)
        grouped_entries[strongest_key].sort(key=_entry_sort_key, reverse=True)

    article_slots = []
    for index, (intent_key, grouped_items) in enumerate(
        sorted(grouped_entries.items(), key=lambda item: _entry_sort_key(item[1][0]), reverse=True),
        start=1,
    ):
        sorted_grouped_items = sorted(grouped_items, key=_entry_sort_key, reverse=True)
        article_slots.append(
            {
                "slot": index,
                "intent_key": intent_key,
                "intent_label": _INTENT_LABELS[intent_key],
                "lead_keyword": sorted_grouped_items[0]["keyword"],
                "keyword_count": len(sorted_grouped_items),
                "keywords": [entry["keyword"] for entry in sorted_grouped_items[:6]],
            }
        )
    return article_slots


def _cluster_sort_key(cluster: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(cluster.get("avg_score") or 0.0),
        float(cluster.get("total_search_volume") or 0.0),
        float(cluster.get("keyword_count") or 0.0),
        float(cluster.get("recommended_article_count") or 0.0),
    )


def _entry_sort_key(entry: dict[str, Any]) -> tuple[float, float, float, float, float]:
    return (
        float(entry.get("score") or 0.0),
        float(entry.get("volume") or 0.0),
        float(entry.get("cpc") or 0.0),
        float(entry.get("confidence") or 0.0),
        -float(len(entry.get("keyword") or "")),
    )


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_grade(item: dict[str, Any]) -> str:
    grade = str(item.get("grade") or "").strip().upper()
    if grade in {"S", "A", "B", "C", "D", "F"}:
        return grade

    score_value = _coerce_float(item.get("score"))
    if score_value >= 85.0:
        return "S"
    if score_value >= 70.0:
        return "A"
    if score_value >= 55.0:
        return "B"
    if score_value >= 40.0:
        return "C"
    if score_value >= 25.0:
        return "D"
    return "F"


def _resolve_profitability_grade(item: dict[str, Any]) -> str:
    grade = str(item.get("profitability_grade") or "").strip().upper()
    return grade if grade in {"A", "B", "C", "D"} else ""


def _resolve_attackability_grade(item: dict[str, Any]) -> str:
    grade = str(item.get("attackability_grade") or "").strip()
    return grade if grade in {"1", "2", "3", "4"} else ""


def _resolve_combo_grade(item: dict[str, Any]) -> str:
    combo_grade = str(item.get("combo_grade") or "").strip().upper()
    if re.fullmatch(r"[ABCD][1-4]", combo_grade):
        return combo_grade

    profitability_grade = _resolve_profitability_grade(item)
    attackability_grade = _resolve_attackability_grade(item)
    if profitability_grade and attackability_grade:
        return f"{profitability_grade}{attackability_grade}"
    return ""


def _resolve_golden_bucket(item: dict[str, Any]) -> str:
    bucket = str(item.get("golden_bucket") or "").strip().lower()
    return bucket if bucket in {"gold", "promising", "experimental", "hold"} else ""
