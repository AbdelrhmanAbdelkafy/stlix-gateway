"""Cross-cutting middleware: request-id + access logging + metrics + security
headers (observability), and a simple fixed-window rate limiter."""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config import get_settings
from .metrics import metrics

_access_log = logging.getLogger("gateway.access")

# Paths never rate-limited (probes/telemetry/docs).
_RL_EXEMPT = {"/health", "/metrics", "/", "/favicon.ico", "/docs", "/openapi.json", "/redoc"}

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
}


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path_format", None) or getattr(route, "path", None) or request.url.path


def _client_key(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key[:8]}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, times the request, records metrics, logs, and
    (optionally) sets security headers on the response."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        rid = request.headers.get("x-request-id") or uuid4().hex[:12]
        request.state.request_id = rid
        start = time.perf_counter()
        status = 500
        try:
            response: Response = await call_next(request)
            status = response.status_code
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            metrics.record(_route_label(request), 500, elapsed)
            _access_log.exception(
                "request failed",
                extra={"extra_fields": {
                    "request_id": rid, "method": request.method,
                    "path": request.url.path, "status": 500,
                    "duration_ms": round(elapsed, 1),
                }},
            )
            raise
        elapsed = (time.perf_counter() - start) * 1000
        metrics.record(_route_label(request), status, elapsed)
        _access_log.info(
            "request",
            extra={"extra_fields": {
                "request_id": rid, "method": request.method,
                "path": request.url.path, "status": status,
                "duration_ms": round(elapsed, 1), "client": _client_key(request),
            }},
        )
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time-ms"] = f"{elapsed:.1f}"
        if settings.security_headers:
            for k, v in _SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-client limiter. In-memory (single process)."""

    def __init__(self, app, limit_per_minute: int) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._hits: dict[tuple[str, int], int] = {}

    async def dispatch(self, request: Request, call_next):
        if self._limit <= 0 or request.url.path in _RL_EXEMPT:
            return await call_next(request)
        window = int(time.time() // 60)
        key = (_client_key(request), window)
        # prune old windows cheaply
        if len(self._hits) > 4096:
            self._hits = {k: v for k, v in self._hits.items() if k[1] >= window}
        count = self._hits.get(key, 0) + 1
        self._hits[key] = count
        if count > self._limit:
            metrics.note_rate_limited()
            return JSONResponse(
                status_code=429,
                content={"error": "RateLimited", "detail": f"Limit {self._limit}/min exceeded."},
                headers={"Retry-After": "60", "X-RateLimit-Limit": str(self._limit)},
            )
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(self._limit)
        resp.headers["X-RateLimit-Remaining"] = str(max(0, self._limit - count))
        return resp
