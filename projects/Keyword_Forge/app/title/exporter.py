from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.expander.utils.tokenizer import normalize_text


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"
_KST = ZoneInfo("Asia/Seoul")
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_FILENAME_SPACE_PATTERN = re.compile(r"\s+")
_FORMAT_SPLIT_PATTERN = re.compile(r"[\s,|;/]+")
_TITLE_EXPORT_HEADER = [
    "keyword",
    "duplicate",
    "recent_used_date",
    "naver_home_1",
    "naver_home_2",
    "blog_1",
    "blog_2",
]
_DEFAULT_EXPORT_FORMATS = ("csv",)
_ALL_EXPORT_FORMATS = ("csv", "xlsx", "md")
_FORMAT_ALIASES = {
    "csv": "csv",
    "xlsx": "xlsx",
    "excel": "xlsx",
    "md": "md",
    "markdown": "md",
    "txt": "txt",
    "text": "txt",
}


@dataclass(frozen=True)
class TitleExportSettings:
    enabled: bool = False
    output_dir: Path = _DEFAULT_OUTPUT_DIR
    formats: tuple[str, ...] = _DEFAULT_EXPORT_FORMATS

    @classmethod
    def from_input(cls, input_data: Any) -> "TitleExportSettings":
        root = input_data if isinstance(input_data, dict) else {}
        export = root.get("title_export") if isinstance(root.get("title_export"), dict) else {}
        enabled = _coerce_bool(
            export.get("enabled"),
            root.get("title_export_enabled"),
            default=False,
        )
        output_dir_value = (
            normalize_text(export.get("output_dir"))
            or normalize_text(root.get("title_output_dir"))
        )
        output_dir = Path(output_dir_value).expanduser() if output_dir_value else _DEFAULT_OUTPUT_DIR
        formats = _resolve_export_formats(
            export.get("formats"),
            export.get("format"),
            root.get("title_export_formats"),
            root.get("title_export_format"),
        )
        return cls(enabled=enabled, output_dir=output_dir, formats=formats)


