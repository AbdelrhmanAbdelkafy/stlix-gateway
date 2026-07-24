"""Gateway meta endpoints: health + system landscape."""
from fastapi import APIRouter, Depends

from .. import __version__
from ..config import Settings, get_settings
from ..integrations.nama.client import NamaClient
from ..registry import as_dicts

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    """Liveness + Nama reachability/auth check."""
    nama_reachable, detail = False, None
    if settings.nama_configured:
        try:
            await NamaClient(settings).ping()
            nama_reachable = True
        except Exception as exc:  # noqa: BLE001 - report any upstream failure
            detail = str(exc)
    else:
        detail = "Nama credentials not configured."
    return {
        "status": "ok",
        "version": __version__,
        "env": settings.app_env,
        "nama": {"configured": settings.nama_configured, "reachable": nama_reachable, "detail": detail},
    }


@router.get("/systems")
async def systems() -> dict:
    """The full integration landscape - one entry per company system."""
    items = as_dicts()
    live = sum(1 for s in items if s["status"] == "live")
    return {"count": len(items), "live": live, "planned": len(items) - live, "systems": items}
