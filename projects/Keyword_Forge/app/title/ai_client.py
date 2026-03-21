from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.selector.serp_summary import build_search_url, fetch_naver_serp_html, parse_serp_titles
from app.title.category_detector import detect_category
from app.title.quality import TITLE_QUALITY_PASS_SCORE
from app.title.presets import DEFAULT_TITLE_PRESET_KEY, get_title_preset
from app.title.rules import NAVER_HOME_MAX_LENGTH


_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash-lite",
    "anthropic": "claude-haiku-4-5",
}
_ISSUE_CONTEXT_MAX_LIMIT = 5
_ISSUE_CONTEXT_DEFAULT_LIMIT = 3
_ISSUE_CONTEXT_HEADLINE_LIMIT = 3
_ISSUE_CONTEXT_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_ISSUE_CONTEXT_STOPWORD_KEYS = {
    normalize_key(token)
    for token in (
        "추천",
        "비교",
        "정리",
        "가이드",
        "방법",
        "사용법",
        "후기",
        "리뷰",
        "체크",
        "체크리스트",
        "포인트",
        "핵심",
        "이번주",
        "이번달",
        "오늘",
        "어제",
        "방금",
    )
    if normalize_key(token)
}

_PROMPT_CATEGORY_LABELS = {
    "product_review": "상품 리뷰 블로그",
    "travel_leisure": "여행레저 블로그",
    "economy_stock": "경제주식 분석 블로그",
    "senior_health_info": "노인건강·노인정보 블로그",
    "health_food": "건강음식 블로그",
    "real_estate": "부동산 블로그",
    "general": "일반 정보형 블로그",
}

_PROMPT_CATEGORY_OVERLAYS = {
    "product_review": (
        "Focus on model or brand, rating, price move, discount, coupon, real-use period, "
        "core specs, and safe review wording."
    ),
    "travel_leisure": (
        "Focus on route efficiency, passes, seasonality, crowd level, wait time, budget, "
        "booking tips, and travel timing."
    ),
    "economy_stock": (
        "Focus on index events, rate path, earnings preview, consensus gaps, ETF flow, "
        "rebalancing, and neutral analytical wording."
    ),
    "senior_health_info": (
        "Focus on benefits, eligibility, application timing, care, safety aids, checklists, "
        "and official-guide wording without medical certainty."
    ),
    "health_food": (
        "Focus on ingredient plus method, cooking time, serving size, calories, protein, sodium, "
        "diet swaps, and practical kitchen cues."
    ),
    "real_estate": (
        "Focus on region, project, line, subscription competition, unsold inventory, transaction "
        "volume, policy, transit, and supply calendar with hedged wording."
    ),
    "general": (
        "Focus on the freshest practical issue, comparison point, reversal, update, or checklist "
        "without mixing domain-specific jargon."
    ),
}

_PROMPT_CATEGORY_HOME_ANGLE_HINTS = {
    "product_review": (
        "issue/update + price, rating, or comparison debate | "
        "issue/update + unexpected real-use takeaway"
    ),
    "travel_leisure": (
        "issue/update + route, crowd, or budget debate | "
        "issue/update + timing reversal or morning-slot surprise"
    ),
    "economy_stock": (
        "issue/update + policy, earnings, or consensus comparison | "
        "issue/update + flow reversal or variable-risk question"
    ),
    "senior_health_info": (
        "issue/update + eligibility, checklist, or support-gap debate | "
        "issue/update + application timing reversal or missed-step warning"
    ),
    "health_food": (
        "issue/update + nutrition, time, or portion comparison | "
        "issue/update + easy swap or taste-reversal takeaway"
    ),
    "real_estate": (
        "issue/update + policy, transit, supply, or competition debate | "
        "issue/update + unsold, ranking, or opportunity reversal question"
    ),
    "general": (
        "issue/update + comparison or debate | "
        "issue/update + reversal or question"
    ),
}

