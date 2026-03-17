from typing import Any

from pydantic import BaseModel, Field


class ModuleRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)


class ModuleResponse(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)

