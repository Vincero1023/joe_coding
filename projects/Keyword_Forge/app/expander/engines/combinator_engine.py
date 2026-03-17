from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text, tokenize_text


_LOCATION_HINTS = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "제주",
    "강남",
    "홍대",
    "성수",
)

_LOCATION_SUFFIXES = ("시", "군", "구", "동", "역", "읍", "면")
_PLACE_BY_CATEGORY = {
    "맛집": ["맛집", "카페"],
    "국내여행": ["명소", "코스"],
    "세계여행": ["여행지", "코스"],
    "패션미용": ["매장", "샵"],
    "비즈니스경제": ["업체", "브랜드"],
}
_DEFAULT_TIME_SLOTS = ["오늘", "주말"]


def expand_combinator_engine(
    keyword: str,
    strategy: dict[str, Any] | None = None,
    collected_item: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    base_keyword = normalize_text(keyword)
    if not base_keyword:
        return []

    slots = _build_slot_map(base_keyword, strategy, collected_item)
    results: list[dict[str, str]] = []

    for value in slots["intent"]:
        results.append(_make_item(f"{base_keyword} {value}", base_keyword))

    for value in slots["category"]:
        results.append(_make_item(f"{base_keyword} {value}", base_keyword))

    for value in slots["place"]:
        results.append(_make_item(f"{base_keyword} {value}", base_keyword))

    for value in slots["time"]:
        results.append(_make_item(f"{base_keyword} {value}", base_keyword))

    for location in slots["location"]:
        for intent in slots["intent"][:2]:
            results.append(_make_item(f"{location} {base_keyword} {intent}", base_keyword))

    return _deduplicate_items(results)


def _build_slot_map(
    base_keyword: str,
    strategy: dict[str, Any] | None,
    collected_item: dict[str, Any] | None,
) -> dict[str, list[str]]:
    category = normalize_text(collected_item.get("category")) if isinstance(collected_item, dict) else ""
    category_key = category.replace("·", "")
    strategy = strategy or {}

    slot_map = {
        "location": _extract_locations(base_keyword),
        "category": [category] if category else [],
        "intent": [normalize_text(item) for item in strategy.get("intent_terms", []) if normalize_text(item)],
        "place": list(_PLACE_BY_CATEGORY.get(category_key, [])),
        "time": [normalize_text(item) for item in strategy.get("time_terms", []) if normalize_text(item)],
    }

    if not slot_map["intent"]:
        slot_map["intent"] = ["추천", "후기"]
    if not slot_map["time"]:
        slot_map["time"] = list(_DEFAULT_TIME_SLOTS)

    return {name: _unique_non_base(values, base_keyword) for name, values in slot_map.items()}


def _extract_locations(keyword: str) -> list[str]:
    tokens = tokenize_text(keyword)
    results = []
    for token in tokens:
        if token in _LOCATION_HINTS or token.endswith(_LOCATION_SUFFIXES):
            results.append(token)
    return list(dict.fromkeys(results))


def _unique_non_base(values: list[str], base_keyword: str) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(value)
        if not text or text in base_keyword or text in seen:
            continue
        seen.add(text)
        unique_values.append(text)
    return unique_values


def _make_item(keyword: str, origin: str) -> dict[str, str]:
    return {
        "keyword": normalize_text(keyword),
        "origin": origin,
        "type": "combinator",
    }


def _deduplicate_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduplicated: list[dict[str, str]] = []
    for item in items:
        key = normalize_text(item.get("keyword"))
        if not key or key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated
