"""Application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from app.api.routes import router
from app.config import get_settings
from app.observability.logging import setup_structured_logging
from app.security.audit import configure_audit_logger
from app.security.encryption import get_data_encryptor
from app.security.middleware import (
    AuditMiddleware,
    RateLimitMiddleware,
    SanitizationMiddleware,
)
from app.security.rate_limit import RateLimiter
from app.security.vault import get_vault_client

setup_structured_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

audit_logger = configure_audit_logger(settings.audit_log_path)
rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

app.add_middleware(AuditMiddleware, audit_logger=audit_logger)
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
app.add_middleware(SanitizationMiddleware)

app.state.audit_logger = audit_logger
app.state.rate_limiter = rate_limiter
app.state.vault_client = get_vault_client()
app.state.encryptor = get_data_encryptor()

app.include_router(router, prefix="/api")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return service health status."""

    return {"status": "ok"}


@app.get("/", tags=["meta"])
def read_root() -> dict[str, str]:
    """Return basic application metadata."""

    return {"application": settings.app_name, "environment": settings.app_env}
