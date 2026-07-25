"""FastAPI app factory - mounts every integration router under /api/v1."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, graph
from .config import get_settings
from .core.errors import register_error_handlers
from .core.logging_conf import configure_logging
from .core.middleware import ObservabilityMiddleware, RateLimitMiddleware
from .core.render import respond
from .core.security import require_api_key
from .ideas import registry as ideas
from .ideas.router import router as ideas_router
from .integrations.attendance.router import router as attendance_router
from .integrations.banks.router import router as banks_router
from .integrations.crm.router import router as crm_router
from .integrations.finance.live import refresh_loop
from .integrations.finance.router import router as finance_router
from .integrations.inventory.router import router as inventory_router
from .integrations.nama.router import router as nama_router
from .registry import SYSTEMS, Status
from .routers.graph import router as graph_router
from .routers.meta import router as meta_router
from .routers.observability import router as observability_router
from .routers.tools import router as tools_router
from .workspace.router import router as workspace_router

API_PREFIX = "/api/v1"


def _placeholder_router(key: str, name_en: str) -> APIRouter:
    """A PLANNED system still gets a mount point, so the gateway advertises the
    whole landscape.

    It answers 501 but is not a dead end: the body names the requirements
    waiting on this system and where to read about them, so hitting a planned
    route tells you what building it would unlock.
    """
    r = APIRouter(prefix=f"/{key}", tags=[key], dependencies=[Depends(require_api_key)])

    @r.get("", summary=f"{name_en} (planned)", status_code=501)
    async def _not_ready(request: Request):  # noqa: ANN202
        node = graph.system(key) or {}
        rows = [i for i in ideas.as_dicts() if key in i["systems"]]
        data = {
            "error": "NotImplementedYet",
            "detail": f"System '{key}' is planned but not wired yet.",
            "system": key,
            "ideas_waiting": len(rows),
            "connectors": node.get("connectors", []),
            "see": f"/systems/{key}",
            "board": f"/tools/ideas?sys={key}",
        }
        resp = respond(request, data, title=f"{name_en} — مخطّط (501)",
                       rows=rows or None, columns=["id", "title", "readiness", "needs"])
        resp.status_code = 501
        return resp

    return r


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Keep the live AR/AP snapshot warm while the app is up.

    The sweep is ~14,000 Nama documents and takes minutes, so it can never run
    inside a request; running it here means a snapshot already exists by the time
    anyone asks for `?source=live`, instead of the first visitor paying for it.
    Read-only — `/list` calls only. Off unless `LIVE_FINANCE_REFRESH_SECONDS` is
    set, so importing the app (as the test suite does) never touches the ERP.
    """
    settings = get_settings()
    task = None
    if settings.live_finance_refresh_seconds > 0:
        task = asyncio.create_task(
            refresh_loop(settings, settings.live_finance_refresh_seconds))
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="نقطة تكامل واحدة لكل الأنظمة - single integration point for all systems.",
        lifespan=_lifespan,
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
    app.include_router(tools_router)

    # live integrations
    app.include_router(nama_router, prefix=API_PREFIX)
    app.include_router(attendance_router, prefix=API_PREFIX)
    app.include_router(crm_router, prefix=API_PREFIX)
    app.include_router(banks_router, prefix=API_PREFIX)
    app.include_router(inventory_router, prefix=API_PREFIX)
    app.include_router(finance_router, prefix=API_PREFIX)
    app.include_router(workspace_router, prefix=API_PREFIX)
    app.include_router(ideas_router, prefix=API_PREFIX)
    app.include_router(graph_router, prefix=API_PREFIX)

    # planned integrations -> 501 placeholders (keeps the map complete)
    for s in SYSTEMS:
        if s.status is Status.PLANNED:
            app.include_router(_placeholder_router(s.key, s.name_en), prefix=API_PREFIX)

    @app.get("/", tags=["meta"])
    async def root(request: Request):
        cov = graph.coverage()
        data = {
            "service": settings.app_name, "version": __version__,
            "docs": "/docs", "systems": "/systems", "map": "/api/v1/map",
            "coverage": cov,
        }
        # Counts are computed, never typed in — the old page advertised
        # "11 systems" long after there were 22.
        rows = [
            {"link": "/tools/platform", "purpose": "الهَب — نقطة الدخول"},
            {"link": "/api/v1/map", "purpose": f"الخريطة الموحّدة ({cov['systems']} systems × {cov['ideas']} ideas)"},
            {"link": "/tools/ideas", "purpose": f"لوحة الأفكار ({cov['ideas']} requirement)"},
            {"link": "/api/v1/workspace", "purpose": "Unified workspace (all sections)"},
            {"link": "/systems", "purpose": f"All {cov['systems']} systems (live/planned)"},
            {"link": "/connectors", "purpose": "Connectors, mode, and what each unblocks"},
            {"link": "/health", "purpose": "Liveness + Nama reachability"},
            {"link": "/docs", "purpose": "Interactive Swagger UI"},
        ]
        return respond(request, data, title=settings.app_name, rows=rows, columns=["link", "purpose"])

    return app


app = create_app()
