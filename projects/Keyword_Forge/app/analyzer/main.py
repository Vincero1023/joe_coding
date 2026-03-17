from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.analyzer.config import DEFAULT_CONFIG
from app.analyzer.scorer import analyze_items
from app.core.interfaces import ModuleRunner


class AnalyzerService:
    def run(self, input_data: Any) -> Any:
        analyzed = analyze_keywords(input_data)
        if isinstance(input_data, list):
            return analyzed
        return {"analyzed_keywords": analyzed}


service = AnalyzerService()

# 예시 입력: 확장 결과를 받아 수익성과 우선순위를 평가한다.
EXAMPLE_INPUT = [
    {"keyword": "보험 추천", "root_origin": "보험"},
    {"keyword": "카드 비교", "root_origin": "카드"},
    {"keyword": "뜻 정리", "root_origin": "뜻"},
]


def run(input_data: Any) -> Any:
    return service.run(input_data)


def analyze_keywords(input_data: Any) -> list[dict[str, Any]]:
    keywords = _coerce_input_items(input_data)
    return analyze_items(keywords, config=DEFAULT_CONFIG)


class AnalyzerModule(ModuleRunner):
    def __init__(self, service: AnalyzerService) -> None:
        self._service = service

    def run(self, input_data: dict) -> dict:
        return self._service.run(input_data)


analyzer_module = AnalyzerModule(service=service)


def _coerce_input_items(input_data: Any) -> list[dict[str, Any]]:
    if isinstance(input_data, list):
        return [item for item in input_data if isinstance(item, dict)]

    if isinstance(input_data, dict):
        if isinstance(input_data.get("expanded_keywords"), list):
            return [item for item in input_data["expanded_keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("keywords"), list):
            return [item for item in input_data["keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("analyzed_keywords"), list):
            return [item for item in input_data["analyzed_keywords"] if isinstance(item, dict)]

    return []


if __name__ == "__main__":
    from pprint import pprint

    print("분석 예시 결과")
    pprint(run(EXAMPLE_INPUT), sort_dicts=False)
