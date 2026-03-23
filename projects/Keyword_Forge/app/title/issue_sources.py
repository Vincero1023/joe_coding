from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


DEFAULT_ISSUE_SOURCE_MODE = "mixed"
ISSUE_SOURCE_MODE_CHOICES: tuple[dict[str, str], ...] = (
    {
        "key": "news",
        "label": "뉴스형",
        "description": "뉴스/공식 발표 쪽 신호를 더 강하게 반영합니다.",
    },
    {
        "key": "reaction",
        "label": "반응형",
        "description": "선택한 커뮤니티/블로그 반응을 더 강하게 반영합니다.",
    },
    {
        "key": "mixed",
        "label": "혼합형",
        "description": "뉴스와 반응형 신호를 함께 반영합니다.",
    },
)

COMMUNITY_SOURCE_LIBRARY: tuple[dict[str, Any], ...] = (
    {
        "key": "cafe_naver",
        "label": "네이버 카페",
        "domains": ("cafe.naver.com",),
    },
    {
        "key": "blog_naver",
        "label": "네이버 블로그",
        "domains": ("blog.naver.com",),
    },
    {
        "key": "post_naver",
        "label": "네이버 포스트",
        "domains": ("post.naver.com",),
    },
    {
        "key": "dcinside",
        "label": "디시인사이드",
        "domains": ("dcinside.com", "gall.dcinside.com"),
    },
    {
        "key": "clien",
        "label": "클리앙",
        "domains": ("clien.net",),
    },
    {
        "key": "ppomppu",
        "label": "뽐뿌",
        "domains": ("ppomppu.co.kr",),
    },
)

DEFAULT_COMMUNITY_SOURCE_KEYS: tuple[str, ...] = (
    "cafe_naver",
    "blog_naver",
    "post_naver",
)

_COMMUNITY_SOURCE_KEY_MAP = {
    str(item["key"]).strip().lower(): tuple(str(domain).strip().lower() for domain in item.get("domains", ()))
    for item in COMMUNITY_SOURCE_LIBRARY
}
_COMMUNITY_SOURCE_LABEL_MAP = {
    str(item["key"]).strip().lower(): str(item.get("label") or "").strip()
    for item in COMMUNITY_SOURCE_LIBRARY
}
_COMMUNITY_DOMAIN_LABEL_MAP = {
    str(domain).strip().lower(): str(item.get("label") or "").strip()
    for item in COMMUNITY_SOURCE_LIBRARY
    for domain in item.get("domains", ())
}


def normalize_issue_source_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {item["key"] for item in ISSUE_SOURCE_MODE_CHOICES}:
        return normalized
    return DEFAULT_ISSUE_SOURCE_MODE


def normalize_community_source_keys(values: Any) -> list[str]:
    normalized_values = _coerce_string_list(values)
    seen: set[str] = set()
    resolved: list[str] = []
    for value in normalized_values:
        if value in _COMMUNITY_SOURCE_KEY_MAP and value not in seen:
            seen.add(value)
            resolved.append(value)
    return resolved


def normalize_custom_domain_list(values: Any) -> list[str]:
    seen: set[str] = set()
    normalized_domains: list[str] = []
    for value in _coerce_string_list(values):
        normalized = normalize_domain(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_domains.append(normalized)
    return normalized_domains


def resolve_community_source_domains(
    source_values: Any,
    custom_domains: Any = None,
    *,
    use_default_when_empty: bool = True,
) -> list[str]:
    raw_values = _coerce_string_list(source_values)
    source_keys = [value for value in raw_values if value in _COMMUNITY_SOURCE_KEY_MAP]
    direct_domains = [
        normalize_domain(value)
        for value in raw_values
        if value not in _COMMUNITY_SOURCE_KEY_MAP and normalize_domain(value)
    ]
    if not source_keys and use_default_when_empty:
        source_keys = list(DEFAULT_COMMUNITY_SOURCE_KEYS)

    seen: set[str] = set()
    domains: list[str] = []

    for key in source_keys:
        for domain in _COMMUNITY_SOURCE_KEY_MAP.get(key, ()):
            if domain and domain not in seen:
                seen.add(domain)
                domains.append(domain)

    for domain in direct_domains:
        if domain not in seen:
            seen.add(domain)
            domains.append(domain)

    for domain in normalize_custom_domain_list(custom_domains):
        if domain not in seen:
            seen.add(domain)
            domains.append(domain)

    return domains


def normalize_domain(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""

    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.netloc or parsed.path or ""

    raw = raw.split("/")[0].split("?")[0].split("#")[0].strip()
    raw = raw.lstrip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


def match_domain_against_allowlist(domain: str, allowed_domains: list[str] | tuple[str, ...]) -> bool:
    normalized_domain = normalize_domain(domain)
    if not normalized_domain:
        return False

    for allowed in allowed_domains:
        normalized_allowed = normalize_domain(allowed)
        if not normalized_allowed:
            continue
        if normalized_domain == normalized_allowed or normalized_domain.endswith(f".{normalized_allowed}"):
            return True
    return False


def describe_community_domains(domains: list[str] | tuple[str, ...]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for domain in domains:
        normalized = normalize_domain(domain)
        if not normalized:
            continue
        label = _COMMUNITY_DOMAIN_LABEL_MAP.get(normalized) or normalized
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def build_issue_source_mode_payload() -> list[dict[str, str]]:
    return [dict(item) for item in ISSUE_SOURCE_MODE_CHOICES]


def build_community_source_payload() -> list[dict[str, Any]]:
    return [
        {
            "key": str(item["key"]),
            "label": str(item["label"]),
            "domains": list(item.get("domains", ())),
            "is_default": str(item["key"]) in DEFAULT_COMMUNITY_SOURCE_KEYS,
        }
        for item in COMMUNITY_SOURCE_LIBRARY
    ]


def _coerce_string_list(values: Any) -> list[str]:
    if isinstance(values, str):
        raw_values = [chunk for chunk in values.replace("\r", "\n").replace(",", "\n").split("\n")]
    elif isinstance(values, (list, tuple, set)):
        raw_values = [str(value or "") for value in values]
    else:
        raw_values = []

    seen: set[str] = set()
    normalized_values: list[str] = []
    for value in raw_values:
        normalized = str(value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)
    return normalized_values
