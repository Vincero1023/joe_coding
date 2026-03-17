from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_json(data: dict[str, Any], output_path: str) -> Path:
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
