from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup, Tag


_PLACEHOLDER_KEYWORDS = {
    "",
    '" " 검색 결과',
    "데이터 준비중",
    "키워드 분석 중",
    "데이터 수집 중...",
    "지금 데이터를 불러오고 있습니다.",
    "KEYWORD LIST",
    "No.",
    "#",
    "키워드",
    "월간 검색량",
    "문서수",
    "경쟁도",
    "PC 1위",
    "PC 2위",
    "모바일 1위",
    "모바일 2위",
    "분석",
    "목록으로 돌아가기",
    "엑셀 저장",
    "기본",
    "검색량 순",
    "경쟁도 낮은 순",
    "입찰가 높은 순",
}


@dataclass(frozen=True)
class CollectorOptions:
    collect_related: bool
    collect_autocomplete: bool
    collect_bulk: bool

    @classmethod
    def from_dict(cls, raw: Any) -> "CollectorOptions":
        if not isinstance(raw, dict):
            raw = {}

        return cls(
            collect_related=bool(raw.get("collect_related", True)),
            collect_autocomplete=bool(raw.get("collect_autocomplete", False)),
            collect_bulk=bool(raw.get("collect_bulk", False)),
        )


@dataclass(frozen=True)
class CollectorRequest:
    mode: str
    category: str
    seed_input: str
    options: CollectorOptions
    analysis_json_path: Path | None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CollectorRequest":
        analysis_json_path = raw.get("analysis_json_path")
        normalized_path: Path | None = None
        if isinstance(analysis_json_path, str) and analysis_json_path.strip():
            normalized_path = Path(analysis_json_path.strip())

        return cls(
            mode=_normalize_mode(raw.get("mode")),
            category=str(raw.get("category") or "").strip(),
            seed_input=str(raw.get("seed_input") or "").strip(),
            options=CollectorOptions.from_dict(raw.get("options")),
            analysis_json_path=normalized_path,
        )


@dataclass(frozen=True)
class BenchmarkSignals:
    source: str
    source_files: tuple[str, ...]
    core_functions: tuple[str, ...]
    ui_types: tuple[str, ...]
    ui_roles: tuple[str, ...]
    input_roles: tuple[str, ...]
    output_roles: tuple[str, ...]
    extractor_names: tuple[str, ...]

    @classmethod
    def from_analysis(cls, raw: dict[str, Any]) -> "BenchmarkSignals":
        ui_types = tuple(_collect_named_values(raw.get("ui_components"), "type"))
        ui_roles = tuple(_collect_named_values(raw.get("ui_components"), "role"))
        input_roles = tuple(_collect_named_values(raw.get("data_inputs"), "role"))
        output_roles = tuple(_collect_named_values(raw.get("data_outputs"), "role"))
        core_functions = tuple(_collect_string_values(raw.get("core_functions")))
        extractor_names = _infer_extractors(
            ui_types=ui_types,
            ui_roles=ui_roles,
            output_roles=output_roles,
            source_files=tuple(_collect_string_values(raw.get("source_files"))),
            core_functions=core_functions,
        )

        return cls(
            source=_infer_source(raw),
            source_files=tuple(_collect_string_values(raw.get("source_files"))),
            core_functions=core_functions,
            ui_types=ui_types,
            ui_roles=ui_roles,
            input_roles=input_roles,
            output_roles=output_roles,
            extractor_names=extractor_names,
        )


