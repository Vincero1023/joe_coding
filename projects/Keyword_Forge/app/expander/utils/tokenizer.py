from __future__ import annotations

import re
from typing import Any


_SPECIAL_PATTERN = re.compile(r"[^0-9A-Za-z\u3131-\u318E\uAC00-\uD7A3]+")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def tokenize_text(value: Any) -> list[str]:
    normalized = normalize_text(value)
    return [token for token in normalized.split(" ") if token]


def normalize_key(value: Any) -> str:
    normalized = normalize_text(value).lower()
    return _SPECIAL_PATTERN.sub("", normalized)
