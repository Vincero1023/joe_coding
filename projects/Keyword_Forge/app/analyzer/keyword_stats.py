from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from app.expander.utils.tokenizer import normalize_key, normalize_text


_NUMBER_PATTERN = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "pc_searches": ("pc_searches", "pc_search", "pc", "pc_volume", "pc_count"),
    "mobile_searches": (
        "mobile_searches",
        "mobile_search",
        "mo_searches",
        "mo_search",
        "mo",
        "mobile_volume",
        "mo_count",
    ),
    "total_searches": (
        "total_searches",
        "total_search",
        "search_volume",
        "monthly_searches",
        "sum",
        "total",
        "volume",
    ),
    "blog_results": ("blog_results", "blog_count", "blogs", "blog"),
    "pc_clicks": ("pc_clicks", "pc_click"),
    "mobile_clicks": ("mobile_clicks", "mobile_click", "mo_clicks", "mo_click"),
    "total_clicks": ("total_clicks", "total_click", "clicks"),
    "bid_1": ("bid_1", "bid1", "top_bid", "primary_bid", "cpc"),
    "bid_2": ("bid_2", "bid2", "secondary_bid"),
    "bid_3": ("bid_3", "bid3", "third_bid"),
    "bid_4": ("bid_4", "bid4"),
    "bid_5": ("bid_5", "bid5"),
    "bid_6": ("bid_6", "bid6"),
    "bid_7": ("bid_7", "bid7"),
    "bid_8": ("bid_8", "bid8"),
    "bid_9": ("bid_9", "bid9"),
    "bid_10": ("bid_10", "bid10"),
    "mobile_bid_1": ("mobile_bid_1", "mobile_bid1", "mo_bid_1", "mo_bid1"),
    "mobile_bid_2": ("mobile_bid_2", "mobile_bid2", "mo_bid_2", "mo_bid2"),
    "mobile_bid_3": ("mobile_bid_3", "mobile_bid3", "mo_bid_3", "mo_bid3"),
    "mobile_bid_4": ("mobile_bid_4", "mobile_bid4", "mo_bid_4", "mo_bid4"),
    "mobile_bid_5": ("mobile_bid_5", "mobile_bid5", "mo_bid_5", "mo_bid5"),
}


@dataclass(frozen=True)
class KeywordStats:
    keyword: str
    pc_searches: float | None = None
    mobile_searches: float | None = None
    total_searches: float | None = None
    blog_results: float | None = None
    pc_clicks: float | None = None
    mobile_clicks: float | None = None
    total_clicks: float | None = None
    bid_1: float | None = None
    bid_2: float | None = None
    bid_3: float | None = None
    bid_4: float | None = None
    bid_5: float | None = None
    bid_6: float | None = None
    bid_7: float | None = None
    bid_8: float | None = None
    bid_9: float | None = None
    bid_10: float | None = None
    mobile_bid_1: float | None = None
    mobile_bid_2: float | None = None
    mobile_bid_3: float | None = None
    mobile_bid_4: float | None = None
    mobile_bid_5: float | None = None
    source: str = "unknown"

    def resolved_total_searches(self) -> float:
        total_searches = _positive_or_none(self.total_searches)
        if total_searches is not None:
            return total_searches
        return (_positive_or_zero(self.pc_searches) + _positive_or_zero(self.mobile_searches))

    def resolved_total_clicks(self) -> float:
        total_clicks = _positive_or_none(self.total_clicks)
        if total_clicks is not None:
            return total_clicks
        return (_positive_or_zero(self.pc_clicks) + _positive_or_zero(self.mobile_clicks))

    def resolved_primary_bid(self) -> float:
        pc_bids = self.resolved_pc_bids(limit=1)
        if pc_bids:
            return pc_bids[0]
        mobile_bids = self.resolved_mobile_bids(limit=1)
        if mobile_bids:
            return mobile_bids[0]
        return 0.0

    def resolved_average_bid(self) -> float:
        bids = self.resolved_pc_bids(limit=3)
        if not bids:
            bids = self.resolved_mobile_bids(limit=3)
        if not bids:
            return 0.0
        return round(sum(bids) / len(bids), 4)

    def resolved_pc_bids(self, *, limit: int | None = None) -> list[float]:
        bids = [
            normalized
            for normalized in (
                _positive_or_none(self.bid_1),
                _positive_or_none(self.bid_2),
                _positive_or_none(self.bid_3),
                _positive_or_none(self.bid_4),
                _positive_or_none(self.bid_5),
                _positive_or_none(self.bid_6),
                _positive_or_none(self.bid_7),
                _positive_or_none(self.bid_8),
                _positive_or_none(self.bid_9),
                _positive_or_none(self.bid_10),
            )
            if normalized is not None
        ]
        if limit is None:
            return bids
        return bids[: max(0, limit)]

    def resolved_mobile_bids(self, *, limit: int | None = None) -> list[float]:
        bids = [
            normalized
            for normalized in (
                _positive_or_none(self.mobile_bid_1),
                _positive_or_none(self.mobile_bid_2),
                _positive_or_none(self.mobile_bid_3),
                _positive_or_none(self.mobile_bid_4),
                _positive_or_none(self.mobile_bid_5),
            )
            if normalized is not None
        ]
        if limit is None:
            return bids
        return bids[: max(0, limit)]

    def with_keyword(self, keyword: str) -> "KeywordStats":
        return replace(self, keyword=normalize_text(keyword))


