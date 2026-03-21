from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.errors import install_error_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.scheduler.service import get_job_scheduler_service
from app.web import router as web_router


settings = get_settings()
assets_dir = Path(__file__).resolve().parent / "web_assets"


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler_service = get_job_scheduler_service()
    scheduler_service.start()
    try:
        yield
    finally:
        scheduler_service.shutdown()

app = FastAPI(
    title="키워드 포지",
    version="0.1.0",
    description="키워드 수집, 확장, 분석, 선별, 제목 생성을 실행하는 모듈형 API입니다.",
    docs_url="/api-docs",
    redoc_url=None,
    lifespan=lifespan,
)

install_error_handlers(app, app_env=settings.app_env)

app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.include_router(web_router)
app.include_router(api_router)
