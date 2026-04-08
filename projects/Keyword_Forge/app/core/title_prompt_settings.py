from __future__ import annotations

import json
from pathlib import Path
import re
from threading import RLock
from typing import Any

from app.expander.utils.tokenizer import normalize_text
from app.title.evaluation_prompt import DEFAULT_TITLE_EVALUATION_PROMPT


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TITLE_PROMPT_SETTINGS_PATH = _PROJECT_ROOT / "settings" / "title_prompt_settings.json"
_PROFILE_NAME_SPACE_PATTERN = re.compile(r"\s+")
_LOCK = RLock()
_PATH_OVERRIDE: Path | None = None
_DEFAULT_PRESET_TEMPERATURE = 0.7
_DEFAULT_QUALITY_RETRY_THRESHOLD = 75
_DEFAULT_ISSUE_CONTEXT_LIMIT = 3


def _build_default_settings() -> dict[str, Any]:
    return {
        "preset_key": "",
        "direct_system_prompt": "",
        "system_prompt": "",
        "prompt_profiles": [],
        "active_prompt_profile_id": "",
        "evaluation_direct_prompt": DEFAULT_TITLE_EVALUATION_PROMPT,
        "evaluation_prompt": DEFAULT_TITLE_EVALUATION_PROMPT,
        "evaluation_prompt_profiles": [],
        "active_evaluation_prompt_profile_id": "",
        "preset_profiles": [],
        "active_preset_profile_id": "",
    }


def get_title_prompt_settings() -> dict[str, Any]:
    with _LOCK:
        path = _resolve_settings_path()
        if not path.exists():
            return _build_default_settings()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _build_default_settings()
        return _normalize_title_prompt_settings(payload)


def update_title_prompt_settings(raw: Any) -> dict[str, Any]:
    with _LOCK:
        source = raw if isinstance(raw, dict) else {}
        normalized = _normalize_title_prompt_settings(
            {
                **get_title_prompt_settings(),
                **source,
            }
        )
        path = _resolve_settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    return normalized


def set_title_prompt_settings_path_for_tests(path: Path | str | None) -> None:
    global _PATH_OVERRIDE
    _PATH_OVERRIDE = Path(path) if path is not None else None


def reset_title_prompt_settings_for_tests() -> None:
    global _PATH_OVERRIDE
    _PATH_OVERRIDE = None


def _resolve_settings_path() -> Path:
    return _PATH_OVERRIDE or _DEFAULT_TITLE_PROMPT_SETTINGS_PATH


