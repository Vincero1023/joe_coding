from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text
from app.title.ai_client import TitleGenerationOptions, TitleProviderError, request_ai_titles
from app.title.category_detector import detect_category
from app.title.templates import build_blog_titles, build_naver_home_titles
from app.title.types import TitleOutputItem


def generate_titles(
    items: list[dict[str, Any]],
    options: TitleGenerationOptions | None = None,
) -> tuple[list[TitleOutputItem], dict[str, Any]]:
    normalized_items = _normalize_input_items(items)
    if options is None or options.mode != "ai":
        return _build_template_results(normalized_items), _build_meta(
            requested_mode=options.mode if options else "template",
            used_mode="template",
        )

    if not options.api_key:
        if not options.fallback_to_template:
            raise TitleProviderError("AI mode requires an API key.")
        return _build_template_results(normalized_items), _build_meta(
            requested_mode="ai",
            used_mode="template_fallback",
            provider=options.provider,
            model=options.model,
            fallback_reason="missing_api_key",
        )

    ai_results: dict[str, TitleOutputItem] = {}
    fallback_keywords: list[str] = []

    try:
        for chunk in _chunk_keywords(normalized_items, options.batch_size):
            response_items = request_ai_titles(
                [item["keyword"] for item in chunk],
                options=options,
            )
            for item in response_items:
                keyword = normalize_text(item.get("keyword"))
                titles = item.get("titles") if isinstance(item, dict) else None
                if not keyword or not _is_valid_title_bundle(titles):
                    continue
                ai_results[keyword] = {
                    "keyword": keyword,
                    "titles": {
                        "naver_home": list(titles["naver_home"]),
                        "blog": list(titles["blog"]),
                    },
                }
    except TitleProviderError as exc:
        if not options.fallback_to_template:
            raise
        return _build_template_results(normalized_items), _build_meta(
            requested_mode="ai",
            used_mode="template_fallback",
            provider=options.provider,
            model=options.model,
            fallback_reason=str(exc),
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

    return results, _build_meta(
        requested_mode="ai",
        used_mode=used_mode,
        provider=options.provider,
        model=options.model,
        fallback_reason=", ".join(fallback_keywords[:10]) if fallback_keywords else "",
        fallback_keywords=fallback_keywords,
    )


def _normalize_input_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized_items: list[dict[str, str]] = []

    for item in items:
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue
        normalized_items.append({"keyword": keyword})

    return normalized_items


def _build_template_results(items: list[dict[str, str]]) -> list[TitleOutputItem]:
    return [_build_template_title_item(item["keyword"]) for item in items]


def _build_template_title_item(keyword: str) -> TitleOutputItem:
    category = detect_category(keyword)
    return {
        "keyword": keyword,
        "titles": {
            "naver_home": build_naver_home_titles(keyword, category),
            "blog": build_blog_titles(keyword, category),
        },
    }


def _chunk_keywords(items: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


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


def _build_meta(
    *,
    requested_mode: str,
    used_mode: str,
    provider: str | None = None,
    model: str | None = None,
    fallback_reason: str = "",
    fallback_keywords: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requested_mode": requested_mode,
        "used_mode": used_mode,
        "provider": provider,
        "model": model,
        "fallback_reason": fallback_reason,
        "fallback_keywords": fallback_keywords or [],
    }
