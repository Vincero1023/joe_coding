from fastapi import APIRouter

from app.api.routes import analyze, collect, expand, generate_title, selector


api_router = APIRouter()
api_router.include_router(collect.router, tags=["collector"])
api_router.include_router(expand.router, tags=["expander"])
api_router.include_router(analyze.router, tags=["analyzer"])
api_router.include_router(selector.router, tags=["selector"])
api_router.include_router(generate_title.router, tags=["title_gen"])
