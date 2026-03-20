from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


TitleType = Literal["naver_home", "blog"]
CategoryType = Literal["product", "travel", "finance", "health", "real_estate", "food", "general"]


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


class GeneratedTitles(TypedDict):
    naver_home: list[str]
    blog: list[str]


class TitleCheckItem(TypedDict, total=False):
    title: str
    score: int
    status: str
    critical: bool
    issues: list[str]
    checks: dict[str, bool]


class TitleQualityReport(TypedDict, total=False):
    bundle_score: int
    status: str
    label: str
    passes_threshold: bool
    retry_recommended: bool
    issue_count: int
    issues: list[str]
    summary: str
    channel_scores: dict[str, int]
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
