"""Gateway meta endpoints: health + system landscape (HTML or JSON)."""
from fastapi import APIRouter, Depends, Request

from .. import __version__
from ..config import Settings, get_settings
from ..core.render import respond
from ..integrations.nama.connector import NamaConnector
from ..registry import as_dicts

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
    data = {
        "status": "ok",
        "version": __version__,
        "env": settings.app_env,
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
        {"field": "nama.configured", "value": data["nama"]["configured"]},
        {"field": "nama.reachable", "value": data["nama"]["reachable"]},
        {"field": "nama.mode", "value": data["nama"]["mode"]},
        {"field": "nama.detail", "value": data["nama"]["detail"]},
    ]
    return respond(request, data, title="Health", rows=rows, columns=["field", "value"])


@router.get("/systems")
async def systems(request: Request):
    """The full integration landscape - one entry per company system."""
    items = as_dicts()
    live = sum(1 for s in items if s["status"] == "live")
    data = {"count": len(items), "live": live, "planned": len(items) - live, "systems": items}
    badges = f'<span class="badge">{live} live</span><span class="badge ro">{len(items) - live} planned</span>'
    return respond(
        request, data, title="Systems", rows=items,
        columns=["key", "name_en", "name_ar", "status", "description"], badges=badges,
    )


@router.get("/connectors")
async def connectors(request: Request, settings: Settings = Depends(get_settings)):
    """Live connectors and their read/write mode."""
    rows = [
        {"key": "nama", "mode": settings.nama_mode, "read_only": settings.nama_mode == "read_only"},
    ]
    data = {"connectors": rows}
    ro = settings.nama_mode == "read_only"
    badges = f'<span class="badge {"ro" if ro else ""}">{settings.nama_mode}</span>'
    return respond(request, data, title="Connectors", rows=rows,
                   columns=["key", "mode", "read_only"], badges=badges)
