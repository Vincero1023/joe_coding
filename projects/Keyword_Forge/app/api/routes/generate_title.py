from fastapi import APIRouter
from typing import Any

from app.api.schemas import ModuleRequest, ModuleResponse
from app.core.runtime_settings import record_operation_start
from app.title_gen.main import title_generator_module


router = APIRouter()


@router.post("/generate-title", response_model=ModuleResponse)
def generate_title(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("generate_title")
    return ModuleResponse(result=title_generator_module.run(_with_default_title_export(payload.input_data)))


def _with_default_title_export(input_data: Any) -> Any:
    if not isinstance(input_data, dict):
        return input_data

    merged = dict(input_data)
    raw_export = merged.get("title_export") if isinstance(merged.get("title_export"), dict) else {}
    merged["title_export"] = {
        **raw_export,
        "enabled": _coerce_boolish(raw_export.get("enabled"), default=True),
    }
    return merged


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


