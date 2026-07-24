"""FastAPI app factory - mounts every integration router under /api/v1."""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .core.errors import NotImplementedYet, register_error_handlers
from .core.logging_conf import configure_logging
from .core.middleware import ObservabilityMiddleware, RateLimitMiddleware
from .core.render import respond
from .core.security import require_api_key
from .integrations.attendance.router import router as attendance_router
from .integrations.crm.router import router as crm_router
from .integrations.nama.router import router as nama_router
from .registry import SYSTEMS, Status
from .routers.meta import router as meta_router
from .routers.observability import router as observability_router

API_PREFIX = "/api/v1"


def _placeholder_router(key: str, name_en: str) -> APIRouter:
    """A PLANNED system still gets a mount point that returns 501, so the
    gateway advertises the whole landscape and clients get a clear signal."""
    r = APIRouter(prefix=f"/{key}", tags=[key], dependencies=[Depends(require_api_key)])

    @r.get("", summary=f"{name_en} (planned)")
    async def _not_ready() -> dict:  # noqa: ANN202
        raise NotImplementedYet(key)

    return r


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="نقطة تكامل واحدة لكل الأنظمة - single integration point for all systems.",
    )
    # Middleware runs outermost-first in reverse add order: add rate-limit first
    # (inner), then observability (outer) so every request gets an id + metrics.
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    # meta (health, systems) + monitoring at root
    app.include_router(meta_router)
    app.include_router(observability_router)

    # live integrations
    app.include_router(nama_router, prefix=API_PREFIX)
    app.include_router(attendance_router, prefix=API_PREFIX)
    app.include_router(crm_router, prefix=API_PREFIX)

    # planned integrations -> 501 placeholders (keeps the map complete)
    live_keys = {"nama", "attendance", "crm"}
    for s in SYSTEMS:
        if s.status is Status.PLANNED and s.key not in live_keys:
            app.include_router(_placeholder_router(s.key, s.name_en), prefix=API_PREFIX)

    @app.get("/", tags=["meta"])
    async def root(request: Request):
        data = {"service": settings.app_name, "version": __version__, "docs": "/docs", "systems": "/systems"}
        rows = [
            {"link": "/health", "purpose": "Liveness + Nama reachability"},
            {"link": "/systems", "purpose": "All 11 systems (live/planned)"},
            {"link": "/connectors", "purpose": "Live connectors + mode"},
            {"link": "/api/v1/nama/employees", "purpose": "List employees (read-only)"},
            {"link": "/docs", "purpose": "Interactive Swagger UI"},
        ]
        return respond(request, data, title=settings.app_name, rows=rows, columns=["link", "purpose"])

    return app


app = create_app()
