from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.runtime_settings import (
    get_runtime_operation_snapshot,
    reset_runtime_operation_guards,
    update_runtime_operation_settings,
)


router = APIRouter()


class RuntimeSettingsUpdateRequest(BaseModel):
    mode: str = "always_on_slow"
    naver_request_gap_seconds: float | None = None
    daily_operation_limit: int | None = None
    daily_naver_request_limit: int | None = None
    max_continuous_minutes: int | None = None
    stop_on_auth_error: bool | None = None


class RuntimeSettingsEnvelope(BaseModel):
    operation_settings: dict[str, Any] = Field(default_factory=dict)


@router.get("/settings/runtime", response_model=RuntimeSettingsEnvelope)
def read_runtime_settings() -> RuntimeSettingsEnvelope:
    return RuntimeSettingsEnvelope(operation_settings=get_runtime_operation_snapshot())


@router.post("/settings/runtime", response_model=RuntimeSettingsEnvelope)
def write_runtime_settings(payload: RuntimeSettingsUpdateRequest) -> RuntimeSettingsEnvelope:
    update_runtime_operation_settings(payload.model_dump())
    return RuntimeSettingsEnvelope(operation_settings=get_runtime_operation_snapshot())


@router.post("/settings/runtime/reset-guards", response_model=RuntimeSettingsEnvelope)
def reset_runtime_guards() -> RuntimeSettingsEnvelope:
    return RuntimeSettingsEnvelope(operation_settings=reset_runtime_operation_guards())
