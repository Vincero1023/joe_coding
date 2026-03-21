from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text


_INTENT_TERMS: dict[str, tuple[str, ...]] = {
    "commercial": ("추천", "비교", "가격", "비용", "견적", "순위", "구매"),
    "info": ("뜻", "정보", "정리", "가이드", "방법", "사용법", "기초", "설명"),
    "review": ("후기", "리뷰", "평판", "체험", "경험"),
    "action": ("예약", "신청", "등록", "조회", "발급"),
    "location": ("위치", "코스", "루트", "근처", "동선"),
    "policy": ("조건", "기준", "제도", "지원", "기한", "정책"),
    "problem": ("원인", "해결", "증상", "부작용", "주의", "대처"),
}
_INTENT_TOKEN_MAP = {
    normalize_key(term): intent_key
    for intent_key, terms in _INTENT_TERMS.items()
    for term in terms
    if normalize_key(term)
}
_STOPWORD_KEYS = {
    normalize_key(term)
    for terms in _INTENT_TERMS.values()
    for term in terms
    if normalize_key(term)
}
_STOPWORD_KEYS.update(
    {
        normalize_key(term)
        for term in (
            "체크",
            "체크리스트",
            "포인트",
            "핵심",
            "요약",
            "완벽",
            "총정리",
            "선택",
            "확인",
        )
        if normalize_key(term)
    }
)