def export_generated_titles(
    input_data: Any,
    generated_titles: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = TitleExportSettings.from_input(input_data)
    if not settings.enabled or not generated_titles:
        return {}

    now = _now_kst()
    category_label = _resolve_category_label(input_data, generated_titles)
    seed_keyword_label = _resolve_seed_keyword_label(input_data, generated_titles)
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    export_rows = _build_title_export_rows(generated_titles)

    filename_stem = _build_filename_stem(
        now=now,
        category_label=category_label,
        seed_keyword_label=seed_keyword_label,
    )
    filename_stem = _resolve_available_stem(output_dir, filename_stem, settings.formats)

    artifacts: list[dict[str, Any]] = []
    for format_key in settings.formats:
        artifact_path = output_dir / f"{filename_stem}.{format_key}"
        _write_title_export_file(
            format_key=format_key,
            artifact_path=artifact_path,
            export_rows=export_rows,
            generated_titles=generated_titles,
            now=now,
            category_label=category_label,
            seed_keyword_label=seed_keyword_label,
        )
        artifacts.append(
            _build_artifact_metadata(
                format_key=format_key,
                artifact_path=artifact_path,
                row_count=len(export_rows),
                now=now,
                category_label=category_label,
                seed_keyword_label=seed_keyword_label,
            )
        )

    primary_artifact = next((item for item in artifacts if item["format"] == "csv"), artifacts[0])
    return {
        "primary_artifact": primary_artifact,
        "artifacts": artifacts,
    }


def _build_title_export_rows(generated_titles: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in generated_titles:
        if not isinstance(item, dict):
            continue
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        naver_home_titles = titles.get("naver_home") if isinstance(titles.get("naver_home"), list) else []
        blog_titles = titles.get("blog") if isinstance(titles.get("blog"), list) else []
        rows.append(
            [
                normalize_text(item.get("keyword")),
                "",
                "",
                normalize_text(naver_home_titles[0]) if len(naver_home_titles) > 0 else "",
                normalize_text(naver_home_titles[1]) if len(naver_home_titles) > 1 else "",
                normalize_text(blog_titles[0]) if len(blog_titles) > 0 else "",
                normalize_text(blog_titles[1]) if len(blog_titles) > 1 else "",
            ]
        )
    return rows


def _write_title_export_file(
    *,
    format_key: str,
    artifact_path: Path,
    export_rows: list[list[str]],
    generated_titles: list[dict[str, Any]],
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> None:
    if format_key == "csv":
        _write_csv_export(artifact_path, export_rows)
        return
    if format_key == "xlsx":
        _write_xlsx_export(
            artifact_path,
            export_rows,
            now=now,
            category_label=category_label,
            seed_keyword_label=seed_keyword_label,
        )
        return
    if format_key == "md":
        artifact_path.write_text(
            _build_markdown_export_text(
                generated_titles,
                now=now,
                category_label=category_label,
                seed_keyword_label=seed_keyword_label,
            ),
            encoding="utf-8",
        )
        return
    if format_key == "txt":
        artifact_path.write_text(
            _build_text_export(
                generated_titles,
                now=now,
                category_label=category_label,
                seed_keyword_label=seed_keyword_label,
            ),
            encoding="utf-8",
        )
        return
    raise ValueError(f"unsupported title export format: {format_key}")


def _write_csv_export(artifact_path: Path, export_rows: list[list[str]]) -> None:
    with artifact_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_TITLE_EXPORT_HEADER)
        writer.writerows(export_rows)


def _write_xlsx_export(
    artifact_path: Path,
    export_rows: list[list[str]],
    *,
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> None:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "summary"
    summary_sheet.append(["saved_at", now.isoformat(timespec="seconds")])
    summary_sheet.append(["category", category_label])
    summary_sheet.append(["seed_keyword", seed_keyword_label])
    summary_sheet.append(["row_count", len(export_rows)])

    title_sheet = workbook.create_sheet("titles")
    title_sheet.append(_TITLE_EXPORT_HEADER)
    for row in export_rows:
        title_sheet.append(row)

    workbook.save(artifact_path)


def _build_markdown_export_text(
    generated_titles: list[dict[str, Any]],
    *,
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> str:
    lines = [
        "# Title Export",
        "",
        f"- saved_at: {now.isoformat(timespec='seconds')}",
        f"- category: {category_label}",
        f"- seed_keyword: {seed_keyword_label}",
        f"- row_count: {len(generated_titles)}",
        "",
    ]
    for item in generated_titles:
        if not isinstance(item, dict):
            continue
        keyword = normalize_text(item.get("keyword")) or "untitled-keyword"
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        naver_home_titles = titles.get("naver_home") if isinstance(titles.get("naver_home"), list) else []
        blog_titles = titles.get("blog") if isinstance(titles.get("blog"), list) else []
        lines.append(f"## {keyword}")
        lines.append(f"- naver_home_1: {normalize_text(naver_home_titles[0]) if len(naver_home_titles) > 0 else ''}")
        lines.append(f"- naver_home_2: {normalize_text(naver_home_titles[1]) if len(naver_home_titles) > 1 else ''}")
        lines.append(f"- blog_1: {normalize_text(blog_titles[0]) if len(blog_titles) > 0 else ''}")
        lines.append(f"- blog_2: {normalize_text(blog_titles[1]) if len(blog_titles) > 1 else ''}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_text_export(
    generated_titles: list[dict[str, Any]],
    *,
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> str:
    lines = [
        "TITLE EXPORT",
        f"saved_at: {now.isoformat(timespec='seconds')}",
        f"category: {category_label}",
        f"seed_keyword: {seed_keyword_label}",
        f"row_count: {len(generated_titles)}",
        "",
    ]
    for item in generated_titles:
        if not isinstance(item, dict):
            continue
        keyword = normalize_text(item.get("keyword")) or "untitled-keyword"
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        naver_home_titles = titles.get("naver_home") if isinstance(titles.get("naver_home"), list) else []
        blog_titles = titles.get("blog") if isinstance(titles.get("blog"), list) else []
        lines.append(f"[{keyword}]")
        lines.append(f"naver_home_1: {normalize_text(naver_home_titles[0]) if len(naver_home_titles) > 0 else ''}")
        lines.append(f"naver_home_2: {normalize_text(naver_home_titles[1]) if len(naver_home_titles) > 1 else ''}")
        lines.append(f"blog_1: {normalize_text(blog_titles[0]) if len(blog_titles) > 0 else ''}")
        lines.append(f"blog_2: {normalize_text(blog_titles[1]) if len(blog_titles) > 1 else ''}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_artifact_metadata(
    *,
    format_key: str,
    artifact_path: Path,
    row_count: int,
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> dict[str, Any]:
    return {
        "path": str(artifact_path),
        "filename": artifact_path.name,
        "format": format_key,
        "row_count": row_count,
        "saved_at": now.isoformat(timespec="seconds"),
        "category": category_label,
        "seed_keyword": seed_keyword_label,
    }


def _resolve_category_label(input_data: Any, generated_titles: list[dict[str, Any]]) -> str:
    root = input_data if isinstance(input_data, dict) else {}
    collector = root.get("collector") if isinstance(root.get("collector"), dict) else {}
    category = normalize_text(root.get("category")) or normalize_text(collector.get("category"))
    if category:
        return category

    mode = normalize_text(root.get("mode")) or normalize_text(collector.get("mode"))
    if mode == "seed":
        return "seed"
    return "uncategorized"


def _resolve_seed_keyword_label(input_data: Any, generated_titles: list[dict[str, Any]]) -> str:
    root = input_data if isinstance(input_data, dict) else {}
    collector = root.get("collector") if isinstance(root.get("collector"), dict) else {}
    seed_input = normalize_text(root.get("seed_input")) or normalize_text(collector.get("seed_input"))
    if seed_input:
        seed_lines = [line for line in (normalize_text(item) for item in seed_input.splitlines()) if line]
        if seed_lines:
            lead_seed = seed_lines[0]
            if len(seed_lines) > 1:
                return f"{lead_seed}-plus{len(seed_lines) - 1}"
            return lead_seed

    first_item = generated_titles[0] if generated_titles and isinstance(generated_titles[0], dict) else {}
    return (
        normalize_text(first_item.get("base_keyword"))
        or normalize_text(first_item.get("keyword"))
        or "titles"
    )


def _build_filename_stem(
    *,
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> str:
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    category_segment = _sanitize_filename_segment(category_label, fallback="uncategorized")
    seed_segment = _sanitize_filename_segment(seed_keyword_label, fallback="titles")
    return f"{timestamp}__{category_segment}__{seed_segment}"


def _sanitize_filename_segment(value: str, *, fallback: str) -> str:
    normalized = normalize_text(value) or fallback
    normalized = _INVALID_FILENAME_CHARS.sub("-", normalized)
    normalized = _FILENAME_SPACE_PATTERN.sub(" ", normalized).strip(" .-_")
    if not normalized:
        return fallback
    return normalized[:60]


def _resolve_available_stem(output_dir: Path, stem: str, formats: tuple[str, ...]) -> str:
    if _stem_is_available(output_dir, stem, formats):
        return stem

    for index in range(2, 1000):
        candidate = f"{stem}-{index}"
        if _stem_is_available(output_dir, candidate, formats):
            return candidate
    return f"{stem}-{_now_kst().strftime('%H%M%S')}"


def _stem_is_available(output_dir: Path, stem: str, formats: tuple[str, ...]) -> bool:
    return all(not (output_dir / f"{stem}.{format_key}").exists() for format_key in formats)


def _resolve_export_formats(*values: Any) -> tuple[str, ...]:
    resolved: list[str] = []
    seen: set[str] = set()
    for value in values:
        for format_key in _iter_export_formats(value):
            if format_key in seen:
                continue
            seen.add(format_key)
            resolved.append(format_key)
    return tuple(resolved or _DEFAULT_EXPORT_FORMATS)


def _iter_export_formats(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        formats: list[str] = []
        for item in value:
            formats.extend(_iter_export_formats(item))
        return formats
    if value is None:
        return []
    normalized_value = str(value).strip().lower()
    if not normalized_value:
        return []
    if normalized_value == "all":
        return list(_ALL_EXPORT_FORMATS)
    parts = [part for part in _FORMAT_SPLIT_PATTERN.split(normalized_value) if part]
    formats: list[str] = []
    for part in parts or [normalized_value]:
        canonical = _FORMAT_ALIASES.get(part)
        if canonical:
            formats.append(canonical)
    return formats


def _coerce_bool(*values: Any, default: bool) -> bool:
    for value in values:
        if isinstance(value, bool):
            return value
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _now_kst() -> datetime:
    return datetime.now(_KST)
