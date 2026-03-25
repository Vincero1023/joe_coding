from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.core.runtime_settings import record_operation_start
from app.selector.longtail import verify_longtail_candidates
from app.selector.main import selector_module
from app.selector.serp_summary import summarize_serp_competition


router = APIRouter()


@router.post("/select", response_model=ModuleResponse)
def select_keywords(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("select")
    return ModuleResponse(result=selector_module.run(_with_default_selection_export(payload.input_data)))


@router.post("/verify-longtail", response_model=ModuleResponse)
def verify_longtail(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("verify_longtail")
    return ModuleResponse(result=verify_longtail_candidates(payload.input_data))


@router.post("/serp-competition-summary", response_model=ModuleResponse)
def serp_competition_summary(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("serp_competition_summary")
    return ModuleResponse(result=summarize_serp_competition(payload.input_data))


def _with_default_selection_export(input_data):
    if not isinstance(input_data, dict):
        return input_data

    merged = dict(input_data)
    raw_export = merged.get("selection_export") if isinstance(merged.get("selection_export"), dict) else {}
    title_export = merged.get("title_export") if isinstance(merged.get("title_export"), dict) else {}
    merged["selection_export"] = {
        **raw_export,
        "enabled": _coerce_boolish(raw_export.get("enabled"), default=True),
        "output_dir": raw_export.get("output_dir") or title_export.get("output_dir") or raw_export.get("output_dir"),
    }
    return merged


def _coerce_boolish(value, *, default: bool) -> bool:
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
