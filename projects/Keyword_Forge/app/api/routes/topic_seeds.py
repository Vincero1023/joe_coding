from fastapi import APIRouter

from app.api.schemas import ModuleRequest, ModuleResponse
from app.core.runtime_settings import record_operation_start
from app.title.topic_seed_generator import generate_topic_seed_keywords


router = APIRouter()


@router.post("/topic-seeds", response_model=ModuleResponse)
def topic_seeds(payload: ModuleRequest) -> ModuleResponse:
    record_operation_start("topic_seeds")
    return ModuleResponse(result=generate_topic_seed_keywords(payload.input_data))
