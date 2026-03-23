from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.expander.utils.tokenizer import normalize_text
from app.title.ai_client import TitleGenerationOptions, TitleProviderError, request_ai_titles
from app.title.category_detector import detect_category
from app.title.quality import TITLE_QUALITY_PASS_SCORE, enrich_title_results
from app.title.rules import NAVER_HOME_MAX_LENGTH
from app.title.templates import build_blog_titles, build_naver_home_titles
from app.title.types import TitleOutputItem

_MODEL_ESCALATION_TRIGGER_FAILURES = 2
_MODEL_ESCALATION_MAP: dict[str, dict[str, str]] = {
    "openai": {
        "gpt-4o-mini": "gpt-4.1-mini",
    },
    "gemini": {
        "gemini-2.5-flash-lite": "gemini-2.5-flash",
        "gemini-2.5-flash": "gemini-2.5-pro",
    },
    "vertex": {
        "gemini-2.5-flash-lite": "gemini-2.5-flash",
        "gemini-2.5-flash": "gemini-2.5-pro",
    },
    "anthropic": {
        "claude-haiku-4-5": "claude-sonnet-4-6",
    },
}


def generate_titles(
    items: list[dict[str, Any]],
    options: TitleGenerationOptions | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any]]:
    normalized_items = _normalize_input_items(items)
    input_items_by_keyword = {
        normalize_text(item.get("keyword")): item
        for item in normalized_items
        if normalize_text(item.get("keyword"))
    }
    if options is None or options.mode != "ai":
        return _finalize_generated_results(
            _build_template_results(normalized_items),
            _build_meta(
                requested_mode=options.mode if options else "template",
                used_mode="template",
                provider=options.provider if options else None,
                model=options.model if options else None,
                temperature=options.temperature if options else None,
                preset_key=options.preset_key if options else "",
                preset_label=options.preset_label if options else "",
                auto_retry_enabled=options.auto_retry_enabled if options else False,
                quality_retry_threshold=options.quality_retry_threshold if options else TITLE_QUALITY_PASS_SCORE,
                issue_context_enabled=options.issue_context_enabled if options else False,
                issue_context_limit=options.issue_context_limit if options else 0,
                issue_source_mode=options.issue_source_mode if options else "",
                community_sources=list(options.community_sources) if options else [],
            ),
        )

    if not options.api_key:
        if not options.fallback_to_template:
            raise TitleProviderError("AI mode requires an API key.")
        return _finalize_generated_results(
            _build_template_results(normalized_items),
            _build_meta(
                requested_mode="ai",
                used_mode="template_fallback",
                provider=options.provider,
                model=options.model,
                temperature=options.temperature,
                preset_key=options.preset_key,
                preset_label=options.preset_label,
                fallback_reason="missing_api_key",
                auto_retry_enabled=options.auto_retry_enabled,
                quality_retry_threshold=options.quality_retry_threshold,
                issue_context_enabled=options.issue_context_enabled,
                issue_context_limit=options.issue_context_limit,
                issue_source_mode=options.issue_source_mode,
                community_sources=list(options.community_sources),
            ),
        )

    ai_results: dict[str, TitleOutputItem] = {}
    fallback_keywords: list[str] = []

    try:
        for chunk in _chunk_keywords(normalized_items, options.batch_size):
            response_items = request_ai_titles(
                chunk,
                options=options,
            )
            for item in response_items:
                keyword = normalize_text(item.get("keyword"))
                titles = item.get("titles") if isinstance(item, dict) else None
                if not keyword or not _is_valid_title_bundle(titles):
                    continue
                source_item = input_items_by_keyword.get(keyword, {"keyword": keyword})
                ai_results[keyword] = {
                    **_strip_generated_fields(source_item),
                    "keyword": keyword,
                    "titles": {
                        "naver_home": list(titles["naver_home"]),
                        "blog": list(titles["blog"]),
                    },
                }
    except TitleProviderError as exc:
        if not options.fallback_to_template:
            raise
        return _finalize_generated_results(
            _build_template_results(normalized_items),
            _build_meta(
                requested_mode="ai",
                used_mode="template_fallback",
                provider=options.provider,
                model=options.model,
                temperature=options.temperature,
                preset_key=options.preset_key,
                preset_label=options.preset_label,
                fallback_reason=str(exc),
                auto_retry_enabled=options.auto_retry_enabled,
                quality_retry_threshold=options.quality_retry_threshold,
                issue_context_enabled=options.issue_context_enabled,
                issue_context_limit=options.issue_context_limit,
                issue_source_mode=options.issue_source_mode,
                community_sources=list(options.community_sources),
            ),
        )

    results: list[TitleOutputItem] = []
    for item in normalized_items:
        keyword = item["keyword"]
        ai_item = ai_results.get(keyword)
        if ai_item:
            results.append(ai_item)
            continue

        fallback_keywords.append(keyword)
        results.append(_build_template_title_item(keyword))

    used_mode = "ai"
    if fallback_keywords:
        used_mode = "ai_with_template_fallback"

    return _finalize_generated_results(
        results,
            _build_meta(
                requested_mode="ai",
                used_mode=used_mode,
                provider=options.provider,
                model=options.model,
                temperature=options.temperature,
                preset_key=options.preset_key,
                preset_label=options.preset_label,
                fallback_reason=", ".join(fallback_keywords[:10]) if fallback_keywords else "",
                fallback_keywords=fallback_keywords,
                auto_retry_enabled=options.auto_retry_enabled,
                quality_retry_threshold=options.quality_retry_threshold,
                issue_context_enabled=options.issue_context_enabled,
                issue_context_limit=options.issue_context_limit,
                issue_source_mode=options.issue_source_mode,
                community_sources=list(options.community_sources),
            ),
            options=options,
            allow_auto_retry=used_mode in {"ai", "ai_with_template_fallback"} and options.auto_retry_enabled,
        )