def _normalize_title_prompt_settings(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    prompt_profiles = _normalize_prompt_profiles(source.get("prompt_profiles"))
    active_prompt_profile_id = _normalize_profile_id(source.get("active_prompt_profile_id"))
    active_profile = next(
        (profile for profile in prompt_profiles if profile["id"] == active_prompt_profile_id),
        None,
    )
    evaluation_prompt_profiles = _normalize_prompt_profiles(source.get("evaluation_prompt_profiles"))
    active_evaluation_prompt_profile_id = _normalize_profile_id(source.get("active_evaluation_prompt_profile_id"))
    active_evaluation_profile = next(
        (
            profile
            for profile in evaluation_prompt_profiles
            if profile["id"] == active_evaluation_prompt_profile_id
        ),
        None,
    )
    preset_profiles = _normalize_preset_profiles(source.get("preset_profiles"))
    active_preset_profile_id = _normalize_profile_id(source.get("active_preset_profile_id"))
    active_preset_profile = next(
        (profile for profile in preset_profiles if profile["id"] == active_preset_profile_id),
        None,
    )
    direct_system_prompt = _normalize_prompt_text(
        source.get("direct_system_prompt") or (source.get("system_prompt") if active_profile is None else "")
    )
    has_explicit_evaluation_prompt_settings = any(
        key in source
        for key in (
            "evaluation_direct_prompt",
            "evaluation_prompt",
            "evaluation_prompt_profiles",
            "active_evaluation_prompt_profile_id",
        )
    )
    evaluation_direct_prompt = _normalize_prompt_text(
        source.get("evaluation_direct_prompt")
        if "evaluation_direct_prompt" in source
        else (
            source.get("evaluation_prompt")
            if active_evaluation_profile is None and "evaluation_prompt" in source
            else (
                DEFAULT_TITLE_EVALUATION_PROMPT
                if not has_explicit_evaluation_prompt_settings
                else ""
            )
        )
    )
    preset_key = _normalize_token(source.get("preset_key"))
    system_prompt = active_profile["prompt"] if active_profile else direct_system_prompt
    evaluation_prompt = (
        active_evaluation_profile["prompt"] if active_evaluation_profile else evaluation_direct_prompt
    )
    return {
        "preset_key": preset_key,
        "direct_system_prompt": direct_system_prompt,
        "system_prompt": system_prompt,
        "prompt_profiles": prompt_profiles,
        "active_prompt_profile_id": active_profile["id"] if active_profile else "",
        "evaluation_direct_prompt": evaluation_direct_prompt,
        "evaluation_prompt": evaluation_prompt,
        "evaluation_prompt_profiles": evaluation_prompt_profiles,
        "active_evaluation_prompt_profile_id": (
            active_evaluation_profile["id"] if active_evaluation_profile else ""
        ),
        "preset_profiles": preset_profiles,
        "active_preset_profile_id": active_preset_profile["id"] if active_preset_profile else "",
    }


def _normalize_prompt_profiles(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    output: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        profile_id = _normalize_profile_id(item.get("id")) or f"profile-{index}"
        if profile_id in seen_ids:
            continue
        seen_ids.add(profile_id)
        profile_name = _normalize_profile_name(item.get("name")) or f"저장본 {len(output) + 1}"
        output.append(
            {
                "id": profile_id,
                "name": profile_name,
                "prompt": _normalize_prompt_text(item.get("prompt")),
                "updated_at": normalize_text(item.get("updated_at")),
            }
        )
    return output


def _normalize_prompt_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").strip()


def _normalize_profile_name(value: Any) -> str:
    return _PROFILE_NAME_SPACE_PATTERN.sub(" ", str(value or "")).strip()


def _normalize_profile_id(value: Any) -> str:
    return str(value or "").strip()


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        candidates = [str(item or "").strip() for item in value]
    else:
        return []

    output: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _coerce_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _coerce_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_preset_profiles(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    output: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        profile_id = _normalize_profile_id(item.get("id")) or f"preset-{index}"
        if profile_id in seen_ids:
            continue
        seen_ids.add(profile_id)
        profile_name = _normalize_profile_name(item.get("name")) or f"프리셋 {len(output) + 1}"
        output.append(
            {
                "id": profile_id,
                "name": profile_name,
                "preset_key": _normalize_token(item.get("preset_key")),
                "provider": _normalize_token(item.get("provider")),
                "model": normalize_text(item.get("model")),
                "temperature": _coerce_float(
                    item.get("temperature"),
                    default=_DEFAULT_PRESET_TEMPERATURE,
                    minimum=0.0,
                    maximum=1.5,
                ),
                "auto_retry_enabled": _coerce_bool(item.get("auto_retry_enabled"), default=False),
                "quality_retry_threshold": _coerce_int(
                    item.get("quality_retry_threshold"),
                    default=_DEFAULT_QUALITY_RETRY_THRESHOLD,
                    minimum=70,
                    maximum=100,
                ),
                "issue_context_enabled": _coerce_bool(item.get("issue_context_enabled"), default=True),
                "issue_context_limit": _coerce_int(
                    item.get("issue_context_limit"),
                    default=_DEFAULT_ISSUE_CONTEXT_LIMIT,
                    minimum=1,
                    maximum=5,
                ),
                "issue_source_mode": _normalize_token(item.get("issue_source_mode")),
                "community_sources": _normalize_string_list(item.get("community_sources")),
                "community_custom_domains": _normalize_string_list(item.get("community_custom_domains")),
                "prompt_profile_id": _normalize_profile_id(item.get("prompt_profile_id")),
                "direct_system_prompt": _normalize_prompt_text(
                    item.get("direct_system_prompt") or item.get("system_prompt")
                ),
                "evaluation_prompt_profile_id": _normalize_profile_id(item.get("evaluation_prompt_profile_id")),
                "evaluation_direct_prompt": _normalize_prompt_text(
                    item.get("evaluation_direct_prompt") or item.get("evaluation_prompt")
                ),
                "rewrite_provider": _normalize_token(item.get("rewrite_provider")),
                "rewrite_model": normalize_text(item.get("rewrite_model")),
                "updated_at": normalize_text(item.get("updated_at")),
            }
        )
    return output
