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
from app.expander.utils.tokenizer import normalize_text
from app.title.ai_client import TitleGenerationOptions
from app.title.targets import build_title_targets
from app.title.title_generator import generate_titles


class TitleService:
    def run(self, input_data: Any) -> Any:
        if isinstance(input_data, dict):
            items, target_summary = build_title_targets(input_data)
            options = TitleGenerationOptions.from_input(input_data)
            items = _attach_issue_context_from_input(items, input_data)
        else:
            items = _coerce_input_items(input_data)
            target_summary = {}
            options = None
        generated, meta = generate_titles(items, options=options)
        if target_summary:
            meta["target_summary"] = target_summary

        if isinstance(input_data, list):
            return generated
        return {
            "generated_titles": generated,
            "generation_meta": meta,
        }


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
        if isinstance(input_data.get("title_targets"), list):
            return [item for item in input_data["title_targets"] if isinstance(item, dict)]
        if isinstance(input_data.get("selected_keywords"), list):
            return [item for item in input_data["selected_keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("analyzed_keywords"), list):
            return [item for item in input_data["analyzed_keywords"] if isinstance(item, dict)]
        if isinstance(input_data.get("generated_titles"), list):
            return [item for item in input_data["generated_titles"] if isinstance(item, dict)]

    return []


def _attach_issue_context_from_input(
    items: list[dict[str, Any]],
    input_data: dict[str, Any],
) -> list[dict[str, Any]]:
    serp_summary = input_data.get("serp_competition_summary")
    if not isinstance(serp_summary, dict):
        return items

    queries = serp_summary.get("queries")
    if not isinstance(queries, list):
        return items

    context_by_keyword = {
        normalize_text(item.get("query")): item
        for item in queries
        if isinstance(item, dict) and normalize_text(item.get("query"))
    }
    if not context_by_keyword:
        return items

    enriched_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("issue_context"), dict):
            enriched_items.append(item)
            continue

        lookup_candidates = [
            normalize_text(item.get("keyword")),
            normalize_text(item.get("base_keyword")),
        ]
        source_keywords = item.get("source_keywords")
        if isinstance(source_keywords, list):
            lookup_candidates.extend(normalize_text(keyword) for keyword in source_keywords)

        issue_context = next(
            (
                context_by_keyword[candidate]
                for candidate in lookup_candidates
                if candidate and candidate in context_by_keyword
            ),
            None,
        )
        if issue_context is None:
            enriched_items.append(item)
            continue

        enriched_items.append(
            {
                **item,
                "issue_context": issue_context,
            }
        )

    return enriched_items


if __name__ == "__main__":
    from pprint import pprint

    print("제목 생성 예시 결과")
    pprint(run(EXAMPLE_INPUT), sort_dicts=False)