class CollectorService:
    def run(self, input_data: dict) -> dict:
        request = CollectorRequest.from_dict(input_data)
        if request.analysis_json_path is None:
            return {"collected_keywords": []}

        analysis_path = request.analysis_json_path.expanduser()
        if not analysis_path.is_absolute():
            analysis_path = Path.cwd() / analysis_path

        if not analysis_path.exists():
            return {"collected_keywords": []}

        analysis_raw = json.loads(analysis_path.read_text(encoding="utf-8"))
        signals = BenchmarkSignals.from_analysis(analysis_raw)
        source_paths = self._resolve_source_paths(analysis_path, signals)

        collected_keywords: list[dict[str, Any]] = []
        for source_path in source_paths:
            soup = self._load_soup(source_path)
            if soup is None:
                continue
            collected_keywords.extend(self._extract_keywords(soup, signals))

        deduped_keywords = _dedupe_keyword_entries(collected_keywords)
        return {
            "collected_keywords": self._apply_mode(
                entries=deduped_keywords,
                request=request,
            )
        }

    def _resolve_source_paths(self, analysis_path: Path, signals: BenchmarkSignals) -> tuple[Path, ...]:
        base_dir = analysis_path.parent
        resolved_paths: list[Path] = []
        for source_file in signals.source_files:
            source_path = base_dir / source_file
            if source_path.exists():
                resolved_paths.append(source_path)
        return tuple(resolved_paths)

    def _load_soup(self, source_path: Path) -> BeautifulSoup | None:
        if not source_path.exists():
            return None
        html = source_path.read_text(encoding="utf-8", errors="ignore")
        return BeautifulSoup(html, "html.parser")

    def _extract_keywords(self, soup: BeautifulSoup, signals: BenchmarkSignals) -> list[dict[str, Any]]:
        collected_keywords: list[dict[str, Any]] = []

        for extractor_name in signals.extractor_names:
            if extractor_name == "trend_list":
                collected_keywords.extend(self._extract_from_trend_lists(soup, signals.source))
            elif extractor_name == "keyword_table":
                collected_keywords.extend(self._extract_from_keyword_tables(soup, signals.source))

        if collected_keywords or signals.extractor_names:
            return collected_keywords

        return self._extract_from_generic_lists(soup, signals.source)

    def _extract_from_trend_lists(self, soup: BeautifulSoup, source: str) -> list[dict[str, Any]]:
        collected_keywords: list[dict[str, Any]] = []

        for block in soup.select(".u_ni_trend_list"):
            category = _normalize_text(_node_text(block.select_one(".u_ni_trend_title")))
            for item in block.select(".u_ni_trend_item"):
                keyword_node = item.select_one(".u_ni_trend_text")
                raw_keyword = _node_text(keyword_node)
                keyword = _normalize_text(raw_keyword)
                if keyword is None:
                    continue

                collected_keywords.append(
                    {
                        "keyword": keyword,
                        "category": category,
                        "source": source,
                        "raw": raw_keyword,
                    }
                )

        return collected_keywords

    def _extract_from_keyword_tables(self, soup: BeautifulSoup, source: str) -> list[dict[str, Any]]:
        collected_keywords: list[dict[str, Any]] = []

        for table in soup.select("table"):
            rows = table.select("tr")
            if not rows:
                continue

            header_cells = [_normalize_text(_node_text(cell)) for cell in rows[0].select("th, td")]
            if "키워드" not in header_cells:
                continue

            keyword_index = header_cells.index("키워드")
            for row in rows[1:]:
                cells = [_node_text(cell) for cell in row.select("td")]
                if keyword_index >= len(cells):
                    continue

                raw_keyword = cells[keyword_index]
                keyword = _normalize_text(raw_keyword)
                if keyword is None:
                    continue

                collected_keywords.append(
                    {
                        "keyword": keyword,
                        "category": None,
                        "source": source,
                        "raw": raw_keyword,
                    }
                )

        return collected_keywords

    def _extract_from_generic_lists(self, soup: BeautifulSoup, source: str) -> list[dict[str, Any]]:
        collected_keywords: list[dict[str, Any]] = []
        for node in soup.select("li a, li span, li strong"):
            raw_keyword = _node_text(node)
            keyword = _normalize_text(raw_keyword)
            if keyword is None:
                continue

            collected_keywords.append(
                {
                    "keyword": keyword,
                    "category": None,
                    "source": source,
                    "raw": raw_keyword,
                }
            )

        return collected_keywords

    def _apply_mode(self, entries: list[dict[str, Any]], request: CollectorRequest) -> list[dict[str, Any]]:
        if request.mode == "seed":
            return _filter_entries_by_seed(entries, request.seed_input)

        requested_category = _normalize_category_key(request.category)
        if not requested_category:
            return []

        return [
            entry
            for entry in entries
            if _category_matches(requested_category, entry.get("category"))
        ]


