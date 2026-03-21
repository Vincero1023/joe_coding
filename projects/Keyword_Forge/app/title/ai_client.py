from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.expander.utils.tokenizer import normalize_text
from app.title.quality import TITLE_QUALITY_PASS_SCORE
from app.title.presets import get_title_preset
from app.title.rules import NAVER_HOME_MAX_LENGTH


_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash-lite",
    "anthropic": "claude-haiku-4-5",
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are a Korean SEO title generator for Naver-focused content.\n"
    "Return strict JSON only.\n"
    "Preserve each keyword exactly.\n"
    "For every keyword, generate exactly 2 naver_home titles and 2 blog titles.\n"
    f"Each naver_home title must be {NAVER_HOME_MAX_LENGTH} characters or fewer.\n"
    "Write natural Korean titles that sound like a real editor wrote them.\n"
    "Keep the keyword near the front unless it becomes awkward.\n"
    "The 2 naver_home titles for the same keyword must use clearly different framing.\n"
    "The 2 blog titles for the same keyword must use clearly different framing.\n"
    "Across the whole batch, avoid repeating the same headline skeleton.\n"
    "Reflect the search intent in the wording: price, review, comparison, reservation, profile, location, how-to, or guide.\n"
    "Avoid generic template phrases such as '완벽 정리', '한 번에 정리', '갑자기 바뀌었다', '이유가 이상하다', '놓치면 손해' unless they are truly necessary.\n"
    "Avoid clickbait, exaggerated fear, and empty filler.\n"
    "Do not include markdown, commentary, or code fences."
)


class TitleProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class TitleGenerationOptions:
    mode: str = "template"
    provider: str = "openai"
    api_key: str | None = None
    model: str = _DEFAULT_MODELS["openai"]
    temperature: float = 0.7
    max_output_tokens: int = 1200
    batch_size: int = 8
    fallback_to_template: bool = True
    system_prompt: str = ""
    preset_key: str = ""
    preset_label: str = ""
    preset_prompt: str = ""
    auto_retry_enabled: bool = True
    quality_retry_threshold: int = TITLE_QUALITY_PASS_SCORE

    @classmethod
    def from_input(cls, input_data: Any) -> "TitleGenerationOptions":
        raw = input_data.get("title_options") if isinstance(input_data, dict) else {}
        if not isinstance(raw, dict):
            raw = {}

        preset = get_title_preset(raw.get("preset_key") or raw.get("preset"))
        provider = _normalize_provider(raw.get("provider") or (preset.provider if preset else None))
        mode = "ai" if str(raw.get("mode") or "").strip().lower() == "ai" else "template"
        model = normalize_text(raw.get("model")) or (preset.model if preset else _DEFAULT_MODELS[provider])
        temperature = _coerce_float(
            raw.get("temperature"),
            default=float(preset.temperature if preset else 0.7),
            minimum=0.0,
            maximum=1.5,
        )
        max_output_tokens = _coerce_int(raw.get("max_output_tokens"), default=1200, minimum=200, maximum=4000)
        batch_size = _coerce_int(raw.get("batch_size"), default=8, minimum=1, maximum=20)

        return cls(
            mode=mode,
            provider=provider,
            api_key=normalize_text(raw.get("api_key")) or None,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            batch_size=batch_size,
            fallback_to_template=bool(raw.get("fallback_to_template", True)),
            system_prompt=normalize_text(raw.get("system_prompt")) or "",
            preset_key=preset.key if preset else "",
            preset_label=preset.label if preset else "",
            preset_prompt=preset.prompt_guidance if preset else "",
            auto_retry_enabled=bool(raw.get("auto_retry_enabled", True)),
            quality_retry_threshold=_coerce_int(
                raw.get("quality_retry_threshold"),
                default=TITLE_QUALITY_PASS_SCORE,
                minimum=70,
                maximum=100,
            ),
        )

    @property
    def effective_system_prompt(self) -> str:
        prompt_sections = [_DEFAULT_SYSTEM_PROMPT]
        preset_prompt = normalize_text(self.preset_prompt)
        extra_prompt = normalize_text(self.system_prompt)
        if preset_prompt:
            prompt_sections.append(f"Preset guidance:\n{preset_prompt}")
        if extra_prompt:
            prompt_sections.append(f"Additional guidance:\n{extra_prompt}")
        return "\n\n".join(prompt_sections)


def request_ai_titles(
    keywords: list[str],
    options: TitleGenerationOptions,
) -> list[dict[str, Any]]:
    if not keywords:
        return []

    if not options.api_key:
        raise TitleProviderError("AI mode requires an API key.")

    prompt = _build_user_prompt(keywords)
    if options.provider == "openai":
        return _request_openai_titles(prompt, options)
    if options.provider == "gemini":
        return _request_gemini_titles(prompt, options)
    if options.provider == "anthropic":
        return _request_anthropic_titles(prompt, options)

    raise TitleProviderError(f"Unsupported provider: {options.provider}")


