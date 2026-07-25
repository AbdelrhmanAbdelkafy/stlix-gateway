"""Gateway meta endpoints: health + the system/connector landscape (HTML or JSON)."""
from fastapi import APIRouter, Depends, HTTPException, Request

from .. import __version__, catalog, graph
from ..config import Settings, get_settings
from ..core.metrics import metrics
from ..core.render import respond
from ..ideas import registry as ideas
from ..integrations.nama.connector import NamaConnector

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(request: Request, settings: Settings = Depends(get_settings)):
    """Liveness + Nama reachability/auth check."""
    nama_reachable, detail = False, None
    if settings.nama_configured:
        try:
            await NamaConnector(settings).ping()
            nama_reachable = True
        except Exception as exc:  # noqa: BLE001 - report any upstream failure
            detail = str(exc)
    else:
        detail = "Nama credentials not configured."
    # Every live connector's wiring state, without hammering six upstreams on
    # each poll: `configured` is local, only Nama is actually probed.
    conns = [c for c in catalog.as_dicts(settings) if c["live"]]
    data = {
        "status": "ok",
        "version": __version__,
        "env": settings.app_env,
        "uptime_seconds": metrics.uptime_seconds,
        "requests_total": metrics.total,
        "connectors_live": len(conns),
        "connectors_configured": sum(1 for c in conns if c["configured"]),
        "connectors": {c["key"]: {"configured": c["configured"], "mode": c["mode"]} for c in conns},
        "nama": {
            "configured": settings.nama_configured,
            "reachable": nama_reachable,
            "mode": settings.nama_mode,
            "detail": detail,
        },
    }
    rows = [
        {"field": "status", "value": data["status"]},
        {"field": "version", "value": data["version"]},
        {"field": "env", "value": data["env"]},
        {"field": "uptime_seconds", "value": data["uptime_seconds"]},
        {"field": "requests_total", "value": data["requests_total"]},
        {"field": "connectors_live", "value": data["connectors_live"]},
        {"field": "connectors_configured", "value": data["connectors_configured"]},
        {"field": "nama.configured", "value": data["nama"]["configured"]},
        {"field": "nama.reachable", "value": data["nama"]["reachable"]},
        {"field": "nama.mode", "value": data["nama"]["mode"]},
        {"field": "nama.detail", "value": data["nama"]["detail"]},
    ]
    return respond(request, data, title="Health", rows=rows, columns=["field", "value"])


@router.get("/systems")
async def systems(request: Request):
    """The integration landscape — each system with what waits on it.

    The counts come from the same join the map and the ideas board use, so a
    system can never report one number here and another there.
    """
    items = graph.systems()
    live = sum(1 for s in items if s["status"] == "live")
    cov = graph.coverage()
    rows = [
        {**s, "connectors": ", ".join(s["connectors"]) or "—",
         "ideas_total": s["ideas"]["total"], "ideas_ready": s["ideas"]["ready"]}
        for s in items
    ]
    data = {
        "count": len(items), "live": live, "planned": len(items) - live,
        "ideas_total": cov["ideas"], "ideas_unmapped": cov["ideas_unmapped"],
        # A system nothing asks for means either the map or the backlog is wrong.
        "systems_without_ideas": cov["systems_without_ideas"],
        "systems": items,
    }
    badges = f'<span class="badge">{live} live</span><span class="badge ro">{len(items) - live} planned</span>'
    return respond(
        request, data, title="Systems", rows=rows, badges=badges,
        columns=["key", "name_en", "name_ar", "status", "url", "connectors",
                 "ideas_total", "ideas_ready", "ideas_owned", "board"],
    )


@router.get("/systems/{key}")
async def system_detail(request: Request, key: str):
    """One system: its connectors, its endpoints, and every requirement on it."""
    sysrow = graph.system(key)
    if sysrow is None:
        raise HTTPException(status_code=404, detail=f"No system '{key}' on the map")
    mine = [i for i in ideas.as_dicts() if key.lower() in i["systems"]]
    data = {**sysrow, "ideas_detail": mine}
    badges = (f'<span class="badge">{sysrow["status"]}</span>'
              f'<span class="badge ro">{sysrow["ideas"]["total"]} ideas</span>')
    return respond(
        request, data, title=f'{sysrow["name_ar"]} · {sysrow["name_en"]}',
        rows=mine, badges=badges,
        columns=["id", "title", "readiness", "source", "data_endpoints", "needs"],
    )


@router.get("/connectors")
async def connectors(request: Request, settings: Settings = Depends(get_settings)):
    """Every connector: mode, endpoints, and how much of the backlog it unblocks.

    Reads the catalogue rather than a hardcoded list — this used to report only
    `nama` while five other connectors were live.
    """
    rows = graph.connectors(settings)
    live = [r for r in rows if r["live"]]
    data = {
        "count": len(rows),
        "live": len(live),
        "planned": len(rows) - len(live),
        "writes_enabled": [r["key"] for r in rows if not r["read_only"]],
        "connectors": rows,
    }
    badges = (f'<span class="badge">{len(live)} live</span>'
              f'<span class="badge ro">{len(rows) - len(live)} planned</span>')
    return respond(
        request, data, title="Connectors", rows=rows, badges=badges,
        columns=["key", "name_ar", "system", "upstream", "live", "configured",
                 "mode", "endpoints_count", "ideas", "ideas_ready", "sole_blocker_for"],
    )


@router.get("/connectors/{key}")
async def connector_detail(request: Request, key: str, settings: Settings = Depends(get_settings)):
    """One connector: what it reads, and exactly which requirements wait on it.

    This is where an idea's "ناقص: X" lands, so a blocked idea leads somewhere
    instead of dead-ending on the word "missing".
    """
    row = graph.connector(key, settings)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No connector '{key}' in the catalogue")
    waiting = [i for i in ideas.as_dicts() if key.lower() in i["missing_connectors"]]
    data = {**row, "waiting_on_it": waiting}
    badges = (f'<span class="badge{"" if row["live"] else " ro"}">'
              f'{"live" if row["live"] else "planned"}</span>'
              f'<span class="badge ro">{len(waiting)} waiting</span>')
    return respond(
        request, data, title=f'{row["name_ar"]} · {row["name_en"]}',
        rows=waiting or None, badges=badges,
        columns=["id", "title", "domain", "readiness", "needs"],
    )
