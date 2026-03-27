from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.analyzer.main import analyzer_module
from app.core.api_usage import capture_api_usage, merge_api_usage_snapshots
from app.core.keyword_inputs import coerce_collected_keyword_items
from app.core.interfaces import ModuleRunner
from app.expander.engines.autocomplete_engine import expand_autocomplete_engine
from app.expander.engines.combinator_engine import expand_combinator_engine
from app.expander.engines.related_engine import expand_related_engine
from app.expander.utils.dedup import deduplicate_expansions
from app.expander.utils.filtering import (
    apply_seed_filter,
    filter_expansions,
    limit_expansions_per_origin,
    limit_total_expansions,
)
from app.expander.utils.tokenizer import normalize_key, normalize_text


_MAX_DEPTH = 3
_MAX_PER_ORIGIN_PER_DEPTH = 20
_MAX_TOTAL_PER_ORIGIN = 50
ExpansionProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ExpansionRequest:
    collected_keywords: tuple[dict[str, Any], ...]
    analysis_json_path: Path | None
    enable_combinator: bool
    enable_related: bool
    enable_autocomplete: bool
    enable_seed_filter: bool
    max_results: int | None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ExpansionRequest":
        collected_keywords = tuple(coerce_collected_keyword_items(raw))
        raw_options = raw.get("expand_options") if isinstance(raw.get("expand_options"), dict) else {}

        raw_path = raw.get("analysis_json_path")
        analysis_json_path = Path(raw_path.strip()) if isinstance(raw_path, str) and raw_path.strip() else None
        return cls(
            collected_keywords=collected_keywords,
            analysis_json_path=analysis_json_path,
            enable_combinator=bool(raw.get("enable_combinator", False)),
            enable_related=_coerce_bool(raw.get("enable_related"), raw_options.get("enable_related"), default=True),
            enable_autocomplete=_coerce_bool(
                raw.get("enable_autocomplete"),
                raw_options.get("enable_autocomplete"),
                default=True,
            ),
            enable_seed_filter=_coerce_bool(
                raw.get("enable_seed_filter"),
                raw_options.get("enable_seed_filter"),
                default=True,
            ),
            max_results=_coerce_positive_int(raw.get("max_results"), raw_options.get("max_results")),
        )


@dataclass(frozen=True)
class ExpansionNode:
    current_keyword: str
    root_origin: str
    collected_item: dict[str, Any]


@dataclass(frozen=True)
class ExpansionStrategy:
    use_autocomplete: bool
    use_related: bool
    use_combinator: bool
    related_terms: tuple[str, ...]
    intent_terms: tuple[str, ...]
    time_terms: tuple[str, ...]

    @classmethod
    def from_analysis(cls, raw: dict[str, Any]) -> "ExpansionStrategy":
        core_functions = set(_collect_string_values(raw.get("core_functions")))
        feature_names = {
            str(item.get("feature", "")).strip()
            for item in raw.get("feature_logic", [])
            if isinstance(item, dict) and str(item.get("feature", "")).strip()
        }
        feature_texts = [
            normalize_text(item.get("logic"))
            for item in raw.get("feature_logic", [])
            if isinstance(item, dict)
        ]
        ui_types = {
            str(item.get("type", "")).strip()
            for item in raw.get("ui_components", [])
            if isinstance(item, dict) and str(item.get("type", "")).strip()
        }
        ui_roles = {
            str(item.get("role", "")).strip()
            for item in raw.get("ui_components", [])
            if isinstance(item, dict) and str(item.get("role", "")).strip()
        }

        supports_keyword_expansion = (
            "keyword_expansion" in core_functions
            or "keyword_expansion" in feature_names
            or "keyword suggestions" in ui_roles
            or "list" in ui_types
        )
        supports_keyword_analysis = (
            "keyword_analysis" in core_functions
            or "keyword_analysis" in feature_names
            or "keyword search" in ui_roles
        )
        supports_bulk_input = "bulk keyword input" in ui_roles or "textarea" in ui_types

        related_terms: list[str] = []
        if supports_keyword_expansion:
            related_terms.extend(["연관", "추천", "확장"])
        if supports_keyword_analysis:
            related_terms.extend(["분석", "트렌드"])
        if "guide content" in ui_roles:
            related_terms.append("가이드")
        if any("비교" in text for text in feature_texts if text):
            related_terms.append("비교")

        intent_terms: list[str] = []
        if supports_keyword_expansion:
            intent_terms.extend(["추천", "후기"])
        if supports_keyword_analysis:
            intent_terms.extend(["비교", "정리"])
        if "guide content" in ui_roles:
            intent_terms.append("방법")
        if not intent_terms:
            intent_terms.extend(["추천", "정리"])

        time_terms: list[str] = []
        if any("트렌드" in text for text in feature_texts if text) or supports_keyword_analysis:
            time_terms.extend(["오늘", "주간"])
        if supports_bulk_input:
            time_terms.append("이번주")
        if not time_terms:
            time_terms.extend(["오늘", "주말"])

        return cls(
            use_autocomplete=supports_keyword_expansion,
            use_related=supports_keyword_expansion or supports_keyword_analysis,
            use_combinator=supports_bulk_input,
            related_terms=tuple(dict.fromkeys(term for term in related_terms if term)),
            intent_terms=tuple(dict.fromkeys(term for term in intent_terms if term)),
            time_terms=tuple(dict.fromkeys(term for term in time_terms if term)),
        )

    def to_engine_payload(self) -> dict[str, Any]:
        return {
            "related_terms": list(self.related_terms),
            "intent_terms": list(self.intent_terms),
            "time_terms": list(self.time_terms),
        }


