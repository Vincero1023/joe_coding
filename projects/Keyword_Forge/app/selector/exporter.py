from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from app.expander.utils.tokenizer import normalize_text


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_ROOT = _PROJECT_ROOT / "output"
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')
_FILENAME_SPACE_PATTERN = re.compile(r"\s+")
_KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class SelectionExportSettings:
    enabled: bool = False
    output_dir: Path = _DEFAULT_OUTPUT_ROOT

    @classmethod
    def from_input(cls, input_data: Any) -> "SelectionExportSettings":
        root = input_data if isinstance(input_data, dict) else {}
        raw = root.get("selection_export") if isinstance(root.get("selection_export"), dict) else {}
        title_export = root.get("title_export") if isinstance(root.get("title_export"), dict) else {}

        enabled = _coerce_boolish(raw.get("enabled"), default=False)
        output_dir = Path(
            normalize_text(raw.get("output_dir"))
            or normalize_text(title_export.get("output_dir"))
            or str(_DEFAULT_OUTPUT_ROOT)
        )
        return cls(enabled=enabled, output_dir=output_dir)


def export_selected_keywords(input_data: Any, selected_keywords: list[dict[str, Any]]) -> dict[str, Any]:
    settings = SelectionExportSettings.from_input(input_data)
    if not settings.enabled or not selected_keywords:
        return {}

    lines = _build_export_lines(selected_keywords)
    if not lines:
        return {}

    now = _now_kst()
    label = _resolve_selection_label(input_data, selected_keywords)
    label_segment = _sanitize_filename_segment(label, fallback="selected-keywords")
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    date_segment = now.strftime("%Y-%m-%d")

    archive_dir = settings.output_dir / "txt" / "selected" / "archive" / date_segment
    live_dir = settings.output_dir / "txt" / "selected" / "live"
    archive_dir.mkdir(parents=True, exist_ok=True)
    live_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{timestamp}__{label_segment}.txt"
    live_path = live_dir / f"{date_segment}__{label_segment}.txt"

    text = "\n".join(lines).rstrip() + "\n"
    archive_path.write_text(text, encoding="utf-8")
    live_path.write_text(text, encoding="utf-8")

    artifacts = [
        _build_artifact_metadata("txt_live", live_path),
        _build_artifact_metadata("txt_archive", archive_path),
    ]
    category_label = _resolve_category_label(input_data)
    seed_keyword_label = _resolve_seed_keyword_label(input_data, selected_keywords)
    return {
        "enabled": True,
        "row_count": len(lines),
        "label": label,
        "category": category_label,
        "seed_keyword": seed_keyword_label,
        "artifacts": artifacts,
        "artifact": artifacts[0],
    }


def _build_export_lines(selected_keywords: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for item in selected_keywords:
        keyword = normalize_text(item.get("keyword")) if isinstance(item, dict) else ""
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        lines.append(keyword)
    return lines


def _resolve_selection_label(input_data: Any, selected_keywords: list[dict[str, Any]]) -> str:
    root = input_data if isinstance(input_data, dict) else {}
    category_label = _resolve_category_label(root)
    mode = _resolve_mode(root)
    if category_label and mode == "category":
        return category_label

    seed_keyword_label = _resolve_seed_keyword_label(root, selected_keywords)
    if seed_keyword_label:
        return seed_keyword_label

    if category_label:
        return category_label
    return "selected-keywords"


def _resolve_category_label(input_data: Any) -> str:
    root = input_data if isinstance(input_data, dict) else {}
    collector = root.get("collector") if isinstance(root.get("collector"), dict) else {}
    return normalize_text(root.get("category")) or normalize_text(collector.get("category"))


def _resolve_seed_keyword_label(input_data: Any, selected_keywords: list[dict[str, Any]]) -> str:
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

    first_item = selected_keywords[0] if selected_keywords and isinstance(selected_keywords[0], dict) else {}
    return normalize_text(first_item.get("keyword"))


def _resolve_mode(input_data: Any) -> str:
    root = input_data if isinstance(input_data, dict) else {}
    collector = root.get("collector") if isinstance(root.get("collector"), dict) else {}
    return normalize_text(root.get("mode")) or normalize_text(collector.get("mode")) or "category"


def _sanitize_filename_segment(value: str, *, fallback: str) -> str:
    normalized = normalize_text(value) or fallback
    normalized = _INVALID_FILENAME_CHARS.sub("-", normalized)
    normalized = _FILENAME_SPACE_PATTERN.sub(" ", normalized).strip(" .-_")
    if not normalized:
        return fallback
    return normalized[:60]


def _build_artifact_metadata(format_key: str, path: Path) -> dict[str, Any]:
    return {
        "format": format_key,
        "path": str(path),
        "filename": path.name,
    }


def _coerce_boolish(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _now_kst() -> datetime:
    return datetime.now(_KST)
