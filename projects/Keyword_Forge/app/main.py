from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.web import router as web_router


settings = get_settings()
assets_dir = Path(__file__).resolve().parent / "web_assets"

app = FastAPI(
    title="키워드 포지",
    version="0.1.0",
    description="키워드 수집, 확장, 분석, 선별, 제목 생성을 실행하는 한국어 웹 인터페이스와 API입니다.",
    docs_url="/api-docs",
    redoc_url=None,
)

app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.include_router(web_router)
app.include_router(api_router)