def _request_openai_titles(prompt: str, options: TitleGenerationOptions) -> list[dict[str, Any]]:
    payload = {
        "model": options.model,
        "messages": [
            {"role": "system", "content": options.effective_system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": options.temperature,
        "max_tokens": options.max_output_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {options.api_key}",
        "Content-Type": "application/json",
    }
    response = _post_json(_OPENAI_URL, headers, payload)
    content = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return _parse_title_items(content)


def _request_gemini_titles(prompt: str, options: TitleGenerationOptions) -> list[dict[str, Any]]:
    payload = {
        "systemInstruction": {
            "parts": [{"text": options.effective_system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": options.temperature,
            "responseMimeType": "application/json",
            "maxOutputTokens": options.max_output_tokens,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": options.api_key or "",
    }
    url = _GEMINI_URL_TEMPLATE.format(model=options.model)
    response = _post_json(url, headers, payload)
    parts = (
        response.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    content = "\n".join(
        normalize_text(part.get("text"))
        for part in parts
        if isinstance(part, dict) and normalize_text(part.get("text"))
    )
    return _parse_title_items(content)


def _request_anthropic_titles(prompt: str, options: TitleGenerationOptions) -> list[dict[str, Any]]:
    payload = {
        "model": options.model,
        "system": options.effective_system_prompt,
        "max_tokens": options.max_output_tokens,
        "temperature": options.temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": options.api_key or "",
        "anthropic-version": "2023-06-01",
    }
    response = _post_json(_ANTHROPIC_URL, headers, payload)
    content_items = response.get("content", [])
    content = "\n".join(
        normalize_text(item.get("text"))
        for item in content_items
        if isinstance(item, dict) and normalize_text(item.get("text"))
    )
    return _parse_title_items(content)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url=url,
        headers=headers,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )

    try:
        with urlopen(request, timeout=30.0) as response:
            raw_text = response.read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        raw_text = exc.read().decode("utf-8", errors="ignore")
        detail = _extract_error_message(raw_text) or raw_text or exc.reason
        raise TitleProviderError(f"{exc.code} {detail}") from exc
    except URLError as exc:
        raise TitleProviderError(str(exc.reason)) from exc
    except Exception as exc:  # pragma: no cover - network runtime guard
        raise TitleProviderError(str(exc)) from exc

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise TitleProviderError("Provider returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise TitleProviderError("Provider returned an unexpected payload.")
    return parsed


def _build_user_prompt(keywords: list[str]) -> str:
    keyword_lines = "\n".join(f"- {keyword}" for keyword in keywords)
    return (
        "Generate titles for the following Korean keywords.\n\n"
        "Return JSON in this exact shape:\n"
        '{\n'
        '  "items": [\n'
        '    {\n'
        '      "keyword": "보험 추천",\n'
        '      "naver_home": ["...", "..."],\n'
        '      "blog": ["...", "..."]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Preserve each keyword exactly.\n"
        "- Write all titles in Korean.\n"
        "- naver_home and blog must each contain exactly 2 items.\n"
        "- Avoid duplicate titles within the same keyword.\n"
        "- Avoid using the same sentence frame repeatedly across keywords.\n"
        "- Make the 2 naver_home titles differ in angle such as comparison, checklist, question, update, or decision point.\n"
        "- Make the 2 blog titles differ in angle such as guide, FAQ, checklist, comparison, or practical tips.\n"
        "- Prefer specific wording that matches the keyword intent instead of generic SEO filler.\n"
        "- Avoid stale patterns like '<keyword> 완벽 정리', '<keyword> 비교 및 선택 기준 정리', or '<time> <keyword> 갑자기 바뀌었다'.\n\n"
        f"Keywords:\n{keyword_lines}"
    )


def _parse_title_items(content: str) -> list[dict[str, Any]]:
    normalized = normalize_text(content)
    if not normalized:
        raise TitleProviderError("Provider returned empty content.")

    parsed = _extract_json_object(normalized)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        raise TitleProviderError("Provider JSON must include an items array.")

    normalized_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue
        normalized_items.append(
            {
                "keyword": keyword,
                "titles": {
                    "naver_home": _normalize_title_list(item.get("naver_home"), NAVER_HOME_MAX_LENGTH),
                    "blog": _normalize_title_list(item.get("blog")),
                },
            }
        )

    return normalized_items


def _extract_json_object(content: str) -> Any:
    fenced = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    start_index = min(
        [index for index in (content.find("{"), content.find("[")) if index >= 0],
        default=-1,
    )
    if start_index < 0:
        raise TitleProviderError("Provider response did not contain JSON.")

    for end_index in range(len(content), start_index, -1):
        candidate = content[start_index:end_index].strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise TitleProviderError("Provider response contained invalid JSON.")


def _normalize_title_list(raw_titles: Any, max_length: int | None = None) -> list[str]:
    if not isinstance(raw_titles, list):
        return []

    normalized_titles: list[str] = []
    seen: set[str] = set()
    for raw_title in raw_titles:
        title = normalize_text(raw_title).replace(":", "")
        if not title:
            continue
        if max_length is not None and len(title) > max_length:
            title = title[:max_length].rstrip()
        if not title or title in seen:
            continue
        seen.add(title)
        normalized_titles.append(title)
    return normalized_titles[:2]


def _extract_error_message(raw_text: str) -> str:
    if not raw_text:
        return ""

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return ""

    if not isinstance(parsed, dict):
        return ""

    error = parsed.get("error")
    if isinstance(error, dict):
        message = normalize_text(error.get("message"))
        if message:
            return message

    message = normalize_text(parsed.get("message"))
    return message


def _normalize_provider(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _DEFAULT_MODELS:
        return normalized
    return "openai"


def _coerce_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    return max(minimum, min(maximum, number))


def _coerce_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default

    return max(minimum, min(maximum, number))