def build_cannibalization_report(
    selected_items: list[dict[str, Any]],
    keyword_clusters: list[dict[str, Any]] | None = None,
    longtail_suggestions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_items = [
        item
        for item in selected_items
        if isinstance(item, dict) and normalize_text(item.get("keyword"))
    ]
    keyword_clusters = [cluster for cluster in keyword_clusters or [] if isinstance(cluster, dict)]
    longtail_suggestions = [
        item
        for item in longtail_suggestions or []
        if isinstance(item, dict) and normalize_text(item.get("longtail_keyword"))
    ]

    if not selected_items and not longtail_suggestions:
        return {
            "summary": {
                "candidate_count": 0,
                "issue_group_count": 0,
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "safe_split_cluster_count": 0,
            },
            "groups": [],
        }

    cluster_lookup = _build_cluster_lookup(keyword_clusters)
    candidates = _build_candidates(
        selected_items=selected_items,
        longtail_suggestions=longtail_suggestions,
        cluster_lookup=cluster_lookup,
    )

    grouped_candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped_candidates[(candidate["topic_key"], candidate["intent_key"])].append(candidate)

    groups = [
        _build_group(group_candidates)
        for group_candidates in grouped_candidates.values()
        if len(group_candidates) > 1
    ]
    groups = [group for group in groups if group]
    groups.sort(key=_group_sort_key)

    for index, group in enumerate(groups, start=1):
        group["group_id"] = f"cannibal-{index:02d}"

    summary = {
        "candidate_count": len(candidates),
        "issue_group_count": len(groups),
        "high_risk_count": sum(1 for group in groups if group.get("risk_level") == "high"),
        "medium_risk_count": sum(1 for group in groups if group.get("risk_level") == "medium"),
        "safe_split_cluster_count": sum(
            1
            for cluster in keyword_clusters
            if int(cluster.get("recommended_article_count") or 0) > 1
        ),
    }
    return {
        "summary": summary,
        "groups": groups,
    }


def _build_cluster_lookup(keyword_clusters: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for cluster in keyword_clusters:
        cluster_id = normalize_text(cluster.get("cluster_id"))
        representative_keyword = normalize_text(cluster.get("representative_keyword"))
        topic_terms = [
            normalize_text(term)
            for term in cluster.get("topic_terms", [])
            if normalize_text(term)
        ]
        topic_key = _build_topic_key_from_terms(topic_terms) or _build_topic_key(representative_keyword)
        for keyword in cluster.get("all_keywords", []):
            keyword_key = normalize_key(keyword)
            if not keyword_key:
                continue
            lookup[keyword_key] = {
                "cluster_id": cluster_id,
                "representative_keyword": representative_keyword,
                "topic_key": topic_key,
            }
    return lookup


def _build_candidates(
    *,
    selected_items: list[dict[str, Any]],
    longtail_suggestions: list[dict[str, Any]],
    cluster_lookup: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for item in selected_items:
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue
        keyword_key = normalize_key(keyword)
        cluster_meta = cluster_lookup.get(keyword_key, {})
        candidates.append(
            {
                "keyword": keyword,
                "source_type": "selected",
                "cluster_id": cluster_meta.get("cluster_id") or "",
                "representative_keyword": cluster_meta.get("representative_keyword") or keyword,
                "topic_key": cluster_meta.get("topic_key") or _build_topic_key(keyword),
                "intent_key": _resolve_intent_key(keyword),
                "score": _coerce_float(item.get("score")),
                "verification_status": "selected",
                "token_keys": _meaningful_token_keys(keyword),
            }
        )

    for item in longtail_suggestions:
        verification_status = str(item.get("verification_status") or "pending").strip().lower()
        if verification_status in {"fail", "error"}:
            continue

        keyword = normalize_text(item.get("longtail_keyword"))
        if not keyword:
            continue
        keyword_key = normalize_key(keyword)
        cluster_meta = cluster_lookup.get(keyword_key, {})
        cluster_id = normalize_text(item.get("cluster_id")) or cluster_meta.get("cluster_id") or ""
        representative_keyword = (
            normalize_text(item.get("representative_keyword"))
            or cluster_meta.get("representative_keyword")
            or keyword
        )
        candidates.append(
            {
                "keyword": keyword,
                "source_type": "longtail",
                "cluster_id": cluster_id,
                "representative_keyword": representative_keyword,
                "topic_key": cluster_meta.get("topic_key") or _build_topic_key(representative_keyword or keyword),
                "intent_key": str(item.get("intent_key") or "").strip().lower() or _resolve_intent_key(keyword),
                "score": _coerce_float(item.get("verified_score", item.get("projected_score"))),
                "verification_status": verification_status or "pending",
                "token_keys": _meaningful_token_keys(keyword),
            }
        )

    return candidates


def _build_group(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    sorted_candidates = sorted(candidates, key=_candidate_sort_key)
    if len(sorted_candidates) < 2:
        return None

    primary = sorted_candidates[0]
    secondaries = sorted_candidates[1:]
    overlap_scores = [_token_similarity(primary["token_keys"], item["token_keys"]) for item in secondaries]
    max_overlap = max(overlap_scores) if overlap_scores else 0.0
    avg_overlap = sum(overlap_scores) / max(1, len(overlap_scores))
    subset_match = any(
        _is_subset(primary["token_keys"], item["token_keys"])
        or _is_subset(item["token_keys"], primary["token_keys"])
        for item in secondaries
    )

    risk_level, recommended_action = _resolve_group_risk(
        candidate_count=len(sorted_candidates),
        max_overlap=max_overlap,
        avg_overlap=avg_overlap,
        subset_match=subset_match,
    )
    if risk_level not in {"high", "medium"}:
        return None

    return {
        "group_id": "",
        "cluster_id": primary.get("cluster_id") or "",
        "representative_keyword": primary.get("representative_keyword") or primary["keyword"],
        "intent_key": primary["intent_key"],
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "primary_keyword": primary["keyword"],
        "candidate_count": len(sorted_candidates),
        "overlap_score": int(round(max_overlap * 100)),
        "shared_terms": _extract_shared_terms(sorted_candidates),
        "rationale": "same_cluster_same_intent",
        "items": [
            {
                "keyword": item["keyword"],
                "source_type": item["source_type"],
                "score": round(item["score"], 1),
                "verification_status": item["verification_status"],
                "is_primary": index == 0,
            }
            for index, item in enumerate(sorted_candidates)
        ],
    }


def _resolve_group_risk(
    *,
    candidate_count: int,
    max_overlap: float,
    avg_overlap: float,
    subset_match: bool,
) -> tuple[str, str]:
    if subset_match or candidate_count >= 3 or max_overlap >= 0.82 or avg_overlap >= 0.72:
        return "high", "merge"
    if max_overlap >= 0.58 or avg_overlap >= 0.42:
        return "medium", "primary_sub"
    return "low", "separate"


def _extract_shared_terms(candidates: list[dict[str, Any]]) -> list[str]:
    counter: Counter[str] = Counter()
    for candidate in candidates:
        counter.update(candidate["token_keys"])
    return [token for token, count in counter.most_common(4) if token and count >= 2]


def _resolve_intent_key(keyword: str) -> str:
    keyword_key = normalize_key(keyword)
    for token_key, intent_key in _INTENT_TOKEN_MAP.items():
        if token_key and token_key in keyword_key:
            return intent_key
    return "general"


def _meaningful_token_keys(keyword: str) -> list[str]:
    token_keys = [
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
    ]
    filtered = [token for token in token_keys if token not in _STOPWORD_KEYS]
    return filtered or token_keys or [normalize_key(keyword)]


def _build_topic_key(keyword: str) -> str:
    token_keys = _meaningful_token_keys(keyword)
    return "".join(token_keys[:4]) or normalize_key(keyword)


def _build_topic_key_from_terms(topic_terms: list[str]) -> str:
    token_keys = [normalize_key(term) for term in topic_terms if normalize_key(term)]
    return "".join(token_keys[:4])


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, float, int]:
    source_rank = 0 if candidate["source_type"] == "selected" else 1
    verification_rank = {
        "selected": 0,
        "pass": 1,
        "review": 2,
        "pending": 3,
    }.get(candidate["verification_status"], 4)
    return (
        source_rank,
        verification_rank,
        -float(candidate.get("score") or 0.0),
        len(candidate.get("keyword") or ""),
    )


def _group_sort_key(group: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        0 if group.get("risk_level") == "high" else 1,
        -int(group.get("overlap_score") or 0),
        -int(group.get("candidate_count") or 0),
        str(group.get("primary_keyword") or ""),
    )


def _token_similarity(left: list[str], right: list[str]) -> float:
    left_set = {token for token in left if token}
    right_set = {token for token in right if token}
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / max(1, len(left_set | right_set))


def _is_subset(left: list[str], right: list[str]) -> bool:
    left_set = {token for token in left if token}
    right_set = {token for token in right if token}
    if not left_set or not right_set:
        return False
    return left_set <= right_set


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
