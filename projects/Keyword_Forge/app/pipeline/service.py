from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.analyzer.main import analyzer_module
from app.collector.main import collector_module
from app.expander.main import expander_module
from app.selector.main import selector_module
from app.title_gen.main import title_generator_module


class PipelineService:
    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        debug_enabled = bool(input_data.get("debug"))
        pipeline_debug = _start_pipeline_debug() if debug_enabled else None

        collector_input = _build_collector_input(input_data)
        if debug_enabled:
            collector_input["debug"] = True
        collected_result = _run_stage(
            pipeline_debug,
            stage_name="collector",
            runner=lambda: collector_module.run(collector_input),
        )

        expander_input = _build_expander_input(input_data)
        expander_input["collected_keywords"] = _get_list(collected_result, "collected_keywords")
        expanded_result = _run_stage(
            pipeline_debug,
            stage_name="expander",
            runner=lambda: expander_module.run(expander_input),
        )

        analyzer_input = _build_analyzer_input(input_data, expanded_result, collected_result)
        analyzed_result = _run_stage(
            pipeline_debug,
            stage_name="analyzer",
            runner=lambda: analyzer_module.run(analyzer_input),
        )
        selected_result = _run_stage(
            pipeline_debug,
            stage_name="selector",
            runner=lambda: selector_module.run(
                {
                    "analyzed_keywords": _get_list(analyzed_result, "analyzed_keywords"),
                    "select_options": input_data.get("select_options", {}),
                }
            ),
        )
        titled_result = _run_stage(
            pipeline_debug,
            stage_name="title_gen",
            runner=lambda: title_generator_module.run(_build_title_input(input_data, selected_result, analyzed_result)),
        )

        result = {
            "collected_keywords": _get_list(collected_result, "collected_keywords"),
            "expanded_keywords": _get_list(expanded_result, "expanded_keywords"),
            "analyzed_keywords": _get_list(analyzed_result, "analyzed_keywords"),
            "selected_keywords": _get_list(selected_result, "selected_keywords"),
            "keyword_clusters": _get_list(selected_result, "keyword_clusters"),
            "longtail_suggestions": _get_list(selected_result, "longtail_suggestions"),
            "longtail_options": selected_result.get("longtail_options", {})
            if isinstance(selected_result, dict)
            else {},
            "generated_titles": _get_list(titled_result, "generated_titles"),
            "content_map_summary": selected_result.get("content_map_summary", {})
            if isinstance(selected_result, dict)
            else {},
            "longtail_summary": selected_result.get("longtail_summary", {})
            if isinstance(selected_result, dict)
            else {},
            "cannibalization_report": selected_result.get("cannibalization_report", {})
            if isinstance(selected_result, dict)
            else {},
            "title_generation_meta": titled_result.get("generation_meta", {})
            if isinstance(titled_result, dict)
            else {},
        }

        if pipeline_debug is not None:
            pipeline_debug["duration_ms"] = _elapsed_ms(pipeline_debug["perf_started_at"])
            pipeline_debug["counts"] = {
                "collected_keywords": len(result["collected_keywords"]),
                "expanded_keywords": len(result["expanded_keywords"]),
                "analyzed_keywords": len(result["analyzed_keywords"]),
                "selected_keywords": len(result["selected_keywords"]),
                "keyword_clusters": len(result["keyword_clusters"]),
                "longtail_suggestions": len(result["longtail_suggestions"]),
                "generated_titles": len(result["generated_titles"]),
            }
            pipeline_debug.pop("perf_started_at", None)
            result["debug"] = pipeline_debug

        return result


def _build_collector_input(input_data: dict[str, Any]) -> dict[str, Any]:
    collector_defaults = {
        "mode": input_data.get("mode", "category"),
        "category": input_data.get("category", ""),
        "seed_input": input_data.get("seed_input", ""),
        "options": input_data.get("options", {}),
        "analysis_json_path": input_data.get("collector_analysis_json_path")
        or input_data.get("analysis_json_path", ""),
    }
    return _merge_stage_config(collector_defaults, input_data.get("collector"))


