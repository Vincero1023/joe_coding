from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.collector.main import collector_module


router = APIRouter()


@router.post("/collect", response_model=ModuleResponse)
def collect_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=collector_module.run(payload.input_data))


