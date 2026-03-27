from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from dataclasses import dataclass
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from app.core.api_usage import record_api_usage
from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.selector.serp_summary import build_search_url, fetch_naver_serp_html, parse_serp_titles
from app.title.category_detector import detect_category
from app.title.evaluation_prompt import DEFAULT_TITLE_EVALUATION_PROMPT
from app.title.issue_sources import (
    DEFAULT_ISSUE_SOURCE_MODE,
    describe_community_domains,
    match_domain_against_allowlist,
    normalize_issue_source_mode,
    resolve_community_source_domains,
)
from app.title.presets import DEFAULT_TITLE_PRESET_KEY, get_title_preset
from app.title.rules import NAVER_HOME_MAX_LENGTH, TITLE_QUALITY_REVIEW_SCORE


_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_VERTEX_EXPRESS_URL_TEMPLATE = (
    "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent?key={api_key}"
)
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash-lite",
    "vertex": "gemini-2.5-flash-lite",
    "anthropic": "claude-haiku-4-5",
}
_ISSUE_CONTEXT_MAX_LIMIT = 5
_ISSUE_CONTEXT_DEFAULT_LIMIT = 3
_ISSUE_CONTEXT_HEADLINE_LIMIT = 3
_DEFAULT_QUALITY_RETRY_THRESHOLD = TITLE_QUALITY_REVIEW_SCORE
_ISSUE_CONTEXT_CACHE: dict[tuple[str, ...], dict[str, Any]] = {}
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

_COMMUNITY_COMPARISON_TERMS = (
    "비교",
    "차이",
    "장단점",
    "vs",
    "가성비",
    "가격",
    "순위",
    "추천",
)
_COMMUNITY_PAIN_TERMS = (
    "후기",
    "불만",
    "실패",
    "주의",
    "단점",
    "문제",
    "부작용",
    "환불",
    "아쉬움",
)
_COMMUNITY_REACTION_TERMS = (
    "후기",
    "체감",
    "직접",
    "실사용",
    "리뷰",
    "경험",
    "반응",
)

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
    "Every title must contain all meaningful keyword tokens from the input keyword.\n"
    "Keep those keyword tokens in the same order, even when you insert short modifiers between them.\n"
    "Do not shorten or compress the keyword phrase. If the keyword starts with descriptive words, keep them all.\n"
    "Do not drop or paraphrase modifier tokens such as 체크리스트, 비교, 후기, 가격, 일정, 신청방법, 원인, 부작용, 추천, or 가이드.\n"
    "For every keyword, generate exactly 2 naver_home titles and 2 blog titles.\n"
    f"Each naver_home title must be {NAVER_HOME_MAX_LENGTH} characters or fewer.\n"
    "Write natural Korean titles that sound like a real editor wrote them.\n"
    "Keep the keyword near the front unless it becomes awkward.\n"
    "Prefer concise hook-first wording: one clear hook plus one concrete noun is better than a long abstract explanation.\n"
    "Do not use a colon in any title, including full-width punctuation like ：.\n"
    "Prefer zero or one comma per title.\n"
    "The 2 naver_home titles for the same keyword must use clearly different framing.\n"
    "The 2 blog titles for the same keyword must use clearly different framing.\n"
    "For naver_home titles, when natural, combine at least two of issue/update, debate/comparison, and reversal/question framing.\n"
    "Across the whole batch, avoid repeating the same headline skeleton.\n"
    "Favor timely issue-aware framing over evergreen encyclopedia phrasing when the keyword allows it.\n"
    "Reflect the search intent in the wording: price, review, comparison, reservation, profile, location, how-to, or guide.\n"
    "For blog titles, prioritize search exposure structure before copywriting flair.\n"
    "When natural, shape each blog title like main keyword + support keyword + concrete descriptor, similar to a common top-ranked Naver search-result pattern for that intent.\n"
    "For blog titles, full keyword coverage and structure fit matter more than forcing the keyword into the absolute first token.\n"
    "Keep strict category boundaries. Do not import another category's jargon, entities, or policy concepts just to make a title feel smarter.\n"
    "Prefer concrete nouns such as 실사용, 장단점, 차이, 성능, 가격대, 세팅, 연결, 사용감, 추천 대상, or 주의점 over vague labels.\n"
    "Avoid low-information skeletons such as '최신 정보', '업데이트 확인', '왜 인기?', '이것만 알면', '구매 가이드', '사용 후기', '신상', or a bare '비교' unless the keyword itself truly requires that wording.\n"
    "Avoid generic template phrases such as '완벽 정리', '한 번에 정리', '갑자기 바뀌었다', '이유가 이상하다', '놓치면 손해' unless they are truly necessary.\n"
    "For preorder or reservation keywords, prefer 일정, 오픈 시간, 링크, 인증, 결제, 혜택, 수령, or 제한 같은 구체 명사를 쓰고 teaser questions로 흐리지 마라.\n"
    "For value or 가성비 keywords, prefer 위치, 교통, 추가요금, 조식, 객실, 취소 조건, 예산, or 후기 분포 같은 구체 축을 써라.\n"
    "For broad single product keywords, prefer 실사용, 장단점, 가격대, 추천 대상, 클릭감, 배터리, 그립, or 연결 안정성 같은 평가 축을 써라.\n"
    "Do not invent unsupported freshness, price movement, discount windows, or experience-duration claims such as 오늘, 이번주, 이번달, 최저가, 할인율, 가격 변동, or 2주 사용 unless the keyword or provided issue context explicitly supports them.\n"
    "For finance keywords without verified live issue context, prefer hook frames based on gap, interpretation, checkpoint, variable, condition, timing, or domestic-vs-global difference rather than pretending to know today's move.\n"
    "For finance keywords, avoid device-style frames such as 실사용 차이, 사용 후기, 자주 생기는 문제, 설정 팁, 연결 문제, or 동선 체크 unless the keyword itself naturally requires them.\n"
    "For naver_home titles, do not stop at bare labels like 환율 영향, 확인 포인트, 기준선, 조건 차이, 실시간 현황, or 국내외 차이. Turn that axis into a real question, contrast, implication, or decision point.\n"
    "For finance analysis titles, retrospective windows such as 2주 흐름, 2주간 추이, 3주 변동, or 1개월 비교 are acceptable only when they clearly describe analysis rather than fake breaking news.\n"
    "Search-visible effective blog patterns are concrete: model + symptom or benefit + timeframe or environment, model + connection or setup + device context, or model + problem + fix or result.\n"
    "Do not wrap already-concrete keywords such as 실사용 차이, 장단점, 설정 팁, 연결 방법, 연결 문제, or 자주 생기는 문제 with stale wrappers like 총정리, 완벽 가이드, 최신 정보, 최신 비교 분석, 이것만 알면, or 꼭 알아두세요.\n"
    "In YMYL areas such as money, health, law, and real estate, use hedged wording and avoid certainty or guarantee language.\n"
    "Avoid clickbait, exaggerated fear, and empty filler.\n"
    "Do not include markdown, commentary, or code fences."
)