def _normalize_input_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized_items: list[dict[str, Any]] = []

    for item in items:
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue
        normalized_items.append(
            {
                **_strip_generated_fields(item),
                "keyword": keyword,
            }
        )

    return normalized_items


def _build_template_results(items: list[dict[str, Any]]) -> list[TitleOutputItem]:
    return [_build_template_title_item(item) for item in items]


def _build_template_title_item(item: dict[str, Any] | str) -> TitleOutputItem:
    if isinstance(item, dict):
        keyword = normalize_text(item.get("keyword"))
        source_item = _strip_generated_fields(item)
    else:
        keyword = normalize_text(item)
        source_item = {"keyword": keyword}
    category = detect_category(keyword)
    return {
        **source_item,
        "keyword": keyword,
        "titles": {
            "naver_home": build_naver_home_titles(keyword, category),
            "blog": build_blog_titles(keyword, category),
        },
    }


def _chunk_keywords(items: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _strip_generated_fields(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key not in {"titles", "quality_report"}
    }


def _is_valid_title_bundle(titles: Any) -> bool:
    if not isinstance(titles, dict):
        return False

    naver_home = titles.get("naver_home")
    blog = titles.get("blog")
    return (
        isinstance(naver_home, list)
        and isinstance(blog, list)
        and len(naver_home) >= 2
        and len(blog) >= 2
    )


def _finalize_generated_results(
    results: list[TitleOutputItem],
    meta: dict[str, Any],
    *,
    options: TitleGenerationOptions | None = None,
    allow_auto_retry: bool = False,
) -> tuple[list[TitleOutputItem], dict[str, Any]]:
    enriched_results, quality_summary = enrich_title_results(results)
    auto_retry_meta = _build_auto_retry_meta()
    model_escalation_meta = _build_model_escalation_meta(
        enabled=bool(options and _resolve_escalated_model(options.provider, options.model)),
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        source_model=options.model if options else "",
    )

    if allow_auto_retry and options is not None:
        enriched_results, quality_summary, auto_retry_meta, model_escalation_meta = _auto_retry_low_quality_results(
            results,
            enriched_results,
            options,
        )

    meta["quality_summary"] = quality_summary
    meta["auto_retry"] = auto_retry_meta
    meta["model_escalation"] = model_escalation_meta
    meta["final_model"] = (
        str(model_escalation_meta.get("target_model") or "").strip()
        if int(model_escalation_meta.get("accepted_count") or 0) > 0
        else meta.get("model")
    )
    return enriched_results, meta


def _auto_retry_low_quality_results(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    retry_threshold = _resolve_quality_retry_threshold(options.quality_retry_threshold)
    retry_keywords = [
        normalize_text(item.get("keyword"))
        for item in enriched_results
        if _should_retry_for_quality(item.get("quality_report", {}), retry_threshold)
    ]
    retry_keywords = [keyword for keyword in retry_keywords if keyword]
    escalation_options = _build_model_escalation_options(options, retry_threshold)
    base_escalation_meta = _build_model_escalation_meta(
        enabled=bool(escalation_options),
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        source_model=options.model,
        target_model=escalation_options.model if escalation_options else "",
    )
    if not retry_keywords:
        quality_summary = _build_quality_summary_from_items(enriched_results)
        return (
            enriched_results,
            quality_summary,
            _build_auto_retry_meta(retry_threshold=retry_threshold),
            base_escalation_meta,
        )

    retried_by_keyword: dict[str, TitleOutputItem] = {}
    retry_error_messages: list[str] = []
    original_items_by_keyword = {
        normalize_text(item.get("keyword")): item
        for item in original_results
        if normalize_text(item.get("keyword"))
    }
    retry_options = replace(
        options,
        batch_size=max(1, min(options.batch_size, 4)),
        system_prompt=_build_quality_retry_prompt(options.system_prompt, retry_threshold),
    )
    retry_input_items = [
        {
            **_strip_generated_fields(original_items_by_keyword.get(keyword, {"keyword": keyword})),
            "keyword": keyword,
        }
        for keyword in retry_keywords
    ]

    for chunk in _chunk_keywords(retry_input_items, retry_options.batch_size):
        try:
            response_items = request_ai_titles(
                chunk,
                options=retry_options,
            )
        except TitleProviderError as exc:
            retry_error_messages.append(str(exc))
            continue

        for item in response_items:
            keyword = normalize_text(item.get("keyword"))
            titles = item.get("titles") if isinstance(item, dict) else None
            if not keyword or not _is_valid_title_bundle(titles):
                continue
            source_item = original_items_by_keyword.get(keyword, {"keyword": keyword})
            retried_by_keyword[keyword] = {
                **_strip_generated_fields(source_item),
                "keyword": keyword,
                "titles": {
                    "naver_home": list(titles["naver_home"]),
                    "blog": list(titles["blog"]),
                },
            }

    retry_results, accepted_retry_keywords = _merge_retry_candidates(
        current_results=original_results,
        current_enriched_results=enriched_results,
        retry_candidates=retried_by_keyword,
    )
    retry_enriched_results, quality_summary = enrich_title_results(retry_results)
    auto_retry_meta = _build_auto_retry_meta(
        attempted_keywords=retry_keywords,
        accepted_keywords=accepted_retry_keywords,
        remaining_retry_count=int(quality_summary.get("retry_count", 0)),
        error_messages=retry_error_messages,
        retry_threshold=retry_threshold,
    )
    if not escalation_options:
        return retry_enriched_results, quality_summary, auto_retry_meta, base_escalation_meta

    escalation_keywords = [
        normalize_text(item.get("keyword"))
        for item in retry_enriched_results
        if _should_retry_for_quality(item.get("quality_report", {}), retry_threshold)
    ]
    escalation_keywords = [keyword for keyword in escalation_keywords if keyword]
    if not escalation_keywords:
        return retry_enriched_results, quality_summary, auto_retry_meta, base_escalation_meta

    escalated_candidates, escalation_error_messages = _request_retry_candidates(
        original_items_by_keyword,
        escalation_keywords,
        escalation_options,
    )
    final_results, accepted_escalation_keywords = _merge_retry_candidates(
        current_results=retry_results,
        current_enriched_results=retry_enriched_results,
        retry_candidates=escalated_candidates,
    )
    final_enriched_results, quality_summary = enrich_title_results(final_results)
    escalation_meta = _build_model_escalation_meta(
        enabled=True,
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        triggered=True,
        source_model=options.model,
        target_model=escalation_options.model,
        attempted_keywords=escalation_keywords,
        accepted_keywords=accepted_escalation_keywords,
        remaining_retry_count=int(quality_summary.get("retry_count", 0)),
        error_messages=escalation_error_messages,
    )
    return final_enriched_results, quality_summary, auto_retry_meta, escalation_meta


def _should_retry_for_quality(report: dict[str, Any], retry_threshold: int) -> bool:
    if not isinstance(report, dict):
        return False
    if bool(report.get("retry_recommended")):
        return True
    return int(report.get("bundle_score") or 0) < retry_threshold


def _should_accept_retry(current_report: dict[str, Any], retry_report: dict[str, Any]) -> bool:
    current_score = int(current_report.get("bundle_score") or 0)
    retry_score = int(retry_report.get("bundle_score") or 0)
    current_retry = bool(current_report.get("retry_recommended"))
    retry_pass = bool(retry_report.get("passes_threshold"))
    retry_retry = bool(retry_report.get("retry_recommended"))
    current_issue_count = int(current_report.get("issue_count") or 0)
    retry_issue_count = int(retry_report.get("issue_count") or 0)

    if retry_pass and not bool(current_report.get("passes_threshold")):
        return True
    if current_retry and not retry_retry:
        return True
    if retry_score >= current_score + 4:
        return True
    return retry_score >= current_score and retry_issue_count < current_issue_count


def _build_quality_retry_prompt(existing_prompt: str, retry_threshold: int) -> str:
    retry_guidance = (
        "Quality retry guidance:\n"
        "- Keep the exact keyword at the front of each title when natural.\n"
        "- Keep the home-feed pair issue-aware: usually make one title issue/update + comparison/debate and the other title issue/update + reversal/question.\n"
        "- Make the 2 naver_home titles clearly different from each other.\n"
        "- Make the 2 blog titles clearly different from each other.\n"
        f"- Keep every naver_home title within {NAVER_HOME_MAX_LENGTH} characters.\n"
        "- Avoid exaggerated words such as 무조건, 충격, 레전드, 미쳤다, 대박.\n"
        "- Do not invent unsupported dates, numbers, rankings, or official changes just to sound current.\n"
        "- Avoid stale filler such as 완벽 정리, 한 번에 정리, 갑자기 바뀌었다, 이유가 이상하다, 놓치면 손해.\n"
        f"- Aim for a bundle quality score of at least {retry_threshold}."
    )
    base_prompt = str(existing_prompt or "").strip()
    if not base_prompt:
        return retry_guidance
    return f"{base_prompt}\n\n{retry_guidance}"


def _build_model_escalation_prompt(existing_prompt: str, retry_threshold: int) -> str:
    escalation_guidance = (
        "Model escalation guidance:\n"
        "- This is the rescue pass after two failed quality attempts.\n"
        "- Prefer the safest clean structure over forced novelty.\n"
        "- If the issue angle is weak, choose a cleaner comparison, checklist, update, or decision-point frame.\n"
        "- Keep every title clearly distinct without drifting away from the keyword intent."
    )
    return f"{_build_quality_retry_prompt(existing_prompt, retry_threshold)}\n\n{escalation_guidance}"


def _build_quality_summary_from_items(items: list[TitleOutputItem]) -> dict[str, Any]:
    reports = [
        item.get("quality_report", {})
        for item in items
        if isinstance(item, dict) and isinstance(item.get("quality_report"), dict)
    ]
    if not reports:
        return {
            "total_count": 0,
            "good_count": 0,
            "review_count": 0,
            "retry_count": 0,
            "average_score": 0,
        }
    return {
        "total_count": len(reports),
        "good_count": sum(1 for report in reports if report.get("status") == "good"),
        "review_count": sum(1 for report in reports if report.get("status") == "review"),
        "retry_count": sum(1 for report in reports if report.get("status") == "retry"),
        "average_score": round(
            sum(int(report.get("bundle_score") or 0) for report in reports) / len(reports),
            1,
        ),
    }


def _build_auto_retry_meta(
    *,
    attempted_keywords: list[str] | None = None,
    accepted_keywords: list[str] | None = None,
    remaining_retry_count: int = 0,
    error_messages: list[str] | None = None,
    retry_threshold: int = TITLE_QUALITY_PASS_SCORE,
) -> dict[str, Any]:
    attempted_keywords = attempted_keywords or []
    accepted_keywords = accepted_keywords or []
    error_messages = error_messages or []
    return {
        "attempted_count": len(attempted_keywords),
        "attempted_keywords": attempted_keywords,
        "accepted_count": len(accepted_keywords),
        "accepted_keywords": accepted_keywords,
        "remaining_retry_count": remaining_retry_count,
        "error_messages": error_messages[:3],
        "retry_threshold": retry_threshold,
    }


def _build_model_escalation_meta(
    *,
    enabled: bool,
    trigger_failure_count: int,
    triggered: bool = False,
    source_model: str = "",
    target_model: str = "",
    attempted_keywords: list[str] | None = None,
    accepted_keywords: list[str] | None = None,
    remaining_retry_count: int = 0,
    error_messages: list[str] | None = None,
) -> dict[str, Any]:
    attempted_keywords = attempted_keywords or []
    accepted_keywords = accepted_keywords or []
    error_messages = error_messages or []
    return {
        "enabled": enabled,
        "trigger_failure_count": max(1, int(trigger_failure_count or _MODEL_ESCALATION_TRIGGER_FAILURES)),
        "triggered": triggered,
        "source_model": str(source_model or "").strip(),
        "target_model": str(target_model or "").strip(),
        "attempted_count": len(attempted_keywords),
        "attempted_keywords": attempted_keywords,
        "accepted_count": len(accepted_keywords),
        "accepted_keywords": accepted_keywords,
        "remaining_retry_count": remaining_retry_count,
        "error_messages": error_messages[:3],
    }


def _merge_retry_candidates(
    *,
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
    retry_candidates: dict[str, TitleOutputItem],
) -> tuple[list[TitleOutputItem], list[str]]:
    current_report_by_keyword = {
        normalize_text(item.get("keyword")): item.get("quality_report", {})
        for item in current_enriched_results
        if normalize_text(item.get("keyword"))
    }

    accepted_keywords: list[str] = []
    merged_results: list[TitleOutputItem] = []

    for item in current_results:
        keyword = normalize_text(item.get("keyword"))
        retry_item = retry_candidates.get(keyword)
        if not retry_item:
            merged_results.append(item)
            continue

        retried_enriched_items, _ = enrich_title_results([retry_item])
        retried_candidate = retried_enriched_items[0]
        current_report = current_report_by_keyword.get(keyword, {})
        retry_report = retried_candidate.get("quality_report", {})

        if _should_accept_retry(current_report, retry_report):
            accepted_keywords.append(keyword)
            merged_results.append(retry_item)
        else:
            merged_results.append(item)

    return merged_results, accepted_keywords


def _request_retry_candidates(
    original_items_by_keyword: dict[str, TitleOutputItem],
    retry_keywords: list[str],
    retry_options: TitleGenerationOptions,
) -> tuple[dict[str, TitleOutputItem], list[str]]:
    retried_by_keyword: dict[str, TitleOutputItem] = {}
    retry_error_messages: list[str] = []
    retry_input_items = [
        {
            **_strip_generated_fields(original_items_by_keyword.get(keyword, {"keyword": keyword})),
            "keyword": keyword,
        }
        for keyword in retry_keywords
    ]

    for chunk in _chunk_keywords(retry_input_items, retry_options.batch_size):
        try:
            response_items = request_ai_titles(
                chunk,
                options=retry_options,
            )
        except TitleProviderError as exc:
            retry_error_messages.append(str(exc))
            continue

        for item in response_items:
            keyword = normalize_text(item.get("keyword"))
            titles = item.get("titles") if isinstance(item, dict) else None
            if not keyword or not _is_valid_title_bundle(titles):
                continue
            source_item = original_items_by_keyword.get(keyword, {"keyword": keyword})
            retried_by_keyword[keyword] = {
                **_strip_generated_fields(source_item),
                "keyword": keyword,
                "titles": {
                    "naver_home": list(titles["naver_home"]),
                    "blog": list(titles["blog"]),
                },
            }

    return retried_by_keyword, retry_error_messages


def _build_model_escalation_options(
    options: TitleGenerationOptions,
    retry_threshold: int,
) -> TitleGenerationOptions | None:
    escalated_model = _resolve_escalated_model(options.provider, options.model)
    if not escalated_model:
        return None
    return replace(
        options,
        model=escalated_model,
        batch_size=max(1, min(options.batch_size, 4)),
        system_prompt=_build_model_escalation_prompt(options.system_prompt, retry_threshold),
    )


def _resolve_escalated_model(provider: str, model: str) -> str:
    normalized_provider = str(provider or "").strip().lower()
    normalized_model = normalize_text(model)
    provider_map = _MODEL_ESCALATION_MAP.get(normalized_provider, {})
    return str(provider_map.get(normalized_model, "")).strip()


def _resolve_quality_retry_threshold(value: int | float | None) -> int:
    try:
        number = int(value or TITLE_QUALITY_PASS_SCORE)
    except (TypeError, ValueError):
        return TITLE_QUALITY_PASS_SCORE
    return max(70, min(100, number))


def _build_meta(
    *,
    requested_mode: str,
    used_mode: str,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    preset_key: str = "",
    preset_label: str = "",
    fallback_reason: str = "",
    fallback_keywords: list[str] | None = None,
    auto_retry_enabled: bool = False,
    quality_retry_threshold: int = TITLE_QUALITY_PASS_SCORE,
    issue_context_enabled: bool = False,
    issue_context_limit: int = 0,
    issue_source_mode: str = "",
    community_sources: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requested_mode": requested_mode,
        "used_mode": used_mode,
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "preset_key": preset_key,
        "preset_label": preset_label,
        "fallback_reason": fallback_reason,
        "fallback_keywords": fallback_keywords or [],
        "auto_retry_enabled": auto_retry_enabled,
        "quality_retry_threshold": _resolve_quality_retry_threshold(quality_retry_threshold),
        "issue_context_enabled": issue_context_enabled,
        "issue_context_limit": max(0, int(issue_context_limit or 0)),
        "issue_source_mode": str(issue_source_mode or "").strip(),
        "community_sources": list(community_sources or []),
    }
