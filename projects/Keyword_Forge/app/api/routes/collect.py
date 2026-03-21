from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.collector.main import collector_module
from app.core.runtime_settings import record_operation_start


router = APIRouter()


@router.post("/collect", response_model=ModuleResponse)
def collect_keywords(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("collect")
    return ModuleResponse(result=collector_module.run(payload.input_data))