_SLOT_TITLE_SYSTEM_PROMPT = (
    "You are a Korean title generator for Naver home CTR and SEO blog content.\n"
    "Return strict JSON only.\n"
    "\n"
    "[MODE DETECTION]\n"
    "If current_title is provided, use REWRITE MODE.\n"
    "If current_title is empty, use GENERATION MODE.\n"
    "\n"
    "[COMMON RULES]\n"
    "- Preserve the keyword exactly.\n"
    "- Do not change token order of the keyword.\n"
    "- Natural Korean only.\n"
    "- No colon.\n"
    "- Prefer zero or one comma.\n"
    "\n"
    "[GENERATION MODE]\n"
    "Goal: Generate a high-quality title.\n"
    "\n"
    "[NAVER_HOME RULES]\n"
    f"- Max {NAVER_HOME_MAX_LENGTH} characters.\n"
    "- Focus on click-through rate.\n"
    "- Use at least two of issue/change, comparison/difference, reversal/unexpected, and question.\n"
    "- Create curiosity gap and do not fully explain.\n"
    "- Allow emotional hooks and question forms.\n"
    "- Avoid flat informational titles, generic phrasing, and repeated patterns across the batch.\n"
    "\n"
    "[BLOG RULES]\n"
    "- Focus on clarity and SEO structure.\n"
    "- Structure the title like keyword + specific detail + explanation.\n"
    "- Include method, condition, comparison, or criteria.\n"
    "- Avoid vague wording and excessive emotional hooks.\n"
    "\n"
    "[REWRITE MODE]\n"
    "Goal: Fix the title based on issues and improve quality.\n"
    "- The rewritten title must be clearly different from current_title.\n"
    "- Fix all listed issues explicitly.\n"
    "- Do not reuse the same structure from peer_titles.\n"
    "- If channel is naver_home, strengthen curiosity and contrast and avoid repeating the same question pattern.\n"
    "- If channel is blog, improve clarity and specificity and remove vague or weak phrasing.\n"
    "\n"
    "[OUTPUT FORMAT]\n"
    "{\n"
    '  "items": [\n'
    "    {\n"
    '      "slot_id": "...",\n'
    '      "title": "..."\n'
    "    }\n"
    "  ]\n"
    "}"
)


class TitleProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class TitleGenerationOptions:
    mode: str = "template"
    provider: str = "openai"
    api_key: str | None = None
    model: str = _DEFAULT_MODELS["openai"]
    rewrite_provider: str = ""
    rewrite_api_key: str | None = None
    rewrite_model: str = ""
    temperature: float = 0.7
    max_output_tokens: int = 1200
    batch_size: int = 20
    fallback_to_template: bool = True
    system_prompt: str = ""
    quality_system_prompt: str = DEFAULT_TITLE_EVALUATION_PROMPT
    quality_prompt_profile_id: str = ""
    preset_key: str = ""
    preset_label: str = ""
    preset_prompt: str = ""
    auto_retry_enabled: bool = False
    quality_retry_threshold: int = _DEFAULT_QUALITY_RETRY_THRESHOLD
    issue_context_enabled: bool = True
    issue_context_limit: int = _ISSUE_CONTEXT_DEFAULT_LIMIT
    issue_source_mode: str = DEFAULT_ISSUE_SOURCE_MODE
    community_sources: tuple[str, ...] = ()

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
        rewrite_provider = ""
        if normalize_text(raw.get("rewrite_provider")):
            rewrite_provider = _normalize_provider(raw.get("rewrite_provider"))
        rewrite_model = (
            normalize_text(raw.get("rewrite_model"))
            if rewrite_provider
            else ""
        ) or (_DEFAULT_MODELS[rewrite_provider] if rewrite_provider else "")
        temperature = _coerce_float(
            raw.get("temperature"),
            default=float(preset.temperature if preset else 0.7),
            minimum=0.0,
            maximum=1.5,
        )
        max_output_tokens = _coerce_int(raw.get("max_output_tokens"), default=1200, minimum=200, maximum=4000)
        batch_size = _coerce_int(raw.get("batch_size"), default=20, minimum=1, maximum=20)

        has_explicit_community_sources = (
            "community_sources" in raw
            or "community_source_domains" in raw
            or "community_custom_domains" in raw
        )
        preset_issue_source_mode = normalize_issue_source_mode(preset.issue_source_mode if preset else DEFAULT_ISSUE_SOURCE_MODE)
        preset_community_sources = list(preset.community_sources) if preset else []
        community_sources = tuple(
            resolve_community_source_domains(
                raw.get("community_sources", raw.get("community_source_domains"))
                if has_explicit_community_sources
                else preset_community_sources,
                raw.get("community_custom_domains"),
                use_default_when_empty=not has_explicit_community_sources and not bool(preset_community_sources),
            )
        )
        return cls(
            mode=mode,
            provider=provider,
            api_key=normalize_text(raw.get("api_key")) or None,
            model=model,
            rewrite_provider=rewrite_provider,
            rewrite_api_key=normalize_text(raw.get("rewrite_api_key")) or None,
            rewrite_model=rewrite_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            batch_size=batch_size,
            fallback_to_template=bool(raw.get("fallback_to_template", True)),
            system_prompt=normalize_text(raw.get("system_prompt")) or "",
            quality_system_prompt=(
                normalize_text(raw.get("quality_system_prompt") or raw.get("evaluation_prompt"))
                or DEFAULT_TITLE_EVALUATION_PROMPT
            ),
            quality_prompt_profile_id=normalize_text(
                raw.get("quality_prompt_profile_id") or raw.get("active_evaluation_prompt_profile_id")
            ),
            preset_key=preset.key if preset else "",
            preset_label=preset.label if preset else "",
            preset_prompt=preset.prompt_guidance if preset else "",
            auto_retry_enabled=bool(raw.get("auto_retry_enabled", False)),
            quality_retry_threshold=_coerce_int(
                raw.get("quality_retry_threshold"),
                default=_DEFAULT_QUALITY_RETRY_THRESHOLD,
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
            issue_source_mode=normalize_issue_source_mode(raw.get("issue_source_mode") or preset_issue_source_mode),
            community_sources=community_sources,
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
    if options.provider == "vertex":
        return _request_vertex_titles(prompt, options)
    if options.provider == "anthropic":
        return _request_anthropic_titles(prompt, options)

    raise TitleProviderError(f"Unsupported provider: {options.provider}")


def request_ai_slot_rewrites(
    input_items: list[Any],
    options: TitleGenerationOptions,
) -> list[dict[str, str]]:
    if not input_items:
        return []

    if not options.api_key:
        raise TitleProviderError("AI mode requires an API key.")

    prompt_items = _normalize_slot_prompt_items(input_items)
    if not prompt_items:
        return []

    payload = request_ai_json_object(
        provider=options.provider,
        api_key=options.api_key,
        model=options.model,
        system_prompt=_build_slot_title_system_prompt(options.system_prompt),
        user_prompt=_build_slot_title_user_prompt(prompt_items),
        temperature=options.temperature,
        max_output_tokens=max(600, int(options.max_output_tokens or 0)),
    )
    return _parse_slot_title_items(payload)


def request_ai_json_object(
    *,
    provider: str,
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int = 1400,
    request_timeout_seconds: float = 30.0,
    max_retries: int | None = None,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    normalized_model = normalize_text(model) or _DEFAULT_MODELS[normalized_provider]
    normalized_system_prompt = normalize_text(system_prompt)
    normalized_user_prompt = normalize_text(user_prompt)
    if not api_key:
        raise TitleProviderError("AI mode requires an API key.")
    if not normalized_user_prompt:
        raise TitleProviderError("Evaluation prompt is empty.")

    if normalized_provider == "openai":
        payload = {
            "model": normalized_model,
            "messages": [
                {"role": "system", "content": normalized_system_prompt},
                {"role": "user", "content": normalized_user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = _post_json(
            _OPENAI_URL,
            headers,
            payload,
            max_retries=0 if max_retries is None else max(0, int(max_retries or 0)),
            timeout_seconds=request_timeout_seconds,
        )
        content = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return _parse_json_object_text(content)

    if normalized_provider in {"gemini", "vertex"}:
        payload = _build_gemini_like_json_payload(
            system_prompt=normalized_system_prompt,
            user_prompt=normalized_user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if normalized_provider == "gemini":
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key or "",
            }
            url = _GEMINI_URL_TEMPLATE.format(model=normalized_model)
        else:
            headers = {
                "Content-Type": "application/json",
            }
            url = _VERTEX_EXPRESS_URL_TEMPLATE.format(model=normalized_model, api_key=quote(api_key or "", safe=""))
        response = _post_json(
            url,
            headers,
            payload,
            max_retries=2 if max_retries is None else max(0, int(max_retries or 0)),
            timeout_seconds=request_timeout_seconds,
        )
        return _parse_json_object_text(_extract_gemini_like_text(response))

    if normalized_provider == "anthropic":
        payload = {
            "model": normalized_model,
            "system": normalized_system_prompt,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": normalized_user_prompt,
                }
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
        }
        response = _post_json(
            _ANTHROPIC_URL,
            headers,
            payload,
            max_retries=0 if max_retries is None else max(0, int(max_retries or 0)),
            timeout_seconds=request_timeout_seconds,
        )
        content_items = response.get("content", [])
        content = "\n".join(
            normalize_text(item.get("text"))
            for item in content_items
            if isinstance(item, dict) and normalize_text(item.get("text"))
        )
        return _parse_json_object_text(content)

    raise TitleProviderError(f"Unsupported provider: {normalized_provider}")


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
    payload = _build_gemini_like_payload(prompt, options)
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": options.api_key or "",
    }
    url = _GEMINI_URL_TEMPLATE.format(model=options.model)
    response = _post_json(url, headers, payload, max_retries=2)
    content = _extract_gemini_like_text(response)
    return _parse_title_items(content)


def _request_vertex_titles(prompt: str, options: TitleGenerationOptions) -> list[dict[str, Any]]:
    payload = _build_gemini_like_payload(prompt, options)
    headers = {
        "Content-Type": "application/json",
    }
    url = _VERTEX_EXPRESS_URL_TEMPLATE.format(model=options.model, api_key=quote(options.api_key or "", safe=""))
    response = _post_json(url, headers, payload, max_retries=2)
    content = _extract_gemini_like_text(response)
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


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    max_retries: int = 0,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    raw_payload = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    provider = _resolve_provider_from_url(url)
    model = _resolve_model_from_payload(payload, url)
    endpoint = _resolve_endpoint_from_url(url)

    for attempt in range(max_retries + 1):
        request = Request(
            url=url,
            headers=headers,
            data=raw_payload,
            method="POST",
        )

        try:
            with urlopen(request, timeout=float(timeout_seconds or 30.0)) as response:
                raw_text = response.read().decode("utf-8", errors="ignore")
            break
        except HTTPError as exc:
            raw_text = exc.read().decode("utf-8", errors="ignore")
            detail = _extract_error_message(raw_text) or raw_text or exc.reason
            record_api_usage(
                stage="title",
                service="title_llm",
                provider=provider,
                model=model,
                endpoint=endpoint,
                success=False,
            )
            if attempt < max_retries and exc.code in {429, 500, 503}:
                time.sleep(
                    _resolve_retry_delay_seconds(
                        detail,
                        header_value=exc.headers.get("Retry-After") if exc.headers else "",
                        attempt=attempt,
                    )
                )
                last_error = exc
                continue
            raise TitleProviderError(f"{exc.code} {detail}") from exc
        except URLError as exc:
            record_api_usage(
                stage="title",
                service="title_llm",
                provider=provider,
                model=model,
                endpoint=endpoint,
                success=False,
            )
            if attempt < max_retries:
                time.sleep(_resolve_retry_delay_seconds(str(exc.reason), attempt=attempt))
                last_error = exc
                continue
            raise TitleProviderError(str(exc.reason)) from exc
        except Exception as exc:  # pragma: no cover - network runtime guard
            record_api_usage(
                stage="title",
                service="title_llm",
                provider=provider,
                model=model,
                endpoint=endpoint,
                success=False,
            )
            raise TitleProviderError(str(exc)) from exc
    else:  # pragma: no cover - defensive guard
        raise TitleProviderError(str(last_error) if last_error else "Provider request failed.")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise TitleProviderError("Provider returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise TitleProviderError("Provider returned an unexpected payload.")
    usage = _extract_provider_token_usage(provider, parsed)
    record_api_usage(
        stage="title",
        service="title_llm",
        provider=provider,
        model=model,
        endpoint=endpoint,
        success=True,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
    )
    return parsed


def _resolve_provider_from_url(url: str) -> str:
    normalized = str(url or "")
    if "api.openai.com" in normalized:
        return "openai"
    if "generativelanguage.googleapis.com" in normalized:
        return "gemini"
    if "aiplatform.googleapis.com" in normalized:
        return "vertex"
    if "api.anthropic.com" in normalized:
        return "anthropic"
    return "unknown"


def _resolve_model_from_payload(payload: dict[str, Any], url: str) -> str:
    if normalize_text(payload.get("model")):
        return normalize_text(payload.get("model"))
    parsed = urlparse(str(url or ""))
    path = parsed.path or ""
    if ":generateContent" in path and "/models/" in path:
        return path.split("/models/", 1)[1].split(":generateContent", 1)[0]
    return ""


def _resolve_endpoint_from_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return parsed.path or str(url or "")


def _extract_provider_token_usage(provider: str, response: dict[str, Any]) -> dict[str, int]:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "openai":
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        prompt_tokens = _coerce_int(usage.get("prompt_tokens"), default=0, minimum=0, maximum=1_000_000)
        completion_tokens = _coerce_int(usage.get("completion_tokens"), default=0, minimum=0, maximum=1_000_000)
        total_tokens = _coerce_int(usage.get("total_tokens"), default=0, minimum=0, maximum=1_000_000) or (prompt_tokens + completion_tokens)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    if normalized_provider in {"gemini", "vertex"}:
        usage = response.get("usageMetadata") if isinstance(response.get("usageMetadata"), dict) else {}
        prompt_tokens = _coerce_int(
            usage.get("promptTokenCount") or usage.get("inputTokenCount"),
            default=0,
            minimum=0,
            maximum=1_000_000,
        )
        completion_tokens = _coerce_int(
            usage.get("candidatesTokenCount") or usage.get("outputTokenCount"),
            default=0,
            minimum=0,
            maximum=1_000_000,
        )
        total_tokens = _coerce_int(
            usage.get("totalTokenCount"),
            default=0,
            minimum=0,
            maximum=1_000_000,
        ) or (prompt_tokens + completion_tokens)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    if normalized_provider == "anthropic":
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        prompt_tokens = _coerce_int(usage.get("input_tokens"), default=0, minimum=0, maximum=1_000_000)
        completion_tokens = _coerce_int(usage.get("output_tokens"), default=0, minimum=0, maximum=1_000_000)
        total_tokens = _coerce_int(usage.get("total_tokens"), default=0, minimum=0, maximum=1_000_000) or (prompt_tokens + completion_tokens)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def _build_gemini_like_payload(prompt: str, options: TitleGenerationOptions) -> dict[str, Any]:
    return {
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


def _build_gemini_like_json_payload(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_output_tokens: int,
) -> dict[str, Any]:
    return {
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
            "temperature": temperature,
            "responseMimeType": "application/json",
            "maxOutputTokens": max_output_tokens,
        },
    }


def _extract_gemini_like_text(response: dict[str, Any]) -> str:
    parts = (
        response.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return "\n".join(
        normalize_text(part.get("text"))
        for part in parts
        if isinstance(part, dict) and normalize_text(part.get("text"))
    )


def _parse_json_object_text(raw_text: str) -> dict[str, Any]:
    parsed = _parse_json_with_repairs(
        raw_text,
        empty_message="Provider returned empty JSON content.",
        missing_message="Provider returned empty JSON content.",
        invalid_message="Provider returned invalid JSON content.",
    )
    if isinstance(parsed, dict):
        return parsed
    raise TitleProviderError("Provider returned invalid JSON content.")


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
        "- Every title must contain all meaningful keyword tokens from the input keyword.\n"
        "- Keep keyword tokens in the same order. You may insert short modifiers between tokens, but do not drop or paraphrase any keyword token.\n"
        "- Do not shorten the keyword phrase. If the keyword starts with descriptive words, keep them all.\n"
        "- Write all titles in Korean.\n"
        "- naver_home and blog must each contain exactly 2 items.\n"
        "- For blog titles, prioritize search exposure structure before catchy copywriting.\n"
        "- When natural, use a structure like main keyword + support keyword + concrete descriptor.\n"
        "- For blog titles, full keyword coverage and structure fit matter more than forcing the keyword into the absolute first token.\n"
        "- When the keyword already contains a concrete practical angle such as 실사용 차이, 장단점, 설정 팁, 연결 방법, 연결 문제, or 자주 생기는 문제, keep that angle and deepen it with timeframe, environment, symptom, cause, fix, user type, or device context instead of adding generic wrappers.\n"
        "- Search-visible blog titles usually work when they read like model + symptom or benefit + timeframe or environment, model + setup + device context, or model + problem + fix or result.\n"
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
        "- Every title must contain all meaningful keyword tokens from the input keyword.\n"
        "- Keep keyword tokens in the same order. You may insert short modifiers between tokens, but do not drop or paraphrase any keyword token.\n"
        "- Do not shorten the keyword phrase. If the keyword starts with descriptive words, keep them all.\n"
        "- Pay extra attention to the last keyword token when it carries intent, such as 체크리스트, 후기, 비교, 가격, 일정, 신청방법, 원인, 부작용, 추천, or 가이드.\n"
        "- Write all titles in Korean.\n"
        "- Treat every input item independently on a 1:1 basis.\n"
        "- Return exactly one output item for every input item.\n"
        "- Preserve the input item order exactly. Output items[i] must correspond to input items[i].\n"
        "- naver_home and blog must each contain exactly 2 items.\n"
        "- Prefer concise hook-first wording: one clear hook plus one concrete noun is better than a long abstract explanation.\n"
        "- Apply only one category overlay per keyword.\n"
        "- Keep strict category boundaries. Do not import another category's jargon, entities, or policy concepts into the title.\n"
        "- Prioritize the hottest current issue, update, comparison point, ranking shift, policy change, spike or drop, or reversal angle implied by the keyword.\n"
        "- Each naver_home title should feel optimized for Naver home-feed exposure while staying semi-safe.\n"
        f"- Keep every naver_home title within {NAVER_HOME_MAX_LENGTH} Korean characters.\n"
        "- For blog titles, prioritize search exposure structure before catchy copywriting.\n"
        "- When natural, use a structure like main keyword + support keyword + concrete descriptor, similar to a common top-ranked Naver search-result pattern for that intent.\n"
        "- For blog titles, full keyword coverage and structure fit matter more than forcing the keyword into the absolute first token.\n"
        "- Do not use colons in any title, including full-width punctuation like ：.\n"
        "- Prefer zero or one comma per title.\n"
        "- Use freshness cues aggressively when natural, such as 오늘, 어제, 방금, 이번주, 이번달, or 올해 누계.\n"
        "- Include at least one timely or concrete data cue when natural, such as a recent time stamp, ranking, percentage, price, duration, wait time, budget, or checklist count.\n"
        "- Use a light emotional hook only when it still sounds editorial, such as 왜 이럴까, 알고 보니, 진짜, or 의외였다.\n"
        "- Avoid duplicate titles within the same keyword.\n"
        "- Avoid using the same sentence frame repeatedly across keywords.\n"
        "- If current-issue evidence is weak, use update, checkpoint, comparison, or decision framing instead of fabricating controversy.\n"
        "- Never invent unsupported facts, rankings, official changes, prices, dates, or percentages. Use concrete signals only when they are provided.\n"
        "- For finance keywords without verified live issue context, prefer hook frames based on gap, interpretation, checkpoint, variable, condition, timing, or domestic-vs-global difference rather than pretending to know today's move.\n"
        "- For finance keywords, avoid device-style frames such as 실사용 차이, 사용 후기, 자주 생기는 문제, 설정 팁, 연결 문제, or 동선 체크 unless the keyword itself naturally requires them.\n"
        "- For naver_home titles, do not stop at bare labels like 환율 영향, 확인 포인트, 기준선, 조건 차이, 실시간 현황, or 국내외 차이. Turn that axis into a real question, contrast, implication, or decision point.\n"
        "- For finance analysis titles, retrospective windows such as 2주 흐름, 2주간 추이, 3주 변동, or 1개월 비교 are acceptable only when they clearly describe analysis rather than fake breaking news.\n"
        "- If live issue context or recent headlines are provided, use them as framing cues for home-feed style without copying them verbatim.\n"
        "- If community reaction or community headlines are provided, treat them as selected-domain reaction cues rather than universal public consensus.\n"
        "- Treat live issue context as search-result evidence, not as confirmed fact.\n"
        "- Usually split the 2 naver_home titles into issue/update + debate/comparison and issue/update + reversal/question/surprise.\n"
        "- When natural, let each naver_home title combine at least two of issue/update, debate/comparison, and reversal/question framing.\n"
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
        community_reaction_summary = _build_community_reaction_summary(item)
        community_headlines = _build_community_headline_summary(item)
        normalized_items.append(
            {
                "keyword": keyword,
                "keyword_tokens": _build_keyword_token_summary(keyword),
                "keyword_coverage_rule": _build_keyword_coverage_rule(keyword),
                "category_label": _PROMPT_CATEGORY_LABELS[category_key],
                "overlay": _PROMPT_CATEGORY_OVERLAYS[category_key],
                "pair_hint": _PROMPT_CATEGORY_HOME_ANGLE_HINTS[category_key],
                "freshness_cues": _PROMPT_CATEGORY_FRESHNESS_CUES[category_key],
                "data_hooks": _PROMPT_CATEGORY_DATA_HOOKS[category_key],
                "practical_title_shape": _build_practical_title_shape_hint(keyword),
                "target_context": target_context,
                "signal_summary": signal_summary,
                "source_hint": source_hint,
                "issue_context_summary": issue_context_summary,
                "recent_headlines": recent_headlines,
                "community_reaction_summary": community_reaction_summary,
                "community_headlines": community_headlines,
            }
        )

    return normalized_items


def _format_prompt_item(index: int, item: dict[str, str]) -> str:
    lines = [
        f"Item {index}",
        f"- keyword: {item['keyword']}",
        f"- required keyword tokens: {item['keyword_tokens']}",
        f"- keyword coverage rule: {item['keyword_coverage_rule']}",
        f"- category overlay: {item['category_label']}",
        f"- category focus: {item['overlay']}",
        f"- preferred naver_home pair: {item['pair_hint']}",
        f"- freshness cues: {item['freshness_cues']}",
        f"- data hooks: {item['data_hooks']}",
    ]
    if item.get("practical_title_shape"):
        lines.append(f"- practical title shape: {item['practical_title_shape']}")
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
    if item.get("community_reaction_summary"):
        lines.append(f"- community reaction: {item['community_reaction_summary']}")
    if item.get("community_headlines"):
        lines.append(f"- community headlines: {item['community_headlines']}")
    return "\n".join(lines)


def _build_slot_title_system_prompt(extra_guidance: str) -> str:
    normalized_extra = normalize_text(extra_guidance)
    if not normalized_extra:
        return _SLOT_TITLE_SYSTEM_PROMPT
    return f"{_SLOT_TITLE_SYSTEM_PROMPT}\n\n[ADDITIONAL GUIDANCE]\n{normalized_extra}"


def _normalize_slot_prompt_items(input_items: list[Any]) -> list[dict[str, Any]]:
    normalized_items: list[dict[str, Any]] = []

    for index, raw_item in enumerate(input_items):
        if not isinstance(raw_item, dict):
            continue
        keyword = normalize_text(raw_item.get("keyword"))
        slot_id = normalize_text(raw_item.get("slot_id")) or f"slot_{index}"
        channel = normalize_text(raw_item.get("channel")).lower()
        if channel == "home":
            channel = "naver_home"
        if channel not in {"naver_home", "blog"} or not keyword:
            continue
        try:
            slot_index = max(1, int(raw_item.get("slot_index") or 1))
        except (TypeError, ValueError):
            slot_index = 1

        peer_titles = [
            normalize_text(title)
            for title in (raw_item.get("peer_titles") if isinstance(raw_item.get("peer_titles"), list) else [])
            if normalize_text(title)
        ]
        issues = [
            normalize_text(issue)
            for issue in (raw_item.get("issues") if isinstance(raw_item.get("issues"), list) else [])
            if normalize_text(issue)
        ]
        metrics = raw_item.get("metrics") if isinstance(raw_item.get("metrics"), dict) else {}
        metric_summary = ", ".join(
            f"{normalize_text(key)}={_format_metric_value(value)}"
            for key, value in metrics.items()
            if normalize_text(key) and _format_metric_value(value)
        )
        normalized_items.append(
            {
                "slot_id": slot_id,
                "keyword": keyword,
                "channel": channel,
                "slot_index": slot_index,
                "current_title": normalize_text(raw_item.get("current_title")),
                "peer_titles": peer_titles[:8],
                "issues": issues[:5],
                "score": _coerce_int(raw_item.get("score"), default=0, minimum=0, maximum=100),
                "source_note": normalize_text(raw_item.get("source_note")),
                "source_keywords": [
                    normalize_text(value)
                    for value in (raw_item.get("source_keywords") if isinstance(raw_item.get("source_keywords"), list) else [])
                    if normalize_text(value)
                ][:6],
                "support_keywords": [
                    normalize_text(value)
                    for value in (raw_item.get("support_keywords") if isinstance(raw_item.get("support_keywords"), list) else [])
                    if normalize_text(value)
                ][:6],
                "metrics": metric_summary,
            }
        )

    return normalized_items


def _build_slot_title_user_prompt(input_items: list[dict[str, Any]]) -> str:
    item_blocks = "\n\n".join(
        _format_slot_prompt_item(index + 1, item)
        for index, item in enumerate(input_items)
    )
    return (
        "Generate or rewrite one Korean title per input item.\n\n"
        "Return JSON in this exact shape:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "slot_id": "0_home_1",\n'
        '      "title": "..." \n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Return exactly one output item for every input item.\n"
        "- Preserve the input item order exactly.\n"
        "- Keep each slot_id identical to the input slot_id.\n"
        "- Write the title in natural Korean only.\n"
        "- Do not return commentary, markdown, or code fences.\n\n"
        f"Input items:\n{item_blocks}"
    )


def _format_slot_prompt_item(index: int, item: dict[str, Any]) -> str:
    lines = [
        f"Item {index}",
        f"- slot_id: {item['slot_id']}",
        f"- keyword: {item['keyword']}",
        f"- channel: {item['channel']}",
        f"- slot_index: {item['slot_index']}",
    ]
    if item.get("current_title"):
        lines.append(f"- current_title: {item['current_title']}")
    if item.get("peer_titles"):
        lines.append(f"- peer_titles: {' | '.join(item['peer_titles'])}")
    if item.get("issues"):
        lines.append(f"- issues: {' | '.join(item['issues'])}")
    if "score" in item:
        lines.append(f"- score: {item['score']}")
    if item.get("source_note"):
        lines.append(f"- source_note: {item['source_note']}")
    if item.get("source_keywords"):
        lines.append(f"- source_keywords: {', '.join(item['source_keywords'])}")
    if item.get("support_keywords"):
        lines.append(f"- support_keywords: {', '.join(item['support_keywords'])}")
    if item.get("metrics"):
        lines.append(f"- metrics: {item['metrics']}")
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


def _build_keyword_token_summary(keyword: str) -> str:
    tokens = [token for token in tokenize_text(keyword) if normalize_key(token)]
    return ", ".join(tokens) if tokens else normalize_text(keyword)


def _build_keyword_coverage_rule(keyword: str) -> str:
    tokens = [token for token in tokenize_text(keyword) if normalize_key(token)]
    if len(tokens) <= 1:
        return "Use the full keyword exactly as written in every title."
    return (
        f"Every title must include all tokens in order: {' -> '.join(tokens)}. "
        "You may add short modifiers between tokens, but do not drop, replace, or paraphrase any token."
    )


def _build_practical_title_shape_hint(keyword: str) -> str:
    keyword_key = normalize_key(keyword)
    if not keyword_key:
        return ""
    if any(pattern in keyword_key for pattern in ("사전예약", "예약방법", "신청방법", "오픈일정")):
        return (
            "preorder/application: use open time, link, card benefit, stock window, authentication, "
            "pickup, or payment context instead of generic hype."
        )
    if "가성비" in keyword_key:
        return (
            "value decision: use budget, location, transport, included options, hidden fee, "
            "room condition, or cancellation context instead of vague recommendation language."
        )
    if any(pattern in keyword_key for pattern in ("기준", "조건", "포인트", "체크포인트")):
        return (
            "criteria/checkpoint: spell out concrete evaluation axes, limits, fees, timing, "
            "eligibility, or trade-offs instead of meta wrappers."
        )
    if any(pattern in keyword_key for pattern in ("자주생기는문제", "연결문제", "문제", "오류", "안됨", "끊김", "더블클릭")):
        return (
            "problem/solution: use one symptom plus one cause, fix, or result. "
            "Avoid wrappers like 총정리, 완벽 가이드, or 최신 정보."
        )
    if any(pattern in keyword_key for pattern in ("설정팁", "설정방법", "연결방법")):
        if any(pattern in keyword_key for pattern in ("키보드", "키패드", "한영", "배열", "키맵", "fn")):
            return (
                "setup/help: add device or OS context and the benefit or problem solved. "
                "Prefer cues like 블루투스, 멀티페어링, 키맵, 한영 전환, FN Lock, 배열, or 단축키."
            )
        if any(pattern in keyword_key for pattern in ("마우스", "트랙볼", "버티컬", "유니파잉", "dpi", "클릭")):
            return (
                "setup/help: add device or OS context and the benefit or problem solved. "
                "Prefer cues like 맥북, 윈도우, 블루투스, 유니파잉, DPI, 버튼 설정, or 감도."
            )
        return (
            "setup/help: add device or OS context and the benefit or problem solved. "
            "Prefer cues like OS, pairing, device mode, shortcut, mapping, or benefit solved."
        )
    if "실사용차이" in keyword_key:
        return (
            "real-use difference: use timeframe, user type, grip, weight, click feel, battery, "
            "or workflow context instead of generic review language."
        )
    if "장단점" in keyword_key:
        return (
            "pros/cons decision: show a concrete trade-off such as grip, weight, noise, battery, "
            "price, portability, or button feel."
        )
    return ""


def _build_practical_title_shape_hint(keyword: str) -> str:
    keyword_text = normalize_text(keyword)
    keyword_key = normalize_key(keyword_text)
    if not keyword_key:
        return ""
    if detect_category(keyword_text) == "finance":
        if any(token in keyword_text for token in ("지수", "선물", "실시간", "시세", "금시세", "금값", "코스피", "ETF", "리밸런싱")):
            return (
                "finance market: use gap, interpretation, checkpoint, variable, update timing, "
                "domestic-vs-global difference, or reaction split. Avoid fake live claims and device-style frames."
            )
        return (
            "finance account/policy: use eligibility, fee, benefit, delay reason, document, timing, "
            "or non-face-to-face process frames. Avoid 실사용 차이 or device-style setup framing."
        )
    if any(token in keyword_text for token in ("사전예약", "예약방법", "요청방법", "오픈일정")):
        return (
            "preorder/application: use open time, link, card benefit, stock window, authentication, "
            "pickup, or payment context instead of generic hype."
        )
    if "가성비" in keyword_text:
        return (
            "value decision: use budget, location, transport, included options, hidden fee, "
            "room condition, or cancellation context instead of vague recommendation language."
        )
    if any(token in keyword_text for token in ("기준", "조건", "포인트", "체크포인트")):
        return (
            "criteria/checkpoint: spell out concrete evaluation axes, limits, fees, timing, "
            "eligibility, or trade-offs instead of meta wrappers."
        )
    if any(token in keyword_text for token in ("자주 생기는 문제", "연결 문제", "문제", "오류", "안됨", "더블클릭")):
        return (
            "problem/solution: use one symptom plus one cause, fix, or result. "
            "Avoid wrappers like 총정리, 완벽 가이드, or 최신 정보."
        )
    if any(token in keyword_text for token in ("설정 팁", "설정방법", "연결방법")):
        return (
            "setup/help: add device or OS context and the benefit or problem solved. "
            "Prefer cues like OS, pairing, device mode, shortcut, mapping, or benefit solved."
        )
    if "실사용 차이" in keyword_text:
        return (
            "real-use difference: use timeframe, user type, grip, weight, click feel, battery, "
            "or workflow context instead of generic review language."
        )
    if "장단점" in keyword_text:
        return (
            "pros/cons decision: show a concrete trade-off such as grip, weight, noise, battery, "
            "price, portability, or button feel."
        )
    return ""
    """
    keyword_key = normalize_key(keyword)
    if not keyword_key:
        return ""
    if detect_category(keyword) == "finance":
        if any(token in keyword_key for token in ("지수", "선물", "시세", "금시세", "금값", "코스피", "etf", "리밸런싱")):
            return (
                "finance market: use gap, interpretation, checkpoint, variable, update timing, "
                "domestic-vs-global difference, or reaction split. Avoid fake live claims and device-style frames."
            )
        return (
            "finance account/policy: use eligibility, fee, benefit, delay reason, document, timing, "
            "or non-face-to-face process frames. Avoid 실사용 차이 or device-style setup framing."
        )
    if any(pattern in keyword_key for pattern in ("?ъ쟾?덉빟", "?덉빟諛⑸쾿", "?좎껌諛⑸쾿", "?ㅽ뵂?쇱젙")):
        return (
            "preorder/application: use open time, link, card benefit, stock window, authentication, "
            "pickup, or payment context instead of generic hype."
        )
    if "媛?깅퉬" in keyword_key:
        return (
            "value decision: use budget, location, transport, included options, hidden fee, "
            "room condition, or cancellation context instead of vague recommendation language."
        )
    if any(pattern in keyword_key for pattern in ("湲곗?", "議곌굔", "?ъ씤??, "泥댄겕?ъ씤??)):
        return (
            "criteria/checkpoint: spell out concrete evaluation axes, limits, fees, timing, "
            "eligibility, or trade-offs instead of meta wrappers."
        )
    if any(pattern in keyword_key for pattern in ("?먯＜?앷린?붾Ц??, "?곌껐臾몄젣", "臾몄젣", "?ㅻ쪟", "?덈맖", "?딄?", "?붾툝?대┃")):
        return (
            "problem/solution: use one symptom plus one cause, fix, or result. "
            "Avoid wrappers like 珥앹젙由? ?꾨꼍 媛?대뱶, or 理쒖떊 ?뺣낫."
        )
    if any(pattern in keyword_key for pattern in ("?ㅼ젙??, "?ㅼ젙諛⑸쾿", "?곌껐諛⑸쾿")):
        if any(pattern in keyword_key for pattern in ("?ㅻ낫??, "?ㅽ뙣??, "?쒖쁺", "諛곗뿴", "?ㅻ㏊", "fn")):
            return (
                "setup/help: add device or OS context and the benefit or problem solved. "
                "Prefer cues like 釉붾（?ъ뒪, 硫?고럹?대쭅, ?ㅻ㏊, ?쒖쁺 ?꾪솚, FN Lock, 諛곗뿴, or ?⑥텞??"
            )
        if any(pattern in keyword_key for pattern in ("留덉슦??, "?몃옓蹂?, "踰꾪떚而?, "?좊땲?뚯엵", "dpi", "?대┃")):
            return (
                "setup/help: add device or OS context and the benefit or problem solved. "
                "Prefer cues like 留λ턿, ?덈룄?? 釉붾（?ъ뒪, ?좊땲?뚯엵, DPI, 踰꾪듉 ?ㅼ젙, or 媛먮룄."
            )
        return (
            "setup/help: add device or OS context and the benefit or problem solved. "
            "Prefer cues like OS, pairing, device mode, shortcut, mapping, or benefit solved."
        )
    if "?ㅼ궗?⑹감?? in keyword_key:
        return (
            "real-use difference: use timeframe, user type, grip, weight, click feel, battery, "
            "or workflow context instead of generic review language."
        )
    if "?λ떒?? in keyword_key:
        return (
            "pros/cons decision: show a concrete trade-off such as grip, weight, noise, battery, "
            "price, portability, or button feel."
        )
    return ""


    """


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

    source_selection_mode = normalize_text(item.get("source_selection_mode") or item.get("selection_mode"))
    if source_selection_mode:
        parts.append(f"selection {source_selection_mode}")

    source_keywords = item.get("source_keywords")
    if isinstance(source_keywords, list):
        normalized_source_keywords = [normalize_text(keyword) for keyword in source_keywords if normalize_text(keyword)]
        if normalized_source_keywords:
            parts.append(f"source keywords {', '.join(normalized_source_keywords[:3])}")

    source_selection_reason = normalize_text(item.get("source_selection_reason") or item.get("selection_reason"))
    if source_selection_reason:
        parts.append(f"selection note {source_selection_reason}")

    verification_status = normalize_text(item.get("verification_status"))
    if verification_status:
        parts.append(f"status {verification_status}")

    validated_score = _format_metric_value(item.get("verified_score") or item.get("projected_score"))
    if validated_score:
        parts.append(f"validated score {validated_score}")

    source_note = normalize_text(item.get("source_note"))
    if source_note:
        parts.append(f"note {source_note}")

    return " / ".join(parts[:6])


def _build_issue_context_summary(item: dict[str, Any]) -> str:
    issue_context = item.get("issue_context")
    if not isinstance(issue_context, dict):
        return ""

    parts: list[str] = []
    issue_source_mode = normalize_issue_source_mode(issue_context.get("issue_source_mode"))
    parts.append(f"mode {issue_source_mode}")

    fetched_at = normalize_text(issue_context.get("fetched_at"))
    if fetched_at:
        parts.append(f"fetched {fetched_at[:10]}")

    title_count = _coerce_int(issue_context.get("title_count"), default=0, minimum=0, maximum=20)
    news_count = _coerce_int(issue_context.get("news_count"), default=0, minimum=0, maximum=20)
    if title_count > 0:
        parts.append(f"news {news_count}/{title_count}")

    community_reaction = issue_context.get("community_reaction_summary")
    if isinstance(community_reaction, dict):
        community_count = _coerce_int(community_reaction.get("title_count"), default=0, minimum=0, maximum=20)
        if title_count > 0 and community_count > 0:
            parts.append(f"community {community_count}/{title_count}")

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

    issue_source_mode = normalize_issue_source_mode(issue_context.get("issue_source_mode"))
    if issue_source_mode == "reaction":
        headline_candidates = None
    else:
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


def _build_community_reaction_summary(item: dict[str, Any]) -> str:
    issue_context = item.get("issue_context")
    if not isinstance(issue_context, dict):
        return ""

    community_reaction = issue_context.get("community_reaction_summary")
    if not isinstance(community_reaction, dict):
        return ""

    parts: list[str] = []
    title_count = _coerce_int(community_reaction.get("title_count"), default=0, minimum=0, maximum=20)
    if title_count > 0:
        parts.append(f"{title_count} reaction titles")

    source_mix = community_reaction.get("source_mix")
    if isinstance(source_mix, dict):
        source_parts = [
            f"{_format_community_source_label(source)} {int(count)}"
            for source, count in source_mix.items()
            if normalize_text(source) and int(count or 0) > 0
        ]
        if source_parts:
            parts.append(f"sources {', '.join(source_parts[:3])}")

    terms = community_reaction.get("terms")
    if isinstance(terms, list):
        normalized_terms = [normalize_text(term) for term in terms if normalize_text(term)]
        if normalized_terms:
            parts.append(f"terms {', '.join(normalized_terms[:4])}")

    comparison_axes = community_reaction.get("comparison_axes")
    if isinstance(comparison_axes, list):
        normalized_axes = [normalize_text(term) for term in comparison_axes if normalize_text(term)]
        if normalized_axes:
            parts.append(f"compare {', '.join(normalized_axes[:3])}")

    pain_points = community_reaction.get("pain_points")
    if isinstance(pain_points, list):
        normalized_points = [normalize_text(term) for term in pain_points if normalize_text(term)]
        if normalized_points:
            parts.append(f"watchouts {', '.join(normalized_points[:3])}")

    return " / ".join(parts[:4])


def _build_community_headline_summary(item: dict[str, Any]) -> str:
    issue_context = item.get("issue_context")
    if not isinstance(issue_context, dict):
        return ""

    community_reaction = issue_context.get("community_reaction_summary")
    if not isinstance(community_reaction, dict):
        return ""

    headline_candidates = community_reaction.get("headlines")
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


def resolve_issue_context(
    raw_context: dict[str, Any],
    *,
    issue_source_mode: str = DEFAULT_ISSUE_SOURCE_MODE,
    community_sources: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    if not isinstance(raw_context, dict):
        return {}

    normalized_keyword = normalize_text(raw_context.get("query") or raw_context.get("keyword"))
    normalized_titles = _coerce_issue_titles(raw_context.get("top_titles"))
    if not normalized_titles:
        return {
            **raw_context,
            "issue_source_mode": normalize_issue_source_mode(issue_source_mode),
            "community_sources": list(community_sources),
        }

    source_counts = Counter(
        normalize_text(item.get("source_bucket"))
        for item in normalized_titles
        if normalize_text(item.get("source_bucket"))
    )
    news_headlines = [
        normalize_text(item.get("title"))
        for item in normalized_titles
        if normalize_text(item.get("source_bucket")) == "news" and normalize_text(item.get("title"))
    ]
    issue_context = {
        **raw_context,
        "query": normalized_keyword,
        "fetched_at": normalize_text(raw_context.get("fetched_at"))
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        "search_url": normalize_text(raw_context.get("search_url"))
        or (build_search_url(normalized_keyword) if normalized_keyword else ""),
        "title_count": _coerce_int(
            raw_context.get("title_count"),
            default=len(normalized_titles),
            minimum=0,
            maximum=20,
        ) or len(normalized_titles),
        "news_count": _coerce_int(
            raw_context.get("news_count"),
            default=len(news_headlines),
            minimum=0,
            maximum=20,
        ) if not news_headlines else len(news_headlines),
        "source_mix": dict(source_counts) if source_counts else dict(raw_context.get("source_mix") or {}),
        "issue_terms": _coerce_text_list(raw_context.get("issue_terms") or raw_context.get("common_terms"))
        or _extract_issue_terms(normalized_keyword, normalized_titles),
        "top_headlines": [
            normalize_text(item.get("title"))
            for item in normalized_titles[:_ISSUE_CONTEXT_HEADLINE_LIMIT]
            if normalize_text(item.get("title"))
        ],
        "news_headlines": (
            news_headlines[:_ISSUE_CONTEXT_HEADLINE_LIMIT]
            or _coerce_text_list(raw_context.get("news_headlines"))
        ),
        "issue_source_mode": normalize_issue_source_mode(issue_source_mode),
        "community_sources": list(community_sources),
    }
    community_reaction = _build_community_reaction_data(
        normalized_keyword,
        normalized_titles,
        list(community_sources),
    )
    if community_reaction:
        issue_context["community_reaction_summary"] = community_reaction
    return issue_context


def _coerce_issue_titles(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            title = normalize_text(item.get("title"))
            if not title:
                continue
            normalized_items.append(
                {
                    "rank": _coerce_int(item.get("rank"), default=index, minimum=1, maximum=20),
                    "title": title,
                    "url": normalize_text(item.get("url")),
                    "domain": normalize_text(item.get("domain")),
                    "source_bucket": normalize_text(item.get("source_bucket")),
                    "intent_key": normalize_text(item.get("intent_key")),
                }
            )
            continue

        title = normalize_text(item)
        if not title:
            continue
        normalized_items.append(
            {
                "rank": index,
                "title": title,
                "url": "",
                "domain": "",
                "source_bucket": "",
                "intent_key": "",
            }
        )
    return normalized_items


def _build_community_reaction_data(
    keyword: str,
    titles: list[dict[str, Any]],
    community_sources: list[str],
) -> dict[str, Any]:
    if not titles or not community_sources:
        return {}

    matched_titles = [
        item
        for item in titles
        if match_domain_against_allowlist(item.get("domain", ""), community_sources)
    ]
    if not matched_titles:
        return {}

    source_counts = Counter(
        normalize_text(item.get("domain"))
        for item in matched_titles
        if normalize_text(item.get("domain"))
    )
    terms = _extract_issue_terms(keyword, matched_titles)
    comparison_axes = _extract_matching_terms(matched_titles, _COMMUNITY_COMPARISON_TERMS)
    pain_points = _extract_matching_terms(matched_titles, _COMMUNITY_PAIN_TERMS)
    reaction_cues = _extract_matching_terms(matched_titles, _COMMUNITY_REACTION_TERMS)
    return {
        "title_count": len(matched_titles),
        "selected_sources": describe_community_domains(community_sources),
        "source_mix": dict(source_counts),
        "terms": terms[:4],
        "comparison_axes": comparison_axes[:3],
        "pain_points": pain_points[:3],
        "reaction_cues": reaction_cues[:3],
        "headlines": [
            normalize_text(item.get("title"))
            for item in matched_titles[:_ISSUE_CONTEXT_HEADLINE_LIMIT]
            if normalize_text(item.get("title"))
        ],
    }


def _extract_matching_terms(titles: list[dict[str, Any]], terms: tuple[str, ...]) -> list[str]:
    original_map = {normalize_key(term): term for term in terms if normalize_key(term)}
    counter: Counter[str] = Counter()

    for item in titles:
        raw_title = normalize_text(item.get("title"))
        if not raw_title:
            continue
        title_key = normalize_key(raw_title)
        if not title_key:
            continue
        matched_keys = {
            term_key
            for term_key in original_map
            if term_key and term_key in title_key
        }
        for term_key in matched_keys:
            counter[term_key] += 1

    return [
        original_map[term_key]
        for term_key, _count in counter.most_common(4)
        if term_key in original_map
    ]


def _format_community_source_label(value: Any) -> str:
    labels = describe_community_domains([str(value or "")])
    return labels[0] if labels else normalize_text(value)


def _coerce_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


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

        if isinstance(item.get("issue_context"), dict):
            item["issue_context"] = resolve_issue_context(
                item["issue_context"],
                issue_source_mode=options.issue_source_mode,
                community_sources=options.community_sources,
            )
        elif keyword and remaining > 0:
            issue_context = _fetch_live_issue_context(keyword, options=options)
            if issue_context:
                item["issue_context"] = issue_context
            remaining -= 1

        if isinstance(raw_item, dict) or isinstance(item.get("issue_context"), dict):
            enriched_items.append(item)
        else:
            enriched_items.append(keyword)

    return enriched_items


def _fetch_live_issue_context(keyword: str, *, options: TitleGenerationOptions | None = None) -> dict[str, Any]:
    normalized_keyword = normalize_text(keyword)
    issue_source_mode = normalize_issue_source_mode(
        options.issue_source_mode if options is not None else DEFAULT_ISSUE_SOURCE_MODE
    )
    community_sources = tuple(options.community_sources if options is not None else ())
    cache_key = (
        normalize_key(normalized_keyword),
        _build_prompt_today_label(),
        issue_source_mode,
        "|".join(community_sources),
    )
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

    issue_context = resolve_issue_context(
        {
            "query": normalized_keyword,
            "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "search_url": build_search_url(normalized_keyword),
            "top_titles": titles,
        },
        issue_source_mode=issue_source_mode,
        community_sources=community_sources,
    )
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


def _parse_slot_title_items(payload: Any) -> list[dict[str, str]]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        raise TitleProviderError("Provider JSON must include an items array.")

    normalized_items: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        slot_id = normalize_text(item.get("slot_id"))
        title = normalize_text(item.get("title"))
        if not slot_id or not title:
            continue
        normalized_items.append(
            {
                "slot_id": slot_id,
                "title": title,
            }
        )
    return normalized_items


def _extract_json_object(content: str) -> Any:
    return _parse_json_with_repairs(
        content,
        empty_message="Provider returned empty content.",
        missing_message="Provider response did not contain JSON.",
        invalid_message="Provider response contained invalid JSON.",
    )


def _parse_json_with_repairs(
    raw_text: str,
    *,
    empty_message: str,
    missing_message: str,
    invalid_message: str,
) -> Any:
    normalized_text = normalize_text(str(raw_text or "").replace("\ufeff", ""))
    if not normalized_text:
        raise TitleProviderError(empty_message)

    saw_json_shape = False
    for candidate in _iter_json_candidate_texts(normalized_text):
        saw_json_shape = True
        parsed = _try_load_json_candidate(candidate)
        if parsed is not None:
            return parsed

    if not saw_json_shape:
        raise TitleProviderError(missing_message)
    raise TitleProviderError(invalid_message)


def _iter_json_candidate_texts(raw_text: str) -> list[str]:
    candidates: list[str] = []

    def add_candidate(value: str) -> None:
        normalized = normalize_text(value)
        if normalized and ("{" in normalized or "[" in normalized) and normalized not in candidates:
            candidates.append(normalized)

    add_candidate(raw_text)
    stripped_fence = _strip_code_fence(raw_text)
    add_candidate(stripped_fence)

    for base in list(candidates):
        balanced = _extract_balanced_json_snippet(base)
        if balanced:
            add_candidate(balanced)

    repaired_candidates: list[str] = []
    for candidate in candidates:
        repaired_candidates.append(candidate)
        trailing_comma_fixed = _remove_trailing_json_commas(candidate)
        if trailing_comma_fixed != candidate:
            repaired_candidates.append(trailing_comma_fixed)

    deduped_candidates: list[str] = []
    for candidate in repaired_candidates:
        normalized = normalize_text(candidate)
        if normalized and normalized not in deduped_candidates:
            deduped_candidates.append(normalized)
    return deduped_candidates


def _strip_code_fence(raw_text: str) -> str:
    lines = str(raw_text or "").strip().splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return str(raw_text or "").strip()


def _extract_balanced_json_snippet(raw_text: str) -> str:
    text = str(raw_text or "")
    start_candidates = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not start_candidates:
        return ""

    start_index = min(start_candidates)
    stack: list[str] = []
    in_string = False
    escape_next = False
    closing_for = {"{": "}", "[": "]"}
    opening_for = {"}": "{", "]": "["}

    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == "\"":
                in_string = False
            continue

        if char == "\"":
            in_string = True
            continue

        if char in closing_for:
            stack.append(char)
            continue

        if char in opening_for:
            if not stack or stack[-1] != opening_for[char]:
                return ""
            stack.pop()
            if not stack:
                return text[start_index:index + 1].strip()

    return ""


def _remove_trailing_json_commas(raw_text: str) -> str:
    text = str(raw_text or "")
    while True:
        updated = re.sub(r",(?=\s*[}\]])", "", text)
        if updated == text:
            return updated
        text = updated


def _try_load_json_candidate(candidate: str) -> Any | None:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _normalize_title_list(raw_titles: Any, max_length: int | None = None) -> list[str]:
    if not isinstance(raw_titles, list):
        return []

    normalized_titles: list[str] = []
    seen: set[str] = set()
    for raw_title in raw_titles:
        title = _normalize_title_surface(raw_title)
        if not title:
            continue
        if max_length is not None and len(title) > max_length:
            title = title[:max_length].rstrip()
        if not title or title in seen:
            continue
        seen.add(title)
        normalized_titles.append(title)
    return normalized_titles[:2]


def _normalize_title_surface(value: Any) -> str:
    title = normalize_text(value)
    if not title:
        return ""
    title = title.replace(":", " ").replace("：", " ")
    return normalize_text(title)


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


def _resolve_retry_delay_seconds(
    detail: str,
    *,
    header_value: str = "",
    attempt: int = 0,
) -> float:
    header_text = normalize_text(header_value)
    if header_text:
        try:
            return max(1.0, min(60.0, float(header_text)))
        except ValueError:
            pass

    normalized_detail = normalize_text(detail)
    marker = "Please retry in "
    if marker in normalized_detail:
        tail = normalized_detail.split(marker, 1)[1]
        number_buffer: list[str] = []
        for character in tail:
            if character.isdigit() or character == ".":
                number_buffer.append(character)
                continue
            if number_buffer:
                break
        if number_buffer:
            try:
                return max(1.0, min(60.0, float("".join(number_buffer))))
            except ValueError:
                pass

    return min(8.0, 1.5 * (attempt + 1))


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
