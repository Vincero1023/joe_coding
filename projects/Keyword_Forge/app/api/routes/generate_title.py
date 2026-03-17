from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.title_gen.main import title_generator_module


router = APIRouter()


@router.post("/generate-title", response_model=ModuleResponse)
def generate_title(payload: ModuleRequest) -> ModuleResponse:
    return ModuleResponse(result=title_generator_module.run(payload.input_data))


