"""Uniform error envelope for every integration."""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class GatewayError(Exception):
    """Base for gateway-side failures that map to a clean HTTP response."""

    def __init__(self, message: str, http_status: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(message)
        self.message = message
        self.http_status = http_status


class UpstreamError(GatewayError):
    """An integrated system (Nama, CRM, ...) returned a failure."""


class NotImplementedYet(GatewayError):
    def __init__(self, system: str) -> None:
        super().__init__(f"System '{system}' is planned but not wired yet.", status.HTTP_501_NOT_IMPLEMENTED)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayError)
    async def _handle(_: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.__class__.__name__, "detail": exc.message},
        )
