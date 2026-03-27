from __future__ import annotations

import math
import re
from typing import Any

from app.analyzer.config import DEFAULT_CONFIG
from app.analyzer.scorer import (
    ATTACKABILITY_GRADE_ORDER,
    PROFITABILITY_GRADE_ORDER,
    calculate_attackability_score,
    calculate_profitability_score,
    classify_attackability_grade,
    classify_golden_bucket,
    classify_profitability_grade,
)
from app.core.api_usage import capture_api_usage
from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.selector.cannibalization import build_cannibalization_report
from app.selector.content_map import build_content_map
from app.selector.exporter import export_selected_keywords
from app.selector.longtail import build_longtail_map, resolve_longtail_options


_EDITORIAL_FALLBACK_LIMIT = 8
_MIN_DEFAULT_SELECTION_COUNT = 4
_DEFAULT_SELECTION_MAX_COUNT = 14
_DEFAULT_SELECTION_TOP_UP_RATIO = 0.16
_DEFAULT_SELECTION_MEDIUM_POOL_THRESHOLD = 20
_DEFAULT_SELECTION_LARGE_POOL_THRESHOLD = 45
_DEFAULT_SELECTION_XL_POOL_THRESHOLD = 80
_TEMPLATE_HEAVY_KEYWORD_PATTERNS = (
    "추천 기준",
    "고를 때 체크",
    "비교 포인트",
    "최신 정보",
)
_TEMPLATE_HEAVY_KEYWORD_KEYS = tuple(
    normalize_key(pattern) for pattern in _TEMPLATE_HEAVY_KEYWORD_PATTERNS if normalize_key(pattern)
)
_SEED_ANCHOR_SIGNAL_TERMS = (
    "사전예약",
    "예약",
    "가입",
    "신청",
    "설정",
    "팁",
    "방법",
    "사용법",
    "조건",
    "기준",
    "일정",
    "혜택",
    "가성비",
    "가격",
    "비교",
    "장단점",
    "실사용",
    "차이",
    "문제",
    "해결",
    "원인",
    "위치",
    "동선",
    "코스",
    "주차",
    "후기",
    "리뷰",
    "대상",
    "제한",
    "주의점",
)
_SEED_ANCHOR_SIGNAL_KEYS = tuple(
    normalize_key(term) for term in _SEED_ANCHOR_SIGNAL_TERMS if normalize_key(term)
)
_MODEL_LIKE_TOKEN_RE = re.compile(r"(?i)(?:[a-z]+\d+|\d+[a-z]+)")


def is_golden_keyword(item: dict[str, Any]) -> bool:
    if _is_template_heavy_keyword(item.get("keyword")):
        return False
    golden_bucket = _resolve_golden_bucket(item)
    return golden_bucket in {"gold", "promising"}


