from __future__ import annotations

import json
from typing import Any

from app.expander.utils.tokenizer import normalize_text
from app.title.ai_client import (
    _ANTHROPIC_URL,
    _GEMINI_URL_TEMPLATE,
    _OPENAI_URL,
    _VERTEX_EXPRESS_URL_TEMPLATE,
    _extract_gemini_like_text,
    _post_json,
    TitleGenerationOptions,
    TitleProviderError,
)


_TOPIC_INTENT_LABELS = {
    "balanced": "균형형",
    "need": "정보형",
    "profit": "수익형",
}

_TOPIC_INTENT_GUIDANCE = {
    "balanced": (
        "Mix helpful information queries, comparison queries, and realistic purchase-intent queries. "
        "Do not skew too hard toward one side."
    ),
    "need": (
        "Prioritize problem-solving, checklist, how-to, setup, maintenance, and decision-support queries "
        "that could become useful blog posts even when monetization is low."
    ),
    "profit": (
        "Prioritize commercial intent, comparison, review, price, ranking, and purchase-decision queries, "
        "while keeping them realistic and not overly spammy."
    ),
}


def generate_topic_seed_keywords(input_data: Any) -> dict[str, Any]:
    if not isinstance(input_data, dict):
        raise ValueError("주제 시드 입력 형식이 올바르지 않습니다.")

    topic = normalize_text(input_data.get("topic"))
    if not topic:
        raise ValueError("주제를 입력해 주세요.")

    requested_count = _coerce_int(input_data.get("count"), default=12, minimum=3, maximum=30)
    intent = _normalize_intent(input_data.get("intent"))
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                **(input_data.get("title_options") if isinstance(input_data.get("title_options"), dict) else {}),
                "mode": "ai",
            }
        }
    )
    if not options.api_key:
        raise TitleProviderError("주제 시드를 만들려면 먼저 AI API를 등록해 주세요.")

    content = _request_seed_keywords(topic, requested_count, intent, options)
    return {
        "topic": topic,
        "intent": intent,
        "intent_label": _TOPIC_INTENT_LABELS[intent],
        "provider": options.provider,
        "model": options.model,
        "seed_keywords": _parse_seed_keywords(content, requested_count),
    }


def _request_seed_keywords(
    topic: str,
    requested_count: int,
    intent: str,
    options: TitleGenerationOptions,
) -> str:
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(topic, requested_count, intent)

    if options.provider == "openai":
        payload = {
            "model": options.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": options.temperature,
            "max_tokens": 900,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {options.api_key}",
            "Content-Type": "application/json",
        }
        response = _post_json(_OPENAI_URL, headers, payload)
        return (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

    if options.provider in {"gemini", "vertex"}:
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": options.temperature,
                "responseMimeType": "application/json",
                "maxOutputTokens": 900,
            },
        }
        headers = {"Content-Type": "application/json"}
        if options.provider == "gemini":
            headers["x-goog-api-key"] = options.api_key or ""
            url = _GEMINI_URL_TEMPLATE.format(model=options.model)
        else:
            url = _VERTEX_EXPRESS_URL_TEMPLATE.format(model=options.model, api_key=options.api_key or "")
        response = _post_json(url, headers, payload, max_retries=2)
        return _extract_gemini_like_text(response)

    if options.provider == "anthropic":
        payload = {
            "model": options.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": options.temperature,
            "max_tokens": 900,
        }
        headers = {
            "x-api-key": options.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        response = _post_json(_ANTHROPIC_URL, headers, payload)
        content_blocks = response.get("content", [])
        if not isinstance(content_blocks, list):
            raise TitleProviderError("Anthropic 응답 형식이 올바르지 않습니다.")
        return "\n".join(
            normalize_text(block.get("text"))
            for block in content_blocks
            if isinstance(block, dict) and normalize_text(block.get("text"))
        )

    raise TitleProviderError(f"지원하지 않는 provider입니다: {options.provider}")


def _build_system_prompt() -> str:
    return (
        "You are a Korean keyword seed strategist for Naver-focused content planning.\n"
        "Return strict JSON only.\n"
        "Do not write article titles.\n"
        "Create realistic search seed keywords that can be used as starting queries for expansion.\n"
        "Each keyword should usually be 2 to 5 Korean words.\n"
        "Avoid clickbait, fake freshness, and unsupported facts.\n"
        "Prefer phrases a Korean user might actually type into Naver search.\n"
        'Return JSON in this exact shape: {"seed_keywords":["...", "..."]}'
    )


def _build_user_prompt(topic: str, requested_count: int, intent: str) -> str:
    return (
        "Generate Korean keyword seed suggestions.\n\n"
        f"Topic: {topic}\n"
        f"Intent mode: {_TOPIC_INTENT_LABELS[intent]}\n"
        f"Need: {requested_count} keywords\n\n"
        "Rules:\n"
        f"- {_TOPIC_INTENT_GUIDANCE[intent]}\n"
        "- Keep them broad enough to expand, but specific enough to start a content search workflow.\n"
        "- Include a mix of core head terms and workable longtail-style seed phrases.\n"
        "- Avoid repeating the same ending word over and over.\n"
        "- Avoid dates unless the topic itself requires dates.\n"
        "- Avoid punctuation-heavy phrases.\n"
        "- Every output must be in Korean.\n"
        "- Deduplicate near-identical variants.\n"
    )


def _parse_seed_keywords(content: str, requested_count: int) -> list[str]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TitleProviderError("주제 시드 응답이 JSON 형식이 아닙니다.") from exc

    if not isinstance(parsed, dict):
        raise TitleProviderError("주제 시드 응답 형식이 올바르지 않습니다.")

    raw_keywords = parsed.get("seed_keywords")
    if not isinstance(raw_keywords, list):
        raise TitleProviderError("주제 시드 목록을 찾지 못했습니다.")

    seen = set()
    output: list[str] = []
    for raw_keyword in raw_keywords:
        keyword = normalize_text(raw_keyword)
        lookup_key = keyword.lower()
        if not keyword or lookup_key in seen:
            continue
        seen.add(lookup_key)
        output.append(keyword)
        if len(output) >= requested_count:
            break

    if not output:
        raise TitleProviderError("주제에서 사용할 시드를 만들지 못했습니다.")
    return output


def _normalize_intent(value: Any) -> str:
    normalized = normalize_text(value).lower()
    return normalized if normalized in _TOPIC_INTENT_LABELS else "balanced"


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))
