from __future__ import annotations

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))

if _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from typing import Any

from app.core.interfaces import ModuleRunner
from app.title.title_generator import generate_titles


class TitleService:
    def run(self, input_data: Any) -> Any:
        items = _coerce_input_items(input_data)
        generated = generate_titles(items)

        if isinstance(input_data, list):
            return generated
        return {"generated_titles": generated}


service = TitleService()

EXAMPLE_INPUT = [
    {
        "keyword": "보험 추천",
        "score": 1.0,
        "metrics": {
            "volume": 1.0,
            "cpc": 1.0,
            "competition": 0.7,
            "bid": 1.0,
            "profit": 1.0,
            "opportunity": 1.4286,
        },
    },
    {
        "keyword": "제주 여행 코스",
        "score": 0.82,
        "metrics": {
            "volume": 0.7,
            "cpc": 0.7,
            "competition": 0.4,
            "bid": 0.6,
            "profit": 0.42,
            "opportunity": 1.75,
        },
    },
]


def run(input_data: Any) -> Any:
    return service.run(input_data)


class TitleModule(ModuleRunner):
    def __init__(self, service: TitleService) -> None:
        self._service = service

    def run(self, input_data: dict) -> dict:
        return self._service.run(input_data)


title_module = TitleModule(service=service)



def _coerce_input_items(input_data: Any) -> list[dict[str, Any]]:
    if isinstance(input_data, list):
        return [item for item in input_data if isinstance(item, dict)]

    if isinstance(input_data, dict):
        if isinstance(input_data.get("selected_keywords"), list):
            return [item for item in input_data["selected_keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("analyzed_keywords"), list):
            return [item for item in input_data["analyzed_keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("generated_titles"), list):
            return [item for item in input_data["generated_titles"] if isinstance(item, dict)]

    return []


if __name__ == "__main__":
    from pprint import pprint

    print("제목 생성 예시 결과")
    pprint(run(EXAMPLE_INPUT), sort_dicts=False)
