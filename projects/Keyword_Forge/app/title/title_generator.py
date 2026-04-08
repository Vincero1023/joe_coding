from __future__ import annotations

from dataclasses import replace
from threading import Event
from typing import Any, Callable

from app.expander.utils.tokenizer import normalize_key, normalize_text
from app.title.ai_client import (
    TitleGenerationOptions,
    TitleProviderError,
    _attach_live_issue_contexts,
    provider_requires_api_key,
    request_ai_slot_rewrites,
    request_ai_titles,
)
from app.title.category_detector import detect_category
from app.title.quality import _build_bundle_report, enrich_title_results, refresh_title_results_for_changed_slots
from app.title.quality_ai import TitleEvaluationOptions
from app.title.rules import NAVER_HOME_MAX_LENGTH, TITLE_QUALITY_REVIEW_SCORE
from app.title.types import (
    DEFAULT_TITLE_CHANNEL_COUNTS,
    MAX_TITLE_COUNT_PER_CHANNEL,
    TITLE_CHANNEL_ORDER,
    TITLE_CHANNEL_SLOT_LABELS,
    build_title_channel_counts,
    create_empty_generated_titles,
)
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
    "codex": {
        "gpt-5.4-mini": "gpt-5.4",
        "gpt-5.3-codex-spark": "gpt-5.3-codex",
    },
}
_PRACTICAL_RESCUE_KIND_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("preorder", ("사전예약", "예약방법", "예약일정", "신청방법", "오픈일정")),
    ("value", ("가성비", "가격대", "최저가", "예산")),
    ("setting", ("설정팁", "설정방법", "연결방법")),
    ("real_use", ("실사용차이",)),
    ("pros_cons", ("장단점",)),
    ("problem", ("자주생기는문제", "연결문제", "문제")),
)
_PRODUCT_CATEGORY_KEYS = {"product"}
_PRODUCT_RESCUE_KEY_PATTERNS = (
    "마우스",
    "키보드",
    "노트북",
    "맥북",
    "아이패드",
    "아이폰",
    "갤럭시",
    "이어폰",
    "헤드셋",
    "모니터",
    "태블릿",
    "스피커",
    "웹캠",
    "프린터",
    "카메라",
    "공유기",
    "와이파이",
    "블루투스",
    "유니파잉",
    "dpi",
    "버튼",
)
_MOUSE_SETTING_KEY_PATTERNS = ("마우스", "트랙볼", "버티컬", "유니파잉", "dpi", "클릭")
_KEYBOARD_SETTING_KEY_PATTERNS = ("키보드", "키패드", "한영", "배열", "키맵", "fn", "멀티페어링")
_INITIAL_GENERATION_PROGRESS_CAP = 70
_QUALITY_PROGRESS_PERCENT = 78
_AUTO_RETRY_PROGRESS_START = 80
_AUTO_RETRY_PROGRESS_END = 90
_MODEL_ESCALATION_PROGRESS_START = 92
_MODEL_ESCALATION_PROGRESS_END = 96
_FINALIZING_PROGRESS_PERCENT = 97
_MAX_RETRY_KEYWORDS_PER_PASS = 5
_MAX_SLOT_REWRITE_ATTEMPTS = 2
_SAME_KEYWORD_PEER_TITLE_LIMIT = 3
_CROSS_KEYWORD_PEER_TITLE_LIMIT = 4
_DEFAULT_PEER_TITLE_BATCH_WINDOW = 20
_RETRY_LIMIT_DOWNGRADE_ISSUE = "재작성 2회 후에도 기준 미달이라 수동 검토로 전환했습니다."
_DEFAULT_HOME_AI_EVALUATION_SAMPLE_RATIO = 0.15
_DEFAULT_HOME_AI_EVALUATION_MAX_ITEMS = 2
_DEFAULT_QUALITY_RETRY_THRESHOLD = TITLE_QUALITY_REVIEW_SCORE
_STRICT_RETRY_SCORE_CUTOFF = 70
_HOME_RETRY_KEEP_SCORE_CUTOFF = 75
_HOME_SHORT_TITLE_MAX_LENGTH = 20
_HOME_CORE_ISSUE_MIN_SCORE = 10
_HOME_CORE_CURIOSITY_MIN_SCORE = 12
_HOME_CORE_CONTRAST_MIN_SCORE = 10
_HOME_EMOTIONAL_HOOK_MIN_SCORE = 10

TitleProgressCallback = Callable[[dict[str, Any]], None]


