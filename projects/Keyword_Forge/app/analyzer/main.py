from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.analyzer.config import DEFAULT_CONFIG
from app.analyzer.keyword_stats import build_stats_index, merge_keyword_stats
from app.analyzer.keywordmaster_benchmark import build_keywordmaster_benchmark_index
from app.analyzer.naver_open_search import build_blog_search_index
from app.analyzer.naver_searchad import build_searchad_bid_index, build_searchad_keyword_tool_index
from app.analyzer.scorer import analyze_items
from app.core.keyword_inputs import coerce_expanded_keyword_items
from app.core.interfaces import ModuleRunner
from app.expander.utils.tokenizer import normalize_key


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
    stats_index = build_stats_index(input_data)
    _merge_measured_stats_index(input_data, keywords, stats_index)
    return analyze_items(
        keywords,
        stats_index=stats_index,
        config=DEFAULT_CONFIG,
    )


class AnalyzerModule(ModuleRunner):
    def __init__(self, service: AnalyzerService) -> None:
        self._service = service

    def run(self, input_data: dict) -> dict:
        return self._service.run(input_data)


analyzer_module = AnalyzerModule(service=service)


def _coerce_input_items(input_data: Any) -> list[dict[str, Any]]:
    if isinstance(input_data, dict) and isinstance(input_data.get("analyzed_keywords"), list):
        return [item for item in input_data["analyzed_keywords"] if isinstance(item, dict)]

    return coerce_expanded_keyword_items(input_data)


def _merge_measured_stats_index(
    input_data: Any,
    keywords: list[dict[str, Any]],
    stats_index: dict[str, Any],
) -> None:
    if not isinstance(input_data, dict):
        return

    _merge_stats_index(
        stats_index,
        build_keywordmaster_benchmark_index(
            input_data,
            keywords,
            stats_index=stats_index,
        ),
    )

    measured_indexes = [
        build_searchad_keyword_tool_index(
            input_data,
            keywords,
            stats_index=stats_index,
        ),
        build_searchad_bid_index(
            input_data,
            keywords,
            stats_index=stats_index,
        ),
        build_blog_search_index(
            input_data,
            keywords,
            stats_index=stats_index,
        ),
    ]

    for measured_index in measured_indexes:
        _merge_stats_index(stats_index, measured_index)


def _merge_stats_index(
    stats_index: dict[str, Any],
    measured_index: dict[str, Any],
) -> None:
    for item in measured_index.values():
        key = normalize_key(item.keyword)
        if not key:
            continue

        existing = stats_index.get(key)
        if existing is None:
            stats_index[key] = item
            continue

        stats_index[key] = merge_keyword_stats(item, existing)


if __name__ == "__main__":
    from pprint import pprint

    print("분석 예시 결과")
    pprint(run(EXAMPLE_INPUT), sort_dicts=False)
