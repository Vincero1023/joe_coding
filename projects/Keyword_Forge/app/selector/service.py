from __future__ import annotations

from typing import Any


def is_golden_keyword(item: dict[str, Any]) -> bool:
    metrics = item.get("metrics")
    if not isinstance(metrics, dict):
        return False

    score = float(item.get("score", 0.0) or 0.0)
    confidence = float(item.get("confidence", metrics.get("confidence", 0.0)) or 0.0)
    analysis_mode = str(item.get("analysis_mode") or "")

    volume = float(metrics.get("volume", 0.0) or 0.0)
    cpc = float(metrics.get("cpc", 0.0) or 0.0)
    competition = float(metrics.get("competition", 0.0) or 0.0)
    opportunity = float(metrics.get("opportunity", 0.0) or 0.0)
    monetization_score = float(metrics.get("monetization_score", 0.0) or 0.0)
    rarity_score = float(metrics.get("rarity_score", 0.0) or 0.0)

    if analysis_mode == "search_metrics" or confidence >= 0.8:
        if score < 55.0:
            return False
        if volume < 100.0:
            return False
        if cpc < 70.0:
            return False
        if opportunity < 1.15:
            return False
        return competition <= 1.5

    if score < 38.0:
        return False
    if monetization_score < 25.0:
        return False
    if rarity_score < 30.0:
        return False
    return opportunity >= 1.6


class SelectorService:
    def run(self, input_data: Any) -> Any:
        items = _coerce_input_items(input_data)
        select_options = _coerce_select_options(input_data)
        allowed_grades = _normalize_allowed_grades(select_options.get("allowed_grades"))
        mode = str(select_options.get("mode") or "").strip().lower()

        if mode == "grade_filter" and allowed_grades:
            selected = [
                _decorate_grade_selected_item(item)
                for item in items
                if _resolve_grade(item) in allowed_grades
            ]
            if isinstance(input_data, list):
                return selected
            return {"selected_keywords": selected}

        selected = [item for item in items if is_golden_keyword(item)]
        if not selected:
            selected = _select_fallback_candidates(items)

        if isinstance(input_data, list):
            return selected
        return {"selected_keywords": selected}


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
