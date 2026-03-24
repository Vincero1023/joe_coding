from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.selector.longtail import (
    build_longtail_map,
    resolve_longtail_options,
    rewrite_low_signal_longtail_suggestion,
)

TITLE_KEYWORD_MODE_LABELS: dict[str, str] = {
    "single": "단일 키워드",
    "longtail_selected": "롱테일 V1",
    "longtail_exploratory": "롱테일 V2",
    "longtail_experimental": "롱테일 V3",
}
DEFAULT_TITLE_KEYWORD_MODES: tuple[str, ...] = ("single", "longtail_selected")
_MODE_ORDER: tuple[str, ...] = (
    "single",
    "longtail_selected",
    "longtail_exploratory",
    "longtail_experimental",
)
_STOP_TOKENS = {
    "추천",
    "비교",
    "정리",
    "가이드",
    "방법",
    "사용법",
    "뜻",
    "의미",
    "체크",
    "체크리스트",
    "핵심",
    "포인트",
}
_STOP_TOKEN_KEYS = {normalize_key(token) for token in _STOP_TOKENS if normalize_key(token)}
_STATUS_PRIORITY = {
    "pass": 4,
    "review": 3,
    "pending": 2,
    "fail": 1,
    "error": 0,
}
_LOW_SIGNAL_LONGTAIL_PATTERNS = (
    "추천 기준",
    "고를 때 체크",
    "비교 포인트",
    "최신 정보",
)
_LOW_SIGNAL_LONGTAIL_KEYS = tuple(
    normalize_key(pattern) for pattern in _LOW_SIGNAL_LONGTAIL_PATTERNS if normalize_key(pattern)
)
_RELATED_CONCRETE_SUFFIXES = (
    "실사용 차이",
    "장단점",
    "설정 팁",
    "자주 생기는 문제",
    "연결 문제",
    "설정 방법",
    "연결 방법",
    "선택 포인트",
    "주의점",
)
_SELECTED_LONGTAIL_WEAK_LIMIT = 1
_SELECTED_LONGTAIL_STRONG_LIMIT = 2
_SELECTED_LONGTAIL_VERIFIED_SCORE_THRESHOLD = 60.0
_SELECTED_LONGTAIL_FAMILY_PATTERNS = (
    ("issue", ("자주 생기는 문제", "문제", "오류", "끊김", "불편", "고장", "이슈", "주의점")),
    ("setup", ("설정 팁", "설정", "세팅", "연결", "페어링", "사용법", "방법")),
    ("review", ("실사용 차이", "실사용", "후기", "리뷰", "체감")),
    ("comparison", ("장단점", "차이", "비교")),
    ("selection", ("추천 대상", "고르는", "선택", "체크포인트", "확인 사항")),
)
_SELECTED_LONGTAIL_FAMILY_PRIORITY = {
    "issue": 5,
    "setup": 4,
    "review": 3,
    "comparison": 2,
    "selection": 1,
    "general": 0,
}
_SELECTED_LONGTAIL_FAMILY_KEYWORDS = tuple(
    (family, tuple(normalize_key(pattern) for pattern in patterns if normalize_key(pattern)))
    for family, patterns in _SELECTED_LONGTAIL_FAMILY_PATTERNS
)
_ALREADY_CONCRETE_SELECTED_KEYWORD_PATTERNS = (
    "실사용 차이",
    "장단점",
    "설정 팁",
    "설정 방법",
    "연결 방법",
    "연결 문제",
    "자주 생기는 문제",
    "문제",
    "오류",
    "안됨",
    "끊김",
)
_ALREADY_CONCRETE_SELECTED_KEYWORD_KEYS = tuple(
    normalize_key(pattern)
    for pattern in _ALREADY_CONCRETE_SELECTED_KEYWORD_PATTERNS
    if normalize_key(pattern)
)
_TITLE_TARGET_GENERIC_TOKENS = {
    "마우스",
    "키보드",
    "모니터",
    "호텔",
    "보험",
    "카드",
    "대출",
    "이어폰",
    "헤드셋",
    "노트북",
}
_TITLE_TARGET_GENERIC_TOKEN_KEYS = {
    normalize_key(token) for token in _TITLE_TARGET_GENERIC_TOKENS if normalize_key(token)
}