class SelectorService:
    def run(self, input_data: Any) -> Any:
        with capture_api_usage() as api_usage:
            items = _coerce_input_items(input_data)
            select_options = _coerce_select_options(input_data)
            allowed_grades = _normalize_allowed_grades(select_options.get("allowed_grades"))
            allowed_profitability_grades = _normalize_allowed_profitability_grades(
                select_options.get("allowed_profitability_grades")
            )
            allowed_attackability_grades = _normalize_allowed_attackability_grades(
                select_options.get("allowed_attackability_grades")
            )
            mode = str(select_options.get("mode") or "").strip().lower()

            if mode == "combo_filter" and (allowed_profitability_grades or allowed_attackability_grades):
                selected = [
                    _decorate_combo_selected_item(item)
                    for item in items
                    if _matches_combo_filter(
                        item,
                        allowed_profitability_grades=allowed_profitability_grades,
                        allowed_attackability_grades=allowed_attackability_grades,
                    )
                ]
                if isinstance(input_data, list):
                    return selected
                payload = _build_selected_payload(
                    selected,
                    longtail_options=select_options.get("longtail_options"),
                    input_data=input_data,
                )
                _attach_selection_profile(
                    payload,
                    source_items=items,
                    selected=selected,
                    select_options=select_options,
                    mode="combo_filter",
                )
                return _attach_selector_debug(
                    payload,
                    api_usage_snapshot=api_usage.snapshot(),
                    input_keyword_count=len(items),
                )

            if mode == "grade_filter" and allowed_grades:
                selected = [
                    _decorate_grade_selected_item(item)
                    for item in items
                    if _resolve_grade(item) in allowed_grades
                ]
                if isinstance(input_data, list):
                    return selected
                payload = _build_selected_payload(
                    selected,
                    longtail_options=select_options.get("longtail_options"),
                    input_data=input_data,
                )
                _attach_selection_profile(
                    payload,
                    source_items=items,
                    selected=selected,
                    select_options=select_options,
                    mode="grade_filter",
                )
                return _attach_selector_debug(
                    payload,
                    api_usage_snapshot=api_usage.snapshot(),
                    input_keyword_count=len(items),
                )

            selected = [_decorate_default_selected_item(item) for item in items if is_golden_keyword(item)]
            target_count = _resolve_default_selection_target_count(items)
            if len(selected) < target_count:
                selected = _top_up_default_selection(selected, items, target_count=target_count)
            if not selected:
                selected = _select_fallback_candidates(items)
            selected = _inject_seed_anchor_candidate(selected, input_data, items)

            if isinstance(input_data, list):
                return selected
            payload = _build_selected_payload(
                selected,
                longtail_options=select_options.get("longtail_options"),
                input_data=input_data,
            )
            _attach_selection_profile(
                payload,
                source_items=items,
                selected=selected,
                select_options=select_options,
                mode="default",
            )
            return _attach_selector_debug(
                payload,
                api_usage_snapshot=api_usage.snapshot(),
                input_keyword_count=len(items),
            )


def _build_selected_payload(
    selected: list[dict[str, Any]],
    *,
    longtail_options: dict[str, Any] | None = None,
    input_data: Any = None,
) -> dict[str, Any]:
    content_map = build_content_map(selected)
    resolved_longtail_options = resolve_longtail_options(longtail_options)
    longtail_map = build_longtail_map(
        selected,
        content_map.get("keyword_clusters") if isinstance(content_map, dict) else [],
        longtail_options=resolved_longtail_options,
    )
    cannibalization_report = build_cannibalization_report(
        selected,
        content_map.get("keyword_clusters") if isinstance(content_map, dict) else [],
        longtail_map.get("longtail_suggestions") if isinstance(longtail_map, dict) else [],
    )
    payload = {
        "selected_keywords": selected,
        **content_map,
        **longtail_map,
        "cannibalization_report": cannibalization_report,
    }
    export_payload = export_selected_keywords(input_data, selected)
    if export_payload:
        payload["selection_export"] = export_payload
    return payload


def _attach_selection_profile(
    payload: dict[str, Any],
    *,
    source_items: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    select_options: dict[str, Any] | None = None,
    mode: str = "default",
) -> None:
    normalized_mode = str(mode or "default").strip().lower() or "default"
    raw_select_options = select_options if isinstance(select_options, dict) else {}
    resolved_longtail_options = (
        payload.get("longtail_options")
        if isinstance(payload.get("longtail_options"), dict)
        else resolve_longtail_options(raw_select_options.get("longtail_options"))
    )
    allowed_profitability_grades = [
        grade
        for grade in PROFITABILITY_GRADE_ORDER
        if grade in _normalize_allowed_profitability_grades(raw_select_options.get("allowed_profitability_grades"))
    ]
    allowed_attackability_grades = [
        grade
        for grade in ATTACKABILITY_GRADE_ORDER
        if grade in _normalize_allowed_attackability_grades(raw_select_options.get("allowed_attackability_grades"))
    ]
    allowed_grades = sorted(_normalize_allowed_grades(raw_select_options.get("allowed_grades")))

    profile: dict[str, Any] = {
        "mode": normalized_mode,
        "candidate_count": len(source_items),
        "selected_count": len(selected),
        "longtail_option_keys": list(resolved_longtail_options.get("optional_suffix_keys", [])),
        "has_editorial_support": any(
            str(item.get("selection_mode") or "").strip().lower() == "editorial_support"
            for item in selected
            if isinstance(item, dict)
        ),
    }
    if allowed_profitability_grades:
        profile["allowed_profitability_grades"] = allowed_profitability_grades
    if allowed_attackability_grades:
        profile["allowed_attackability_grades"] = allowed_attackability_grades
    if allowed_grades:
        profile["allowed_grades"] = allowed_grades
    payload["selection_profile"] = profile


def _attach_selector_debug(
    payload: dict[str, Any],
    *,
    api_usage_snapshot: dict[str, Any],
    input_keyword_count: int,
) -> dict[str, Any]:
    payload["debug"] = {
        "stage": "selector",
        "summary": api_usage_snapshot.get("summary", {}),
        "api_usage": api_usage_snapshot,
        "selection_summary": {
            "input_keyword_count": max(0, int(input_keyword_count or 0)),
            "selected_keyword_count": len(payload.get("selected_keywords", []))
            if isinstance(payload.get("selected_keywords"), list)
            else 0,
            "keyword_cluster_count": len(payload.get("keyword_clusters", []))
            if isinstance(payload.get("keyword_clusters"), list)
            else 0,
            "longtail_suggestion_count": len(payload.get("longtail_suggestions", []))
            if isinstance(payload.get("longtail_suggestions"), list)
            else 0,
        },
    }
    return payload


def _coerce_input_items(input_data: Any) -> list[dict[str, Any]]:
    if isinstance(input_data, list):
        return [item for item in input_data if isinstance(item, dict)]

    if isinstance(input_data, dict):
        if isinstance(input_data.get("analyzed_keywords"), list):
            return [item for item in input_data["analyzed_keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("selected_keywords"), list):
            return [item for item in input_data["selected_keywords"] if isinstance(item, dict)]

    return []


def _coerce_select_options(input_data: Any) -> dict[str, Any]:
    if isinstance(input_data, dict) and isinstance(input_data.get("select_options"), dict):
        return input_data["select_options"]
    return {}


def _normalize_grade(value: Any) -> str:
    grade = str(value or "").strip().upper()
    return grade if grade in {"S", "A", "B", "C", "D", "F"} else ""


def _resolve_grade(item: dict[str, Any]) -> str:
    direct_grade = _normalize_grade(item.get("grade"))
    if direct_grade:
        return direct_grade

    score = item.get("score")
    try:
        score_value = float(score or 0.0)
    except (TypeError, ValueError):
        return ""

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


def _normalize_allowed_grades(grades: Any) -> set[str]:
    if not isinstance(grades, list):
        return set()
    return {_normalize_grade(grade) for grade in grades if _normalize_grade(grade)}


def _normalize_profitability_grade(value: Any) -> str:
    grade = str(value or "").strip().upper()
    return grade if grade in PROFITABILITY_GRADE_ORDER else ""


def _normalize_attackability_grade(value: Any) -> str:
    grade = str(value or "").strip()
    return grade if grade in ATTACKABILITY_GRADE_ORDER else ""


def _normalize_allowed_profitability_grades(grades: Any) -> set[str]:
    if not isinstance(grades, list):
        return set()
    return {
        _normalize_profitability_grade(grade)
        for grade in grades
        if _normalize_profitability_grade(grade)
    }


def _normalize_allowed_attackability_grades(grades: Any) -> set[str]:
    if not isinstance(grades, list):
        return set()
    return {
        _normalize_attackability_grade(grade)
        for grade in grades
        if _normalize_attackability_grade(grade)
    }


def _resolve_profitability_grade(item: dict[str, Any]) -> str:
    direct_grade = _normalize_profitability_grade(item.get("profitability_grade"))
    if direct_grade:
        return direct_grade

    metrics = item.get("metrics")
    if not isinstance(metrics, dict):
        return ""

    profitability_score = calculate_profitability_score(
        float(metrics.get("monetization_score", 0.0) or 0.0),
        float(metrics.get("search_volume_score", metrics.get("volume_score", 0.0)) or 0.0),
        float(metrics.get("total_clicks", 0.0) or 0.0),
        DEFAULT_CONFIG,
    )
    return classify_profitability_grade(profitability_score, DEFAULT_CONFIG)


def _resolve_attackability_grade(item: dict[str, Any]) -> str:
    direct_grade = _normalize_attackability_grade(item.get("attackability_grade"))
    if direct_grade:
        return direct_grade

    metrics = item.get("metrics")
    if not isinstance(metrics, dict):
        return ""

    attackability_score = calculate_attackability_score(
        float(metrics.get("opportunity", 0.0) or 0.0),
        float(metrics.get("rarity_score", 0.0) or 0.0),
        float(metrics.get("competition", 0.0) or 0.0),
        float(metrics.get("search_volume_score", metrics.get("volume_score", 0.0)) or 0.0),
        DEFAULT_CONFIG,
        total_clicks=float(metrics.get("total_clicks", 0.0) or 0.0),
        search_volume=float(metrics.get("volume", 0.0) or 0.0),
    )
    return classify_attackability_grade(attackability_score, DEFAULT_CONFIG)


def _resolve_golden_bucket(item: dict[str, Any]) -> str:
    direct_bucket = str(item.get("golden_bucket") or "").strip().lower()
    if direct_bucket in {"gold", "promising", "experimental", "hold"}:
        return direct_bucket

    profitability_grade = _resolve_profitability_grade(item)
    attackability_grade = _resolve_attackability_grade(item)
    if not profitability_grade or not attackability_grade:
        return ""
    return classify_golden_bucket(profitability_grade, attackability_grade)


def _matches_combo_filter(
    item: dict[str, Any],
    *,
    allowed_profitability_grades: set[str],
    allowed_attackability_grades: set[str],
) -> bool:
    profitability_grade = _resolve_profitability_grade(item)
    attackability_grade = _resolve_attackability_grade(item)
    if allowed_profitability_grades and profitability_grade not in allowed_profitability_grades:
        return False
    if allowed_attackability_grades and attackability_grade not in allowed_attackability_grades:
        return False
    return True


def _resolve_default_selection_target_count(items: list[dict[str, Any]]) -> int:
    measured_count = sum(1 for item in items if _is_measured_candidate(item))
    if measured_count <= 0:
        return 0
    scaled_target = int(math.ceil(measured_count * _DEFAULT_SELECTION_TOP_UP_RATIO))
    if measured_count >= _DEFAULT_SELECTION_XL_POOL_THRESHOLD:
        scaled_target = max(scaled_target, 12)
    elif measured_count >= _DEFAULT_SELECTION_LARGE_POOL_THRESHOLD:
        scaled_target = max(scaled_target, 9)
    elif measured_count >= _DEFAULT_SELECTION_MEDIUM_POOL_THRESHOLD:
        scaled_target = max(scaled_target, 6)
    return max(_MIN_DEFAULT_SELECTION_COUNT, min(_DEFAULT_SELECTION_MAX_COUNT, scaled_target))


def _top_up_default_selection(
    selected: list[dict[str, Any]],
    items: list[dict[str, Any]],
    *,
    target_count: int,
) -> list[dict[str, Any]]:
    if len(selected) >= target_count:
        return selected

    selected_keys = {
        normalize_key(normalize_text(item.get("keyword")))
        for item in selected
        if normalize_key(normalize_text(item.get("keyword")))
    }
    supplemental = _select_fallback_candidates(
        items,
        limit=max(0, target_count - len(selected)),
        exclude_keyword_keys=selected_keys,
    )
    if not supplemental:
        return selected
    return [*selected, *supplemental]


def _select_fallback_candidates(
    items: list[dict[str, Any]],
    *,
    limit: int = _EDITORIAL_FALLBACK_LIMIT,
    exclude_keyword_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    effective_limit = max(0, int(limit))
    if effective_limit == 0:
        return []
    excluded = exclude_keyword_keys or set()
    ranked_items = sorted(
        (
            item
            for item in items
            if isinstance(item, dict)
            and normalize_key(normalize_text(item.get("keyword"))) not in excluded
        ),
        key=_fallback_candidate_sort_key,
        reverse=True,
    )

    exploratory = [
        _decorate_editorial_support_item(item, reason="editorial_longtail_seed")
        for item in ranked_items
        if _is_measured_candidate(item) and _resolve_golden_bucket(item) == "experimental"
    ]
    exposure_first = [
        _decorate_editorial_support_item(item, reason="high_exposure_seed")
        for item in ranked_items
        if _is_measured_candidate(item)
        and _resolve_golden_bucket(item) == "hold"
        and _resolve_attackability_grade(item) in {"1", "2", "3", "4"}
        and float(item.get("score", 0.0) or 0.0) >= 30.0
    ]
    measured = [
        _decorate_editorial_support_item(item, reason="measured_seed")
        for item in ranked_items
        if _is_measured_candidate(item) and float(item.get("score", 0.0) or 0.0) >= 30.0
    ]

    editorial_pool = _merge_unique_candidates(
        exploratory,
        exposure_first,
        measured,
        limit=effective_limit,
    )
    if editorial_pool:
        return editorial_pool

    secondary = [
        _decorate_fallback_item(item)
        for item in ranked_items
        if _is_measured_candidate(item)
    ]
    return secondary[:min(1, effective_limit)]


def _is_measured_candidate(item: dict[str, Any]) -> bool:
    metrics = item.get("metrics")
    if not isinstance(metrics, dict):
        return False

    analysis_mode = str(item.get("analysis_mode") or "")
    confidence = float(item.get("confidence", metrics.get("confidence", 0.0)) or 0.0)
    return analysis_mode == "search_metrics" or confidence >= 0.8


def _decorate_fallback_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "selection_mode": "fallback",
        "selection_reason": "top_scored_candidate",
    }


def _decorate_editorial_support_item(item: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        **item,
        "selection_mode": "editorial_support",
        "selection_reason": reason,
    }


def _decorate_grade_selected_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "selection_mode": "grade_filter",
        "selection_reason": "allowed_grade",
    }


def _decorate_combo_selected_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "profitability_grade": _resolve_profitability_grade(item),
        "attackability_grade": _resolve_attackability_grade(item),
        "golden_bucket": _resolve_golden_bucket(item),
        "selection_mode": "combo_filter",
        "selection_reason": "allowed_axes",
    }