def generate_titles(
    items: list[dict[str, Any]],
    options: TitleGenerationOptions | None = None,
    *,
    progress_callback: TitleProgressCallback | None = None,
    stop_event: Event | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any]]:
    normalized_items = _normalize_input_items(items)
    total_count = len(normalized_items)
    _publish_title_progress(
        progress_callback,
        type="started",
        phase="generate",
        processed_count=0,
        total_count=total_count,
        progress_percent=0,
        message="제목 생성 준비 중",
    )
    if options is None:
        raise TitleProviderError("Title generation now requires AI title_options.")

    if provider_requires_api_key(options.provider) and not options.api_key:
        raise TitleProviderError("AI mode requires an API key.")

    if options.issue_context_enabled:
        normalized_items = _attach_live_issue_contexts(normalized_items, options)
        request_options = replace(
            options,
            issue_context_enabled=False,
            issue_context_limit=0,
        )
    else:
        request_options = options

    generation_batch_size = _resolve_generation_batch_size(options)
    total_chunk_count = (
        (len(normalized_items) + generation_batch_size - 1) // generation_batch_size
        if normalized_items
        else 0
    )
    ai_results: dict[int, TitleOutputItem] = {}
    processed_count = 0

    for chunk_index, chunk_start in enumerate(range(0, len(normalized_items), generation_batch_size), start=1):
        chunk = normalized_items[chunk_start:chunk_start + generation_batch_size]
        if stop_event is not None and stop_event.is_set():
            break
        _publish_title_progress(
            progress_callback,
            type="phase",
            phase="generate",
            processed_count=processed_count,
            total_count=total_count,
            progress_percent=max(
                1 if total_count > 0 else 0,
                _compute_weighted_progress(
                    processed_count,
                    total_count,
                    cap=_INITIAL_GENERATION_PROGRESS_CAP,
                ),
            ),
            message=f"{chunk_index} / {total_chunk_count} 묶음 생성 중 ({len(chunk)}세트)",
        )
        response_items = _request_ai_titles_with_chunk_retry(
            chunk,
            options=request_options,
        )
        aligned_response_items = _align_response_items_to_chunk(chunk, response_items)
        chunk_generated_items: list[TitleOutputItem] = []
        for local_index, source_item in enumerate(chunk):
            keyword = normalize_text(source_item.get("keyword"))
            response_item = aligned_response_items[local_index] if local_index < len(aligned_response_items) else {}
            titles = response_item.get("titles") if isinstance(response_item, dict) else None
            if keyword and _is_valid_title_bundle(titles, options=options):
                generated_item: TitleOutputItem = {
                    **_strip_generated_fields(source_item),
                    "keyword": keyword,
                    "titles": _normalize_generated_title_bundle(titles, options=options),
                }
                ai_results[chunk_start + local_index] = generated_item
                chunk_generated_items.append(_clone_title_output_item(generated_item))
            processed_count += 1
            _publish_title_progress(
                progress_callback,
                type="keyword_completed",
                phase="generate",
                processed_count=processed_count,
                total_count=total_count,
                current_keyword=keyword,
                progress_percent=_compute_weighted_progress(
                    processed_count,
                    total_count,
                    cap=_INITIAL_GENERATION_PROGRESS_CAP,
                ),
                message=f"{processed_count} / {total_count}세트 생성",
            )
        if chunk_generated_items:
            _publish_title_progress(
                progress_callback,
                type="partial_result",
                phase="generate",
                processed_count=processed_count,
                total_count=total_count,
                progress_percent=_compute_weighted_progress(
                    processed_count,
                    total_count,
                    cap=_INITIAL_GENERATION_PROGRESS_CAP,
                ),
                generated_count=len(ai_results),
                batch_index=chunk_index,
                batch_count=total_chunk_count,
                generated_titles=chunk_generated_items,
                message=f"{processed_count} / {total_count}세트 초안 표시",
            )

    results: list[TitleOutputItem] = []
    missing_keywords: list[str] = []
    for index, item in enumerate(normalized_items):
        keyword = item["keyword"]
        ai_item = ai_results.get(index)
        if ai_item:
            results.append(ai_item)
            continue
        missing_keywords.append(keyword)

    if missing_keywords:
        raise TitleProviderError(
            "AI title generation returned incomplete results for: "
            + ", ".join(missing_keywords[:10])
        )

    return _finalize_generated_results(
        results,
        _build_meta(
            requested_mode="ai",
            used_mode="ai",
            provider=options.provider,
            model=options.model,
            rewrite_provider=options.rewrite_provider,
            rewrite_model=options.rewrite_model,
            temperature=options.temperature,
            preset_key=options.preset_key,
            preset_label=options.preset_label,
            auto_retry_enabled=options.auto_retry_enabled,
            quality_retry_threshold=options.quality_retry_threshold,
            issue_context_enabled=options.issue_context_enabled,
            issue_context_limit=options.issue_context_limit,
            issue_source_mode=options.issue_source_mode,
            community_sources=list(options.community_sources),
        ),
        options=options,
        allow_auto_retry=options.auto_retry_enabled,
        progress_callback=progress_callback,
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


def _resolve_title_channel_counts(options: TitleGenerationOptions | None = None) -> dict[str, int]:
    if options is None:
        return {
            channel_name: DEFAULT_TITLE_CHANNEL_COUNTS[channel_name]
            for channel_name in TITLE_CHANNEL_ORDER
        }
    return build_title_channel_counts(
        raw_counts=options.channel_counts,
        enabled_channels=tuple(options.surface_modes),
    )


def _build_empty_title_bundle() -> dict[str, list[str]]:
    return {
        channel_name: list(create_empty_generated_titles().get(channel_name, []))
        for channel_name in TITLE_CHANNEL_ORDER
    }


def _normalize_generated_title_bundle(
    raw_titles: Any,
    *,
    options: TitleGenerationOptions | None = None,
) -> dict[str, list[str]]:
    counts = _resolve_title_channel_counts(options)
    titles = raw_titles if isinstance(raw_titles, dict) else {}
    normalized_bundle = _build_empty_title_bundle()
    for channel_name in TITLE_CHANNEL_ORDER:
        channel_titles = titles.get(channel_name)
        if not isinstance(channel_titles, list):
            normalized_bundle[channel_name] = []
            continue
        filtered_titles = [
            normalize_text(title)
            for title in channel_titles
            if normalize_text(title)
        ]
        normalized_bundle[channel_name] = filtered_titles[:counts[channel_name]]
    return normalized_bundle


def _chunk_keywords(items: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _resolve_generation_batch_size(options: TitleGenerationOptions) -> int:
    configured_batch_size = max(1, min(int(options.batch_size or 20), 20))
    if normalize_text(options.provider).lower() != "codex":
        return configured_batch_size

    reasoning_effort = normalize_text(options.reasoning_effort).lower()
    max_batch_size = 4
    if reasoning_effort == "xhigh":
        max_batch_size = 2
    elif reasoning_effort == "high":
        max_batch_size = 3

    if options.issue_context_enabled:
        max_batch_size = min(max_batch_size, 3 if reasoning_effort != "xhigh" else 2)

    return max(1, min(configured_batch_size, max_batch_size))


def _request_ai_titles_with_chunk_retry(
    chunk: list[dict[str, Any]],
    *,
    options: TitleGenerationOptions,
) -> list[dict[str, Any]]:
    try:
        return request_ai_titles(
            chunk,
            options=options,
        )
    except TitleProviderError as exc:
        if len(chunk) <= 1 or not _is_chunk_retryable_title_error(exc):
            raise

        midpoint = len(chunk) // 2
        if midpoint <= 0 or midpoint >= len(chunk):
            raise

        return [
            *_request_ai_titles_with_chunk_retry(chunk[:midpoint], options=options),
            *_request_ai_titles_with_chunk_retry(chunk[midpoint:], options=options),
        ]


def _is_chunk_retryable_title_error(exc: TitleProviderError) -> bool:
    message = normalize_text(str(exc)).lower()
    if not message:
        return False
    return any(
        token in message
        for token in (
            "invalid json",
            "did not contain json",
            "empty json content",
            "empty content",
        )
    )


def _align_response_items_to_chunk(
    source_items: list[dict[str, Any]],
    response_items: list[dict[str, Any]] | Any,
) -> list[dict[str, Any]]:
    normalized_response_items = [
        item
        for item in (response_items if isinstance(response_items, list) else [])
        if isinstance(item, dict)
    ]
    if not source_items:
        return []
    if len(normalized_response_items) == len(source_items):
        return normalized_response_items

    remaining = list(normalized_response_items)
    aligned_items: list[dict[str, Any]] = []
    for source_item in source_items:
        source_keyword = normalize_text(source_item.get("keyword"))
        matched_index = next(
            (
                index
                for index, candidate in enumerate(remaining)
                if normalize_text(candidate.get("keyword")) == source_keyword
            ),
            -1,
        )
        if matched_index >= 0:
            aligned_items.append(remaining.pop(matched_index))
        elif remaining:
            aligned_items.append(remaining.pop(0))
        else:
            aligned_items.append({})
    return aligned_items


def _strip_generated_fields(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key not in {"titles", "quality_report"}
    }


def _strip_internal_quality_fields(items: list[TitleOutputItem]) -> list[TitleOutputItem]:
    cleaned_items: list[TitleOutputItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        quality_report = item.get("quality_report") if isinstance(item.get("quality_report"), dict) else {}
        cleaned_quality_report = {
            key: value
            for key, value in quality_report.items()
            if not str(key or "").startswith("_")
        }
        cleaned_items.append(
            {
                **item,
                "quality_report": cleaned_quality_report,
            }
        )
    return cleaned_items


def _is_valid_title_bundle(
    titles: Any,
    *,
    options: TitleGenerationOptions | None = None,
) -> bool:
    if not isinstance(titles, dict):
        return False

    counts = _resolve_title_channel_counts(options)
    for channel_name in TITLE_CHANNEL_ORDER:
        channel_titles = titles.get(channel_name)
        required_count = int(counts.get(channel_name, 0) or 0)
        if required_count <= 0:
            if channel_titles is not None and not isinstance(channel_titles, list):
                return False
            continue
        if not isinstance(channel_titles, list):
            return False
        if len(channel_titles) < required_count:
            return False
    return True


def _finalize_generated_results(
    results: list[TitleOutputItem],
    meta: dict[str, Any],
    *,
    options: TitleGenerationOptions | None = None,
    allow_auto_retry: bool = False,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any]]:
    evaluation_options = _build_title_evaluation_options(options)
    _publish_title_progress(
        progress_callback,
        type="phase",
        phase="quality",
        progress_percent=_QUALITY_PROGRESS_PERCENT,
        message="품질 검사 중",
    )
    enriched_results, quality_summary = enrich_title_results(
        results,
        evaluation_options=evaluation_options,
    )
    retry_provider = normalize_text(options.rewrite_provider) if options else ""
    retry_model = normalize_text(options.rewrite_model) if options else ""
    effective_retry_provider = retry_provider or (options.provider if options else "")
    effective_retry_model = retry_model or (options.model if options else "")
    resolved_retry_threshold = _resolve_quality_retry_threshold(
        options.quality_retry_threshold if options is not None else _DEFAULT_QUALITY_RETRY_THRESHOLD
    )
    auto_retry_meta = _build_auto_retry_meta(
        retry_threshold=resolved_retry_threshold,
        provider=effective_retry_provider,
        model=effective_retry_model,
    )
    model_escalation_meta = _build_model_escalation_meta(
        enabled=bool(options and _resolve_escalated_model(effective_retry_provider, effective_retry_model)),
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        source_provider=effective_retry_provider,
        source_model=effective_retry_model,
    )

    if allow_auto_retry and options is not None:
        enriched_results, quality_summary, auto_retry_meta, model_escalation_meta = _auto_retry_low_quality_results(
            results,
            enriched_results,
            options,
            evaluation_options=evaluation_options,
            progress_callback=progress_callback,
        )

    meta["quality_summary"] = quality_summary
    meta["quality_evaluation_provider"] = evaluation_options.provider if evaluation_options.enabled else ""
    meta["quality_evaluation_model"] = evaluation_options.model if evaluation_options.enabled else ""
    meta["quality_prompt_profile_id"] = options.quality_prompt_profile_id if options else ""
    meta["auto_retry"] = auto_retry_meta
    meta["model_escalation"] = model_escalation_meta
    meta["final_model"] = (
        str(model_escalation_meta.get("target_model") or "").strip()
        if int(model_escalation_meta.get("accepted_count") or 0) > 0
        else meta.get("model")
    )
    _publish_title_progress(
        progress_callback,
        type="phase",
        phase="finalizing",
        progress_percent=_FINALIZING_PROGRESS_PERCENT,
        message="제목 결과 정리 중",
    )
    return _strip_internal_quality_fields(enriched_results), meta


def _auto_retry_low_quality_results(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _run_partial_slot_retry_pipeline(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _auto_retry_low_quality_results_with_slots(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _run_slot_auto_retry_flow(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _run_slot_auto_retry_flow(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _execute_slot_auto_retry_flow(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _execute_slot_auto_retry_flow(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _execute_slot_auto_retry_flow_impl(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _execute_slot_auto_retry_flow_impl(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _slot_auto_retry_flow_core(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _slot_auto_retry_flow_core(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _slot_auto_retry_flow_actual(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _slot_auto_retry_flow_actual(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _slot_auto_retry_flow_final(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _slot_auto_retry_flow_final(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _slot_auto_retry_flow_final_impl(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _slot_auto_retry_flow_final_impl(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _slot_auto_retry_flow_live(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _slot_auto_retry_flow_live(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _slot_auto_retry_flow_impl_v2(
        original_results,
        enriched_results,
        options,
        evaluation_options=evaluation_options,
        progress_callback=progress_callback,
    )


def _slot_auto_retry_flow_impl_v2(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    retry_threshold = _resolve_quality_retry_threshold(options.quality_retry_threshold)
    retry_options = _build_retry_request_options(options, retry_threshold)
    retry_candidate_count = _count_retry_candidates(enriched_results, retry_threshold)
    retry_keywords = _select_retry_keywords_for_pass(
        enriched_results,
        retry_threshold,
        limit=_MAX_RETRY_KEYWORDS_PER_PASS,
    )
    escalation_options = _build_model_escalation_options(
        retry_options,
        retry_threshold,
        prompt_source=options.system_prompt,
    )
    base_escalation_meta = _build_model_escalation_meta(
        enabled=bool(escalation_options),
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        source_provider=retry_options.provider,
        source_model=retry_options.model,
        target_provider=escalation_options.provider if escalation_options else "",
        target_model=escalation_options.model if escalation_options else "",
    )
    if not retry_keywords:
        _publish_title_progress(
            progress_callback,
            type="phase",
            phase="quality_ready",
            progress_percent=_QUALITY_PROGRESS_PERCENT + 2,
            message="품질 검사 완료",
        )
        quality_summary = _build_quality_summary_from_items(enriched_results)
        return (
            enriched_results,
            quality_summary,
            _build_auto_retry_meta(
                retry_threshold=retry_threshold,
                provider=retry_options.provider,
                model=retry_options.model,
            ),
            base_escalation_meta,
        )

    retried_by_keyword: dict[str, TitleOutputItem] = {}
    retry_error_messages: list[str] = []
    original_items_by_keyword = {
        normalize_text(item.get("keyword")): item
        for item in original_results
        if normalize_text(item.get("keyword"))
    }
    retry_input_items = [
        {
            **_strip_generated_fields(original_items_by_keyword.get(keyword, {"keyword": keyword})),
            "keyword": keyword,
        }
        for keyword in retry_keywords
    ]
    _publish_title_progress(
        progress_callback,
        type="phase",
        phase="auto_retry",
        processed_count=0,
        total_count=len(retry_keywords),
        progress_percent=_AUTO_RETRY_PROGRESS_START,
        message=_build_retry_progress_message(
            "기준 미달 제목 재작성 준비",
            selected_count=len(retry_keywords),
            total_candidates=retry_candidate_count,
        ),
    )
    retried_count = 0

    for chunk in _chunk_keywords(retry_input_items, retry_options.batch_size):
        try:
            response_items = _request_ai_titles_with_chunk_retry(
                chunk,
                options=retry_options,
            )
        except TitleProviderError as exc:
            retry_error_messages.append(str(exc))
            continue

        aligned_response_items = _align_response_items_to_chunk(chunk, response_items)
        for item in aligned_response_items:
            keyword = normalize_text(item.get("keyword"))
            titles = item.get("titles") if isinstance(item, dict) else None
            if not keyword or not _is_valid_title_bundle(titles, options=retry_options):
                continue
            source_item = original_items_by_keyword.get(keyword, {"keyword": keyword})
            retried_by_keyword[keyword] = {
                **_strip_generated_fields(source_item),
                "keyword": keyword,
                "titles": _normalize_generated_title_bundle(titles, options=retry_options),
            }
        retried_count = min(len(retry_keywords), retried_count + len(chunk))
        _publish_title_progress(
            progress_callback,
            type="phase",
            phase="auto_retry",
            processed_count=retried_count,
            total_count=len(retry_keywords),
            progress_percent=_compute_phase_progress(
                retried_count,
                len(retry_keywords),
                start=_AUTO_RETRY_PROGRESS_START,
                end=_AUTO_RETRY_PROGRESS_END,
            ),
            message=_build_retry_progress_message(
                "기준 미달 제목 재작성 중",
                selected_count=retried_count,
                total_candidates=retry_candidate_count,
                include_ratio=True,
            ),
        )

    retry_results, accepted_retry_keywords = _merge_retry_candidates(
        current_results=original_results,
        current_enriched_results=enriched_results,
        retry_candidates=retried_by_keyword,
        evaluation_options=evaluation_options,
    )
    retry_enriched_results, quality_summary = enrich_title_results(
        retry_results,
        evaluation_options=evaluation_options,
    )
    retry_results, retry_enriched_results, quality_summary, accepted_rescue_keywords = _apply_practical_rescue_candidates(
        current_results=retry_results,
        current_enriched_results=retry_enriched_results,
        original_items_by_keyword=original_items_by_keyword,
        retry_threshold=retry_threshold,
        evaluation_options=evaluation_options,
    )
    auto_retry_meta = _build_auto_retry_meta(
        attempted_keywords=retry_keywords,
        accepted_keywords=accepted_retry_keywords + accepted_rescue_keywords,
        remaining_retry_count=int(quality_summary.get("retry_count", 0)),
        error_messages=retry_error_messages,
        retry_threshold=retry_threshold,
        provider=retry_options.provider,
        model=retry_options.model,
    )
    if not escalation_options:
        return retry_enriched_results, quality_summary, auto_retry_meta, base_escalation_meta

    escalation_candidate_count = _count_retry_candidates(retry_enriched_results, retry_threshold)
    escalation_keywords = _select_retry_keywords_for_pass(
        retry_enriched_results,
        retry_threshold,
        limit=_MAX_RETRY_KEYWORDS_PER_PASS,
    )
    if not escalation_keywords:
        return retry_enriched_results, quality_summary, auto_retry_meta, base_escalation_meta
    _publish_title_progress(
        progress_callback,
        type="phase",
        phase="model_escalation",
        processed_count=0,
        total_count=len(escalation_keywords),
        progress_percent=_MODEL_ESCALATION_PROGRESS_START,
        message=_build_retry_progress_message(
            "상위 모델 재시도 준비",
            selected_count=len(escalation_keywords),
            total_candidates=escalation_candidate_count,
        ),
    )

    escalated_candidates, escalation_error_messages = _request_retry_candidates(
        original_items_by_keyword,
        escalation_keywords,
        escalation_options,
        progress_callback=progress_callback,
    )
    final_results, accepted_escalation_keywords = _merge_retry_candidates(
        current_results=retry_results,
        current_enriched_results=retry_enriched_results,
        retry_candidates=escalated_candidates,
        evaluation_options=evaluation_options,
    )
    final_enriched_results, quality_summary = enrich_title_results(
        final_results,
        evaluation_options=evaluation_options,
    )
    escalation_meta = _build_model_escalation_meta(
        enabled=True,
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        triggered=True,
        source_provider=retry_options.provider,
        source_model=retry_options.model,
        target_provider=escalation_options.provider,
        target_model=escalation_options.model,
        attempted_keywords=escalation_keywords,
        accepted_keywords=accepted_escalation_keywords,
        remaining_retry_count=int(quality_summary.get("retry_count", 0)),
        error_messages=escalation_error_messages,
    )
    return final_enriched_results, quality_summary, auto_retry_meta, escalation_meta

def _run_partial_slot_retry_pipeline(
    original_results: list[TitleOutputItem],
    enriched_results: list[TitleOutputItem],
    options: TitleGenerationOptions,
    *,
    evaluation_options: TitleEvaluationOptions | None = None,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any], dict[str, Any], dict[str, Any]]:
    retry_threshold = _resolve_quality_retry_threshold(options.quality_retry_threshold)
    retry_options = _build_retry_request_options(options, retry_threshold)
    slot_retry_attempt_counts: dict[str, int] = {}
    retry_slot_candidates = _collect_retry_slot_candidates(
        original_results,
        enriched_results,
        retry_threshold,
        recent_batch_size=options.batch_size,
    )
    retry_slot_candidates, _ = _filter_slot_candidates_by_retry_attempts(
        retry_slot_candidates,
        slot_retry_attempt_counts,
        max_attempts=_MAX_SLOT_REWRITE_ATTEMPTS,
    )
    escalation_options = _build_model_escalation_options(
        retry_options,
        retry_threshold,
        prompt_source=options.system_prompt,
    )
    base_escalation_meta = _build_model_escalation_meta(
        enabled=bool(escalation_options),
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        source_provider=retry_options.provider,
        source_model=retry_options.model,
        target_provider=escalation_options.provider if escalation_options else "",
        target_model=escalation_options.model if escalation_options else "",
    )
    if not retry_slot_candidates:
        _publish_title_progress(
            progress_callback,
            type="phase",
            phase="quality_ready",
            progress_percent=_QUALITY_PROGRESS_PERCENT + 2,
            message="품질 검사 완료",
        )
        quality_summary = _build_quality_summary_from_items(enriched_results)
        return (
            enriched_results,
            quality_summary,
            _build_auto_retry_meta(
                retry_threshold=retry_threshold,
                provider=retry_options.provider,
                model=retry_options.model,
            ),
            base_escalation_meta,
        )

    original_items_by_keyword = {
        normalize_text(item.get("keyword")): item
        for item in original_results
        if normalize_text(item.get("keyword"))
    }
    _publish_title_progress(
        progress_callback,
        type="phase",
        phase="auto_retry",
        processed_count=0,
        total_count=len(retry_slot_candidates),
        progress_percent=_AUTO_RETRY_PROGRESS_START,
        message=_build_retry_progress_message(
            "문제 slot 재작성 준비 중",
            selected_count=len(retry_slot_candidates),
            total_candidates=len(retry_slot_candidates),
        ),
    )
    retried_titles_by_slot_id, retry_error_messages, retry_batch_sizes = _request_slot_retry_candidates(
        retry_slot_candidates,
        retry_options,
        phase="auto_retry",
        progress_callback=progress_callback,
        total_candidates=len(retry_slot_candidates),
    )
    retry_results, retry_enriched_results, accepted_retry_slot_ids = _merge_slot_retry_candidates(
        current_results=original_results,
        current_enriched_results=enriched_results,
        slot_candidates=retry_slot_candidates,
        rewritten_titles_by_slot_id=retried_titles_by_slot_id,
        evaluation_options=evaluation_options,
    )
    quality_summary = _build_quality_summary_from_items(retry_enriched_results)
    _record_failed_slot_retry_attempts(
        slot_retry_attempt_counts,
        retry_slot_candidates,
        accepted_retry_slot_ids,
    )
    retry_results, retry_enriched_results, quality_summary, accepted_rescue_keywords = _apply_practical_rescue_candidates(
        current_results=retry_results,
        current_enriched_results=retry_enriched_results,
        original_items_by_keyword=original_items_by_keyword,
        retry_threshold=retry_threshold,
        evaluation_options=evaluation_options,
        retry_attempt_counts=slot_retry_attempt_counts,
        recent_batch_size=options.batch_size,
        max_slot_rewrite_attempts=_MAX_SLOT_REWRITE_ATTEMPTS,
    )
    auto_retry_meta = _build_auto_retry_meta(
        attempted_keywords=_collect_slot_candidate_keywords(retry_slot_candidates),
        accepted_keywords=_dedupe_texts(
            _collect_slot_candidate_keywords(retry_slot_candidates, accepted_retry_slot_ids) + accepted_rescue_keywords
        ),
        remaining_retry_count=int(quality_summary.get("retry_count") or 0),
        error_messages=retry_error_messages,
        retry_threshold=retry_threshold,
        provider=retry_options.provider,
        model=retry_options.model,
        attempted_slot_count=len(retry_slot_candidates),
        accepted_slot_count=len(accepted_retry_slot_ids),
        rewrite_call_count=len(retry_batch_sizes),
        rewrite_batch_sizes=retry_batch_sizes,
    )
    if not escalation_options:
        return retry_enriched_results, quality_summary, auto_retry_meta, base_escalation_meta

    escalation_slot_candidates = _collect_retry_slot_candidates(
        retry_results,
        retry_enriched_results,
        retry_threshold,
        recent_batch_size=options.batch_size,
    )
    escalation_slot_candidates, _ = _filter_slot_candidates_by_retry_attempts(
        escalation_slot_candidates,
        slot_retry_attempt_counts,
        max_attempts=_MAX_SLOT_REWRITE_ATTEMPTS,
    )
    if not escalation_slot_candidates:
        return retry_enriched_results, quality_summary, auto_retry_meta, base_escalation_meta

    _publish_title_progress(
        progress_callback,
        type="phase",
        phase="model_escalation",
        processed_count=0,
        total_count=len(escalation_slot_candidates),
        progress_percent=_MODEL_ESCALATION_PROGRESS_START,
        message=_build_retry_progress_message(
            "상위 모델 slot 재작성 준비 중",
            selected_count=len(escalation_slot_candidates),
            total_candidates=len(escalation_slot_candidates),
        ),
    )
    escalated_titles_by_slot_id, escalation_error_messages, escalation_batch_sizes = _request_slot_retry_candidates(
        escalation_slot_candidates,
        escalation_options,
        phase="model_escalation",
        progress_callback=progress_callback,
        total_candidates=len(escalation_slot_candidates),
    )
    final_results, final_enriched_results, accepted_escalation_slot_ids = _merge_slot_retry_candidates(
        current_results=retry_results,
        current_enriched_results=retry_enriched_results,
        slot_candidates=escalation_slot_candidates,
        rewritten_titles_by_slot_id=escalated_titles_by_slot_id,
        evaluation_options=evaluation_options,
    )
    failed_escalation_slot_ids = _record_failed_slot_retry_attempts(
        slot_retry_attempt_counts,
        escalation_slot_candidates,
        accepted_escalation_slot_ids,
    )
    exhausted_slot_ids = [
        slot_id
        for slot_id in failed_escalation_slot_ids
        if int(slot_retry_attempt_counts.get(slot_id) or 0) >= _MAX_SLOT_REWRITE_ATTEMPTS
    ]
    if exhausted_slot_ids:
        final_enriched_results, downgraded_slot_ids = _downgrade_exhausted_retry_slots(
            final_results,
            final_enriched_results,
            exhausted_slot_ids,
        )
    else:
        downgraded_slot_ids = []
    quality_summary = _build_quality_summary_from_items(final_enriched_results)
    escalation_meta = _build_model_escalation_meta(
        enabled=True,
        trigger_failure_count=_MODEL_ESCALATION_TRIGGER_FAILURES,
        triggered=True,
        source_provider=retry_options.provider,
        source_model=retry_options.model,
        target_provider=escalation_options.provider,
        target_model=escalation_options.model,
        attempted_keywords=_collect_slot_candidate_keywords(escalation_slot_candidates),
        accepted_keywords=_collect_slot_candidate_keywords(escalation_slot_candidates, accepted_escalation_slot_ids),
        remaining_retry_count=int(quality_summary.get("retry_count") or 0),
        error_messages=escalation_error_messages,
        attempted_slot_count=len(escalation_slot_candidates),
        accepted_slot_count=len(accepted_escalation_slot_ids),
        rewrite_call_count=len(escalation_batch_sizes),
        rewrite_batch_sizes=escalation_batch_sizes,
        downgraded_slot_ids=downgraded_slot_ids,
        max_slot_rewrite_attempts=_MAX_SLOT_REWRITE_ATTEMPTS,
    )
    return final_enriched_results, quality_summary, auto_retry_meta, escalation_meta


def _collect_retry_slot_candidates(
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
    retry_threshold: int,
    *,
    recent_batch_size: int = _DEFAULT_PEER_TITLE_BATCH_WINDOW,
) -> list[dict[str, Any]]:
    slot_candidates: list[dict[str, Any]] = []
    resolved_recent_batch_size = max(1, int(recent_batch_size or _DEFAULT_PEER_TITLE_BATCH_WINDOW))

    for result_index, (item, enriched_item) in enumerate(zip(current_results, current_enriched_results)):
        keyword = normalize_text(item.get("keyword") or enriched_item.get("keyword"))
        if not keyword:
            continue
        quality_report = enriched_item.get("quality_report") if isinstance(enriched_item.get("quality_report"), dict) else {}
        if not _should_retry_for_quality(quality_report, retry_threshold):
            continue
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        aligned_title_checks = _align_title_checks_to_current_slots(item, enriched_item)
        for channel_name in TITLE_CHANNEL_ORDER:
            channel_label = TITLE_CHANNEL_SLOT_LABELS[channel_name]
            channel_titles = list(titles.get(channel_name, [])) if isinstance(titles.get(channel_name), list) else []
            channel_reports = aligned_title_checks.get(channel_name, [])
            for slot_index, raw_title in enumerate(channel_titles, start=1):
                title = normalize_text(raw_title)
                if not title:
                    continue
                report = channel_reports[slot_index - 1] if slot_index - 1 < len(channel_reports) else {}
                if not _should_retry_slot(report, retry_threshold, channel_name=channel_name, title=title):
                    continue
                same_keyword_peer_titles = _collect_item_peer_titles(
                    titles,
                    exclude_channel=channel_name,
                    exclude_slot_index=slot_index,
                )[:_SAME_KEYWORD_PEER_TITLE_LIMIT]
                recent_batch_peer_titles = _collect_recent_batch_peer_titles(
                    current_results,
                    result_index=result_index,
                    recent_batch_size=resolved_recent_batch_size,
                    exclude_titles=[title, *same_keyword_peer_titles],
                    limit=_CROSS_KEYWORD_PEER_TITLE_LIMIT,
                )
                slot_candidates.append(
                    {
                        "slot_id": f"{result_index}_{channel_label}_{slot_index}",
                        "result_index": result_index,
                        "keyword": keyword,
                        "channel": channel_name,
                        "slot_index": slot_index,
                        "current_title": title,
                        "peer_titles": same_keyword_peer_titles + recent_batch_peer_titles,
                        "issues": list(report.get("issues", []))[:5],
                        "score": int(report.get("score") or 0),
                        "status": str(report.get("status") or "").strip().lower(),
                        "source_note": normalize_text(item.get("source_note")),
                        "source_keywords": list(item.get("source_keywords", [])) if isinstance(item.get("source_keywords"), list) else [],
                        "support_keywords": list(item.get("support_keywords", [])) if isinstance(item.get("support_keywords"), list) else [],
                        "metrics": dict(item.get("metrics", {})) if isinstance(item.get("metrics"), dict) else {},
                    }
                )

    slot_candidates.sort(
        key=lambda candidate: (
            0 if candidate.get("status") == "retry" else 1,
            int(candidate.get("score") or 0),
            -len(candidate.get("issues", [])),
            int(candidate.get("result_index") or 0),
            TITLE_CHANNEL_ORDER.index(candidate.get("channel")) if candidate.get("channel") in TITLE_CHANNEL_ORDER else len(TITLE_CHANNEL_ORDER),
            int(candidate.get("slot_index") or 0),
        )
    )
    return slot_candidates


def _request_slot_retry_candidates(
    slot_candidates: list[dict[str, Any]],
    retry_options: TitleGenerationOptions,
    *,
    phase: str,
    progress_callback: TitleProgressCallback | None = None,
    total_candidates: int | None = None,
 ) -> tuple[dict[str, str], list[str], list[int]]:
    rewritten_titles_by_slot_id: dict[str, str] = {}
    error_messages: list[str] = []
    processed_count = 0
    resolved_total = total_candidates if isinstance(total_candidates, int) and total_candidates > 0 else len(slot_candidates)
    chunks = _chunk_slot_candidates(slot_candidates, retry_options.batch_size)
    batch_sizes = [len(chunk) for chunk in chunks]
    total_call_count = len(chunks)

    for call_index, chunk in enumerate(chunks, start=1):
        _publish_title_progress(
            progress_callback,
            type="rewrite_batch",
            phase=phase,
            processed_count=processed_count,
            total_count=resolved_total,
            progress_percent=_compute_phase_progress(
                processed_count,
                resolved_total,
                start=_AUTO_RETRY_PROGRESS_START if phase == "auto_retry" else _MODEL_ESCALATION_PROGRESS_START,
                end=_AUTO_RETRY_PROGRESS_END if phase == "auto_retry" else _MODEL_ESCALATION_PROGRESS_END,
            ),
            message=f"slot rewrite batch {call_index}/{total_call_count}",
            bad_slot_count=resolved_total,
            rewrite_call_count=call_index,
            rewrite_total_calls=total_call_count,
            rewrite_batch_size=len(chunk),
            rewrite_status="started",
        )
        try:
            response_items = request_ai_slot_rewrites(chunk, options=retry_options)
        except TitleProviderError as exc:
            error_messages.append(str(exc))
            continue

        for item in response_items:
            slot_id = normalize_text(item.get("slot_id"))
            title = normalize_text(item.get("title"))
            if not slot_id or not title:
                continue
            rewritten_titles_by_slot_id[slot_id] = title

        processed_count = min(resolved_total, processed_count + len(chunk))
        _publish_title_progress(
            progress_callback,
            type="phase",
            phase=phase,
            processed_count=processed_count,
            total_count=resolved_total,
            progress_percent=_compute_phase_progress(
                processed_count,
                resolved_total,
                start=_AUTO_RETRY_PROGRESS_START if phase == "auto_retry" else _MODEL_ESCALATION_PROGRESS_START,
                end=_AUTO_RETRY_PROGRESS_END if phase == "auto_retry" else _MODEL_ESCALATION_PROGRESS_END,
            ),
            message=_build_retry_progress_message(
                "문제 slot 재작성 중" if phase == "auto_retry" else "상위 모델 slot 재작성 중",
                selected_count=processed_count,
                total_candidates=resolved_total,
                include_ratio=True,
            ),
            bad_slot_count=resolved_total,
            rewrite_call_count=call_index,
            rewrite_total_calls=total_call_count,
            rewrite_batch_size=len(chunk),
            rewrite_status="completed",
        )

    return rewritten_titles_by_slot_id, error_messages, batch_sizes


def _merge_slot_retry_candidates(
    *,
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
    slot_candidates: list[dict[str, Any]],
    rewritten_titles_by_slot_id: dict[str, str],
    evaluation_options: TitleEvaluationOptions | None = None,
) -> tuple[list[TitleOutputItem], list[TitleOutputItem], list[str]]:
    if not slot_candidates or not rewritten_titles_by_slot_id:
        return current_results, current_enriched_results, []

    effective_slot_candidates = [
        candidate
        for candidate in slot_candidates
        if normalize_text(rewritten_titles_by_slot_id.get(candidate.get("slot_id")))
        and normalize_text(rewritten_titles_by_slot_id.get(candidate.get("slot_id"))) != normalize_text(candidate.get("current_title"))
    ]
    if not effective_slot_candidates:
        return current_results, current_enriched_results, []

    candidate_results = _apply_slot_title_updates(
        current_results,
        effective_slot_candidates,
        rewritten_titles_by_slot_id,
    )
    candidate_enriched_results, _ = refresh_title_results_for_changed_slots(
        candidate_results,
        current_enriched_results,
        effective_slot_candidates,
        evaluation_options=evaluation_options,
    )
    current_slot_reports = _build_slot_report_map(current_results, current_enriched_results)
    candidate_slot_reports = _build_slot_report_map(candidate_results, candidate_enriched_results)

    accepted_slot_ids: list[str] = []
    accepted_title_updates: dict[str, str] = {}
    for candidate in effective_slot_candidates:
        slot_id = candidate["slot_id"]
        rewritten_title = normalize_text(rewritten_titles_by_slot_id.get(slot_id))
        if not rewritten_title or rewritten_title == normalize_text(candidate.get("current_title")):
            continue
        current_report = current_slot_reports.get(slot_id, {})
        candidate_report = candidate_slot_reports.get(slot_id, {})
        if _should_accept_slot_retry(current_report, candidate_report):
            accepted_slot_ids.append(slot_id)
            accepted_title_updates[slot_id] = rewritten_title

    if not accepted_slot_ids:
        return current_results, current_enriched_results, []

    accepted_slot_candidates = [
        candidate
        for candidate in effective_slot_candidates
        if candidate.get("slot_id") in accepted_title_updates
    ]
    merged_results = _apply_slot_title_updates(
        current_results,
        accepted_slot_candidates,
        accepted_title_updates,
    )
    merged_enriched_results, _ = refresh_title_results_for_changed_slots(
        merged_results,
        current_enriched_results,
        accepted_slot_candidates,
        evaluation_options=evaluation_options,
    )
    return merged_results, merged_enriched_results, accepted_slot_ids


def _apply_slot_title_updates(
    current_results: list[TitleOutputItem],
    slot_candidates: list[dict[str, Any]],
    rewritten_titles_by_slot_id: dict[str, str],
) -> list[TitleOutputItem]:
    next_results = [_clone_title_output_item(item) for item in current_results]
    candidate_lookup = {candidate["slot_id"]: candidate for candidate in slot_candidates}

    for slot_id, rewritten_title in rewritten_titles_by_slot_id.items():
        candidate = candidate_lookup.get(slot_id)
        title = normalize_text(rewritten_title)
        if not candidate or not title:
            continue
        result_index = int(candidate.get("result_index") or 0)
        if result_index < 0 or result_index >= len(next_results):
            continue
        channel_name = str(candidate.get("channel") or "").strip()
        slot_index = int(candidate.get("slot_index") or 0)
        titles = next_results[result_index].get("titles") if isinstance(next_results[result_index].get("titles"), dict) else {}
        channel_titles = titles.get(channel_name) if isinstance(titles.get(channel_name), list) else []
        if slot_index <= 0 or slot_index > len(channel_titles):
            continue
        channel_titles[slot_index - 1] = title

    return next_results


def _build_slot_title_updates_from_bundle_candidates(
    slot_candidates: list[dict[str, Any]],
    bundle_candidates: dict[str, TitleOutputItem],
) -> dict[str, str]:
    rewritten_titles_by_slot_id: dict[str, str] = {}
    for candidate in slot_candidates:
        slot_id = normalize_text(candidate.get("slot_id"))
        keyword = normalize_text(candidate.get("keyword"))
        channel_name = str(candidate.get("channel") or "").strip()
        slot_index = int(candidate.get("slot_index") or 0)
        if not slot_id or not keyword or slot_index <= 0:
            continue
        bundle_candidate = bundle_candidates.get(keyword)
        if not isinstance(bundle_candidate, dict):
            continue
        titles = bundle_candidate.get("titles") if isinstance(bundle_candidate.get("titles"), dict) else {}
        channel_titles = titles.get(channel_name) if isinstance(titles.get(channel_name), list) else []
        if slot_index > len(channel_titles):
            continue
        rewritten_title = normalize_text(channel_titles[slot_index - 1])
        if not rewritten_title or rewritten_title == normalize_text(candidate.get("current_title")):
            continue
        rewritten_titles_by_slot_id[slot_id] = rewritten_title
    return rewritten_titles_by_slot_id


def _clone_title_output_item(item: TitleOutputItem) -> TitleOutputItem:
    titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
    return {
        **_strip_generated_fields(item),
        "keyword": normalize_text(item.get("keyword")),
        "titles": {
            channel_name: list(titles.get(channel_name, [])) if isinstance(titles.get(channel_name), list) else []
            for channel_name in TITLE_CHANNEL_ORDER
        },
    }


def _build_slot_report_map(
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
) -> dict[str, dict[str, Any]]:
    report_map: dict[str, dict[str, Any]] = {}
    for result_index, (item, enriched_item) in enumerate(zip(current_results, current_enriched_results)):
        aligned_title_checks = _align_title_checks_to_current_slots(item, enriched_item)
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        for channel_name in TITLE_CHANNEL_ORDER:
            channel_label = TITLE_CHANNEL_SLOT_LABELS[channel_name]
            channel_titles = list(titles.get(channel_name, [])) if isinstance(titles.get(channel_name), list) else []
            channel_reports = aligned_title_checks.get(channel_name, [])
            for slot_index, raw_title in enumerate(channel_titles, start=1):
                report_map[f"{result_index}_{channel_label}_{slot_index}"] = (
                    channel_reports[slot_index - 1] if slot_index - 1 < len(channel_reports) else {"title": normalize_text(raw_title)}
                )
    return report_map


def _align_title_checks_to_current_slots(
    item: TitleOutputItem,
    enriched_item: TitleOutputItem,
) -> dict[str, list[dict[str, Any]]]:
    titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
    quality_report = enriched_item.get("quality_report") if isinstance(enriched_item.get("quality_report"), dict) else {}
    raw_title_checks = quality_report.get("title_checks") if isinstance(quality_report.get("title_checks"), dict) else {}
    aligned_title_checks: dict[str, list[dict[str, Any]]] = {channel_name: [] for channel_name in TITLE_CHANNEL_ORDER}

    for channel_name in TITLE_CHANNEL_ORDER:
        channel_titles = list(titles.get(channel_name, [])) if isinstance(titles.get(channel_name), list) else []
        raw_reports = list(raw_title_checks.get(channel_name, [])) if isinstance(raw_title_checks.get(channel_name), list) else []
        reports_by_title: dict[str, list[dict[str, Any]]] = {}
        for raw_report in raw_reports:
            normalized_title = normalize_text(raw_report.get("title"))
            reports_by_title.setdefault(normalized_title, []).append(raw_report)

        fallback_reports = raw_reports[:]
        aligned_reports: list[dict[str, Any]] = []
        for raw_title in channel_titles:
            title = normalize_text(raw_title)
            title_reports = reports_by_title.get(title) or []
            if title_reports:
                matched_report = title_reports.pop(0)
                if matched_report in fallback_reports:
                    fallback_reports.remove(matched_report)
                aligned_reports.append(matched_report)
                continue
            if fallback_reports:
                aligned_reports.append(fallback_reports.pop(0))
                continue
            aligned_reports.append({"title": title, "score": 0, "status": "retry", "issues": [], "critical": True})

        aligned_title_checks[channel_name] = aligned_reports

    return aligned_title_checks


def _collect_item_peer_titles(
    titles: dict[str, Any],
    *,
    exclude_channel: str | None = None,
    exclude_slot_index: int | None = None,
) -> list[str]:
    peer_titles: list[str] = []
    for channel_name in TITLE_CHANNEL_ORDER:
        channel_titles = titles.get(channel_name, []) if isinstance(titles.get(channel_name), list) else []
        for slot_index, raw_title in enumerate(channel_titles, start=1):
            if exclude_channel == channel_name and exclude_slot_index == slot_index:
                continue
            title = normalize_text(raw_title)
            if title:
                peer_titles.append(title)
    return peer_titles


def _collect_recent_batch_peer_titles(
    current_results: list[TitleOutputItem],
    *,
    result_index: int,
    recent_batch_size: int,
    exclude_titles: list[str] | None = None,
    limit: int = _CROSS_KEYWORD_PEER_TITLE_LIMIT,
) -> list[str]:
    if limit <= 0 or not current_results:
        return []

    resolved_recent_batch_size = max(1, int(recent_batch_size or _DEFAULT_PEER_TITLE_BATCH_WINDOW))
    batch_start = (result_index // resolved_recent_batch_size) * resolved_recent_batch_size
    batch_end = min(len(current_results), batch_start + resolved_recent_batch_size)
    seen = {normalize_text(title) for title in (exclude_titles or []) if normalize_text(title)}
    title_groups: list[list[str]] = []

    for candidate_index in range(batch_start, batch_end):
        if candidate_index == result_index:
            continue
        titles = current_results[candidate_index].get("titles") if isinstance(current_results[candidate_index].get("titles"), dict) else {}
        title_group = [
            candidate_title
            for candidate_title in _collect_item_peer_titles(titles)
            if candidate_title and candidate_title not in seen
        ]
        if title_group:
            title_groups.append(title_group)

    collected_titles: list[str] = []
    title_offset = 0
    while len(collected_titles) < limit:
        added_in_round = False
        for title_group in title_groups:
            if title_offset >= len(title_group):
                continue
            candidate_title = title_group[title_offset]
            if candidate_title in seen:
                continue
            seen.add(candidate_title)
            collected_titles.append(candidate_title)
            added_in_round = True
            if len(collected_titles) >= limit:
                break
        if not added_in_round:
            break
        title_offset += 1

    return collected_titles


def _extract_ctr_component(report: dict[str, Any], key: str) -> int:
    if not isinstance(report, dict):
        return 0
    score_breakdown = report.get("score_breakdown") if isinstance(report.get("score_breakdown"), dict) else {}
    try:
        return int(score_breakdown.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _count_home_ctr_core_elements(report: dict[str, Any]) -> int:
    return sum(
        (
            _extract_ctr_component(report, "issue_or_context") >= _HOME_CORE_ISSUE_MIN_SCORE,
            _extract_ctr_component(report, "curiosity_gap") >= _HOME_CORE_CURIOSITY_MIN_SCORE,
            _extract_ctr_component(report, "contrast_or_conflict") >= _HOME_CORE_CONTRAST_MIN_SCORE,
        )
    )


def _should_never_retry_home_slot(report: dict[str, Any], title: str) -> bool:
    normalized_title = normalize_text(title or report.get("title"))
    score = int(report.get("score") or 0) if isinstance(report, dict) else 0
    if score >= _HOME_RETRY_KEEP_SCORE_CUTOFF:
        return True
    if normalized_title.endswith("?") or normalized_title.endswith("？"):
        return True
    if len(normalized_title) <= _HOME_SHORT_TITLE_MAX_LENGTH:
        return True
    if _extract_ctr_component(report, "curiosity_gap") >= _HOME_CORE_CURIOSITY_MIN_SCORE:
        return True
    if _extract_ctr_component(report, "contrast_or_conflict") >= _HOME_CORE_CONTRAST_MIN_SCORE:
        return True
    if _extract_ctr_component(report, "emotional_trigger") >= _HOME_EMOTIONAL_HOOK_MIN_SCORE:
        return True
    return False


def _should_retry_slot(report: dict[str, Any], retry_threshold: int, *, channel_name: str = "", title: str = "") -> bool:
    if not isinstance(report, dict):
        return False
    normalized_channel = str(channel_name or "").strip().lower()
    score = int(report.get("score") or 0)
    resolved_threshold = min(int(retry_threshold or _DEFAULT_QUALITY_RETRY_THRESHOLD), _HOME_RETRY_KEEP_SCORE_CUTOFF)

    if normalized_channel == "naver_home":
        if _should_never_retry_home_slot(report, title):
            return False
        if score < _STRICT_RETRY_SCORE_CUTOFF:
            return True
        return _count_home_ctr_core_elements(report) < 2

    return score < min(resolved_threshold, _STRICT_RETRY_SCORE_CUTOFF)


def _should_accept_slot_retry(current_report: dict[str, Any], candidate_report: dict[str, Any]) -> bool:
    if not isinstance(candidate_report, dict):
        return False
    current_score = int(current_report.get("score") or 0)
    candidate_score = int(candidate_report.get("score") or 0)
    current_status = str(current_report.get("status") or "").strip().lower()
    candidate_status = str(candidate_report.get("status") or "").strip().lower()
    current_issue_count = len(current_report.get("issues", [])) if isinstance(current_report.get("issues"), list) else 0
    candidate_issue_count = len(candidate_report.get("issues", [])) if isinstance(candidate_report.get("issues"), list) else 0

    if current_status == "retry" and candidate_status != "retry":
        return True
    if candidate_score >= current_score + 4:
        return True
    if candidate_score > current_score and candidate_issue_count <= current_issue_count:
        return True
    return candidate_score >= current_score and candidate_issue_count < current_issue_count


def _collect_slot_candidate_keywords(
    slot_candidates: list[dict[str, Any]],
    accepted_slot_ids: list[str] | None = None,
) -> list[str]:
    accepted_slot_filter_enabled = accepted_slot_ids is not None
    accepted_lookup = {normalize_text(slot_id) for slot_id in (accepted_slot_ids or []) if normalize_text(slot_id)}
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in slot_candidates:
        slot_id = normalize_text(candidate.get("slot_id"))
        if accepted_slot_filter_enabled and slot_id not in accepted_lookup:
            continue
        keyword = normalize_text(candidate.get("keyword"))
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        keywords.append(keyword)
    return keywords


def _chunk_slot_candidates(
    slot_candidates: list[dict[str, Any]],
    size: int,
) -> list[list[dict[str, Any]]]:
    resolved_size = max(1, min(int(size or 20), 20))
    return [
        slot_candidates[index:index + resolved_size]
        for index in range(0, len(slot_candidates), resolved_size)
    ]


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _filter_slot_candidates_by_retry_attempts(
    slot_candidates: list[dict[str, Any]],
    retry_attempt_counts: dict[str, int],
    *,
    max_attempts: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    filtered_candidates: list[dict[str, Any]] = []
    skipped_slot_ids: list[str] = []
    resolved_max_attempts = max(1, int(max_attempts or _MAX_SLOT_REWRITE_ATTEMPTS))
    for candidate in slot_candidates:
        slot_id = normalize_text(candidate.get("slot_id"))
        if not slot_id:
            continue
        if int(retry_attempt_counts.get(slot_id) or 0) >= resolved_max_attempts:
            skipped_slot_ids.append(slot_id)
            continue
        filtered_candidates.append(candidate)
    return filtered_candidates, skipped_slot_ids


def _record_failed_slot_retry_attempts(
    retry_attempt_counts: dict[str, int],
    slot_candidates: list[dict[str, Any]],
    accepted_slot_ids: list[str] | None = None,
) -> list[str]:
    accepted_lookup = {
        normalize_text(slot_id)
        for slot_id in (accepted_slot_ids or [])
        if normalize_text(slot_id)
    }
    failed_slot_ids: list[str] = []
    for candidate in slot_candidates:
        slot_id = normalize_text(candidate.get("slot_id"))
        if not slot_id or slot_id in accepted_lookup:
            continue
        retry_attempt_counts[slot_id] = int(retry_attempt_counts.get(slot_id) or 0) + 1
        failed_slot_ids.append(slot_id)
    return failed_slot_ids


def _downgrade_exhausted_retry_slots(
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
    exhausted_slot_ids: list[str],
) -> tuple[list[TitleOutputItem], list[str]]:
    exhausted_lookup = {
        normalize_text(slot_id)
        for slot_id in exhausted_slot_ids
        if normalize_text(slot_id)
    }
    if not exhausted_lookup:
        return current_enriched_results, []

    downgraded_slot_ids: list[str] = []
    downgraded_results: list[TitleOutputItem] = []

    for result_index, (item, enriched_item) in enumerate(zip(current_results, current_enriched_results)):
        aligned_title_checks = _align_title_checks_to_current_slots(item, enriched_item)
        changed = False

        for channel_name in TITLE_CHANNEL_ORDER:
            channel_label = TITLE_CHANNEL_SLOT_LABELS[channel_name]
            channel_reports = list(aligned_title_checks.get(channel_name, []))
            for slot_index, report in enumerate(channel_reports, start=1):
                slot_id = f"{result_index}_{channel_label}_{slot_index}"
                if slot_id not in exhausted_lookup:
                    continue
                if str(report.get("status") or "").strip().lower() != "retry":
                    continue
                next_report = dict(report)
                issues = list(next_report.get("issues", [])) if isinstance(next_report.get("issues"), list) else []
                if _RETRY_LIMIT_DOWNGRADE_ISSUE not in issues:
                    issues.append(_RETRY_LIMIT_DOWNGRADE_ISSUE)
                checks = dict(next_report.get("checks", {})) if isinstance(next_report.get("checks"), dict) else {}
                checks["retry_limit_reached"] = True
                next_report["issues"] = _dedupe_texts(issues)
                next_report["critical"] = False
                next_report["status"] = "review"
                next_report["checks"] = checks
                channel_reports[slot_index - 1] = next_report
                changed = True
                downgraded_slot_ids.append(slot_id)
            aligned_title_checks[channel_name] = channel_reports

        if not changed:
            downgraded_results.append(enriched_item)
            continue

        rebuilt_report = _build_bundle_report(
            normalize_text(item.get("keyword")),
            aligned_title_checks,
        )
        rebuilt_issues = list(rebuilt_report.get("issues", [])) if isinstance(rebuilt_report.get("issues"), list) else []
        if _RETRY_LIMIT_DOWNGRADE_ISSUE not in rebuilt_issues:
            rebuilt_issues.append(_RETRY_LIMIT_DOWNGRADE_ISSUE)
        rebuilt_report["issues"] = _dedupe_texts(rebuilt_issues)
        rebuilt_report["issue_count"] = len(rebuilt_report["issues"])
        rebuilt_report["summary"] = " / ".join(rebuilt_report["issues"][:3]) if rebuilt_report["issues"] else _RETRY_LIMIT_DOWNGRADE_ISSUE
        rebuilt_report["status"] = "review"
        rebuilt_report["label"] = "검토 필요"
        rebuilt_report["retry_recommended"] = False
        rebuilt_report["passes_threshold"] = False
        downgraded_results.append(
            {
                **enriched_item,
                "quality_report": rebuilt_report,
            }
        )

    return downgraded_results, _dedupe_texts(downgraded_slot_ids)


def _should_retry_for_quality(report: dict[str, Any], retry_threshold: int) -> bool:
    if not isinstance(report, dict):
        return False
    if bool(report.get("recommended_pair_ready")):
        return False
    title_checks = report.get("title_checks") if isinstance(report.get("title_checks"), dict) else {}
    for channel_name, channel_reports in title_checks.items():
        if not isinstance(channel_reports, list):
            continue
        for slot_report in channel_reports:
            if _should_retry_slot(
                slot_report if isinstance(slot_report, dict) else {},
                retry_threshold,
                channel_name=str(channel_name or "").strip().lower(),
                title=(slot_report or {}).get("title") if isinstance(slot_report, dict) else "",
            ):
                return True
    return int(report.get("bundle_score") or 0) < min(int(retry_threshold or _DEFAULT_QUALITY_RETRY_THRESHOLD), _STRICT_RETRY_SCORE_CUTOFF)


def _count_retry_candidates(items: list[TitleOutputItem], retry_threshold: int) -> int:
    return sum(
        1
        for item in items
        if _should_retry_for_quality(item.get("quality_report", {}), retry_threshold)
        and normalize_text(item.get("keyword"))
    )


def _select_retry_keywords_for_pass(
    items: list[TitleOutputItem],
    retry_threshold: int,
    *,
    limit: int,
) -> list[str]:
    ranked_candidates: list[tuple[int, int, int, str]] = []

    for item in items:
        keyword = normalize_text(item.get("keyword"))
        report = item.get("quality_report", {})
        if not keyword or not _should_retry_for_quality(report, retry_threshold):
            continue
        ranked_candidates.append(
            (
                0 if bool(report.get("retry_recommended")) else 1,
                int(report.get("bundle_score") or 0),
                -int(report.get("issue_count") or 0),
                keyword,
            )
        )

    ranked_candidates.sort()
    if limit > 0:
        ranked_candidates = ranked_candidates[:limit]
    return [keyword for _, _, _, keyword in ranked_candidates]


def _build_retry_progress_message(
    base: str,
    *,
    selected_count: int,
    total_candidates: int,
    include_ratio: bool = False,
) -> str:
    if total_candidates > selected_count:
        if include_ratio:
            return f"{base}: {selected_count} / {total_candidates}건 (상위 {selected_count}건만)"
        return f"{base}: 후보 {total_candidates}건 중 상위 {selected_count}건만"
    if include_ratio:
        return f"{base}: {selected_count} / {total_candidates}건"
    return f"{base}: {selected_count}건"


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
    if current_retry and retry_retry:
        return False
    if retry_score >= current_score + 4:
        return True
    return retry_score >= current_score and retry_issue_count < current_issue_count


def _build_quality_retry_prompt(existing_prompt: str, retry_threshold: int) -> str:
    retry_guidance = (
        "Quality retry guidance:\n"
        "- Keep the exact keyword at the front of each title when natural.\n"
        "- Do not shorten the keyword phrase. If the keyword starts with descriptive words, keep them all.\n"
        "- Prefer concise hook-first wording. One clear hook plus one concrete noun is better than a long abstract explanation.\n"
        "- Keep the home-feed pair issue-aware: usually make one title issue/update + comparison/debate and the other title issue/update + reversal/question.\n"
        "- For naver_home titles, evaluate CTR first, not SEO. Strong titles usually combine issue/context, curiosity, contrast/conflict, reversal/unexpected, emotional trigger, specificity, and readability.\n"
        '- Strong positive CTR signals include question-led hooks such as "왜일까", "뭐지", "진짜?", unresolved curiosity phrasing, and emotional triggers such as "의외", "먼저", "갈렸다".\n'
        "- Do not penalize a naver_home title just because it is phrased as a question, leaves part of the meaning implied, stays short, or keeps some abstraction.\n"
        "- Do not penalize repeated question patterns, low explicit information density, partial abstraction, or curiosity-driven phrasing in naver_home titles. These can be positive CTR signals.\n"
        "- Do penalize purely informational naver_home titles, no-curiosity headlines, flat explanatory tone, and filler endings such as 확인해보자 or 알아보자.\n"
        "- Do not use SEO or blog criteria such as abstract, clickbait, templated, or lacking information as reasons to downscore naver_home titles.\n"
        "- If a naver_home title already reaches practical CTR quality around 68 or higher, prefer keeping it instead of forcing another rewrite.\n"
        "- If a naver_home title is still weak, keep the keyword tokens and order, stay within 40 characters, and combine at least two of issue, contrast, reversal, and curiosity.\n"
        "- Make titles within the same channel clearly different from each other.\n"
        f"- Keep every naver_home and hybrid title within {NAVER_HOME_MAX_LENGTH} characters.\n"
        "- Avoid exaggerated words such as 무조건, 충격, 레전드, 미쳤다, 대박.\n"
        "- Do not invent unsupported dates, numbers, rankings, or official changes just to sound current.\n"
        "- Avoid stale filler such as 완벽 정리, 한 번에 정리, 갑자기 바뀌었다, 이유가 이상하다, 놓치면 손해.\n"
        "- Across the same retry batch, do not keep reusing skeletons such as 뭐가 다를까, 체크리스트, 고를 때, 추천 기준, or 비교 포인트.\n"
        "- Do not use low-information endings such as 최신 정보, 업데이트 확인, 왜 인기, 이것만 알면, 구매 가이드, 사용 후기, 신상, or a bare 비교.\n"
        "- If the keyword already carries concrete intent such as 실사용 차이, 장단점, 설정 팁, 연결 방법, 연결 문제, or 자주 생기는 문제, do not wrap it with 최신 비교 분석, 총정리, 완벽 가이드, 최신 정보, 이것만 알면, or 꼭 알아두세요.\n"
        "- For real-use keywords, prefer timeframe, user type, grip, weight, click feel, battery, workflow, or device-fit nouns.\n"
        "- For setup or problem keywords, prefer one symptom plus one cause, fix, result, or environment such as 맥북, 윈도우, 블루투스, 유니파잉, 연결 끊김, 더블클릭, or 인식 안됨.\n"
        "- Replace abstract meta words with concrete difference, use-case, fit, pain point, setup, price, or performance nouns.\n"
        "- For finance keywords, avoid 느슨한 wrappers such as 투자 전략, 투자 가이드, 총정리, 체크리스트, or 지금 확인하세요 unless the keyword explicitly demands them.\n"
        "- For naver_home titles, do not stop at bare labels like 환율 영향, 확인 포인트, 기준선, 조건 차이, 실시간 현황, or 국내외 차이. Turn the axis into a real question, contrast, implication, or decision point.\n"
        "- For finance analysis titles, 2주 흐름, 2주간 추이, 3주 변동, or 1개월 비교 are acceptable when they clearly describe retrospective analysis instead of pretending to know a live move.\n"
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
        "- If the issue angle is weak, choose a cleaner difference, use-case, fit, setup, or decision frame instead of a generic guide/checklist label.\n"
        "- If the batch still feels templated, change the whole headline skeleton instead of swapping one noun.\n"
        "- Keep every title clearly distinct without drifting away from the keyword intent."
    )
    return f"{_build_quality_retry_prompt(existing_prompt, retry_threshold)}\n\n{escalation_guidance}"


def _apply_practical_rescue_candidates(
    *,
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
    original_items_by_keyword: dict[str, TitleOutputItem],
    retry_threshold: int,
    evaluation_options: TitleEvaluationOptions | None = None,
    retry_attempt_counts: dict[str, int] | None = None,
    recent_batch_size: int = _DEFAULT_PEER_TITLE_BATCH_WINDOW,
    max_slot_rewrite_attempts: int = _MAX_SLOT_REWRITE_ATTEMPTS,
) -> tuple[list[TitleOutputItem], list[TitleOutputItem], dict[str, Any], list[str]]:
    rescue_slot_candidates = _collect_retry_slot_candidates(
        current_results,
        current_enriched_results,
        retry_threshold,
        recent_batch_size=recent_batch_size,
    )
    rescue_slot_candidates, _ = _filter_slot_candidates_by_retry_attempts(
        rescue_slot_candidates,
        retry_attempt_counts or {},
        max_attempts=max_slot_rewrite_attempts,
    )
    if not rescue_slot_candidates:
        quality_summary = _build_quality_summary_from_items(current_enriched_results)
        return current_results, current_enriched_results, quality_summary, []

    rescue_keywords = _collect_slot_candidate_keywords(rescue_slot_candidates)
    rescue_candidates: dict[str, TitleOutputItem] = {}
    for keyword in rescue_keywords:
        source_item = original_items_by_keyword.get(keyword, {"keyword": keyword})
        rescue_item = _build_practical_rescue_item(source_item)
        if rescue_item:
            rescue_candidates[keyword] = rescue_item

    if not rescue_candidates:
        quality_summary = _build_quality_summary_from_items(current_enriched_results)
        return current_results, current_enriched_results, quality_summary, []

    rescued_titles_by_slot_id = _build_slot_title_updates_from_bundle_candidates(
        rescue_slot_candidates,
        rescue_candidates,
    )
    if not rescued_titles_by_slot_id:
        quality_summary = _build_quality_summary_from_items(current_enriched_results)
        return current_results, current_enriched_results, quality_summary, []

    rescued_results, rescued_enriched_results, accepted_rescue_slot_ids = _merge_slot_retry_candidates(
        current_results=current_results,
        current_enriched_results=current_enriched_results,
        slot_candidates=rescue_slot_candidates,
        rewritten_titles_by_slot_id=rescued_titles_by_slot_id,
        evaluation_options=evaluation_options,
    )
    quality_summary = _build_quality_summary_from_items(rescued_enriched_results)
    accepted_rescue_keywords = _collect_slot_candidate_keywords(
        rescue_slot_candidates,
        accepted_rescue_slot_ids,
    )
    return rescued_results, rescued_enriched_results, quality_summary, accepted_rescue_keywords


def _build_practical_rescue_item(item: dict[str, Any]) -> TitleOutputItem | None:
    keyword = normalize_text(item.get("keyword"))
    keyword_key = normalize_key(keyword)
    if not keyword or not keyword_key:
        return None

    category = detect_category(keyword)
    rescue_kind = _resolve_practical_rescue_kind(keyword_key) or _resolve_generic_single_rescue_kind(
        item,
        keyword=keyword,
        category=category,
    )
    if not rescue_kind:
        return None

    naver_suffixes, blog_suffixes = _resolve_practical_rescue_suffixes(
        keyword=keyword,
        rescue_kind=rescue_kind,
        category=category,
        target_mode=normalize_text(item.get("target_mode")),
        source_selection_mode=normalize_text(item.get("source_selection_mode") or item.get("selection_mode")),
    )
    generated_naver_titles = [f"{keyword}, {suffix}" for suffix in naver_suffixes]
    generated_blog_titles = [f"{keyword} {suffix}" for suffix in blog_suffixes]
    return {
        **_strip_generated_fields(item),
        "keyword": keyword,
        "titles": {
            "naver_home": _merge_title_candidates(
                generated_naver_titles,
                limit=MAX_TITLE_COUNT_PER_CHANNEL,
            ),
            "blog": _merge_title_candidates(
                generated_blog_titles,
                limit=MAX_TITLE_COUNT_PER_CHANNEL,
            ),
            "hybrid": _merge_title_candidates(
                generated_naver_titles,
                generated_blog_titles,
                limit=MAX_TITLE_COUNT_PER_CHANNEL,
            ),
        },
    }


def _merge_title_candidates(*groups: list[str], limit: int) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for title in group:
            normalized_title = normalize_text(title)
            if not normalized_title or normalized_title in seen:
                continue
            seen.add(normalized_title)
            merged.append(normalized_title)
            if len(merged) >= limit:
                return merged
    return merged


def _resolve_practical_rescue_kind(keyword_key: str) -> str:
    for rescue_kind, patterns in _PRACTICAL_RESCUE_KIND_PATTERNS:
        if any(pattern in keyword_key for pattern in patterns):
            return rescue_kind
    return ""


def _resolve_practical_rescue_suffixes(
    *,
    keyword: str,
    rescue_kind: str,
    category: str,
    target_mode: str,
    source_selection_mode: str,
) -> tuple[list[str], list[str]]:
    seed = _stable_rescue_seed(keyword)
    keyword_key = normalize_key(keyword)
    use_product_rescue = category in _PRODUCT_CATEGORY_KEYS or _looks_product_like_keyword(keyword)
    keyword_variant = _resolve_practical_rescue_variant(keyword_key, rescue_kind=rescue_kind)
    is_seed_anchor = normalize_key(source_selection_mode) == "seedanchor"
    is_single_target = normalize_key(target_mode) == "single"
    finance_profile = _resolve_finance_rescue_profile(keyword, category=category)
    if finance_profile:
        finance_rescue = _resolve_finance_rescue_pair(
            rescue_kind=rescue_kind,
            finance_profile=finance_profile,
            is_single_target=is_single_target,
            seed=seed,
        )
        if finance_rescue:
            return finance_rescue
    if rescue_kind == "preorder":
        if keyword_variant == "how_to":
            return _rotate_rescue_pair(
                [
                    (
                        ["오픈 시간과 신청 링크", "본인 인증·결제 순서"],
                        ["오픈 시간·링크·결제 순서 정리", "본인 인증·카드 혜택·실수 포인트 정리"],
                    ),
                    (
                        ["접속 링크와 결제 수단", "준비물과 신청 순서"],
                        ["접속 링크·결제 수단·준비물 정리", "신청 순서·제한 수량·실수 포인트 정리"],
                    ),
                    (
                        ["오픈 일정과 인증 준비", "카드 혜택과 결제 조건"],
                        ["오픈 일정·인증 준비·결제 조건 정리", "카드 혜택·신청 순서·실수 포인트 정리"],
                    ),
                ],
                seed,
            )
        if keyword_variant == "checkpoint":
            return _rotate_rescue_pair(
                [
                    (
                        ["본인 인증과 결제 조건", "수령 일정과 제한 수량"],
                        ["본인 인증·결제 조건·수령 일정 정리", "놓치기 쉬운 제한 수량·카드 혜택 정리"],
                    ),
                    (
                        ["카드 혜택과 신청 제한", "접속 시간과 링크 점검"],
                        ["카드 혜택·신청 제한·접속 시간 정리", "링크·수령 일정·결제 조건 점검"],
                    ),
                    (
                        ["결제 수단과 수령 일정", "인증 단계와 신청 제한"],
                        ["결제 수단·수령 일정·신청 제한 정리", "인증 단계·접속 링크·혜택 포인트 정리"],
                    ),
                ],
                seed,
            )
        if is_seed_anchor and is_single_target:
            return _rotate_rescue_pair(
                [
                    (
                        ["오픈 일정과 신청 링크", "카드 혜택과 준비물"],
                        ["오픈 일정·신청 링크·준비물 정리", "카드 혜택·결제 수단·실수 포인트 정리"],
                    ),
                    (
                        ["오픈 시간과 결제 조건", "본인 인증과 수령 일정"],
                        ["오픈 시간·결제 조건·수령 일정 정리", "본인 인증·신청 링크·혜택 포인트 정리"],
                    ),
                    (
                        ["신청 링크와 인증 준비", "제한 수량과 카드 혜택"],
                        ["신청 링크·인증 준비·제한 수량 정리", "카드 혜택·결제 수단·수령 일정 정리"],
                    ),
                ],
                seed,
            )
        return _rotate_rescue_pair(
            [
                (
                    ["오픈 일정과 신청 링크", "혜택 놓치지 않는 순서"],
                    ["오픈 일정·링크·혜택 정리", "신청 전에 꼭 볼 체크포인트"],
                ),
                (
                    ["신청 일정 먼저 확인", "준비물과 신청 순서"],
                    ["일정·준비물·신청 순서 정리", "신청 전에 막히는 부분 정리"],
                ),
                (
                    ["마감 전에 볼 포인트", "혜택 비교부터 보기"],
                    ["마감 전에 볼 일정과 체크포인트", "혜택·일정·신청 순서 정리"],
                ),
                (
                    ["오픈 시간과 링크 확인", "놓치기 쉬운 신청 조건"],
                    ["오픈 시간·링크·조건 정리", "신청 전에 확인할 혜택 포인트"],
                ),
                (
                    ["신청 동선부터 점검", "실수 줄이는 예약 순서"],
                    ["신청 동선·준비물·일정 정리", "실수 줄이는 예약 체크포인트"],
                ),
            ],
            seed,
        )

    if rescue_kind == "value":
        if keyword_variant == "criteria":
            return _rotate_rescue_pair(
                [
                    (
                        ["위치·교통·추가요금", "후기보다 먼저 볼 기준"],
                        ["위치·교통·추가요금 기준 정리", "후기보다 먼저 볼 가성비 기준 정리"],
                    ),
                    (
                        ["조식·객실·취소 조건", "주말 요금과 역 거리"],
                        ["조식·객실·취소 조건 정리", "주말 요금·역 거리·후기 분포 정리"],
                    ),
                    (
                        ["1박 예산과 포함 옵션", "숨은 추가요금 체크"],
                        ["1박 예산·포함 옵션·추가요금 정리", "가성비를 가르는 후기 포인트 정리"],
                    ),
                ],
                seed,
            ) if not use_product_rescue else _rotate_rescue_pair(
                [
                    (
                        ["가격대·성능·유지비", "할인보다 먼저 볼 기준"],
                        ["가격대·성능·유지비 기준 정리", "할인보다 먼저 볼 선택 기준 정리"],
                    ),
                    (
                        ["체감 성능과 추가 비용", "가격 차이와 추천 대상"],
                        ["체감 성능·추가 비용 정리", "가격 차이·추천 대상·주의점 정리"],
                    ),
                    (
                        ["실사용 대비 가격 포인트", "유지비와 교체 주기"],
                        ["실사용 대비 가격 포인트 정리", "유지비·교체 주기·체감 차이 정리"],
                    ),
                ],
                seed,
            )
        return _rotate_rescue_pair(
            [
                (
                    ["위치·교통·추가요금", "예산 안에서 거르는 기준"],
                    ["위치·교통·추가요금 기준 정리", "예산 안에서 거르는 가성비 기준 정리"],
                ),
                (
                    ["조식 포함과 취소 조건", "후기보다 먼저 볼 포인트"],
                    ["조식 포함·취소 조건·역 거리 정리", "후기보다 먼저 볼 가성비 포인트 정리"],
                ),
                (
                    ["1박 예산과 객실 컨디션", "주말 요금과 숨은 비용"],
                    ["1박 예산·객실 컨디션·추가요금 정리", "주말 요금·후기 분포·교통 포인트 정리"],
                ),
            ],
            seed,
        ) if not use_product_rescue else _rotate_rescue_pair(
            [
                (
                    ["가격대와 체감 차이", "할인보다 먼저 볼 기준"],
                    ["가격대·체감 차이·유지비 정리", "할인보다 먼저 볼 가성비 기준 정리"],
                ),
                (
                    ["추천 대상과 추가 비용", "실사용 대비 가격 포인트"],
                    ["추천 대상·추가 비용·실사용 정리", "실사용 대비 가격 포인트 정리"],
                ),
                (
                    ["체감 성능과 유지비", "가격 차이와 아쉬운 점"],
                    ["체감 성능·유지비·아쉬운 점 정리", "가격 차이·추천 대상·체감 정리"],
                ),
            ],
            seed,
        )

    if rescue_kind == "setting":
        setting_profile = _resolve_setting_rescue_profile(keyword_key)
        if use_product_rescue and setting_profile == "mouse":
            return _rotate_rescue_pair(
                [
                    (
                        ["블루투스 연결과 DPI 세팅", "맥북·윈도우별 버튼 설정"],
                        ["블루투스 연결·DPI 세팅 정리", "맥북·윈도우별 버튼 설정 정리"],
                    ),
                    (
                        ["연결 끊김 줄이는 순서", "처음 세팅할 때 DPI 확인"],
                        ["연결 끊김 줄이는 세팅 순서", "처음 세팅할 때 DPI·휠 설정 정리"],
                    ),
                    (
                        ["유니파잉·블루투스 전환", "버튼 매핑과 감도 기준"],
                        ["유니파잉·블루투스 전환 정리", "버튼 매핑·감도 기준 정리"],
                    ),
                ],
                seed,
            )
        if use_product_rescue and setting_profile == "keyboard":
            return _rotate_rescue_pair(
                [
                    (
                        ["블루투스 연결과 멀티페어링", "맥북·윈도우별 키맵 설정"],
                        ["블루투스 연결·멀티페어링 정리", "맥북·윈도우별 키맵·한영 전환 정리"],
                    ),
                    (
                        ["입력 지연 줄이는 순서", "FN Lock·단축키 설정"],
                        ["입력 지연 줄이는 세팅 순서", "FN Lock·단축키·배열 설정 정리"],
                    ),
                    (
                        ["유선·블루투스 전환", "배열과 키감에 맞는 설정 기준"],
                        ["유선·블루투스 전환 정리", "배열·키감·키맵 설정 기준 정리"],
                    ),
                ],
                seed,
            )
        return _rotate_rescue_pair(
            [
                (
                    ["초기 설정 순서부터 정리", "실수 줄이는 확인 항목"],
                    ["초기 설정 순서와 확인 항목 정리", "실수 줄이는 설정 기준 정리"],
                ),
                (
                    ["처음 세팅할 때 볼 항목", "내게 맞는 설정 기준"],
                    ["처음 세팅할 때 볼 항목 정리", "내게 맞는 설정 기준 정리"],
                ),
                (
                    ["기본값과 사용자 설정 차이", "문제 줄이는 적용 순서"],
                    ["기본값과 사용자 설정 차이 정리", "문제 줄이는 적용 순서 정리"],
                ),
            ],
            seed,
        )

    if rescue_kind == "real_use":
        return _rotate_rescue_pair(
            [
                (
                    ["그립감과 무게 체감", "장시간 사용 차이"],
                    ["그립감·무게·버튼감 비교", "장시간 사용 기준으로 본 체감"],
                ),
                (
                    ["버튼감과 사용 피로", "업무용/게임용 체감"],
                    ["버튼감·사용 피로 비교", "업무용/게임용 기준으로 본 체감"],
                ),
                (
                    ["직접 써본 기준", "손에 남는 차이"],
                    ["직접 써본 기준 정리", "사용 환경별 체감 비교"],
                ),
            ],
            seed,
        ) if use_product_rescue else _rotate_rescue_pair(
            [
                (
                    ["장시간 사용 체감", "상황별 체감은 어땠나"],
                    ["장시간 사용 기준으로 본 체감", "상황별 체감 차이 정리"],
                ),
                (
                    ["사용 환경별 체감", "직접 써본 기준"],
                    ["사용 환경별 체감 비교", "직접 써본 기준 정리"],
                ),
                (
                    ["몸에 남는 차이", "생활 동선 체감"],
                    ["몸에 남는 차이 정리", "생활 동선 기준으로 본 체감"],
                ),
            ],
            seed,
        )

    if rescue_kind == "pros_cons":
        return _rotate_rescue_pair(
            [
                (
                    ["그립감과 아쉬운 점", "장시간 사용 기준"],
                    ["그립감과 아쉬운 점 정리", "장시간 사용 기준으로 본 장단점"],
                ),
                (
                    ["좋았던 점과 불편한 점", "누가 쓰면 맞을까"],
                    ["좋았던 점과 불편한 점 정리", "누가 쓰면 맞는지 기준 정리"],
                ),
                (
                    ["실사용 기준 장단점", "선택 전에 볼 포인트"],
                    ["실사용 기준 장단점 정리", "선택 전에 볼 포인트 정리"],
                ),
            ],
            seed,
        )

    if rescue_kind == "problem":
        return _rotate_rescue_pair(
            [
                (
                    ["원인부터 점검", "해결 순서 바로 보기"],
                    ["원인·해결·예방 정리", "증상별 점검 순서"],
                ),
                (
                    ["증상 먼저 구분하기", "재발 줄이는 점검 포인트"],
                    ["증상 구분부터 해결 순서 정리", "재발 줄이는 점검 포인트 정리"],
                ),
                (
                    ["증상별 원인 확인", "해결 전에 볼 체크포인트"],
                    ["증상별 원인과 해결 순서", "해결 전에 볼 체크포인트 정리"],
                ),
                (
                    ["자주 막히는 지점부터 보기", "문제 반복 막는 점검 순서"],
                    ["자주 막히는 지점과 해결 순서 정리", "문제 반복 막는 점검 순서 정리"],
                ),
                (
                    ["헷갈리는 증상부터 정리", "원인 찾기 전에 볼 포인트"],
                    ["헷갈리는 증상과 원인 찾는 순서", "원인 찾기 전에 볼 포인트 정리"],
                ),
            ],
            seed,
        )

    if rescue_kind == "single_product":
        return _rotate_rescue_pair(
            [
                (
                    ["실사용 장단점과 추천 대상", "가격대와 클릭감 차이"],
                    ["실사용 장단점과 추천 대상 정리", "가격대·클릭감·추천 대상 정리"],
                ),
                (
                    ["업무용·게임용 체감 차이", "무게와 버튼감 기준"],
                    ["업무용·게임용 체감 차이 정리", "무게·버튼감·추천 대상 정리"],
                ),
                (
                    ["배터리와 연결 안정성", "손 크기별 추천 대상"],
                    ["배터리·연결 안정성·추천 대상 정리", "손 크기별 체감과 선택 기준 정리"],
                ),
            ],
            seed,
        )

    if rescue_kind == "single_stay":
        return _rotate_rescue_pair(
            [
                (
                    ["위치·교통·추가요금", "객실·조식·취소 조건"],
                    ["위치·교통·추가요금 기준 정리", "객실·조식·취소 조건 정리"],
                ),
                (
                    ["역 거리와 체크인 동선", "주말 요금과 숨은 비용"],
                    ["역 거리·체크인 동선·후기 분포 정리", "주말 요금·숨은 비용·취소 조건 정리"],
                ),
                (
                    ["1박 예산과 포함 옵션", "후기보다 먼저 볼 기준"],
                    ["1박 예산·포함 옵션·추가요금 정리", "후기보다 먼저 볼 위치·교통 기준 정리"],
                ),
            ],
            seed,
        )

    if rescue_kind == "single_policy":
        return _rotate_rescue_pair(
            [
                (
                    ["조건과 제한부터 확인", "비용과 적용 대상 정리"],
                    ["조건·제한·적용 대상 정리", "비용·준비물·진행 순서 정리"],
                ),
                (
                    ["바뀐 점과 주의점", "신청 전에 볼 기준"],
                    ["바뀐 점·주의점·신청 기준 정리", "적용 대상·비용·제한 정리"],
                ),
                (
                    ["준비물과 진행 순서", "놓치기 쉬운 제한 조건"],
                    ["준비물·진행 순서·제한 조건 정리", "적용 대상·주의점·비용 정리"],
                ),
            ],
            seed,
        )

    return _rotate_rescue_pair(
        [
            (
                ["일정과 링크 확인", "실수 없이 진행하는 순서"],
                ["준비물과 신청 순서", "놓치기 쉬운 일정 체크"],
            ),
            (
                ["신청 순서부터 보기", "마감 전에 볼 포인트"],
                ["일정·링크·준비물 정리", "신청 전에 꼭 볼 체크"],
            ),
            (
                ["준비물부터 체크", "실수 줄이는 진행 순서"],
                ["준비물과 진행 순서 정리", "놓치기 쉬운 체크포인트 정리"],
            ),
        ],
        seed,
    )


def _resolve_practical_rescue_variant(keyword_key: str, *, rescue_kind: str) -> str:
    if not keyword_key:
        return ""
    if rescue_kind == "preorder":
        if any(pattern in keyword_key for pattern in ("전체크포인트", "체크포인트")):
            return "checkpoint"
        if any(pattern in keyword_key for pattern in ("예약방법", "신청방법", "방법")):
            return "how_to"
        return ""
    if rescue_kind in {"value", "setting"}:
        if any(pattern in keyword_key for pattern in ("기준", "조건")):
            return "criteria"
        if any(pattern in keyword_key for pattern in ("포인트", "체크포인트")):
            return "points"
    return ""


def _resolve_generic_single_rescue_kind(
    item: dict[str, Any],
    *,
    keyword: str,
    category: str,
) -> str:
    if normalize_key(item.get("target_mode")) != "single":
        return ""
    source_kind = normalize_key(item.get("source_kind"))
    source_selection_mode = normalize_key(item.get("source_selection_mode") or item.get("selection_mode"))
    if source_kind != "selectedkeyword" and source_selection_mode != "seedanchor":
        return ""

    keyword_key = normalize_key(keyword)
    if category == "product" or _looks_product_like_keyword(keyword):
        return "single_product"
    if category == "travel" or any(pattern in keyword_key for pattern in ("호텔", "숙소")):
        return "single_stay"
    if category in {"finance", "real_estate"}:
        return "single_policy"
    return ""


def _resolve_setting_rescue_profile(keyword_key: str) -> str:
    if any(pattern in keyword_key for pattern in _KEYBOARD_SETTING_KEY_PATTERNS):
        return "keyboard"
    if any(pattern in keyword_key for pattern in _MOUSE_SETTING_KEY_PATTERNS):
        return "mouse"
    return "generic"


def _rotate_rescue_pair(
    options: list[tuple[list[str], list[str]]],
    seed: int,
) -> tuple[list[str], list[str]]:
    if not options:
        return [], []
    index = seed % len(options)
    naver_home, blog = options[index]
    return list(naver_home), list(blog)


def _stable_rescue_seed(keyword: str) -> int:
    return sum((index + 1) * ord(character) for index, character in enumerate(keyword))


def _looks_product_like_keyword(keyword: str) -> bool:
    keyword_key = normalize_key(keyword)
    if not keyword_key:
        return False
    return any(pattern in keyword_key for pattern in _PRODUCT_RESCUE_KEY_PATTERNS)


def _resolve_finance_rescue_profile(keyword: str, *, category: str) -> str:
    if category != "finance":
        return ""
    keyword_key = normalize_key(keyword)
    if any(token in keyword_key for token in ("지수", "선물", "시세", "금시세", "금값", "코스피", "etf", "리밸런싱")):
        return "market"
    return "account"


def _resolve_finance_rescue_pair(
    *,
    rescue_kind: str,
    finance_profile: str,
    is_single_target: bool,
    seed: int,
) -> tuple[list[str], list[str]] | None:
    if finance_profile == "market":
        if rescue_kind in {"problem", "real_use"}:
            return _rotate_rescue_pair(
                [
                    (
                        ["왜 국내 시세와 다를까", "무엇을 같이 봐야 할까"],
                        ["국내외 흐름이 다르게 보이는 이유 정리", "같이 봐야 할 변수와 확인 포인트 정리"],
                    ),
                    (
                        ["어디서 반영 시차가 갈릴까", "환율이 먼저 흔드는 이유"],
                        ["체크할 기준선과 반영 시차 정리", "환율과 선물 흐름을 같이 보는 기준 정리"],
                    ),
                    (
                        ["표시 가격이 왜 다르게 보일까", "어느 지점이 확인 포인트일까"],
                        ["표시 가격과 체감이 다른 이유 정리", "확인 포인트와 업데이트 시간 정리"],
                    ),
                ],
                seed,
            )
        if rescue_kind == "single_policy" or is_single_target:
            return _rotate_rescue_pair(
                [
                    (
                        ["왜 국내 시세와 다를까", "무엇을 먼저 봐야 할까"],
                        ["같이 봐야 할 기준선과 변수 정리", "국내외 흐름이 다르게 보이는 이유 정리"],
                    ),
                    (
                        ["환율이 먼저 흔드는 이유", "어디서 체감이 달라질까"],
                        ["확인 포인트와 반영 시차 정리", "환율과 선물 흐름을 같이 보는 기준 정리"],
                    ),
                ],
                seed,
            )
        return None

    if rescue_kind in {"problem", "real_use"}:
        return _rotate_rescue_pair(
            [
                (
                    ["막히는 단계", "지연되는 이유"],
                    ["막히는 단계와 준비물 정리", "지연되는 이유와 확인할 조건 정리"],
                ),
                (
                    ["준비물", "비대면 개설 순서"],
                    ["준비물과 비대면 개설 순서 정리", "조건과 소요 시간 차이 정리"],
                ),
                (
                    ["조건 차이", "소요 시간 차이"],
                    ["조건 차이와 놓치기 쉬운 포인트 정리", "소요 시간과 지연 이유 정리"],
                ),
            ],
            seed,
        )
    if rescue_kind == "single_policy" or is_single_target:
        return _rotate_rescue_pair(
            [
                (
                    ["개설 전 확인할 조건", "준비물과 소요 시간"],
                    ["개설 전 확인할 조건과 준비물 정리", "비대면 개설 순서와 소요 시간 정리"],
                ),
                (
                    ["혜택 차이", "지연되는 이유"],
                    ["혜택 차이와 선택 기준 정리", "지연되는 이유와 놓치기 쉬운 조건 정리"],
                ),
            ],
            seed,
        )
    return None


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
    attempted_slot_count: int = 0,
    accepted_slot_count: int = 0,
    rewrite_call_count: int = 0,
    rewrite_batch_sizes: list[int] | None = None,
    downgraded_slot_ids: list[str] | None = None,
    remaining_retry_count: int = 0,
    error_messages: list[str] | None = None,
    retry_threshold: int = _DEFAULT_QUALITY_RETRY_THRESHOLD,
    provider: str = "",
    model: str = "",
    max_slot_rewrite_attempts: int = _MAX_SLOT_REWRITE_ATTEMPTS,
) -> dict[str, Any]:
    attempted_keywords = attempted_keywords or []
    accepted_keywords = accepted_keywords or []
    error_messages = error_messages or []
    rewrite_batch_sizes = rewrite_batch_sizes or []
    downgraded_slot_ids = downgraded_slot_ids or []
    return {
        "attempted_count": len(attempted_keywords),
        "attempted_keywords": attempted_keywords,
        "accepted_count": len(accepted_keywords),
        "accepted_keywords": accepted_keywords,
        "bad_slot_count": max(0, int(attempted_slot_count or 0)),
        "attempted_slot_count": max(0, int(attempted_slot_count or 0)),
        "accepted_slot_count": max(0, int(accepted_slot_count or 0)),
        "rewrite_call_count": max(0, int(rewrite_call_count or 0)),
        "rewrite_batch_sizes": [max(0, int(size or 0)) for size in rewrite_batch_sizes],
        "downgraded_slot_count": len(downgraded_slot_ids),
        "downgraded_slot_ids": downgraded_slot_ids,
        "remaining_retry_count": remaining_retry_count,
        "error_messages": error_messages[:3],
        "retry_threshold": retry_threshold,
        "provider": str(provider or "").strip(),
        "model": str(model or "").strip(),
        "max_slot_rewrite_attempts": max(1, int(max_slot_rewrite_attempts or _MAX_SLOT_REWRITE_ATTEMPTS)),
    }


def _build_model_escalation_meta(
    *,
    enabled: bool,
    trigger_failure_count: int,
    triggered: bool = False,
    source_provider: str = "",
    source_model: str = "",
    target_provider: str = "",
    target_model: str = "",
    attempted_keywords: list[str] | None = None,
    accepted_keywords: list[str] | None = None,
    attempted_slot_count: int = 0,
    accepted_slot_count: int = 0,
    rewrite_call_count: int = 0,
    rewrite_batch_sizes: list[int] | None = None,
    downgraded_slot_ids: list[str] | None = None,
    remaining_retry_count: int = 0,
    error_messages: list[str] | None = None,
    max_slot_rewrite_attempts: int = _MAX_SLOT_REWRITE_ATTEMPTS,
) -> dict[str, Any]:
    attempted_keywords = attempted_keywords or []
    accepted_keywords = accepted_keywords or []
    error_messages = error_messages or []
    rewrite_batch_sizes = rewrite_batch_sizes or []
    downgraded_slot_ids = downgraded_slot_ids or []
    return {
        "enabled": enabled,
        "trigger_failure_count": max(1, int(trigger_failure_count or _MODEL_ESCALATION_TRIGGER_FAILURES)),
        "triggered": triggered,
        "source_provider": str(source_provider or "").strip(),
        "source_model": str(source_model or "").strip(),
        "target_provider": str(target_provider or "").strip(),
        "target_model": str(target_model or "").strip(),
        "attempted_count": len(attempted_keywords),
        "attempted_keywords": attempted_keywords,
        "accepted_count": len(accepted_keywords),
        "accepted_keywords": accepted_keywords,
        "bad_slot_count": max(0, int(attempted_slot_count or 0)),
        "attempted_slot_count": max(0, int(attempted_slot_count or 0)),
        "accepted_slot_count": max(0, int(accepted_slot_count or 0)),
        "rewrite_call_count": max(0, int(rewrite_call_count or 0)),
        "rewrite_batch_sizes": [max(0, int(size or 0)) for size in rewrite_batch_sizes],
        "downgraded_slot_count": len(downgraded_slot_ids),
        "downgraded_slot_ids": downgraded_slot_ids,
        "remaining_retry_count": remaining_retry_count,
        "error_messages": error_messages[:3],
        "max_slot_rewrite_attempts": max(1, int(max_slot_rewrite_attempts or _MAX_SLOT_REWRITE_ATTEMPTS)),
    }


def _merge_retry_candidates(
    *,
    current_results: list[TitleOutputItem],
    current_enriched_results: list[TitleOutputItem],
    retry_candidates: dict[str, TitleOutputItem],
    evaluation_options: TitleEvaluationOptions | None = None,
) -> tuple[list[TitleOutputItem], list[str]]:
    current_report_by_keyword = {
        normalize_text(item.get("keyword")): item.get("quality_report", {})
        for item in current_enriched_results
        if normalize_text(item.get("keyword"))
    }

    accepted_keywords: list[str] = []
    merged_results: list[TitleOutputItem] = []
    retry_slots: list[tuple[str, TitleOutputItem]] = []

    for item in current_results:
        keyword = normalize_text(item.get("keyword"))
        retry_item = retry_candidates.get(keyword)
        if retry_item:
            retry_slots.append((keyword, retry_item))

    retry_reports_by_keyword: dict[str, dict[str, Any]] = {}
    if retry_slots:
        retried_enriched_items, _ = enrich_title_results(
            [retry_item for _, retry_item in retry_slots],
            evaluation_options=evaluation_options,
        )
        for (keyword, _), retried_candidate in zip(retry_slots, retried_enriched_items):
            retry_reports_by_keyword[keyword] = retried_candidate.get("quality_report", {})

    for item in current_results:
        keyword = normalize_text(item.get("keyword"))
        retry_item = retry_candidates.get(keyword)
        if not retry_item:
            merged_results.append(item)
            continue

        current_report = current_report_by_keyword.get(keyword, {})
        retry_report = retry_reports_by_keyword.get(keyword, {})

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
    *,
    progress_callback: TitleProgressCallback | None = None,
) -> tuple[dict[str, TitleOutputItem], list[str]]:
    retried_by_keyword: dict[str, TitleOutputItem] = {}
    retry_error_messages: list[str] = []
    processed_count = 0
    retry_input_items = [
        {
            **_strip_generated_fields(original_items_by_keyword.get(keyword, {"keyword": keyword})),
            "keyword": keyword,
        }
        for keyword in retry_keywords
    ]

    for chunk in _chunk_keywords(retry_input_items, retry_options.batch_size):
        try:
            response_items = _request_ai_titles_with_chunk_retry(
                chunk,
                options=retry_options,
            )
        except TitleProviderError as exc:
            retry_error_messages.append(str(exc))
            continue

        aligned_response_items = _align_response_items_to_chunk(chunk, response_items)
        for item in aligned_response_items:
            keyword = normalize_text(item.get("keyword"))
            titles = item.get("titles") if isinstance(item, dict) else None
            if not keyword or not _is_valid_title_bundle(titles, options=retry_options):
                continue
            source_item = original_items_by_keyword.get(keyword, {"keyword": keyword})
            retried_by_keyword[keyword] = {
                **_strip_generated_fields(source_item),
                "keyword": keyword,
                "titles": _normalize_generated_title_bundle(titles, options=retry_options),
            }
        processed_count = min(len(retry_keywords), processed_count + len(chunk))
        _publish_title_progress(
            progress_callback,
            type="phase",
            phase="model_escalation",
            processed_count=processed_count,
            total_count=len(retry_keywords),
            progress_percent=_compute_phase_progress(
                processed_count,
                len(retry_keywords),
                start=_MODEL_ESCALATION_PROGRESS_START,
                end=_MODEL_ESCALATION_PROGRESS_END,
            ),
            message=f"상위 모델 재시도 중: {processed_count} / {len(retry_keywords)}건",
        )

    return retried_by_keyword, retry_error_messages


def _build_retry_request_options(
    options: TitleGenerationOptions,
    retry_threshold: int,
) -> TitleGenerationOptions:
    retry_provider = normalize_text(options.rewrite_provider) or options.provider
    retry_model = normalize_text(options.rewrite_model) or options.model
    retry_api_key = options.rewrite_api_key or options.api_key
    retry_reasoning_effort = normalize_text(options.rewrite_reasoning_effort) or options.reasoning_effort
    return replace(
        options,
        provider=retry_provider,
        model=retry_model,
        api_key=retry_api_key,
        reasoning_effort=retry_reasoning_effort,
        batch_size=_resolve_generation_batch_size(
            replace(
                options,
                provider=retry_provider,
                model=retry_model,
                api_key=retry_api_key,
                reasoning_effort=retry_reasoning_effort,
            )
        ),
        system_prompt=_build_quality_retry_prompt(options.system_prompt, retry_threshold),
    )


def _build_model_escalation_options(
    options: TitleGenerationOptions,
    retry_threshold: int,
    *,
    prompt_source: str | None = None,
) -> TitleGenerationOptions | None:
    escalated_model = _resolve_escalated_model(options.provider, options.model)
    if not escalated_model:
        return None
    escalated_options = replace(
        options,
        model=escalated_model,
        system_prompt=_build_model_escalation_prompt(
            options.system_prompt if prompt_source is None else prompt_source,
            retry_threshold,
        ),
    )
    return replace(
        escalated_options,
        batch_size=_resolve_generation_batch_size(escalated_options),
    )


def _resolve_escalated_model(provider: str, model: str) -> str:
    normalized_provider = str(provider or "").strip().lower()
    normalized_model = normalize_text(model)
    provider_map = _MODEL_ESCALATION_MAP.get(normalized_provider, {})
    return str(provider_map.get(normalized_model, "")).strip()


def _resolve_quality_retry_threshold(value: int | float | None) -> int:
    try:
        number = int(value or _DEFAULT_QUALITY_RETRY_THRESHOLD)
    except (TypeError, ValueError):
        return _DEFAULT_QUALITY_RETRY_THRESHOLD
    return max(70, min(100, number))


def _build_title_evaluation_options(
    options: TitleGenerationOptions | None,
) -> TitleEvaluationOptions:
    if options is None:
        return TitleEvaluationOptions()

    evaluation_provider = normalize_text(options.rewrite_provider) or options.provider
    evaluation_model = normalize_text(options.rewrite_model) or options.model
    evaluation_api_key = options.rewrite_api_key or options.api_key
    evaluation_reasoning_effort = normalize_text(options.rewrite_reasoning_effort) or options.reasoning_effort
    return TitleEvaluationOptions(
        provider=evaluation_provider,
        model=evaluation_model,
        api_key=evaluation_api_key,
        reasoning_effort=evaluation_reasoning_effort,
        system_prompt=normalize_text(options.quality_system_prompt),
        batch_size=max(1, min(options.batch_size, 20)),
        sample_ratio=_DEFAULT_HOME_AI_EVALUATION_SAMPLE_RATIO,
        max_sampled_items=_DEFAULT_HOME_AI_EVALUATION_MAX_ITEMS,
    )


def _compute_weighted_progress(processed_count: int, total_count: int, *, cap: int) -> int:
    if total_count <= 0:
        return 0
    return min(cap, round((processed_count / total_count) * cap))


def _compute_phase_progress(processed_count: int, total_count: int, *, start: int, end: int) -> int:
    if total_count <= 0:
        return end
    width = max(0, end - start)
    return min(end, start + round((processed_count / total_count) * width))


def _publish_title_progress(progress_callback: TitleProgressCallback | None, **payload: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(payload)


def _build_meta(
    *,
    requested_mode: str,
    used_mode: str,
    provider: str | None = None,
    model: str | None = None,
    rewrite_provider: str | None = None,
    rewrite_model: str | None = None,
    temperature: float | None = None,
    preset_key: str = "",
    preset_label: str = "",
    fallback_reason: str = "",
    fallback_keywords: list[str] | None = None,
    auto_retry_enabled: bool = False,
    quality_retry_threshold: int = _DEFAULT_QUALITY_RETRY_THRESHOLD,
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
        "rewrite_provider": rewrite_provider,
        "rewrite_model": rewrite_model,
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