def _build_expander_input(input_data: dict[str, Any]) -> dict[str, Any]:
    expander_defaults = {
        "analysis_json_path": input_data.get("expander_analysis_json_path", ""),
    }
    return _merge_stage_config(expander_defaults, input_data.get("expander"))


def _build_title_input(
    input_data: dict[str, Any],
    selected_result: dict[str, Any],
    analyzed_result: dict[str, Any],
) -> dict[str, Any]:
    collector_config = input_data.get("collector", {}) if isinstance(input_data.get("collector"), dict) else {}
    title_defaults = {
        "selected_keywords": _get_list(selected_result, "selected_keywords"),
        "keyword_clusters": _get_list(selected_result, "keyword_clusters"),
        "longtail_suggestions": _get_list(selected_result, "longtail_suggestions"),
        "longtail_options": (
            selected_result.get("longtail_options", {})
            if isinstance(selected_result, dict)
            else input_data.get("longtail_options", {})
        ),
        "analyzed_keywords": _get_list(analyzed_result, "analyzed_keywords"),
        "title_options": input_data.get("title_options", {}),
        "mode": input_data.get("mode", collector_config.get("mode", "")),
        "category": input_data.get("category", collector_config.get("category", "")),
        "seed_input": input_data.get("seed_input", collector_config.get("seed_input", "")),
        "collector": collector_config,
        "title_export": _build_title_export_input(input_data),
    }
    return _merge_stage_config(title_defaults, input_data.get("title"))


def _build_analyzer_input(
    input_data: dict[str, Any],
    expanded_result: dict[str, Any],
    collected_result: dict[str, Any],
) -> dict[str, Any]:
    expanded_keywords = _get_list(expanded_result, "expanded_keywords")
    if not expanded_keywords:
        expanded_keywords = _get_list(collected_result, "collected_keywords")

    analyzer_defaults = {
        "expanded_keywords": expanded_keywords,
        "keyword_stats_path": input_data.get("keyword_stats_path", ""),
        "keyword_stats_text": input_data.get("keyword_stats_text", ""),
        "keyword_stats_items": input_data.get("keyword_stats_items", []),
        "searchad": input_data.get("searchad", {}),
        "naver_ads_api_key": input_data.get("naver_ads_api_key", ""),
        "naver_ads_customer_id": input_data.get("naver_ads_customer_id", ""),
        "naver_ads_access_license": input_data.get("naver_ads_access_license", ""),
        "naver_ads_secret_key": input_data.get("naver_ads_secret_key", ""),
        "naver_search_api": input_data.get("naver_search_api", {}),
        "naver_search_client_id": input_data.get("naver_search_client_id", ""),
        "naver_search_client_secret": input_data.get("naver_search_client_secret", ""),
    }
    return _merge_stage_config(analyzer_defaults, input_data.get("analyzer"))


def _build_title_export_input(input_data: dict[str, Any]) -> dict[str, Any]:
    raw_export = input_data.get("title_export") if isinstance(input_data.get("title_export"), dict) else {}
    enabled = _coerce_boolish(raw_export.get("enabled"), default=True)
    return {
        **raw_export,
        "enabled": enabled,
    }


def _coerce_boolish(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _merge_stage_config(defaults: dict[str, Any], overrides: Any) -> dict[str, Any]:
    merged = dict(defaults)
    if not isinstance(overrides, dict):
        return merged

    for key, value in overrides.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def _get_list(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    items = payload.get(key)
    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def _start_pipeline_debug() -> dict[str, Any]:
    return {
        "stage": "pipeline",
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "perf_started_at": time.perf_counter(),
        "stages": {},
    }


def _run_stage(
    pipeline_debug: dict[str, Any] | None,
    *,
    stage_name: str,
    runner: Any,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    result = runner()

    if pipeline_debug is not None:
        payload = result if isinstance(result, dict) else {}
        pipeline_debug["stages"][stage_name] = {
            "duration_ms": _elapsed_ms(started_at),
            "result_keys": sorted(payload.keys()),
            "debug": payload.get("debug"),
        }

    return result if isinstance(result, dict) else {}


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
