from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.expander.utils.tokenizer import normalize_text


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_ROOT = _PROJECT_ROOT / "output"
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
_QUEUE_DESTINATION_CHANNEL_MAP = {
    "wordpress": "blog",
    "home": "naver_home",
}


@dataclass(frozen=True)
class TitleQueueExportSettings:
    enabled: bool = False
    topic: str = ""
    destination: str = ""
    append: bool = True


@dataclass(frozen=True)
class TitleExportSettings:
    enabled: bool = False
    output_root: Path = _DEFAULT_OUTPUT_ROOT
    formats: tuple[str, ...] = _DEFAULT_EXPORT_FORMATS
    queue_export: TitleQueueExportSettings = TitleQueueExportSettings()

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
        output_root = Path(output_dir_value).expanduser() if output_dir_value else _DEFAULT_OUTPUT_ROOT
        formats = _resolve_export_formats(
            export.get("formats"),
            export.get("format"),
            root.get("title_export_formats"),
            root.get("title_export_format"),
        )
        raw_queue_export = export.get("queue_export") if isinstance(export.get("queue_export"), dict) else {}
        if not raw_queue_export and isinstance(export.get("txt_queue"), dict):
            raw_queue_export = export.get("txt_queue")
        queue_export = TitleQueueExportSettings(
            enabled=_coerce_bool(raw_queue_export.get("enabled"), default=False),
            topic=normalize_text(raw_queue_export.get("topic")),
            destination=_normalize_queue_destination(raw_queue_export.get("destination")),
            append=_coerce_bool(raw_queue_export.get("append"), default=True),
        )
        return cls(
            enabled=enabled,
            output_root=output_root,
            formats=formats,
            queue_export=queue_export,
        )


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
    output_root = Path(settings.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    export_rows = _build_title_export_rows(generated_titles)

    filename_stem = _build_filename_stem(
        now=now,
        category_label=category_label,
        seed_keyword_label=seed_keyword_label,
    )
    artifact_dirs = {
        format_key: _resolve_format_output_dir(output_root, format_key, now=now)
        for format_key in settings.formats
    }
    filename_stem = _resolve_available_stem(artifact_dirs, filename_stem, settings.formats)

    artifacts: list[dict[str, Any]] = []
    for format_key in settings.formats:
        artifact_dir = artifact_dirs[format_key]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{filename_stem}.{format_key}"
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

    if settings.queue_export.enabled:
        queue_export_payload = _export_title_queue_bundle(
            settings=settings,
            generated_titles=generated_titles,
            output_root=output_root,
            now=now,
            category_label=category_label,
            seed_keyword_label=seed_keyword_label,
        )
        artifacts.extend(queue_export_payload.get("artifacts", []))

    primary_artifact = next((item for item in artifacts if item["format"] == "csv"), artifacts[0])
    payload = {
        "primary_artifact": primary_artifact,
        "artifacts": artifacts,
    }
    if settings.queue_export.enabled and queue_export_payload:
        payload["queue_export"] = queue_export_payload
    return payload


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


def _export_title_queue_bundle(
    *,
    settings: TitleExportSettings,
    generated_titles: list[dict[str, Any]],
    output_root: Path,
    now: datetime,
    category_label: str,
    seed_keyword_label: str,
) -> dict[str, Any]:
    queue_settings = settings.queue_export
    if not queue_settings.topic or not queue_settings.destination:
        return {}

    queue_lines, manifest_entries = _build_queue_export_entries(
        generated_titles,
        destination=queue_settings.destination,
        topic=queue_settings.topic,
    )
    if not queue_lines:
        return {}

    destination_segment = _sanitize_filename_segment(queue_settings.destination, fallback="queue")
    topic_segment = _sanitize_filename_segment(queue_settings.topic, fallback="topic")
    seed_segment = _sanitize_filename_segment(seed_keyword_label, fallback="titles")
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    archive_dir = output_root / "txt" / "archive" / now.strftime("%Y-%m-%d")
    live_dir = output_root / "txt" / "live" / destination_segment
    manifest_dir = output_root / "manifests" / now.strftime("%Y-%m-%d")
    archive_dir.mkdir(parents=True, exist_ok=True)
    live_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{timestamp}__{destination_segment}__{topic_segment}__{seed_segment}.txt"
    live_path = live_dir / f"{topic_segment}.txt"
    manifest_path = manifest_dir / f"{timestamp}__{destination_segment}__{topic_segment}__{seed_segment}.json"

    archive_text = "\n".join(queue_lines).rstrip() + "\n"
    archive_path.write_text(archive_text, encoding="utf-8")
    _write_live_queue_file(live_path, queue_lines, append=queue_settings.append)
    manifest_payload = {
        "queued_at": now.isoformat(timespec="seconds"),
        "topic": queue_settings.topic,
        "destination": queue_settings.destination,
        "category": category_label,
        "seed_keyword": seed_keyword_label,
        "append_mode": queue_settings.append,
        "row_count": len(manifest_entries),
        "entries": manifest_entries,
        "artifacts": {
            "live_txt": str(live_path),
            "archive_txt": str(archive_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    row_count = len(manifest_entries)
    return {
        "topic": queue_settings.topic,
        "destination": queue_settings.destination,
        "row_count": row_count,
        "artifacts": [
            _build_artifact_metadata(
                format_key="txt_live",
                artifact_path=live_path,
                row_count=row_count,
                now=now,
                category_label=category_label,
                seed_keyword_label=seed_keyword_label,
            ),
            _build_artifact_metadata(
                format_key="txt_archive",
                artifact_path=archive_path,
                row_count=row_count,
                now=now,
                category_label=category_label,
                seed_keyword_label=seed_keyword_label,
            ),
            _build_artifact_metadata(
                format_key="manifest_json",
                artifact_path=manifest_path,
                row_count=row_count,
                now=now,
                category_label=category_label,
                seed_keyword_label=seed_keyword_label,
            ),
        ],
    }


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


def _write_live_queue_file(path: Path, lines: list[str], *, append: bool) -> None:
    existing_lines: list[str] = []
    if append and path.exists():
        existing_lines = [
            normalize_text(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if normalize_text(line)
        ]
    combined_lines = existing_lines[:]
    existing_lookup = {normalize_text(line) for line in existing_lines if normalize_text(line)}
    for line in lines:
        normalized_line = normalize_text(line)
        if not normalized_line or normalized_line in existing_lookup:
            continue
        existing_lookup.add(normalized_line)
        combined_lines.append(normalized_line)
    path.write_text("\n".join(combined_lines).rstrip() + "\n", encoding="utf-8")


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


def _build_queue_export_entries(
    generated_titles: list[dict[str, Any]],
    *,
    destination: str,
    topic: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    channel_name = _QUEUE_DESTINATION_CHANNEL_MAP.get(destination)
    if not channel_name:
        return [], []

    queue_lines: list[str] = []
    manifest_entries: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in generated_titles:
        if not isinstance(item, dict):
            continue
        keyword = normalize_text(item.get("keyword"))
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        channel_titles = titles.get(channel_name) if isinstance(titles.get(channel_name), list) else []
        selected_title = normalize_text(channel_titles[0]) if channel_titles else ""
        if not keyword or not selected_title:
            continue
        normalized_lookup = normalize_text(selected_title)
        if not normalized_lookup or normalized_lookup in seen_titles:
            continue
        seen_titles.add(normalized_lookup)
        queue_lines.append(selected_title)
        manifest_entries.append(
            {
                "keyword": keyword,
                "topic": topic,
                "destination": destination,
                "selected_title": selected_title,
                "channel": channel_name,
                "target_mode": normalize_text(item.get("target_mode")),
                "base_keyword": normalize_text(item.get("base_keyword")),
                "source_kind": normalize_text(item.get("source_kind")),
            }
        )
    return queue_lines, manifest_entries


def _resolve_format_output_dir(output_root: Path, format_key: str, *, now: datetime) -> Path:
    if format_key == "csv":
        return output_root / "csv"
    if format_key == "xlsx":
        return output_root / "xlsx"
    if format_key == "md":
        return output_root / "md"
    if format_key == "txt":
        return output_root / "txt" / "archive" / now.strftime("%Y-%m-%d")
    return output_root / "misc"


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


def _resolve_available_stem(output_dirs: dict[str, Path], stem: str, formats: tuple[str, ...]) -> str:
    if _stem_is_available(output_dirs, stem, formats):
        return stem

    for index in range(2, 1000):
        candidate = f"{stem}-{index}"
        if _stem_is_available(output_dirs, candidate, formats):
            return candidate
    return f"{stem}-{_now_kst().strftime('%H%M%S')}"


def _stem_is_available(output_dirs: dict[str, Path], stem: str, formats: tuple[str, ...]) -> bool:
    return all(
        not (output_dirs[format_key] / f"{stem}.{format_key}").exists()
        for format_key in formats
    )


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


def _normalize_queue_destination(value: Any) -> str:
    normalized = normalize_text(value).lower()
    return normalized if normalized in _QUEUE_DESTINATION_CHANNEL_MAP else ""


def _now_kst() -> datetime:
    return datetime.now(_KST)
