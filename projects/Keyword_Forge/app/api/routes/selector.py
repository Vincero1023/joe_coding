from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.selector.longtail import verify_longtail_candidates
from app.selector.main import selector_module
from app.selector.serp_summary import summarize_serp_competition


router = APIRouter()


@router.post("/select", response_model=ModuleResponse)
def select_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=selector_module.run(payload.input_data))


@router.post("/verify-longtail", response_model=ModuleResponse)
def verify_longtail(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=verify_longtail_candidates(payload.input_data))


@router.post("/serp-competition-summary", response_model=ModuleResponse)
def serp_competition_summary(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=summarize_serp_competition(payload.input_data))
