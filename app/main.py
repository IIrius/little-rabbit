"""Application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(router, prefix="/api")


@app.get("/", tags=["meta"])
def read_root() -> dict[str, str]:
    """Return basic application metadata."""

    return {"application": settings.app_name, "environment": settings.app_env}
