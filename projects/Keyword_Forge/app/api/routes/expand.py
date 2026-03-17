from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.expander.main import expander_module


router = APIRouter()


@router.post("/expand", response_model=ModuleResponse)
def expand_keywords(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=expander_module.run(payload.input_data))