_PROMPT_CATEGORY_FRESHNESS_CUES = {
    "product_review": "this week price move, latest rating change, coupon window, 2-week use",
    "travel_leisure": "this week crowd level, seasonal route, booking window, wait time, 2-day plan",
    "economy_stock": "today, yesterday, this week, monthly flow, earnings calendar, rebalance window",
    "senior_health_info": "this month, application window, updated checklist, support timing, changed rule",
    "health_food": "today meal, this week ingredient, 10-minute cooking, current diet swap",
    "real_estate": "today, yesterday tally, this week schedule, monthly supply, subscription result window",
    "general": "today, yesterday, this week, latest update, current ranking, recent shift",
}

_PROMPT_CATEGORY_DATA_HOOKS = {
    "product_review": "price, discount %, rating, weight, battery, chip, use period",
    "travel_leisure": "travel time, crowd, wait time, budget, pass count, room option",
    "economy_stock": "change %, consensus gap, volume, turnover, PER, PB, rate path",
    "senior_health_info": "support amount, checklist count, application period, eligibility step",
    "health_food": "minutes, servings, calories, protein, sodium, sugar reduction",
    "real_estate": "competition rate, unsold count, transaction volume, ranking, index level, stage",
    "general": "ranking, time stamp, percentage, price, duration, count, checklist size",
}

_PROMPT_CATEGORY_PATTERNS = {
    "product_review": (
        "브랜드", "모델", "언박싱", "후기", "쿠폰", "as", "평점", "사양", "용량", "컬러",
    ),
    "travel_leisure": (
        "항공", "숙소", "패스", "루트", "축제", "캠핑", "등산", "투어", "렌터카",
    ),
    "economy_stock": (
        "지수", "금리", "환율", "업종", "실적", "컨센서스", "etf", "리밸런싱", "주식", "증시",
    ),
    "senior_health_info": (
        "기초연금", "장기요양", "복지", "돌봄", "낙상", "연하", "보청기", "보조기구",
    ),
    "health_food": (
        "레시피", "영양", "칼로리", "단백질", "나트륨", "다이어트", "외식", "간식", "대체식",
    ),
    "real_estate": (
        "청약", "분양", "미분양", "전월세", "재건축", "거래량", "전망지수", "gtx", "신도시", "공공분양",
    ),
}

_PROMPT_CATEGORY_PRIORITY = (
    "real_estate",
    "economy_stock",
    "senior_health_info",
    "health_food",
    "travel_leisure",
    "product_review",
)

