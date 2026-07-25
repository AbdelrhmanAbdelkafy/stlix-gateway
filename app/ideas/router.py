"""Ideas endpoints — the whole backlog, filterable, as HTML or JSON.

Scales with the file: whether BACKLOG.md holds 180 rows or 500, these endpoints
return all of them. Filters exist so a human can narrow, not because the API
truncates.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.render import respond
from ..core.security import require_api_key
from . import registry

router = APIRouter(prefix="/ideas", tags=["ideas"], dependencies=[Depends(require_api_key)])

_COLUMNS = ["id", "title", "domain", "primary_system", "readiness",
            "data_endpoints", "needs", "link"]


@router.get("")
async def list_ideas(
    request: Request,
    q: str | None = Query(None, description="Free-text search over id/title/domain/source"),
    domain: str | None = Query(None, description="Domain prefix, e.g. S / WH / UX"),
    status: str | None = Query(None, pattern="^(live|next|planned)$"),
    readiness: str | None = Query(
        None, pattern="^(done|ready|partial|blocked)$",
        description="ready = every connector it needs already exists",
    ),
    engine: str | None = Query(None, description="One of the reusable engines"),
    system: str | None = Query(None, description="registry.SYSTEMS key, e.g. nama / crm / banks"),
    connector: str | None = Query(None, description="Catalog connector key, e.g. sql / crm"),
    endpoint: str | None = Query(None, description="Only ideas whose raw data this route holds"),
    section: str | None = Query(None, description="Workspace section key"),
    has_data: bool | None = Query(None, description="true = at least one live data endpoint"),
):
    """Every requirement the owner has voiced — no cap, filters optional.

    The filters are the edges of the map: from a system, a connector, an
    endpoint or a workspace section you can ask what it carries.
    """
    rows = registry.as_dicts()
    if domain:
        d = domain.strip().upper()
        rows = [r for r in rows if r["prefix"] == d]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if readiness:
        rows = [r for r in rows if r["readiness"] == readiness]
    if engine:
        e = engine.strip().lower()
        rows = [r for r in rows if (r["engine"] or "").lower() == e]
    if system:
        s = system.strip().lower()
        rows = [r for r in rows if s in r["systems"]]
    if connector:
        c = connector.strip().lower()
        rows = [r for r in rows if c in r["connectors"]]
    if endpoint:
        rows = [r for r in rows if endpoint in r["data_endpoints"]]
    if section:
        rows = [r for r in rows if r["workspace_section"] == section.strip().lower()]
    if has_data is not None:
        rows = [r for r in rows if bool(r["data_endpoints"]) is has_data]
    if q:
        needle = q.strip().lower()
        rows = [
            r for r in rows
            if needle in f"{r['id']} {r['title']} {r['domain']} {r['domain_en']} {r['source']}".lower()
        ]

    data = {
        "summary": registry.summary(),
        "returned": len(rows),
        "data_endpoints_mean": "raw data already queryable there — NOT a built report",
        "filters": {"q": q, "domain": domain, "status": status, "readiness": readiness,
                    "engine": engine, "system": system, "connector": connector,
                    "endpoint": endpoint, "section": section, "has_data": has_data},
        "page": "/tools/ideas",
        "map": "/api/v1/map",
        "ideas": rows,
    }
    return respond(request, data, title=f"الأفكار والمتطلبات ({len(rows)})",
                   rows=rows, columns=_COLUMNS)


@router.get("/domains")
async def list_domains(request: Request):
    """One row per domain: its counts, its systems, and how much has live data."""
    rows = registry.domains()
    data = {"summary": registry.summary(), "domains": rows}
    return respond(request, data, title="دومينات الأفكار", rows=rows,
                   columns=["prefix", "domain", "domain_en", "total", "ready",
                            "with_data", "systems", "page"])


@router.get("/{idea_id}")
async def get_idea(request: Request, idea_id: str):
    """A single idea by its backlog id (S1, WH13, UX1b …)."""
    idea = registry.get(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"No idea '{idea_id}' in BACKLOG.md")
    return respond(request, idea, title=f"{idea['id']} · {idea['title'][:60]}",
                   rows=[idea], columns=_COLUMNS)