class ExpanderService:
    def run(self, input_data: dict) -> dict:
        return run_with_progress(input_data)


service = ExpanderService()

# 예시 입력: 수집된 키워드를 받아 전략 기반 다중 엔진 확장을 수행한다.
EXAMPLE_INPUT = {
    "keywords_text": "버터떡\n성심당 빵 추천",
    "category": "맛집",
    "analysis_json_path": "app/expander/sample/site_analysis.json",
}


def run(input_data: dict) -> dict:
    return service.run(input_data)


class ExpanderModule(ModuleRunner):
    def __init__(self, service: ExpanderService) -> None:
        self._service = service

    def run(self, input_data: dict) -> dict:
        return self._service.run(input_data)


expander_module = ExpanderModule(service=service)


def run_expander(input_data: dict, analysis_data: dict[str, Any]) -> dict:
    return _run_expander_internal(input_data, analysis_data)


def run_with_progress(
    input_data: dict,
    progress_callback: ExpansionProgressCallback | None = None,
    stop_event: Event | None = None,
) -> dict:
    with capture_api_usage() as api_usage:
        analysis_data = load_analysis_data(input_data.get("analysis_json_path"))
        result = _run_expander_internal(
            input_data,
            analysis_data,
            progress_callback=progress_callback,
            stop_event=stop_event,
        )
    result["debug"] = {
        "stage": "expander",
        "summary": api_usage.snapshot().get("summary", {}),
        "api_usage": api_usage.snapshot(),
        "expansion_summary": {
            "expanded_keyword_count": len(
                [item for item in result.get("expanded_keywords", []) if isinstance(item, dict)]
            ),
            "stopped": bool(result.get("stopped")),
        },
    }
    return result


def run_with_analysis_progress(
    input_data: dict,
    *,
    progress_callback: ExpansionProgressCallback | None = None,
    analysis_callback: ExpansionProgressCallback | None = None,
    stop_event: Event | None = None,
) -> dict:
    def forward_progress(event: dict[str, Any]) -> None:
        if progress_callback is not None:
            progress_callback(event)

    expanded_result = run_with_progress(
        input_data,
        progress_callback=forward_progress,
        stop_event=stop_event,
    )
    expanded_debug = expanded_result.get("debug") if isinstance(expanded_result.get("debug"), dict) else {}
    expanded_keywords = [
        item
        for item in expanded_result.get("expanded_keywords", [])
        if isinstance(item, dict)
    ]
    if _is_stop_requested(stop_event):
        return {
            "expanded_keywords": expanded_keywords,
            "analyzed_keywords": [],
            "stopped": True,
            "debug": expanded_debug,
        }
    if analysis_callback is not None:
        analysis_callback(
            {
                "type": "analysis_started",
                "total_candidates": len(expanded_keywords),
            }
        )
    analyzed_result = analyzer_module.run(_build_analyzer_input(input_data, expanded_keywords))
    analyzed_keywords = [
        item
        for item in analyzed_result.get("analyzed_keywords", [])
        if isinstance(item, dict)
    ]
    analyzed_debug = analyzed_result.get("debug") if isinstance(analyzed_result.get("debug"), dict) else {}
    merged_api_usage = merge_api_usage_snapshots(
        expanded_debug.get("api_usage"),
        analyzed_debug.get("api_usage"),
    )
    if analysis_callback is not None:
        analysis_callback(
            {
                "type": "analysis_completed",
                "total_analyzed": len(analyzed_keywords),
            }
        )
    return {
        "expanded_keywords": expanded_keywords,
        "analyzed_keywords": analyzed_keywords,
        "stopped": False,
        "debug": {
            "stage": "expand_analyze",
            "summary": merged_api_usage.get("summary", {}),
            "api_usage": merged_api_usage,
            "stage_api_usage": {
                "expander": expanded_debug.get("api_usage", {}),
                "analyzer": analyzed_debug.get("api_usage", {}),
            },
        },
    }