def resolve_title_keyword_modes(input_data: Any) -> list[str]:
    if not isinstance(input_data, dict):
        return list(DEFAULT_TITLE_KEYWORD_MODES)

    raw_options = input_data.get("title_options")
    if not isinstance(raw_options, dict):
        return list(DEFAULT_TITLE_KEYWORD_MODES)

    raw_modes = raw_options.get("keyword_modes")
    if not isinstance(raw_modes, list):
        return list(DEFAULT_TITLE_KEYWORD_MODES)

    normalized_modes: list[str] = []
    seen_modes: set[str] = set()
    for raw_mode in raw_modes:
        mode = str(raw_mode or "").strip().lower()
        if mode not in TITLE_KEYWORD_MODE_LABELS or mode in seen_modes:
            continue
        seen_modes.add(mode)
        normalized_modes.append(mode)

    return normalized_modes or list(DEFAULT_TITLE_KEYWORD_MODES)


def build_title_targets(input_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(input_data, list):
        explicit_targets = _coerce_explicit_title_targets(input_data)
        return explicit_targets, _build_target_summary(
            explicit_targets,
            requested_modes=_resolve_requested_modes_for_targets(explicit_targets),
        )

    if not isinstance(input_data, dict):
        return [], _build_target_summary([], requested_modes=list(DEFAULT_TITLE_KEYWORD_MODES))

    explicit_targets = _coerce_explicit_title_targets(input_data.get("title_targets"))
    requested_modes = resolve_title_keyword_modes(input_data)
    if explicit_targets:
        return explicit_targets, _build_target_summary(
            explicit_targets,
            requested_modes=_resolve_requested_modes_for_targets(explicit_targets),
        )

    selected_items = _coerce_items(input_data.get("selected_keywords"))
    keyword_clusters = _coerce_items(input_data.get("keyword_clusters"))
    longtail_suggestions = _coerce_items(input_data.get("longtail_suggestions"))
    analyzed_items = _coerce_items(input_data.get("analyzed_keywords"))
    longtail_options = resolve_longtail_options(input_data.get("longtail_options"))

    selected_items = [
        item
        for item in selected_items
        if normalize_text(item.get("keyword"))
    ]
    selected_items = _dedupe_selected_items_for_title(selected_items)
    if not selected_items:
        return [], _build_target_summary([], requested_modes=requested_modes)

    selected_keyword_keys = {
        normalize_key(item.get("keyword"))
        for item in selected_items
        if normalize_key(item.get("keyword"))
    }
    cluster_by_keyword = _build_cluster_lookup(keyword_clusters)
    seen_keywords: set[str] = set()
    targets: list[dict[str, Any]] = []

    if "single" in requested_modes:
        for item in selected_items:
            keyword = normalize_text(item.get("keyword"))
            keyword_key = normalize_key(keyword)
            if not keyword or not keyword_key or keyword_key in seen_keywords:
                continue
            seen_keywords.add(keyword_key)
            cluster = cluster_by_keyword.get(keyword_key)
            targets.append(
                _build_title_target(
                    keyword=keyword,
                    target_mode="single",
                    base_keyword=keyword,
                    support_keywords=[],
                    source_keywords=[keyword],
                    cluster_id=normalize_text(cluster.get("cluster_id")) if cluster else "",
                    source_kind="selected_keyword",
                    source_note="선별 통과 키워드를 그대로 제목 생성 대상으로 사용합니다.",
                    source_selection_mode=normalize_text(item.get("selection_mode")),
                    source_selection_reason=normalize_text(item.get("selection_reason")),
                )
            )

    if "longtail_selected" in requested_modes:
        selected_suggestions = _resolve_selected_longtail_suggestions(
            selected_items,
            keyword_clusters,
            longtail_suggestions,
            longtail_options=longtail_options,
        )
        for suggestion in selected_suggestions:
            keyword = normalize_text(suggestion.get("longtail_keyword"))
            keyword_key = normalize_key(keyword)
            if not keyword or not keyword_key or keyword_key in seen_keywords:
                continue
            seen_keywords.add(keyword_key)
            targets.append(
                _build_suggestion_target(
                    suggestion,
                    target_mode="longtail_selected",
                    source_kind="selected_longtail",
                    representative_item=next(
                        (
                            item
                            for item in selected_items
                            if normalize_key(item.get("keyword")) == normalize_key(suggestion.get("representative_keyword"))
                        ),
                        None,
                    ),
                )
            )

    if "longtail_exploratory" in requested_modes:
        exploratory_targets = _build_related_mode_targets(
            selected_items=selected_items,
            analyzed_items=analyzed_items,
            selected_keyword_keys=selected_keyword_keys,
            cluster_by_keyword=cluster_by_keyword,
            target_mode="longtail_exploratory",
            per_keyword_limit=2,
            minimum_score=33.0,
            minimum_volume=50.0,
            longtail_options=longtail_options,
        )
        for target in exploratory_targets:
            keyword_key = normalize_key(target.get("keyword"))
            if not keyword_key or keyword_key in seen_keywords:
                continue
            seen_keywords.add(keyword_key)
            targets.append(target)

    if "longtail_experimental" in requested_modes:
        experimental_targets = _build_related_mode_targets(
            selected_items=selected_items,
            analyzed_items=analyzed_items,
            selected_keyword_keys=selected_keyword_keys,
            cluster_by_keyword=cluster_by_keyword,
            target_mode="longtail_experimental",
            per_keyword_limit=2,
            minimum_score=18.0,
            minimum_volume=10.0,
            longtail_options=longtail_options,
        )
        for target in experimental_targets:
            keyword_key = normalize_key(target.get("keyword"))
            if not keyword_key or keyword_key in seen_keywords:
                continue
            seen_keywords.add(keyword_key)
            targets.append(target)

    return targets, _build_target_summary(targets, requested_modes=requested_modes)


def _resolve_selected_longtail_suggestions(
    selected_items: list[dict[str, Any]],
    keyword_clusters: list[dict[str, Any]],
    longtail_suggestions: list[dict[str, Any]],
    *,
    longtail_options: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    suggestions = longtail_suggestions or _coerce_items(
        build_longtail_map(
            selected_items,
            keyword_clusters,
            longtail_options=longtail_options,
        ).get("longtail_suggestions")
    )
    selected_keyword_keys = {
        normalize_key(item.get("keyword"))
        for item in selected_items
        if normalize_key(item.get("keyword"))
    }
    cluster_by_keyword = _build_cluster_lookup(keyword_clusters)

    grouped_suggestions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for suggestion in suggestions:
        representative_keyword = normalize_text(suggestion.get("representative_keyword"))
        representative_key = normalize_key(representative_keyword)
        if not representative_key or representative_key not in selected_keyword_keys:
            continue
        verification_status = str(suggestion.get("verification_status") or "").strip().lower()
        if verification_status in {"fail", "error"}:
            continue
        for candidate_suggestion in rewrite_low_signal_longtail_suggestion(suggestion, limit=1):
            grouped_suggestions[representative_key].append(candidate_suggestion)

    output: list[dict[str, Any]] = []
    representative_item_by_key = {
        normalize_key(item.get("keyword")): item
        for item in selected_items
        if normalize_key(item.get("keyword"))
    }
    for representative_key, rows in grouped_suggestions.items():
        representative_keyword = next(
            (
                normalize_text(item.get("representative_keyword"))
                for item in rows
                if normalize_text(item.get("representative_keyword"))
            ),
            "",
        )
        selection_limit = _resolve_selected_longtail_limit(
            representative_keyword,
            cluster_by_keyword.get(representative_key) or {},
            rows,
            representative_item_by_key.get(representative_key) or {},
        )
        sorted_rows = sorted(
            rows,
            key=lambda item: (
                _STATUS_PRIORITY.get(str(item.get("verification_status") or "").strip().lower(), -1),
                float(item.get("verified_score") or item.get("projected_score") or 0.0),
                _SELECTED_LONGTAIL_FAMILY_PRIORITY.get(_classify_selected_longtail_family(item), 0),
                float(len(tokenize_text(item.get("longtail_keyword") or ""))),
            ),
            reverse=True,
        )
        output.extend(_pick_selected_longtail_rows(sorted_rows, limit=selection_limit))
    return output


def _resolve_selected_longtail_limit(
    representative_keyword: str,
    cluster: dict[str, Any],
    rows: list[dict[str, Any]],
    representative_item: dict[str, Any],
) -> int:
    if _selected_keyword_is_already_concrete(representative_keyword):
        return 0
    representative_key = normalize_key(representative_keyword)
    cluster_keywords = {
        normalize_key(keyword)
        for keyword in cluster.get("all_keywords", [])
        if normalize_key(keyword)
    }
    support_keyword_count = len(
        {
            keyword_key
            for keyword_key in cluster_keywords
            if keyword_key and keyword_key != representative_key
        }
    )
    if support_keyword_count > 0:
        limit = _SELECTED_LONGTAIL_STRONG_LIMIT
    elif _looks_like_specific_selected_keyword(representative_keyword):
        limit = _SELECTED_LONGTAIL_STRONG_LIMIT
    elif any(_has_distinct_selected_longtail_source(item, representative_key=representative_key) for item in rows):
        limit = _SELECTED_LONGTAIL_STRONG_LIMIT
    elif any(_is_high_confidence_selected_longtail(item) for item in rows):
        limit = _SELECTED_LONGTAIL_STRONG_LIMIT
    else:
        limit = _SELECTED_LONGTAIL_WEAK_LIMIT

    if normalize_text(representative_item.get("selection_mode")) == "seed_anchor":
        return min(limit, _SELECTED_LONGTAIL_WEAK_LIMIT)
    return limit


def _selected_keyword_is_already_concrete(keyword: str) -> bool:
    keyword_key = normalize_key(keyword)
    if not keyword_key:
        return False
    return any(pattern in keyword_key for pattern in _ALREADY_CONCRETE_SELECTED_KEYWORD_KEYS)


def _pick_selected_longtail_rows(
    sorted_rows: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0 or not sorted_rows:
        return []

    picked_rows: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for row in sorted_rows:
        family = _classify_selected_longtail_family(row)
        if family in seen_families:
            continue
        picked_rows.append(row)
        seen_families.add(family)
        if len(picked_rows) >= limit:
            return picked_rows

    for row in sorted_rows:
        if row in picked_rows:
            continue
        picked_rows.append(row)
        if len(picked_rows) >= limit:
            break
    return picked_rows


def _classify_selected_longtail_family(item: dict[str, Any]) -> str:
    keyword_key = normalize_key(item.get("longtail_keyword"))
    if not keyword_key:
        return "general"
    for family, pattern_keys in _SELECTED_LONGTAIL_FAMILY_KEYWORDS:
        if any(pattern_key and pattern_key in keyword_key for pattern_key in pattern_keys):
            return family
    return "general"


def _has_distinct_selected_longtail_source(item: dict[str, Any], *, representative_key: str) -> bool:
    source_keyword_key = normalize_key(item.get("source_keyword"))
    return bool(source_keyword_key and source_keyword_key != representative_key)


def _is_high_confidence_selected_longtail(item: dict[str, Any]) -> bool:
    verification_status = str(item.get("verification_status") or "").strip().lower()
    if verification_status not in {"pass", "review"}:
        return False
    score = float(item.get("verified_score") or item.get("projected_score") or 0.0)
    return score >= _SELECTED_LONGTAIL_VERIFIED_SCORE_THRESHOLD


def _looks_like_specific_selected_keyword(keyword: str) -> bool:
    tokens = tokenize_text(keyword)
    for token in tokens:
        if any(character.isdigit() for character in token):
            return True
        if any(character.isascii() and character.isalnum() for character in token):
            return True
    return False


def _build_related_mode_targets(
    *,
    selected_items: list[dict[str, Any]],
    analyzed_items: list[dict[str, Any]],
    selected_keyword_keys: set[str],
    cluster_by_keyword: dict[str, dict[str, Any]],
    target_mode: str,
    per_keyword_limit: int,
    minimum_score: float,
    minimum_volume: float,
    longtail_options: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    generated_targets: list[dict[str, Any]] = []
    seen_keywords: set[str] = set()

    for selected_item in selected_items:
        representative_keyword = normalize_text(selected_item.get("keyword"))
        representative_key = normalize_key(representative_keyword)
        if not representative_keyword or not representative_key:
            continue

        cluster = cluster_by_keyword.get(representative_key) or {}
        related_candidates = _pick_related_analyzed_items(
            representative_keyword=representative_keyword,
            cluster=cluster,
            analyzed_items=analyzed_items,
            selected_keyword_keys=selected_keyword_keys,
            minimum_score=minimum_score,
            minimum_volume=minimum_volume,
        )
        if not related_candidates:
            continue

        custom_cluster = {
            "cluster_id": f"{target_mode}-{representative_key}",
            "representative_keyword": representative_keyword,
            "topic_terms": _resolve_topic_terms(cluster, representative_keyword),
            "all_keywords": [representative_keyword] + [normalize_text(item.get("keyword")) for item in related_candidates],
        }
        suggestions = _coerce_items(
            build_longtail_map(
                [selected_item, *related_candidates],
                [custom_cluster],
                longtail_options=longtail_options,
            ).get("longtail_suggestions")
        )
        for suggestion in suggestions:
            if _should_skip_related_mode_suggestion(
                suggestion,
                representative_keyword=representative_keyword,
            ):
                continue
            keyword = _sanitize_related_mode_keyword(
                normalize_text(suggestion.get("longtail_keyword")),
                representative_keyword=representative_keyword,
            )
            keyword_key = normalize_key(keyword)
            if not keyword or not keyword_key or keyword_key in seen_keywords:
                continue
            seen_keywords.add(keyword_key)
            generated_targets.append(
                _build_suggestion_target(
                    {
                        **suggestion,
                        "longtail_keyword": keyword,
                    },
                    target_mode=target_mode,
                    source_kind="rejected_related_keyword" if target_mode == "longtail_exploratory" else "experimental_related_keyword",
                    source_note=(
                        "선별 탈락이지만 검색 의도가 맞는 관련 키워드를 조합해 만든 확장형 제목 대상입니다."
                        if target_mode == "longtail_exploratory"
                        else "저검색량까지 넓혀 잡는 실험형 제목 대상입니다."
                    ),
                    representative_item=selected_item,
                )
            )
            if sum(1 for item in generated_targets if item.get("base_keyword") == representative_keyword and item.get("target_mode") == target_mode) >= per_keyword_limit:
                break

    return generated_targets


def _pick_related_analyzed_items(
    *,
    representative_keyword: str,
    cluster: dict[str, Any],
    analyzed_items: list[dict[str, Any]],
    selected_keyword_keys: set[str],
    minimum_score: float,
    minimum_volume: float,
) -> list[dict[str, Any]]:
    topic_keys = _resolve_topic_keys(cluster, representative_keyword)
    representative_tokens = set(_filter_core_tokens(tokenize_text(representative_keyword)))
    if not topic_keys:
        topic_keys = representative_tokens

    ranked_candidates: list[tuple[tuple[float, float, float, float], dict[str, Any]]] = []
    for candidate in analyzed_items:
        keyword = normalize_text(candidate.get("keyword"))
        keyword_key = normalize_key(keyword)
        if not keyword or not keyword_key or keyword_key in selected_keyword_keys:
            continue

        candidate_tokens = set(_filter_core_tokens(tokenize_text(keyword)))
        overlap = len(topic_keys & candidate_tokens)
        if overlap <= 0:
            continue

        score = _coerce_float(candidate.get("score"))
        volume = _coerce_float(candidate.get("metrics", {}).get("volume"))
        cpc = _coerce_float(candidate.get("metrics", {}).get("cpc"))
        if score < minimum_score and volume < minimum_volume:
            continue

        ranked_candidates.append(((float(overlap), score, volume, cpc), candidate))

    ranked_candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _rank, candidate in ranked_candidates[:4]]


def _build_suggestion_target(
    suggestion: dict[str, Any],
    *,
    target_mode: str,
    source_kind: str,
    source_note: str = "",
    representative_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keyword = normalize_text(suggestion.get("longtail_keyword"))
    representative_keyword = normalize_text(suggestion.get("representative_keyword"))
    support_keywords = [
        normalize_text(term)
        for term in suggestion.get("combination_terms", [])
        if normalize_text(term) and normalize_text(term) != representative_keyword
    ]
    return _build_title_target(
        keyword=keyword,
        target_mode=target_mode,
        base_keyword=representative_keyword or keyword,
        support_keywords=support_keywords[:2],
        source_keywords=[
            normalize_text(suggestion.get("representative_keyword")),
            normalize_text(suggestion.get("source_keyword")),
        ],
        cluster_id=normalize_text(suggestion.get("cluster_id")),
        source_kind=source_kind,
        source_note=source_note or normalize_text(suggestion.get("verification_reason")) or "",
        source_suggestion_id=normalize_text(suggestion.get("suggestion_id")),
        source_selection_mode=normalize_text((representative_item or {}).get("selection_mode")),
        source_selection_reason=normalize_text((representative_item or {}).get("selection_reason")),
    )


def _build_title_target(
    *,
    keyword: str,
    target_mode: str,
    base_keyword: str,
    support_keywords: list[str],
    source_keywords: list[str],
    cluster_id: str,
    source_kind: str,
    source_note: str,
    source_suggestion_id: str = "",
    source_selection_mode: str = "",
    source_selection_reason: str = "",
) -> dict[str, Any]:
    normalized_keyword = normalize_text(keyword)
    normalized_base_keyword = normalize_text(base_keyword) or normalized_keyword
    normalized_support_keywords = [
        normalize_text(item)
        for item in support_keywords
        if normalize_text(item) and normalize_text(item) != normalized_base_keyword
    ]
    normalized_source_keywords = [
        normalize_text(item)
        for item in source_keywords
        if normalize_text(item)
    ]
    target_key = normalize_key(normalized_keyword)
    mode_label = TITLE_KEYWORD_MODE_LABELS.get(target_mode, target_mode)
    return {
        "target_id": f"{target_mode}:{target_key}",
        "keyword": normalized_keyword,
        "target_mode": target_mode,
        "target_mode_label": mode_label,
        "base_keyword": normalized_base_keyword,
        "support_keywords": normalized_support_keywords[:2],
        "source_keywords": normalized_source_keywords[:3],
        "source_kind": source_kind,
        "source_note": normalize_text(source_note),
        "cluster_id": cluster_id,
        "source_suggestion_id": source_suggestion_id,
        "source_selection_mode": normalize_text(source_selection_mode),
        "source_selection_reason": normalize_text(source_selection_reason),
    }


def _is_low_signal_longtail_keyword(keyword: Any) -> bool:
    keyword_key = normalize_key(normalize_text(keyword))
    if not keyword_key:
        return False
    return any(pattern in keyword_key for pattern in _LOW_SIGNAL_LONGTAIL_KEYS)


def _sanitize_related_mode_keyword(keyword: str, *, representative_keyword: str) -> str:
    normalized_keyword = _collapse_duplicate_keyword_tokens(normalize_text(keyword))
    normalized_representative = normalize_text(representative_keyword)
    if not normalized_keyword or not normalized_representative:
        return normalized_keyword

    for suffix in _RELATED_CONCRETE_SUFFIXES:
        if not normalized_keyword.endswith(suffix):
            continue
        if not normalized_keyword.startswith(normalized_representative):
            break

        middle = normalize_text(
            normalized_keyword[len(normalized_representative) : len(normalized_keyword) - len(suffix)]
        )
        if middle and _looks_like_related_mode_noise(middle, representative_keyword=normalized_representative):
            return f"{normalized_representative} {suffix}"
        break

    return normalized_keyword


def _looks_like_related_mode_noise(middle: str, *, representative_keyword: str) -> bool:
    middle_tokens = [token for token in tokenize_text(middle) if normalize_key(token)]
    if not middle_tokens or len(middle_tokens) > 2:
        return False

    representative_key = normalize_key(representative_keyword)
    for token in middle_tokens:
        token_key = normalize_key(token)
        if not token_key:
            continue
        if any(character.isascii() and character.isalnum() for character in token):
            return True
        if representative_key and (token_key in representative_key or representative_key.endswith(token_key)):
            return True
    return False


def _collapse_duplicate_keyword_tokens(keyword: str) -> str:
    tokens = tokenize_text(keyword)
    compact_tokens: list[str] = []
    previous_key = ""
    for token in tokens:
        token_key = normalize_key(token)
        if token_key and token_key == previous_key:
            continue
        compact_tokens.append(normalize_text(token))
        previous_key = token_key
    return normalize_text(" ".join(compact_tokens))


def _build_target_summary(targets: list[dict[str, Any]], *, requested_modes: list[str]) -> dict[str, Any]:
    mode_counts = {
        mode: sum(1 for item in targets if item.get("target_mode") == mode)
        for mode in _MODE_ORDER
    }
    return {
        "requested_modes": requested_modes,
        "mode_counts": mode_counts,
        "target_count": len(targets),
        "base_keyword_count": len(
            {
                normalize_text(item.get("base_keyword"))
                for item in targets
                if normalize_text(item.get("base_keyword"))
            }
        ),
    }


def _resolve_requested_modes_for_targets(targets: list[dict[str, Any]]) -> list[str]:
    inferred_modes: list[str] = []
    seen_modes: set[str] = set()
    for target in targets:
        mode = str(target.get("target_mode") or "").strip().lower()
        if mode not in TITLE_KEYWORD_MODE_LABELS or mode in seen_modes:
            continue
        seen_modes.add(mode)
        inferred_modes.append(mode)
    return inferred_modes or list(DEFAULT_TITLE_KEYWORD_MODES)


def _coerce_explicit_title_targets(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    targets: list[dict[str, Any]] = []
    seen_target_ids: set[str] = set()
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        keyword = normalize_text(raw_item.get("keyword"))
        keyword_key = normalize_key(keyword)
        if not keyword or not keyword_key:
            continue
        mode = str(raw_item.get("target_mode") or "single").strip().lower()
        if mode not in TITLE_KEYWORD_MODE_LABELS:
            mode = "single"
        target = _build_title_target(
            keyword=keyword,
            target_mode=mode,
            base_keyword=normalize_text(raw_item.get("base_keyword")) or keyword,
            support_keywords=_coerce_string_list(raw_item.get("support_keywords"))[:2],
            source_keywords=_coerce_string_list(raw_item.get("source_keywords"))[:3] or [keyword],
            cluster_id=normalize_text(raw_item.get("cluster_id")),
            source_kind=normalize_text(raw_item.get("source_kind")) or "explicit_target",
            source_note=normalize_text(raw_item.get("source_note")),
            source_suggestion_id=normalize_text(raw_item.get("source_suggestion_id")),
            source_selection_mode=normalize_text(raw_item.get("source_selection_mode") or raw_item.get("selection_mode")),
            source_selection_reason=normalize_text(raw_item.get("source_selection_reason") or raw_item.get("selection_reason")),
        )
        target_identity = normalize_text(target.get("target_id"))
        if not target_identity or target_identity in seen_target_ids:
            continue
        seen_target_ids.add(target_identity)
        targets.append(target)
    return targets


def _dedupe_selected_items_for_title(selected_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(selected_items) <= 1:
        return selected_items

    leading_token_keys = _resolve_leading_selected_item_tokens(selected_items)
    grouped_items: dict[str, list[dict[str, Any]]] = defaultdict(list)
    group_order: list[str] = []
    for item in selected_items:
        signature = _resolve_selected_item_signature(item, leading_token_keys=leading_token_keys)
        if signature not in grouped_items:
            group_order.append(signature)
        grouped_items[signature].append(item)

    deduped_items: list[dict[str, Any]] = []
    for signature in group_order:
        deduped_items.append(_pick_preferred_selected_item(grouped_items[signature], leading_token_keys=leading_token_keys))
    return deduped_items


def _resolve_leading_selected_item_tokens(selected_items: list[dict[str, Any]]) -> set[str]:
    token_counts: dict[str, int] = defaultdict(int)
    for item in selected_items:
        keyword = normalize_text(item.get("keyword"))
        tokens = tokenize_text(keyword)
        if not tokens:
            continue
        token_key = normalize_key(tokens[0])
        if token_key and token_key not in _STOP_TOKEN_KEYS:
            token_counts[token_key] += 1

    threshold = max(3, int(math.ceil(len(selected_items) * 0.45)))
    return {
        token_key
        for token_key, count in token_counts.items()
        if count >= threshold
    }


def _resolve_selected_item_signature(
    item: dict[str, Any],
    *,
    leading_token_keys: set[str],
) -> str:
    keyword = normalize_text(item.get("keyword"))
    filtered_token_keys = [
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
        and normalize_key(token) not in _STOP_TOKEN_KEYS
        and normalize_key(token) not in leading_token_keys
        and normalize_key(token) not in _TITLE_TARGET_GENERIC_TOKEN_KEYS
    ]
    if filtered_token_keys:
        return "|".join(sorted(set(filtered_token_keys)))

    fallback_token_keys = [
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
        and normalize_key(token) not in _STOP_TOKEN_KEYS
        and normalize_key(token) not in leading_token_keys
    ]
    if fallback_token_keys:
        return f"kw:{'|'.join(sorted(set(fallback_token_keys)))}"
    return f"raw:{normalize_key(keyword)}"


def _pick_preferred_selected_item(
    items: list[dict[str, Any]],
    *,
    leading_token_keys: set[str],
) -> dict[str, Any]:
    return max(
        items,
        key=lambda item: (
            _coerce_float(item.get("score")),
            -_count_selected_item_generic_tokens(item),
            len(_resolve_selected_item_signature(item, leading_token_keys=leading_token_keys)),
            -len(normalize_text(item.get("keyword"))),
        ),
    )


def _count_selected_item_generic_tokens(item: dict[str, Any]) -> int:
    return sum(
        1
        for token in tokenize_text(item.get("keyword") or "")
        if normalize_key(token) in _TITLE_TARGET_GENERIC_TOKEN_KEYS
    )


def _build_cluster_lookup(keyword_clusters: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for cluster in keyword_clusters:
        if not isinstance(cluster, dict):
            continue
        for keyword in cluster.get("all_keywords", []):
            keyword_key = normalize_key(keyword)
            if keyword_key:
                output[keyword_key] = cluster
    return output


def _resolve_topic_terms(cluster: dict[str, Any], representative_keyword: str) -> list[str]:
    topic_terms = _coerce_string_list(cluster.get("topic_terms"))
    filtered_topic_terms = [
        term
        for term in topic_terms
        if normalize_key(term) and normalize_key(term) not in _STOP_TOKEN_KEYS
    ]
    if filtered_topic_terms:
        return filtered_topic_terms[:4]
    if topic_terms:
        return topic_terms[:4]

    representative_tokens = tokenize_text(representative_keyword)
    filtered_representative_tokens = [
        token
        for token in representative_tokens
        if normalize_key(token) and normalize_key(token) not in _STOP_TOKEN_KEYS
    ]
    if filtered_representative_tokens:
        return filtered_representative_tokens[:4]
    return representative_tokens[:4]


def _resolve_topic_keys(cluster: dict[str, Any], representative_keyword: str) -> set[str]:
    topic_terms = _resolve_topic_terms(cluster, representative_keyword)
    return {token for token in _filter_core_tokens(topic_terms) if token}


def _filter_core_tokens(tokens: list[str]) -> list[str]:
    output: list[str] = []
    for token in tokens:
        token_key = normalize_key(token)
        if not token_key or token_key in _STOP_TOKEN_KEYS:
            continue
        output.append(token_key)
    return output


def _coerce_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _should_skip_related_mode_suggestion(
    suggestion: dict[str, Any],
    *,
    representative_keyword: str,
) -> bool:
    if _is_low_signal_longtail_keyword(suggestion.get("longtail_keyword")):
        return True

    source_keyword = normalize_text(suggestion.get("source_keyword"))
    if source_keyword and normalize_key(source_keyword) == normalize_key(representative_keyword):
        return True

    modifier_phrase_key = normalize_key(suggestion.get("modifier_phrase"))
    return bool(modifier_phrase_key and modifier_phrase_key in _STOP_TOKEN_KEYS)
