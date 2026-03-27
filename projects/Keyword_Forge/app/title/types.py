from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict


TitleType = Literal["naver_home", "blog", "hybrid"]
CategoryType = Literal["product", "travel", "finance", "health", "real_estate", "food", "general"]
TITLE_CHANNEL_ORDER: tuple[TitleType, ...] = ("naver_home", "blog", "hybrid")
DEFAULT_TITLE_CHANNEL_ORDER: tuple[TitleType, ...] = ("naver_home", "blog")
TITLE_CHANNEL_LABELS: dict[TitleType, str] = {
    "naver_home": "네이버 홈형",
    "blog": "블로그형",
    "hybrid": "공용형",
}
TITLE_CHANNEL_SHORT_LABELS: dict[TitleType, str] = {
    "naver_home": "홈판",
    "blog": "블로그형",
    "hybrid": "둘다",
}
TITLE_CHANNEL_EXPORT_SEGMENTS: dict[TitleType, str] = {
    "naver_home": "home",
    "blog": "blog",
    "hybrid": "both",
}
TITLE_CHANNEL_SLOT_LABELS: dict[TitleType, str] = {
    "naver_home": "home",
    "blog": "blog",
    "hybrid": "hybrid",
}
TITLE_CHANNEL_SLOT_TO_NAME: dict[str, TitleType] = {
    "home": "naver_home",
    "naver_home": "naver_home",
    "blog": "blog",
    "hybrid": "hybrid",
    "both": "hybrid",
}
DEFAULT_TITLE_CHANNEL_COUNTS: dict[TitleType, int] = {
    "naver_home": 2,
    "blog": 2,
    "hybrid": 0,
}
MAX_TITLE_COUNT_PER_CHANNEL = 4


class KeywordMetrics(TypedDict, total=False):
    volume: float
    cpc: float
    competition: float
    bid: float
    profit: float
    opportunity: float


class SelectedKeywordItem(TypedDict, total=False):
    keyword: str
    score: float
    metrics: KeywordMetrics


class GeneratedTitles(TypedDict, total=False):
    naver_home: list[str]
    blog: list[str]
    hybrid: list[str]


class TitleCheckItem(TypedDict, total=False):
    title: str
    score: int
    status: str
    critical: bool
    issues: list[str]
    score_breakdown: dict[str, int]
    checks: dict[str, bool]


class TitleQualityReport(TypedDict, total=False):
    bundle_score: int
    status: str
    label: str
    passes_threshold: bool
    retry_recommended: bool
    recommended_pair_ready: bool
    usable_pair_ready: bool
    issue_count: int
    issues: list[str]
    summary: str
    channel_scores: dict[str, int]
    channel_good_counts: dict[str, int]
    channel_usable_counts: dict[str, int]
    title_checks: dict[str, list[TitleCheckItem]]


class TitleOutputItem(TypedDict, total=False):
    target_id: str
    keyword: str
    target_mode: str
    target_mode_label: str
    base_keyword: str
    support_keywords: list[str]
    source_keywords: list[str]
    source_kind: str
    source_note: str
    cluster_id: str
    source_suggestion_id: str
    titles: GeneratedTitles
    quality_report: TitleQualityReport


@dataclass(frozen=True)
class TriggerBundle:
    time: str
    curiosity: str
    contrast: str
    numeric: str
    opportunity: str


def normalize_title_channel_name(value: Any) -> TitleType | None:
    normalized = str(value or "").strip().lower()
    return TITLE_CHANNEL_SLOT_TO_NAME.get(normalized)


def normalize_title_channels(raw_channels: Any) -> tuple[TitleType, ...]:
    values = raw_channels if isinstance(raw_channels, (list, tuple, set)) else [raw_channels]
    normalized_channels: list[TitleType] = []
    for value in values:
        channel = normalize_title_channel_name(value)
        if channel and channel not in normalized_channels:
            normalized_channels.append(channel)
    return tuple(normalized_channels)


def normalize_title_channel_count(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(0, min(MAX_TITLE_COUNT_PER_CHANNEL, number))


def build_title_channel_counts(
    *,
    raw_counts: Any = None,
    enabled_channels: tuple[TitleType, ...] | list[TitleType] | None = None,
) -> dict[TitleType, int]:
    source = raw_counts if isinstance(raw_counts, dict) else {}
    resolved_enabled = tuple(enabled_channels or DEFAULT_TITLE_CHANNEL_ORDER)
    counts: dict[TitleType, int] = {}
    for channel_name in TITLE_CHANNEL_ORDER:
        default_count = DEFAULT_TITLE_CHANNEL_COUNTS[channel_name]
        if channel_name not in resolved_enabled:
            counts[channel_name] = 0
            continue
        counts[channel_name] = max(
            1,
            normalize_title_channel_count(source.get(channel_name), default=default_count or 1),
        )
    return counts


def create_empty_generated_titles() -> GeneratedTitles:
    return {
        "naver_home": [],
        "blog": [],
        "hybrid": [],
    }