def _run_expander_internal(
    input_data: dict,
    analysis_data: dict[str, Any],
    progress_callback: ExpansionProgressCallback | None = None,
    stop_event: Event | None = None,
) -> dict:
    request = ExpansionRequest.from_dict(input_data)
    strategy = ExpansionStrategy.from_analysis(analysis_data)
    strategy = replace(
        strategy,
        use_autocomplete=request.enable_autocomplete,
        use_related=request.enable_related,
        use_combinator=request.enable_combinator and strategy.use_combinator,
    )
    engine_payload = strategy.to_engine_payload()
    queue = _build_initial_queue(request.collected_keywords)
    results: list[dict[str, str]] = []
    total_counts: dict[str, int] = {}
    seen_queue: set[tuple[str, str]] = set(
        (normalize_key(node.root_origin), normalize_key(node.current_keyword))
        for node in queue
    )

    if progress_callback is not None:
        progress_callback(
            {
                "type": "started",
                "total_origins": len(queue),
                "max_depth": _MAX_DEPTH,
            }
        )

    for depth_index in range(_MAX_DEPTH):
        if _is_stop_requested(stop_event):
            break
        if not queue:
            break

        depth = depth_index + 1
        if progress_callback is not None:
            progress_callback(
                {
                    "type": "depth_started",
                    "depth": depth,
                    "queue_size": len(queue),
                    "total_results": len(results),
                }
            )

        depth_expanded: list[dict[str, str]] = []
        for node_index, node in enumerate(queue, start=1):
            if _is_stop_requested(stop_event):
                break
            if progress_callback is not None:
                progress_callback(
                    {
                        "type": "keyword_started",
                        "depth": depth,
                        "index": node_index,
                        "total": len(queue),
                        "keyword": node.current_keyword,
                        "origin": node.root_origin,
                    }
                )

            node_results = _expand_all_engines(
                node,
                strategy,
                engine_payload,
                enable_seed_filter=request.enable_seed_filter,
            )
            if progress_callback is not None:
                preview_results = deduplicate_expansions(filter_expansions(node_results))
                if preview_results:
                    progress_callback(
                        {
                            "type": "keyword_results",
                            "depth": depth,
                            "index": node_index,
                            "total": len(queue),
                            "keyword": node.current_keyword,
                            "origin": node.root_origin,
                            "items": preview_results,
                        }
                    )
            depth_expanded.extend(node_results)

        filtered_results = filter_expansions(depth_expanded)
        deduplicated_results = deduplicate_expansions(filtered_results)
        depth_limited_results = limit_expansions_per_origin(
            deduplicated_results,
            max_per_origin=_MAX_PER_ORIGIN_PER_DEPTH,
        )
        accepted_results = limit_total_expansions(
            depth_limited_results,
            totals=total_counts,
            max_total_per_origin=_MAX_TOTAL_PER_ORIGIN,
        )
        if request.max_results is not None:
            remaining_slots = request.max_results - len(results)
            if remaining_slots <= 0:
                accepted_results = []
            elif len(accepted_results) > remaining_slots:
                accepted_results = accepted_results[:remaining_slots]

        results.extend(accepted_results)
        queue = _build_next_queue(accepted_results, request.collected_keywords, seen_queue)
        if progress_callback is not None:
            progress_callback(
                {
                    "type": "depth_completed",
                    "depth": depth,
                    "accepted_count": len(accepted_results),
                    "total_results": len(results),
                    "next_queue_size": len(queue),
                    "items": accepted_results,
                }
            )
        if _is_stop_requested(stop_event):
            break
        if request.max_results is not None and len(results) >= request.max_results:
            break

    final_results = deduplicate_expansions(results)
    final_results = limit_expansions_per_origin(final_results, max_per_origin=_MAX_TOTAL_PER_ORIGIN)
    if request.max_results is not None:
        final_results = final_results[: request.max_results]
    return {
        "expanded_keywords": final_results,
        "stopped": _is_stop_requested(stop_event),
    }