def _decorate_default_selected_item(item: dict[str, Any]) -> dict[str, Any]:
    golden_bucket = _resolve_golden_bucket(item)
    return {
        **item,
        "profitability_grade": _resolve_profitability_grade(item),
        "attackability_grade": _resolve_attackability_grade(item),
        "golden_bucket": golden_bucket,
        "selection_mode": "golden_combo",
        "selection_reason": golden_bucket or "golden_combo",
    }


def _is_template_heavy_keyword(keyword: Any) -> bool:
    keyword_key = normalize_key(normalize_text(keyword))
    if not keyword_key:
        return False
    return any(pattern in keyword_key for pattern in _TEMPLATE_HEAVY_KEYWORD_KEYS)


def _fallback_candidate_sort_key(item: dict[str, Any]) -> tuple[float, float, float, float, float, float, float]:
    template_rank = 0.0 if _is_template_heavy_keyword(item.get("keyword")) else 1.0
    bucket_rank = {
        "experimental": 2.0,
        "hold": 1.0,
        "promising": 0.5,
        "gold": 0.0,
    }.get(_resolve_golden_bucket(item), 0.0)
    attackability_grade = _resolve_attackability_grade(item)
    attackability_rank = float(
        len(ATTACKABILITY_GRADE_ORDER) - ATTACKABILITY_GRADE_ORDER.index(attackability_grade)
    ) if attackability_grade in ATTACKABILITY_GRADE_ORDER else 0.0
    specificity = float(len(tokenize_text(normalize_text(item.get("keyword")))))
    confidence = float(item.get("confidence", item.get("metrics", {}).get("confidence", 0.0)) or 0.0)
    score = float(item.get("score", 0.0) or 0.0)
    volume = float(item.get("metrics", {}).get("volume", 0.0) or 0.0)
    return (
        template_rank,
        bucket_rank,
        attackability_rank,
        specificity,
        confidence,
        score,
        volume,
    )