def _collect_named_values(raw_items: Any, field_name: str) -> list[str]:
    values: list[str] = []
    if not isinstance(raw_items, list):
        return values

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_text(str(item.get(field_name, "")))
        if normalized:
            values.append(normalized)
    return values


def _collect_string_values(raw_items: Any) -> list[str]:
    values: list[str] = []
    if not isinstance(raw_items, list):
        return values

    for item in raw_items:
        normalized = _normalize_text(str(item))
        if normalized:
            values.append(normalized)
    return values


def _infer_extractors(
    ui_types: tuple[str, ...],
    ui_roles: tuple[str, ...],
    output_roles: tuple[str, ...],
    source_files: tuple[str, ...],
    core_functions: tuple[str, ...],
) -> tuple[str, ...]:
    extractor_names: list[str] = []

    has_list_signal = (
        "list" in ui_types
        or "keyword results" in output_roles
        or "related keyword suggestions" in output_roles
        or "keyword suggestions" in ui_roles
        or "keyword_expansion" in core_functions
    )
    has_table_signal = "table" in ui_types or "keyword metrics" in output_roles

    if has_list_signal:
        extractor_names.append("trend_list")
    if has_table_signal:
        extractor_names.append("keyword_table")

    if not extractor_names:
        joined_names = " ".join(source_files).lower()
        if "creator advisor" in joined_names:
            extractor_names.append("trend_list")
        elif "prime" in joined_names:
            extractor_names.append("keyword_table")

    return tuple(dict.fromkeys(extractor_names))


def _infer_source(raw: dict[str, Any]) -> str:
    explicit_source = _normalize_text(str(raw.get("source", "")))
    if explicit_source:
        return explicit_source

    source_files = " ".join(_collect_string_values(raw.get("source_files"))).lower()
    if "creator advisor" in source_files:
        return "naver_trend"
    if "prime" in source_files:
        return "keyword_prime"

    data_source = _normalize_text(str(raw.get("data_source", "")))
    if data_source:
        return re.sub(r"\s+", "_", data_source.lower())

    site_types = _collect_string_values(raw.get("site_type"))
    if site_types:
        return "_".join(site_types)

    return "unknown"


def _node_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return node.get_text(" ", strip=True)


def _normalize_text(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized or normalized in _PLACEHOLDER_KEYWORDS:
        return None
    if normalized.startswith('"') and normalized.endswith('"') and len(normalized) <= 3:
        return None
    return normalized


def _normalize_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "category":
        return "category"
    return "seed"


def _normalize_category_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z\u3131-\u318E\uAC00-\uD7A3]+", "", str(value or "")).lower()


def _category_matches(requested_category: str, entry_category: Any) -> bool:
    normalized_entry_category = _normalize_category_key(entry_category)
    if not requested_category or not normalized_entry_category:
        return False
    return (
        requested_category in normalized_entry_category
        or normalized_entry_category in requested_category
    )


def _filter_entries_by_seed(entries: list[dict[str, Any]], seed_input: str) -> list[dict[str, Any]]:
    normalized_seed = str(seed_input or "").strip().lower()
    if not normalized_seed:
        return entries

    return [
        entry
        for entry in entries
        if normalized_seed in str(entry.get("keyword") or "").lower()
    ]


def _dedupe_keyword_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        identity = (entry["keyword"], entry.get("category"), entry["source"])
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(entry)
    return deduped
