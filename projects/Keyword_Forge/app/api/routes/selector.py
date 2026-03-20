from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.selector.longtail import verify_longtail_candidates
from app.selector.main import selector_module


router = APIRouter()


@router.post("/select", response_model=ModuleResponse)
def select_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=selector_module.run(payload.input_data))


@router.post("/verify-longtail", response_model=ModuleResponse)
def verify_longtail(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=verify_longtail_candidates(payload.input_data))