def build_stats_index(input_data: Any) -> dict[str, KeywordStats]:
    if not isinstance(input_data, dict):
        return {}

    index: dict[str, KeywordStats] = {}

    for item in _coerce_stats_items(input_data.get("keyword_stats_items")):
        _upsert_stats(index, item)

    keyword_stats_text = input_data.get("keyword_stats_text")
    if isinstance(keyword_stats_text, str) and keyword_stats_text.strip():
        for item in parse_keyword_stats_lines(keyword_stats_text):
            _upsert_stats(index, item)

    keyword_stats_html = input_data.get("keyword_stats_html")
    if isinstance(keyword_stats_html, str) and keyword_stats_html.strip():
        for item in parse_keyword_stats_html(keyword_stats_html):
            _upsert_stats(index, item)

    keyword_stats_path = input_data.get("keyword_stats_path")
    if isinstance(keyword_stats_path, str) and keyword_stats_path.strip():
        for item in load_keyword_stats_path(keyword_stats_path):
            _upsert_stats(index, item)

    return index


def extract_item_stats(item: dict[str, Any], stats_index: dict[str, KeywordStats] | None = None) -> KeywordStats | None:
    direct_stats = normalize_keyword_stats(item)
    keyword = normalize_text(item.get("keyword"))
    indexed_stats = None
    if keyword and stats_index:
        indexed_stats = stats_index.get(normalize_key(keyword))

    if direct_stats is None:
        return indexed_stats
    if indexed_stats is None:
        return direct_stats
    return merge_keyword_stats(indexed_stats, direct_stats).with_keyword(keyword or indexed_stats.keyword)


