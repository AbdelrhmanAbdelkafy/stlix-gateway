"""Banks read endpoints (Nama-backed) - HTML or JSON."""
from fastapi import APIRouter, Depends, Query, Request

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from .connector import BanksConnector

router = APIRouter(prefix="/banks", tags=["banks"], dependencies=[Depends(require_api_key)])


def get_banks(settings: Settings = Depends(get_settings)) -> BanksConnector:
    return BanksConnector(settings)


@router.get("")
async def bank_accounts(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    banks: BanksConnector = Depends(get_banks),
):
    """Bank accounts enriched with bank name, GL account, currency."""
    rows = await banks.accounts(limit=limit)
    return respond(
        request, {"count": len(rows), "records": rows}, title="Bank Accounts",
        rows=rows, columns=["code", "name1", "_bankName", "_glAccount", "_currency"],
    )


@router.get("/master")
async def bank_master(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    banks: BanksConnector = Depends(get_banks),
):
    """Bank master list."""
    rows = await banks.banks(limit=limit)
    return respond(
        request, {"count": len(rows), "records": rows}, title="Banks",
        rows=rows, columns=["code", "name1", "name2"],
    )
