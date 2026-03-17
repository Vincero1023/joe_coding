from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.interfaces import ModuleRunner
from app.selector.service import SelectorService


service = SelectorService()

EXAMPLE_INPUT = [
    {
        "keyword": "보험 추천",
        "score": 1.0,
        "priority": "high",
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
        "keyword": "뜻 정리",
        "score": 0.454,
        "priority": "low",
        "metrics": {
            "volume": 1.0,
            "cpc": 0.3,
            "competition": 1.0,
            "bid": 0.3,
            "profit": 0.09,
            "opportunity": 1.0,
        },
    },
]


def run(input_data: Any) -> Any:
    return service.run(input_data)


class SelectorModule(ModuleRunner):
    def __init__(self, service: SelectorService) -> None:
        self._service = service

    def run(self, input_data: dict) -> dict:
        return self._service.run(input_data)


selector_module = SelectorModule(service=service)


if __name__ == "__main__":
    from pprint import pprint

    print("골든 키워드 선별 결과")
    pprint(run(EXAMPLE_INPUT), sort_dicts=False)