def _merge_unique_candidates(*groups: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            keyword_key = normalize_key(normalize_text(item.get("keyword")))
            if not keyword_key or keyword_key in seen:
                continue
            seen.add(keyword_key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def _inject_seed_anchor_candidate(
    selected: list[dict[str, Any]],
    input_data: Any,
    analyzed_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(input_data, dict):
        return selected

    seed_input = normalize_text(input_data.get("seed_input"))
    if not seed_input or not _should_consider_seed_anchor(seed_input):
        return selected
    if _selected_keywords_cover_seed(selected, seed_input):
        return selected

    seed_candidate = _build_seed_anchor_candidate(seed_input, analyzed_items)
    if seed_candidate is None:
        return selected

    selected_copy = [dict(item) for item in selected if isinstance(item, dict)]
    if not selected_copy:
        return [seed_candidate]

    replaceable_indexes = [
        index
        for index, item in enumerate(selected_copy)
        if str(item.get("selection_mode") or "").strip().lower() in {"fallback", "editorial_support"}
        and not _keyword_covers_seed(item.get("keyword"), seed_input)
    ]
    if replaceable_indexes:
        replace_index = min(replaceable_indexes, key=lambda index: _seed_replacement_sort_key(selected_copy[index]))
        selected_copy[replace_index] = seed_candidate
    else:
        selected_copy.insert(0, seed_candidate)

    unique_selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in selected_copy:
        keyword_key = normalize_key(normalize_text(item.get("keyword")))
        if not keyword_key or keyword_key in seen:
            continue
        seen.add(keyword_key)
        unique_selected.append(item)
    return unique_selected


def _build_seed_anchor_candidate(seed_input: str, analyzed_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    reference = _pick_seed_anchor_reference_item(seed_input, analyzed_items)
    reference_score = _coerce_float(reference.get("score")) if reference else 0.0
    reference_confidence = _coerce_float(
        reference.get("confidence", reference.get("metrics", {}).get("confidence")) if reference else 0.0
    )
    score_floor = 36.0 if len(tokenize_text(seed_input)) >= 4 else 34.0

    candidate = {
        "keyword": seed_input,
        "selection_mode": "seed_anchor",
        "selection_reason": "seed_intent_preserved",
        "analysis_mode": str(reference.get("analysis_mode") or "seed_anchor") if reference else "seed_anchor",
        "confidence": round(min(0.89, max(0.55, reference_confidence or 0.55)), 2),
        "score": round(max(score_floor, reference_score - 2.0), 1) if reference else score_floor,
    }
    if reference:
        origin = normalize_text(reference.get("origin"))
        item_type = normalize_text(reference.get("type"))
        if origin:
            candidate["origin"] = origin
        if item_type:
            candidate["type"] = item_type
        candidate["reference_keyword"] = normalize_text(reference.get("keyword")) or seed_input
    return candidate


def _pick_seed_anchor_reference_item(seed_input: str, analyzed_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    anchor_keys = _extract_seed_anchor_token_keys(seed_input)
    signal_keys = _extract_seed_signal_token_keys(seed_input)
    if not anchor_keys:
        return None

    ranked = sorted(
        (
            item
            for item in analyzed_items
            if isinstance(item, dict) and normalize_text(item.get("keyword"))
        ),
        key=lambda item: _seed_reference_sort_key(item, seed_input, anchor_keys, signal_keys),
        reverse=True,
    )
    if not ranked:
        return None

    top_item = ranked[0]
    top_overlap = _seed_keyword_overlap_ratio(top_item.get("keyword"), anchor_keys)
    return top_item if top_overlap > 0.0 else None


def _seed_reference_sort_key(
    item: dict[str, Any],
    seed_input: str,
    anchor_keys: set[str],
    signal_keys: set[str],
) -> tuple[float, float, float, float, float, float]:
    keyword = normalize_text(item.get("keyword"))
    keyword_key = normalize_key(keyword)
    seed_key = normalize_key(seed_input)
    exact_match_rank = 1.0 if keyword_key == seed_key else 0.0
    containment_rank = 1.0 if seed_key and keyword_key and (seed_key in keyword_key or keyword_key in seed_key) else 0.0
    signal_coverage = _seed_signal_coverage_ratio(keyword, signal_keys)
    overlap_ratio = _seed_keyword_overlap_ratio(keyword, anchor_keys)
    score = _coerce_float(item.get("score"))
    confidence = _coerce_float(item.get("confidence", item.get("metrics", {}).get("confidence")))
    return (
        exact_match_rank,
        containment_rank,
        signal_coverage,
        overlap_ratio,
        score,
        confidence,
    )


def _should_consider_seed_anchor(seed_input: str) -> bool:
    tokens = [normalize_text(token) for token in tokenize_text(seed_input) if normalize_text(token)]
    if len(tokens) >= 4:
        return True
    if _extract_seed_signal_token_keys(seed_input):
        return True
    return _looks_like_specific_seed(seed_input)


def _selected_keywords_cover_seed(selected: list[dict[str, Any]], seed_input: str) -> bool:
    return any(_keyword_covers_seed(item.get("keyword"), seed_input) for item in selected if isinstance(item, dict))


def _keyword_covers_seed(keyword: Any, seed_input: str) -> bool:
    keyword_text = normalize_text(keyword)
    if not keyword_text:
        return False
    keyword_key = normalize_key(keyword_text)
    seed_key = normalize_key(seed_input)
    if keyword_key == seed_key:
        return True
    if seed_key and seed_key in keyword_key:
        return True

    anchor_keys = _extract_seed_anchor_token_keys(seed_input)
    signal_keys = _extract_seed_signal_token_keys(seed_input)
    if not anchor_keys:
        return False

    keyword_token_keys = {
        normalize_key(token)
        for token in tokenize_text(keyword_text)
        if normalize_key(token)
    }
    if signal_keys and not signal_keys.issubset(keyword_token_keys):
        return False
    overlap_ratio = len(anchor_keys & keyword_token_keys) / max(1, len(anchor_keys))
    return overlap_ratio >= 0.75


def _extract_seed_anchor_token_keys(seed_input: str) -> set[str]:
    token_keys = {
        normalize_key(token)
        for token in tokenize_text(seed_input)
        if normalize_key(token)
    }
    if not token_keys:
        return set()
    if _extract_seed_signal_token_keys(seed_input) or _looks_like_specific_seed(seed_input):
        return token_keys
    if len(token_keys) >= 4:
        return token_keys
    return set()


def _extract_seed_signal_token_keys(seed_input: str) -> set[str]:
    signal_keys: set[str] = set()
    for token in tokenize_text(seed_input):
        token_key = normalize_key(token)
        if not token_key:
            continue
        if any(signal_key in token_key or token_key in signal_key for signal_key in _SEED_ANCHOR_SIGNAL_KEYS):
            signal_keys.add(token_key)
    return signal_keys


def _looks_like_specific_seed(seed_input: str) -> bool:
    tokens = [normalize_text(token) for token in tokenize_text(seed_input) if normalize_text(token)]
    if len(tokens) < 2:
        return False
    return any(_MODEL_LIKE_TOKEN_RE.search(token) for token in tokens)


def _seed_keyword_overlap_ratio(keyword: Any, anchor_keys: set[str]) -> float:
    keyword_token_keys = {
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
    }
    if not anchor_keys or not keyword_token_keys:
        return 0.0
    return len(anchor_keys & keyword_token_keys) / max(1, len(anchor_keys))


def _seed_signal_coverage_ratio(keyword: Any, signal_keys: set[str]) -> float:
    if not signal_keys:
        return 0.0
    keyword_token_keys = {
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
    }
    if not keyword_token_keys:
        return 0.0
    return len(signal_keys & keyword_token_keys) / max(1, len(signal_keys))


def _seed_replacement_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    return (
        _coerce_float(item.get("score")),
        _coerce_float(item.get("confidence", item.get("metrics", {}).get("confidence"))),
        float(len(tokenize_text(normalize_text(item.get("keyword"))))),
    )


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
