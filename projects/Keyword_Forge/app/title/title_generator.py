from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text
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
    retry_results, retry_enriched_results, quality_summary, accepted_rescue_keywords = _apply_practical_rescue_candidates(
        current_results=retry_results,
        current_enriched_results=retry_enriched_results,
        original_items_by_keyword=original_items_by_keyword,
        retry_threshold=retry_threshold,
    )
    auto_retry_meta = _build_auto_retry_meta(
        attempted_keywords=retry_keywords,
        accepted_keywords=accepted_retry_keywords + accepted_rescue_keywords,
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
    if bool(report.get("recommended_pair_ready")):
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
        "- Keep the home-feed pair issue-aware: usually make one title issue/update + comparison/debate and the other title issue/update + reversal/question.\n"
        "- Make the 2 naver_home titles clearly different from each other.\n"
        "- Make the 2 blog titles clearly different from each other.\n"
        f"- Keep every naver_home title within {NAVER_HOME_MAX_LENGTH} characters.\n"
        "- Avoid exaggerated words such as 무조건, 충격, 레전드, 미쳤다, 대박.\n"
        "- Do not invent unsupported dates, numbers, rankings, or official changes just to sound current.\n"
        "- Avoid stale filler such as 완벽 정리, 한 번에 정리, 갑자기 바뀌었다, 이유가 이상하다, 놓치면 손해.\n"
        "- Across the same retry batch, do not keep reusing skeletons such as 뭐가 다를까, 체크리스트, 고를 때, 추천 기준, or 비교 포인트.\n"
        "- Do not use low-information endings such as 최신 정보, 업데이트 확인, 왜 인기, 이것만 알면, 구매 가이드, 사용 후기, 신상, or a bare 비교.\n"
        "- If the keyword already carries concrete intent such as 실사용 차이, 장단점, 설정 팁, 연결 방법, 연결 문제, or 자주 생기는 문제, do not wrap it with 최신 비교 분석, 총정리, 완벽 가이드, 최신 정보, 이것만 알면, or 꼭 알아두세요.\n"
        "- For real-use keywords, prefer timeframe, user type, grip, weight, click feel, battery, workflow, or device-fit nouns.\n"
        "- For setup or problem keywords, prefer one symptom plus one cause, fix, result, or environment such as 맥북, 윈도우, 블루투스, 유니파잉, 연결 끊김, 더블클릭, or 인식 안됨.\n"
        "- Replace abstract meta words with concrete difference, use-case, fit, pain point, setup, price, or performance nouns.\n"
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
) -> tuple[list[TitleOutputItem], list[TitleOutputItem], dict[str, Any], list[str]]:
    rescue_keywords = [
        normalize_text(item.get("keyword"))
        for item in current_enriched_results
        if _should_retry_for_quality(item.get("quality_report", {}), retry_threshold)
    ]
    rescue_keywords = [keyword for keyword in rescue_keywords if keyword]
    if not rescue_keywords:
        quality_summary = _build_quality_summary_from_items(current_enriched_results)
        return current_results, current_enriched_results, quality_summary, []

    rescue_candidates: dict[str, TitleOutputItem] = {}
    for keyword in rescue_keywords:
        source_item = original_items_by_keyword.get(keyword, {"keyword": keyword})
        rescue_item = _build_practical_rescue_item(source_item)
        if rescue_item:
            rescue_candidates[keyword] = rescue_item

    if not rescue_candidates:
        quality_summary = _build_quality_summary_from_items(current_enriched_results)
        return current_results, current_enriched_results, quality_summary, []

    rescued_results, accepted_rescue_keywords = _merge_retry_candidates(
        current_results=current_results,
        current_enriched_results=current_enriched_results,
        retry_candidates=rescue_candidates,
    )
    rescued_enriched_results, quality_summary = enrich_title_results(rescued_results)
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
    return {
        **_strip_generated_fields(item),
        "keyword": keyword,
        "titles": {
            "naver_home": [f"{keyword}, {suffix}" for suffix in naver_suffixes[:2]],
            "blog": [f"{keyword} {suffix}" for suffix in blog_suffixes[:2]],
        },
    }


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
