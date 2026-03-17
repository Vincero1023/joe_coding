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


class TitleOutputItem(TypedDict):
    keyword: str
    titles: GeneratedTitles


@dataclass(frozen=True)
class TriggerBundle:
    time: str
    curiosity: str
    contrast: str
    numeric: str
    opportunity: str
