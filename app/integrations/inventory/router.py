"""Inventory / Stocktake (الجرد) read endpoints - HTML or JSON."""
from fastapi import APIRouter, Depends, Request

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from .connector import InventoryConnector

router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[Depends(require_api_key)])


def get_inv(settings: Settings = Depends(get_settings)) -> InventoryConnector:
    return InventoryConnector(settings)


@router.get("")
async def progress(request: Request, inv: InventoryConnector = Depends(get_inv)):
    """Stocktake progress summary."""
    p = await inv.progress()
    rows = [
        {"metric": "rev (cursor)", "value": p["rev"]},
        {"metric": "tracked items", "value": p["tracked"]},
        {"metric": "counted (has qty)", "value": p["counted"]},
        {"metric": "manual items", "value": p["manual"]},
        {"metric": "counters", "value": ", ".join(p["counters"])},
    ]
    return respond(request, p, title="Stocktake · الجرد", rows=rows, columns=["metric", "value"])


@router.get("/counts")
async def counts(request: Request, inv: InventoryConnector = Depends(get_inv)):
    """Items that have a counted quantity."""
    p = await inv.progress()
    return respond(request, {"count": p["counted"], "records": p["counted_items"]},
                   title="Stocktake counts", rows=p["counted_items"], columns=["code", "q", "u", "counter", "zone"])


@router.get("/manual")
async def manual(request: Request, inv: InventoryConnector = Depends(get_inv)):
    """Manually-added items (built via the unified code builder)."""
    p = await inv.progress()
    return respond(request, {"count": p["manual"], "records": p["manual_items"]},
                   title="Stocktake manual items", rows=p["manual_items"],
                   columns=["newCode", "name", "q", "u", "counter"])
