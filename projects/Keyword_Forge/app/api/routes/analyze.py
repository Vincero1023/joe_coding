from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.analyzer.main import analyzer_module
from app.core.runtime_settings import record_operation_start


router = APIRouter()


@router.post("/analyze", response_model=ModuleResponse)
def analyze_keywords(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("analyze")
    return ModuleResponse(result=analyzer_module.run(payload.input_data))


