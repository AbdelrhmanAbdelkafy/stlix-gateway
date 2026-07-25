"""The unified map: every system, connector, endpoint, idea and engine, joined.

One endpoint returns the whole graph; `?view=` picks which node type becomes the
HTML table for a browser, while JSON always carries everything so a client never
has to make five calls to answer one question.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from .. import graph
from ..config import Settings, get_settings
from ..core.render import respond
from ..core.security import require_api_key

router = APIRouter(prefix="/map", tags=["map"], dependencies=[Depends(require_api_key)])

_COLUMNS = {
    "systems": ["key", "name_ar", "status", "connectors", "endpoints", "ideas_owned", "board"],
    "connectors": ["key", "name_ar", "system", "live", "configured", "mode",
                   "endpoints_count", "ideas", "sole_blocker_for", "board"],
    "endpoints": ["path", "title_ar", "connector", "system", "method", "feeds_count"],
    "engines": ["key", "name_ar", "vision", "built", "board"],
    "ideas": ["id", "title", "primary_system", "readiness", "data_endpoints", "needs"],
}


@router.get("")
async def unified_map(
    request: Request,
    view: str = Query("systems", pattern="^(systems|connectors|endpoints|engines|ideas)$"),
    system: str | None = Query(None, description="Narrow the graph to one system"),
    connector: str | None = Query(None, description="Narrow the graph to one connector"),
    engine: str | None = Query(None, description="Narrow the graph to one engine"),
    settings: Settings = Depends(get_settings),
):
    """The whole hub in one payload. Every node carries its own edges."""
    data = graph.build(settings)

    if system:
        key = system.strip().lower()
        data["systems"] = [s for s in data["systems"] if s["key"] == key]
        data["ideas"] = [i for i in data["ideas"] if key in i["systems"]]
        data["connectors"] = [c for c in data["connectors"] if c["system"] == key]
        keep = {p for c in data["connectors"] for p in c["endpoints"]}
        data["endpoints"] = [e for e in data["endpoints"] if e["path"] in keep]
    if connector:
        key = connector.strip().lower()
        data["connectors"] = [c for c in data["connectors"] if c["key"] == key]
        data["ideas"] = [i for i in data["ideas"] if key in i["connectors"]]
        data["endpoints"] = [e for e in data["endpoints"] if e["connector"] == key]
    if engine:
        key = engine.strip()
        data["engines"] = [e for e in data["engines"] if e["key"].lower() == key.lower()]
        data["ideas"] = [i for i in data["ideas"] if (i["engine"] or "") == key]

    data["view"] = view
    data["filters"] = {"system": system, "connector": connector, "engine": engine}
    rows = data[view]
    badges = (f'<span class="badge">{len(data["systems"])} systems</span>'
              f'<span class="badge">{len(data["connectors"])} connectors</span>'
              f'<span class="badge">{len(data["ideas"])} ideas</span>')
    return respond(request, data, title=f"الخريطة الموحّدة · {view}",
                   rows=rows, columns=_COLUMNS[view], badges=badges)
