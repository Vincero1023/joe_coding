from __future__ import annotations

from typing import Any



def is_golden_keyword(item: dict[str, Any]) -> bool:
    metrics = item.get("metrics")
    if not isinstance(metrics, dict):
        return False

    cpc = float(metrics.get("cpc", 0.0) or 0.0)
    bid = float(metrics.get("bid", 0.0) or 0.0)
    volume = float(metrics.get("volume", 0.0) or 0.0)
    competition = float(metrics.get("competition", 0.0) or 0.0)

    if cpc < 0.6:
        return False
    if bid < 0.6:
        return False
    if competition > 0.75:
        return False
    if volume < 0.4:
        return False

    return True


class SelectorService:
    def run(self, input_data: Any) -> Any:
        items = _coerce_input_items(input_data)
        selected = [item for item in items if is_golden_keyword(item)]

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
