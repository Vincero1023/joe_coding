from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.analyzer.main import analyzer_module


router = APIRouter()


@router.post("/analyze", response_model=ModuleResponse)
def analyze_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=analyzer_module.run(payload.input_data))


