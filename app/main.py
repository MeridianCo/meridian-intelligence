"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.profiles import router as profiles_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


def create_app() -> FastAPI:
    """Application factory – called at module level and also usable in tests."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Consolidates and enriches professional profiles from sources like "
            "LinkedIn and public websites into a single structured context object."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(profiles_router)

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {"service": settings.app_name, "version": settings.app_version}

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
