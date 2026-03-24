from __future__ import annotations

import math
from typing import Any

from app.analyzer.config import DEFAULT_CONFIG
from app.analyzer.scorer import (
    calculate_attackability_score,
    calculate_profitability_score,
    classify_attackability_grade,
    classify_golden_bucket,
    classify_profitability_grade,
)
from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.selector.cannibalization import build_cannibalization_report
from app.selector.content_map import build_content_map
from app.selector.longtail import build_longtail_map, resolve_longtail_options


_EDITORIAL_FALLBACK_LIMIT = 8
_MIN_DEFAULT_SELECTION_COUNT = 4
_DEFAULT_SELECTION_TOP_UP_RATIO = 0.12
_TEMPLATE_HEAVY_KEYWORD_PATTERNS = (
    "추천 기준",
    "고를 때 체크",
    "비교 포인트",
    "최신 정보",
)
_TEMPLATE_HEAVY_KEYWORD_KEYS = tuple(
    normalize_key(pattern) for pattern in _TEMPLATE_HEAVY_KEYWORD_PATTERNS if normalize_key(pattern)
)


def is_golden_keyword(item: dict[str, Any]) -> bool:
    if _is_template_heavy_keyword(item.get("keyword")):
        return False
    golden_bucket = _resolve_golden_bucket(item)
    return golden_bucket in {"gold", "promising"}


class SelectorService:
    def run(self, input_data: Any) -> Any:
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
            return _build_selected_payload(selected, longtail_options=select_options.get("longtail_options"))

        if mode == "grade_filter" and allowed_grades:
            selected = [
                _decorate_grade_selected_item(item)
                for item in items
                if _resolve_grade(item) in allowed_grades
            ]
            if isinstance(input_data, list):
                return selected
            return _build_selected_payload(selected, longtail_options=select_options.get("longtail_options"))

        selected = [_decorate_default_selected_item(item) for item in items if is_golden_keyword(item)]
        target_count = _resolve_default_selection_target_count(items)
        if len(selected) < target_count:
            selected = _top_up_default_selection(selected, items, target_count=target_count)
        if not selected:
            selected = _select_fallback_candidates(items)

        if isinstance(input_data, list):
            return selected
        return _build_selected_payload(selected, longtail_options=select_options.get("longtail_options"))


def _build_selected_payload(
    selected: list[dict[str, Any]],
    *,
    longtail_options: dict[str, Any] | None = None,
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
    return {
        "selected_keywords": selected,
        **content_map,
        **longtail_map,
        "cannibalization_report": cannibalization_report,
    }


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
    return grade if grade in {"A", "B", "C", "D"} else ""


def _normalize_attackability_grade(value: Any) -> str:
    grade = str(value or "").strip()
    return grade if grade in {"1", "2", "3", "4"} else ""


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
    return max(_MIN_DEFAULT_SELECTION_COUNT, min(_EDITORIAL_FALLBACK_LIMIT, scaled_target))


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
        and _resolve_attackability_grade(item) in {"1", "2", "3"}
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
    attackability_rank = {
        "1": 4.0,
        "2": 3.0,
        "3": 2.0,
        "4": 1.0,
    }.get(_resolve_attackability_grade(item), 0.0)
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
