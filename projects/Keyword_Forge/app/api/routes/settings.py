from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.runtime_settings import (
    get_runtime_operation_snapshot,
    reset_runtime_operation_guards,
    update_runtime_operation_settings,
)
from app.core.title_prompt_settings import get_title_prompt_settings, update_title_prompt_settings


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


class TitlePromptProfilePayload(BaseModel):
    id: str = ""
    name: str = ""
    prompt: str = ""
    updated_at: str = ""


class TitlePresetProfilePayload(BaseModel):
    id: str = ""
    name: str = ""
    preset_key: str = ""
    provider: str = ""
    model: str = ""
    temperature: float | None = None
    fallback_to_template: bool | None = None
    auto_retry_enabled: bool | None = None
    quality_retry_threshold: int | None = None
    issue_context_enabled: bool | None = None
    issue_context_limit: int | None = None
    issue_source_mode: str = ""
    community_sources: list[str] = Field(default_factory=list)
    community_custom_domains: list[str] = Field(default_factory=list)
    prompt_profile_id: str = ""
    direct_system_prompt: str = ""
    evaluation_prompt_profile_id: str = ""
    evaluation_direct_prompt: str = ""
    rewrite_provider: str = ""
    rewrite_model: str = ""
    updated_at: str = ""


class TitlePromptSettingsRequest(BaseModel):
    preset_key: str | None = None
    direct_system_prompt: str | None = None
    system_prompt: str | None = None
    prompt_profiles: list[TitlePromptProfilePayload] | None = None
    active_prompt_profile_id: str | None = None
    evaluation_direct_prompt: str | None = None
    evaluation_prompt: str | None = None
    evaluation_prompt_profiles: list[TitlePromptProfilePayload] | None = None
    active_evaluation_prompt_profile_id: str | None = None
    preset_profiles: list[TitlePresetProfilePayload] | None = None
    active_preset_profile_id: str | None = None


class TitlePromptSettingsEnvelope(BaseModel):
    title_prompt_settings: dict[str, Any] = Field(default_factory=dict)


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


@router.get("/settings/title-prompt", response_model=TitlePromptSettingsEnvelope)
def read_title_prompt_settings() -> TitlePromptSettingsEnvelope:
    return TitlePromptSettingsEnvelope(title_prompt_settings=get_title_prompt_settings())


@router.post("/settings/title-prompt", response_model=TitlePromptSettingsEnvelope)
def write_title_prompt_settings(payload: TitlePromptSettingsRequest) -> TitlePromptSettingsEnvelope:
    return TitlePromptSettingsEnvelope(
        title_prompt_settings=update_title_prompt_settings(payload.model_dump(exclude_none=True))
    )
