"""Structured logging + correlation IDs (Chapters 29 & 31).

Every request gets a correlation_id (from the X-Correlation-ID header or a new
UUID). Logs are emitted as single-line JSON and the id is echoed back on the
response so a business action can be traced end-to-end.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    return _correlation_id.get()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": get_correlation_id(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        token = _correlation_id.set(cid)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(token)
        response.headers["X-Correlation-ID"] = cid
        return response


logger = logging.getLogger("finance_os")
