from __future__ import annotations

from typing import Any

from app.analyzer.config import DEFAULT_CONFIG
from app.analyzer.scorer import (
    calculate_attackability_score,
    calculate_profitability_score,
    classify_attackability_grade,
    classify_golden_bucket,
    classify_profitability_grade,
)
from app.selector.cannibalization import build_cannibalization_report
from app.selector.content_map import build_content_map
from app.selector.longtail import build_longtail_map, resolve_longtail_options


def is_golden_keyword(item: dict[str, Any]) -> bool:
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


def _select_fallback_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked_items = sorted(
        (item for item in items if isinstance(item, dict)),
        key=lambda item: (
            float(item.get("confidence", item.get("metrics", {}).get("confidence", 0.0)) or 0.0),
            float(item.get("score", 0.0) or 0.0),
            float(item.get("metrics", {}).get("cpc", 0.0) or 0.0),
            float(item.get("metrics", {}).get("volume", 0.0) or 0.0),
        ),
        reverse=True,
    )

    primary = [
        _decorate_fallback_item(item)
        for item in ranked_items
        if _is_measured_candidate(item) and float(item.get("score", 0.0) or 0.0) >= 30.0
    ]
    if primary:
        return primary[:3]

    secondary = [
        _decorate_fallback_item(item)
        for item in ranked_items
        if _is_measured_candidate(item)
    ]
    return secondary[:1]


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
