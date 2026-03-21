from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.core.runtime_settings import record_operation_start
from app.pipeline.main import pipeline_module


router = APIRouter()


@router.post("/pipeline", response_model=ModuleResponse)
def run_pipeline(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("pipeline")
    return ModuleResponse(result=pipeline_module.run(payload.input_data))
