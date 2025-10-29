"""Security-focused FastAPI middleware components."""
from __future__ import annotations

import json
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.httpsredirect import (
    HTTPSRedirectMiddleware as StarletteHTTPSRedirectMiddleware,
)
from starlette.responses import JSONResponse, Response

from app.security.rate_limit import RateLimiter
from app.security.sanitization import sanitize_text


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply an application-wide rate limit policy."""

    def __init__(self, app, rate_limiter: RateLimiter) -> None:  # type: ignore[override]
        super().__init__(app)
        self.rate_limiter = rate_limiter

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        identifier = _client_identifier(request)
        if not self.rate_limiter.is_allowed(identifier):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "Retry-After": str(self.rate_limiter.window_seconds),
                    "X-RateLimit-Limit": str(self.rate_limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(self.rate_limiter.window_seconds),
                },
            )

        response = await call_next(request)
        remaining = self.rate_limiter.remaining(identifier)
        response.headers.setdefault(
            "X-RateLimit-Limit", str(self.rate_limiter.max_requests)
        )
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        response.headers.setdefault(
            "X-RateLimit-Reset", str(self.rate_limiter.window_seconds)
        )
        return response


class AuditMiddleware(BaseHTTPMiddleware):
    """Record structured audit events for every request."""

    def __init__(self, app, audit_logger) -> None:  # type: ignore[override]
        super().__init__(app)
        self._logger = audit_logger

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            payload = {
                "path": request.url.path,
                "method": request.method,
                "client": _client_identifier(request),
                "status_code": 500,
                "duration_ms": round(duration_ms, 2),
                "error": repr(exc),
            }
            self._logger.info(json.dumps({"event": "request", **payload}, sort_keys=True))
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        payload = {
            "path": request.url.path,
            "method": request.method,
            "client": _client_identifier(request),
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }
        self._logger.info(json.dumps({"event": "request", **payload}, sort_keys=True))
        return response


class SanitizationMiddleware(BaseHTTPMiddleware):
    """Sanitize query parameters to mitigate reflected injection attacks."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        original_query = request.query_params.multi_items()
        if original_query:
            sanitized_items = [
                (key, sanitize_text(value) or "") for key, value in original_query
            ]
            request.scope["query_string"] = _encode_query_string(sanitized_items)
        return await call_next(request)


class HTTPSRedirectMiddleware(StarletteHTTPSRedirectMiddleware):
    """Redirect HTTP requests to HTTPS without interrupting WebSocket upgrades."""

    async def __call__(self, scope, receive, send):  # type: ignore[override]
        if scope.get("type") == "websocket":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is None:
        return "anonymous"
    return request.client.host


def _encode_query_string(items: list[tuple[str, str]]) -> bytes:
    from urllib.parse import urlencode

    return urlencode(items, doseq=True).encode("latin-1")