_DETECTED_CATEGORY_TO_PROMPT_CATEGORY = {
    "product": "product_review",
    "travel": "travel_leisure",
    "finance": "economy_stock",
    "health": "senior_health_info",
    "food": "health_food",
    "real_estate": "real_estate",
    "general": "general",
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are a Korean SEO title generator for Naver-focused content.\n"
    "Return strict JSON only.\n"
    "Preserve each keyword exactly.\n"
    "For every keyword, generate exactly 2 naver_home titles and 2 blog titles.\n"
    f"Each naver_home title must be {NAVER_HOME_MAX_LENGTH} characters or fewer.\n"
    "Write natural Korean titles that sound like a real editor wrote them.\n"
    "Keep the keyword near the front unless it becomes awkward.\n"
    "Do not use a colon in any title.\n"
    "Prefer zero or one comma per title.\n"
    "The 2 naver_home titles for the same keyword must use clearly different framing.\n"
    "The 2 blog titles for the same keyword must use clearly different framing.\n"
    "Across the whole batch, avoid repeating the same headline skeleton.\n"
    "Favor timely issue-aware framing over evergreen encyclopedia phrasing when the keyword allows it.\n"
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
    issue_context_enabled: bool = True
    issue_context_limit: int = _ISSUE_CONTEXT_DEFAULT_LIMIT

    @classmethod
    def from_input(cls, input_data: Any) -> "TitleGenerationOptions":
        raw = input_data.get("title_options") if isinstance(input_data, dict) else {}
        if not isinstance(raw, dict):
            raw = {}

        mode = "ai" if str(raw.get("mode") or "").strip().lower() == "ai" else "template"
        preset = get_title_preset(
            raw.get("preset_key")
            or raw.get("preset")
            or (DEFAULT_TITLE_PRESET_KEY if mode == "ai" else "")
        )
        provider = _normalize_provider(raw.get("provider") or (preset.provider if preset else None))
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
            issue_context_enabled=bool(raw.get("issue_context_enabled", mode == "ai")),
            issue_context_limit=_coerce_int(
                raw.get("issue_context_limit"),
                default=_ISSUE_CONTEXT_DEFAULT_LIMIT,
                minimum=1,
                maximum=_ISSUE_CONTEXT_MAX_LIMIT,
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
    input_items: list[Any],
    options: TitleGenerationOptions,
) -> list[dict[str, Any]]:
    if not input_items:
        return []

    if not options.api_key:
        raise TitleProviderError("AI mode requires an API key.")

    prompt_items = _attach_live_issue_contexts(input_items, options)
    prompt = _build_user_prompt_from_items(prompt_items)
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


def _build_user_prompt_from_items(input_items: list[Any]) -> str:
    prompt_items = _normalize_prompt_items(input_items)
    item_blocks = "\n\n".join(
        _format_prompt_item(index + 1, item)
        for index, item in enumerate(prompt_items)
    )
    return (
        "Generate Korean blog titles for the following input items.\n\n"
        f"Current local date reference: {_build_prompt_today_label()}\n\n"
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
        "- Treat every input item independently on a 1:1 basis.\n"
        "- naver_home and blog must each contain exactly 2 items.\n"
        "- Apply only one category overlay per keyword.\n"
        "- Prioritize the hottest current issue, update, comparison point, ranking shift, policy change, spike or drop, or reversal angle implied by the keyword.\n"
        "- Each naver_home title should feel optimized for Naver home-feed exposure while staying semi-safe.\n"
        f"- Keep every naver_home title within {NAVER_HOME_MAX_LENGTH} Korean characters.\n"
        "- Do not use colons in any title.\n"
        "- Prefer zero or one comma per title.\n"
        "- Use freshness cues aggressively when natural, such as 오늘, 어제, 방금, 이번주, 이번달, or 올해 누계.\n"
        "- Include at least one timely or concrete data cue when natural, such as a recent time stamp, ranking, percentage, price, duration, wait time, budget, or checklist count.\n"
        "- Use a light emotional hook only when it still sounds editorial, such as 왜 이럴까, 알고 보니, 진짜, or 의외였다.\n"
        "- Avoid duplicate titles within the same keyword.\n"
        "- Avoid using the same sentence frame repeatedly across keywords.\n"
        "- If current-issue evidence is weak, use update, checkpoint, comparison, or decision framing instead of fabricating controversy.\n"
        "- Never invent unsupported facts, rankings, official changes, prices, dates, or percentages. Use concrete signals only when they are provided.\n"
        "- If live issue context or recent headlines are provided, use them as framing cues for home-feed style without copying them verbatim.\n"
        "- Treat live issue context as search-result evidence, not as confirmed fact.\n"
        "- Usually split the 2 naver_home titles into issue/update + debate/comparison and issue/update + reversal/question/surprise.\n"
        "- Make the 2 naver_home titles differ in angle such as issue, debate, comparison, reversal, question, update, or decision point.\n"
        "- Make the 2 blog titles differ in angle such as guide, FAQ, checklist, comparison, practical tips, or issue recap.\n"
        "- Prefer specific wording that matches the keyword intent instead of generic SEO filler.\n"
        "- Do not mix domain-specific jargon across categories.\n"
        "- In YMYL areas, avoid certainty and guarantee language. Prefer hedged wording.\n"
        "- Avoid stale patterns like '<keyword> 배경 정리', '<keyword> 비교 및 선택 기준 정리', or '<time> <keyword> 갑자기 바뀌었다'.\n\n"
        f"Input items:\n{item_blocks}"
    )


def _normalize_prompt_items(input_items: list[Any]) -> list[dict[str, str]]:
    normalized_items: list[dict[str, str]] = []

    for raw_item in input_items:
        if isinstance(raw_item, dict):
            keyword = normalize_text(raw_item.get("keyword"))
            item = raw_item
        else:
            keyword = normalize_text(raw_item)
            item = {"keyword": keyword}

        if not keyword:
            continue

        category_key = _infer_prompt_category(keyword, item)
        target_context = _build_target_context(item)
        signal_summary = _build_signal_summary(item)
        source_hint = _build_source_hint(item)
        issue_context_summary = _build_issue_context_summary(item)
        recent_headlines = _build_issue_headline_summary(item)
        normalized_items.append(
            {
                "keyword": keyword,
                "category_label": _PROMPT_CATEGORY_LABELS[category_key],
                "overlay": _PROMPT_CATEGORY_OVERLAYS[category_key],
                "pair_hint": _PROMPT_CATEGORY_HOME_ANGLE_HINTS[category_key],
                "freshness_cues": _PROMPT_CATEGORY_FRESHNESS_CUES[category_key],
                "data_hooks": _PROMPT_CATEGORY_DATA_HOOKS[category_key],
                "target_context": target_context,
                "signal_summary": signal_summary,
                "source_hint": source_hint,
                "issue_context_summary": issue_context_summary,
                "recent_headlines": recent_headlines,
            }
        )

    return normalized_items


def _format_prompt_item(index: int, item: dict[str, str]) -> str:
    lines = [
        f"Item {index}",
        f"- keyword: {item['keyword']}",
        f"- category overlay: {item['category_label']}",
        f"- category focus: {item['overlay']}",
        f"- preferred naver_home pair: {item['pair_hint']}",
        f"- freshness cues: {item['freshness_cues']}",
        f"- data hooks: {item['data_hooks']}",
    ]
    if item.get("target_context"):
        lines.append(f"- target context: {item['target_context']}")
    if item.get("signal_summary"):
        lines.append(f"- available signals: {item['signal_summary']}")
    if item.get("source_hint"):
        lines.append(f"- source hints: {item['source_hint']}")
    if item.get("issue_context_summary"):
        lines.append(f"- live issue context: {item['issue_context_summary']}")
    if item.get("recent_headlines"):
        lines.append(f"- recent headlines: {item['recent_headlines']}")
    return "\n".join(lines)


def _infer_prompt_category(keyword: str, item: dict[str, Any]) -> str:
    explicit_candidates = (
        item.get("title_category"),
        item.get("content_category"),
        item.get("category"),
        item.get("category_label"),
    )
    for candidate in explicit_candidates:
        mapped = _map_explicit_prompt_category(candidate)
        if mapped:
            return mapped

    normalized_keyword = normalize_text(keyword)
    keyword_key = normalize_key(keyword)
    scores = {
        category: sum(
            1
            for pattern in patterns
            if pattern in normalized_keyword or normalize_key(pattern) in keyword_key
        )
        for category, patterns in _PROMPT_CATEGORY_PATTERNS.items()
    }
    best_score = max(scores.values(), default=0)
    if best_score > 0:
        for category in _PROMPT_CATEGORY_PRIORITY:
            if scores.get(category) == best_score:
                return category

    detected_category = detect_category(keyword)
    return _DETECTED_CATEGORY_TO_PROMPT_CATEGORY.get(detected_category, "general")


def _map_explicit_prompt_category(value: Any) -> str:
    normalized_value = normalize_key(value)
    if not normalized_value:
        return ""
    if any(token in normalized_value for token in ("상품", "리뷰", "언박싱", "모델", "브랜드")):
        return "product_review"
    if any(token in normalized_value for token in ("여행", "레저", "숙소", "항공", "패스", "투어")):
        return "travel_leisure"
    if any(token in normalized_value for token in ("경제", "주식", "증시", "금리", "환율", "etf", "리밸런싱")):
        return "economy_stock"
    if any(token in normalized_value for token in ("노인", "연금", "요양", "복지", "돌봄", "보청기")):
        return "senior_health_info"
    if any(token in normalized_value for token in ("건강음식", "영양", "칼로리", "단백질", "레시피", "나트륨")):
        return "health_food"
    if any(token in normalized_value for token in ("부동산", "청약", "분양", "전세", "재건축", "gtx")):
        return "real_estate"
    return ""


def _build_target_context(item: dict[str, Any]) -> str:
    parts: list[str] = []
    target_mode = normalize_text(item.get("target_mode_label") or item.get("target_mode"))
    if target_mode:
        parts.append(target_mode)
    base_keyword = normalize_text(item.get("base_keyword"))
    if base_keyword and base_keyword != normalize_text(item.get("keyword")):
        parts.append(f"base {base_keyword}")
    support_keywords = item.get("support_keywords")
    if isinstance(support_keywords, list):
        normalized_support = [normalize_text(keyword) for keyword in support_keywords if normalize_text(keyword)]
        if normalized_support:
            parts.append(f"support {', '.join(normalized_support[:3])}")
    return " / ".join(parts)


def _build_signal_summary(item: dict[str, Any]) -> str:
    parts: list[str] = []

    score = _format_metric_value(item.get("score"))
    if score:
        parts.append(f"score {score}")

    profitability_grade = normalize_text(item.get("profitability_grade"))
    attackability_grade = normalize_text(item.get("attackability_grade"))
    if profitability_grade and attackability_grade:
        parts.append(f"grade {profitability_grade}/{attackability_grade}")

    metrics = item.get("metrics")
    if isinstance(metrics, dict):
        metric_labels = (
            ("volume", "volume"),
            ("cpc", "cpc"),
            ("competition", "competition"),
            ("profit", "profit"),
            ("opportunity", "opportunity"),
        )
        for key, label in metric_labels:
            metric_value = _format_metric_value(metrics.get(key))
            if metric_value:
                parts.append(f"{label} {metric_value}")

    return ", ".join(parts[:6])


def _build_source_hint(item: dict[str, Any]) -> str:
    parts: list[str] = []

    source_kind = normalize_text(item.get("source_kind"))
    if source_kind:
        parts.append(source_kind)

    source_keywords = item.get("source_keywords")
    if isinstance(source_keywords, list):
        normalized_source_keywords = [normalize_text(keyword) for keyword in source_keywords if normalize_text(keyword)]
        if normalized_source_keywords:
            parts.append(f"source keywords {', '.join(normalized_source_keywords[:3])}")

    verification_status = normalize_text(item.get("verification_status"))
    if verification_status:
        parts.append(f"status {verification_status}")

    validated_score = _format_metric_value(item.get("verified_score") or item.get("projected_score"))
    if validated_score:
        parts.append(f"validated score {validated_score}")

    source_note = normalize_text(item.get("source_note"))
    if source_note:
        parts.append(f"note {source_note}")

    return " / ".join(parts[:4])


def _build_issue_context_summary(item: dict[str, Any]) -> str:
    issue_context = item.get("issue_context")
    if not isinstance(issue_context, dict):
        return ""

    parts: list[str] = []
    fetched_at = normalize_text(issue_context.get("fetched_at"))
    if fetched_at:
        parts.append(f"fetched {fetched_at[:10]}")

    title_count = _coerce_int(issue_context.get("title_count"), default=0, minimum=0, maximum=20)
    news_count = _coerce_int(issue_context.get("news_count"), default=0, minimum=0, maximum=20)
    if title_count > 0:
        parts.append(f"news {news_count}/{title_count}")

    source_mix = issue_context.get("source_mix")
    if isinstance(source_mix, dict):
        source_parts = [
            f"{normalize_text(source)} {int(count)}"
            for source, count in source_mix.items()
            if normalize_text(source) and int(count or 0) > 0
        ]
        if source_parts:
            parts.append(f"sources {', '.join(source_parts[:3])}")

    issue_terms = issue_context.get("issue_terms") or issue_context.get("common_terms")
    if isinstance(issue_terms, list):
        normalized_terms = [normalize_text(term) for term in issue_terms if normalize_text(term)]
        if normalized_terms:
            parts.append(f"terms {', '.join(normalized_terms[:4])}")

    return " / ".join(parts[:4])


def _build_issue_headline_summary(item: dict[str, Any]) -> str:
    issue_context = item.get("issue_context")
    if not isinstance(issue_context, dict):
        return ""

    headline_candidates = issue_context.get("news_headlines")
    if not isinstance(headline_candidates, list) or not headline_candidates:
        headline_candidates = issue_context.get("top_headlines")
    if not isinstance(headline_candidates, list):
        return ""

    normalized_headlines = [
        _truncate_prompt_text(normalize_text(headline), 52)
        for headline in headline_candidates
        if normalize_text(headline)
    ]
    if not normalized_headlines:
        return ""
    return " | ".join(normalized_headlines[:2])


def _attach_live_issue_contexts(
    input_items: list[Any],
    options: TitleGenerationOptions,
) -> list[Any]:
    if not options.issue_context_enabled:
        return input_items

    remaining = _coerce_int(
        options.issue_context_limit,
        default=_ISSUE_CONTEXT_DEFAULT_LIMIT,
        minimum=1,
        maximum=_ISSUE_CONTEXT_MAX_LIMIT,
    )
    enriched_items: list[Any] = []

    for raw_item in input_items:
        if isinstance(raw_item, dict):
            item = dict(raw_item)
            keyword = normalize_text(item.get("keyword"))
        else:
            keyword = normalize_text(raw_item)
            item = {"keyword": keyword}

        if keyword and not isinstance(item.get("issue_context"), dict) and remaining > 0:
            issue_context = _fetch_live_issue_context(keyword)
            if issue_context:
                item["issue_context"] = issue_context
            remaining -= 1

        if isinstance(raw_item, dict) or isinstance(item.get("issue_context"), dict):
            enriched_items.append(item)
        else:
            enriched_items.append(keyword)

    return enriched_items


def _fetch_live_issue_context(keyword: str) -> dict[str, Any]:
    normalized_keyword = normalize_text(keyword)
    cache_key = (normalize_key(normalized_keyword), _build_prompt_today_label())
    if cache_key in _ISSUE_CONTEXT_CACHE:
        return dict(_ISSUE_CONTEXT_CACHE[cache_key])

    if not normalized_keyword or not cache_key[0]:
        return {}

    try:
        titles = parse_serp_titles(fetch_naver_serp_html(normalized_keyword))
    except Exception:
        return {}

    if not titles:
        return {}

    title_count = len(titles)
    source_counts = Counter(
        normalize_text(item.get("source_bucket"))
        for item in titles
        if normalize_text(item.get("source_bucket"))
    )
    news_headlines = [
        normalize_text(item.get("title"))
        for item in titles
        if normalize_text(item.get("source_bucket")) == "news" and normalize_text(item.get("title"))
    ]
    issue_context = {
        "query": normalized_keyword,
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "search_url": build_search_url(normalized_keyword),
        "title_count": title_count,
        "news_count": len(news_headlines),
        "source_mix": dict(source_counts),
        "issue_terms": _extract_issue_terms(normalized_keyword, titles),
        "top_headlines": [
            normalize_text(item.get("title"))
            for item in titles[:_ISSUE_CONTEXT_HEADLINE_LIMIT]
            if normalize_text(item.get("title"))
        ],
        "news_headlines": news_headlines[:_ISSUE_CONTEXT_HEADLINE_LIMIT],
    }
    _ISSUE_CONTEXT_CACHE[cache_key] = dict(issue_context)
    return issue_context


def _extract_issue_terms(keyword: str, titles: list[dict[str, Any]]) -> list[str]:
    keyword_tokens = {
        normalize_key(token)
        for token in tokenize_text(keyword)
        if normalize_key(token)
    }
    original_token_map: dict[str, str] = {}
    counter: Counter[str] = Counter()

    for item in titles:
        raw_title = normalize_text(item.get("title"))
        if not raw_title:
            continue
        unique_title_tokens: set[str] = set()
        for token in tokenize_text(raw_title):
            token_key = normalize_key(token)
            if (
                not token_key
                or token_key in keyword_tokens
                or token_key in _ISSUE_CONTEXT_STOPWORD_KEYS
                or len(token_key) <= 1
            ):
                continue
            original_token_map.setdefault(token_key, token)
            unique_title_tokens.add(token_key)
        for token_key in unique_title_tokens:
            counter[token_key] += 1

    return [
        original_token_map[token_key]
        for token_key, count in counter.most_common(4)
        if count >= 2 and token_key in original_token_map
    ]


def _build_prompt_today_label() -> str:
    return datetime.now().astimezone().date().isoformat()


def _truncate_prompt_text(value: str, limit: int) -> str:
    normalized = normalize_text(value)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _format_metric_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""

    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


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


def get_default_system_prompt() -> str:
    return _DEFAULT_SYSTEM_PROMPT


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