def normalize_keyword_stats(raw: Any) -> KeywordStats | None:
    if not isinstance(raw, dict):
        return None

    keyword = normalize_text(raw.get("keyword"))
    nested_candidates = [
        raw.get("keyword_stats"),
        raw.get("raw_metrics"),
        raw.get("source_metrics"),
    ]
    metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else None
    if metrics is not None and raw.get("analysis_mode") and not _looks_like_metric_payload(metrics):
        metrics = None

    values: dict[str, float | None] = {}
    for field_name in _FIELD_ALIASES:
        values[field_name] = _extract_number_from_candidates(raw, metrics, nested_candidates, aliases=_FIELD_ALIASES[field_name])

    has_meaningful_value = any(value is not None and value > 0 for value in values.values())
    if not keyword or not has_meaningful_value:
        return None

    return KeywordStats(
        keyword=keyword,
        pc_searches=values["pc_searches"],
        mobile_searches=values["mobile_searches"],
        total_searches=values["total_searches"],
        blog_results=values["blog_results"],
        pc_clicks=values["pc_clicks"],
        mobile_clicks=values["mobile_clicks"],
        total_clicks=values["total_clicks"],
        bid_1=values["bid_1"],
        bid_2=values["bid_2"],
        bid_3=values["bid_3"],
        bid_4=values["bid_4"],
        bid_5=values["bid_5"],
        bid_6=values["bid_6"],
        bid_7=values["bid_7"],
        bid_8=values["bid_8"],
        bid_9=values["bid_9"],
        bid_10=values["bid_10"],
        mobile_bid_1=values["mobile_bid_1"],
        mobile_bid_2=values["mobile_bid_2"],
        mobile_bid_3=values["mobile_bid_3"],
        mobile_bid_4=values["mobile_bid_4"],
        mobile_bid_5=values["mobile_bid_5"],
        source=normalize_text(raw.get("stats_source")) or "item",
    )


def parse_keyword_stats_lines(text: str) -> list[KeywordStats]:
    results: list[KeywordStats] = []
    for line in text.splitlines():
        parsed = parse_keyword_stats_line(line)
        if parsed is not None:
            results.append(parsed)
    return results


def parse_keyword_stats_line(line: str) -> KeywordStats | None:
    raw_line = line.strip()
    if not raw_line:
        return None

    fields = [normalize_text(part) for part in raw_line.split("\t")]
    if len(fields) < 2:
        return None

    keyword = normalize_text(fields[0])
    if not keyword:
        return None

    numeric_values = [_parse_number(field) for field in fields[1:]]
    numeric_values = [value for value in numeric_values if value is not None]
    if not numeric_values:
        return None

    values = numeric_values + [None] * (10 - len(numeric_values))
    return KeywordStats(
        keyword=keyword,
        pc_searches=values[0],
        mobile_searches=values[1],
        total_searches=values[2],
        blog_results=values[3],
        pc_clicks=values[4],
        mobile_clicks=values[5],
        total_clicks=values[6],
        bid_1=values[7],
        bid_2=values[8],
        bid_3=values[9],
        source="text_line",
    )


def parse_keyword_stats_html(html: str) -> list[KeywordStats]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[KeywordStats] = []

    for element in soup.select("[data-line]"):
        raw_line = str(element.get("data-line") or "").strip()
        if not raw_line:
            continue
        parsed = parse_keyword_stats_line(raw_line.replace("\\t", "\t"))
        if parsed is not None:
            results.append(parsed)

    return results


def load_keyword_stats_path(path_value: str) -> list[KeywordStats]:
    path = Path(path_value.strip())
    if not path.exists():
        return []

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8", errors="ignore")
    if suffix in {".html", ".htm"}:
        return parse_keyword_stats_html(text)
    return parse_keyword_stats_lines(text)


