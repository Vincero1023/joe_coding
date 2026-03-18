from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.interfaces import ModuleRunner
from app.pipeline.service import PipelineService


service = PipelineService()

EXAMPLE_INPUT = {
    "collector": {
        "mode": "category",
        "category": "비즈니스경제",
        "seed_input": "",
        "options": {
            "collect_related": False,
            "collect_autocomplete": False,
            "collect_bulk": True,
        },
        "analysis_json_path": "app/collector/sample/site_analysis2.json",
    },
    "expander": {
        "analysis_json_path": "app/expander/sample/site_analysis.json",
    },
}


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    return service.run(input_data)


class PipelineModule(ModuleRunner):
    def __init__(self, service: PipelineService) -> None:
        self._service = service

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return self._service.run(input_data)


pipeline_module = PipelineModule(service=service)


if __name__ == "__main__":
    from pprint import pprint

    result = run(EXAMPLE_INPUT)
    summary = {key: len(value) for key, value in result.items() if isinstance(value, list)}

    print("전체 파이프라인 실행 결과")
    pprint(summary, sort_dicts=False)