def load_analysis_data(analysis_json_path: Any) -> dict[str, Any]:
    if not isinstance(analysis_json_path, str) or not analysis_json_path.strip():
        return {}

    path = Path(analysis_json_path.strip()).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return {}

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _build_initial_queue(collected_keywords: tuple[dict[str, Any], ...]) -> list[ExpansionNode]:
    queue: list[ExpansionNode] = []
    for item in collected_keywords:
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue
        queue.append(
            ExpansionNode(
                current_keyword=keyword,
                root_origin=keyword,
                collected_item=item,
            )
        )
    return queue


def _expand_all_engines(
    node: ExpansionNode,
    strategy: ExpansionStrategy,
    engine_payload: dict[str, Any],
    *,
    enable_seed_filter: bool,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    if strategy.use_autocomplete:
        results.extend(expand_autocomplete_engine(node.current_keyword, engine_payload))

    if strategy.use_related:
        results.extend(expand_related_engine(node.current_keyword, engine_payload, node.collected_item))

    if strategy.use_combinator:
        results.extend(expand_combinator_engine(node.current_keyword, engine_payload, node.collected_item))

    normalized_results: list[dict[str, str]] = []
    for item in results:
        normalized_results.append(
            {
                "keyword": normalize_text(item.get("keyword")),
                "origin": node.root_origin,
                "type": normalize_text(item.get("type")),
            }
        )

    if enable_seed_filter:
        return apply_seed_filter(normalized_results, node.root_origin)
    return normalized_results


def _build_next_queue(
    items: list[dict[str, str]],
    collected_keywords: tuple[dict[str, Any], ...],
    seen_queue: set[tuple[str, str]],
) -> list[ExpansionNode]:
    origin_map = {
        normalize_key(normalize_text(item.get("keyword"))): item
        for item in collected_keywords
        if normalize_text(item.get("keyword"))
    }

    next_queue: list[ExpansionNode] = []
    for item in items:
        origin = normalize_text(item.get("origin"))
        keyword = normalize_text(item.get("keyword"))
        identity = (normalize_key(origin), normalize_key(keyword))
        if not origin or not keyword or identity in seen_queue:
            continue

        seen_queue.add(identity)
        next_queue.append(
            ExpansionNode(
                current_keyword=keyword,
                root_origin=origin,
                collected_item=origin_map.get(normalize_key(origin), {"keyword": origin}),
            )
        )

    return next_queue


def _collect_string_values(raw_items: Any) -> list[str]:
    if not isinstance(raw_items, list):
        return []
    return [text for text in (normalize_text(item) for item in raw_items) if text]


def _build_analyzer_input(input_data: dict[str, Any], expanded_keywords: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "expanded_keywords": expanded_keywords,
        "keyword_stats_path": input_data.get("keyword_stats_path", ""),
        "keyword_stats_text": input_data.get("keyword_stats_text", ""),
        "keyword_stats_items": input_data.get("keyword_stats_items", []),
        "keywordmaster_benchmark": input_data.get("keywordmaster_benchmark", {}),
        "keywordmaster_benchmark_enabled": input_data.get("keywordmaster_benchmark_enabled", None),
        "searchad": input_data.get("searchad", {}),
        "naver_ads_api_key": input_data.get("naver_ads_api_key", ""),
        "naver_ads_customer_id": input_data.get("naver_ads_customer_id", ""),
        "naver_ads_access_license": input_data.get("naver_ads_access_license", ""),
        "naver_ads_secret_key": input_data.get("naver_ads_secret_key", ""),
        "naver_search_api": input_data.get("naver_search_api", {}),
        "naver_search_client_id": input_data.get("naver_search_client_id", ""),
        "naver_search_client_secret": input_data.get("naver_search_client_secret", ""),
    }


def _coerce_bool(*values: Any, default: bool) -> bool:
    for value in values:
        if value is None:
            continue
        return bool(value)
    return default


def _is_stop_requested(stop_event: Event | None) -> bool:
    return bool(stop_event is not None and stop_event.is_set())


def _coerce_positive_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


if __name__ == "__main__":
    from pprint import pprint

    result = run(EXAMPLE_INPUT)
    preview = {"expanded_keywords": result["expanded_keywords"][:10]}
    input_keywords = [item for item in EXAMPLE_INPUT["keywords_text"].splitlines() if item.strip()]

    print("다중 깊이 확장 예시 결과")
    print(f"입력 키워드 수: {len(input_keywords)}")
    print(f"확장 결과 수: {len(result['expanded_keywords'])}")
    print("처음 10개만 표시합니다.")
    pprint(preview, sort_dicts=False)