def merge_keyword_stats(base: KeywordStats, override: KeywordStats) -> KeywordStats:
    return KeywordStats(
        keyword=override.keyword or base.keyword,
        pc_searches=override.pc_searches if override.pc_searches is not None else base.pc_searches,
        mobile_searches=override.mobile_searches if override.mobile_searches is not None else base.mobile_searches,
        total_searches=override.total_searches if override.total_searches is not None else base.total_searches,
        blog_results=override.blog_results if override.blog_results is not None else base.blog_results,
        pc_clicks=override.pc_clicks if override.pc_clicks is not None else base.pc_clicks,
        mobile_clicks=override.mobile_clicks if override.mobile_clicks is not None else base.mobile_clicks,
        total_clicks=override.total_clicks if override.total_clicks is not None else base.total_clicks,
        bid_1=override.bid_1 if override.bid_1 is not None else base.bid_1,
        bid_2=override.bid_2 if override.bid_2 is not None else base.bid_2,
        bid_3=override.bid_3 if override.bid_3 is not None else base.bid_3,
        bid_4=override.bid_4 if override.bid_4 is not None else base.bid_4,
        bid_5=override.bid_5 if override.bid_5 is not None else base.bid_5,
        bid_6=override.bid_6 if override.bid_6 is not None else base.bid_6,
        bid_7=override.bid_7 if override.bid_7 is not None else base.bid_7,
        bid_8=override.bid_8 if override.bid_8 is not None else base.bid_8,
        bid_9=override.bid_9 if override.bid_9 is not None else base.bid_9,
        bid_10=override.bid_10 if override.bid_10 is not None else base.bid_10,
        mobile_bid_1=override.mobile_bid_1 if override.mobile_bid_1 is not None else base.mobile_bid_1,
        mobile_bid_2=override.mobile_bid_2 if override.mobile_bid_2 is not None else base.mobile_bid_2,
        mobile_bid_3=override.mobile_bid_3 if override.mobile_bid_3 is not None else base.mobile_bid_3,
        mobile_bid_4=override.mobile_bid_4 if override.mobile_bid_4 is not None else base.mobile_bid_4,
        mobile_bid_5=override.mobile_bid_5 if override.mobile_bid_5 is not None else base.mobile_bid_5,
        source=override.source if override.source != "unknown" else base.source,
    )


def _coerce_stats_items(raw_items: Any) -> list[KeywordStats]:
    if not isinstance(raw_items, list):
        return []

    results: list[KeywordStats] = []
    for raw_item in raw_items:
        normalized = normalize_keyword_stats(raw_item)
        if normalized is not None:
            results.append(normalized)
    return results


def _upsert_stats(index: dict[str, KeywordStats], item: KeywordStats) -> None:
    key = normalize_key(item.keyword)
    if not key:
        return

    if key not in index:
        index[key] = item
        return

    index[key] = merge_keyword_stats(index[key], item)


def _extract_number_from_candidates(
    raw: dict[str, Any],
    metrics: dict[str, Any] | None,
    nested_candidates: list[Any],
    *,
    aliases: tuple[str, ...],
) -> float | None:
    for alias in aliases:
        parsed = _parse_number(raw.get(alias))
        if parsed is not None:
            return parsed

    if metrics is not None:
        for alias in aliases:
            parsed = _parse_number(metrics.get(alias))
            if parsed is not None:
                return parsed

    for candidate in nested_candidates:
        if not isinstance(candidate, dict):
            continue
        for alias in aliases:
            parsed = _parse_number(candidate.get(alias))
            if parsed is not None:
                return parsed

    return None


def _looks_like_metric_payload(metrics: dict[str, Any]) -> bool:
    explicit_metric_keys = {
        "pc_searches",
        "mobile_searches",
        "total_searches",
        "blog_results",
        "pc_clicks",
        "mobile_clicks",
        "total_clicks",
        "bid_1",
        "bid_2",
        "bid_3",
        "bid_4",
        "bid_5",
        "bid_6",
        "bid_7",
        "bid_8",
        "bid_9",
        "bid_10",
        "mobile_bid_1",
        "mobile_bid_2",
        "mobile_bid_3",
        "mobile_bid_4",
        "mobile_bid_5",
    }
    return any(key in metrics for key in explicit_metric_keys)


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = normalize_text(value)
    if not text:
        return None

    match = _NUMBER_PATTERN.search(text.replace("원", ""))
    if match is None:
        return None

    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _positive_or_none(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return float(value)


def _positive_or_zero(value: float | None) -> float:
    normalized = _positive_or_none(value)
    return normalized if normalized is not None else 0.0
