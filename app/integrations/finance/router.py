"""Finance read endpoints — customer / supplier balances (Nama report-backed)."""
from fastapi import APIRouter, Depends, Query, Request

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from .connector import FinanceConnector

router = APIRouter(prefix="/finance", tags=["finance"], dependencies=[Depends(require_api_key)])


def get_finance(settings: Settings = Depends(get_settings)) -> FinanceConnector:
    return FinanceConnector(settings)


@router.get("/kpis")
async def kpis(request: Request, fin: FinanceConnector = Depends(get_finance)):
    """Company financial KPIs (real, from the Nama SQL DB)."""
    data = await fin.kpis()
    rows = [{"metric": k, "value": v} for k, v in data.items() if k not in ("available", "source")]
    return respond(request, data, title="Finance KPIs", rows=rows, columns=["metric", "value"])


@router.get("/customers")
async def customer_balances(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    fin: FinanceConnector = Depends(get_finance),
):
    """Real customer balances (AR) from the Nama SQL DB."""
    data = await fin.customer_balances(limit=limit)
    return respond(request, data, title="Customer Balances", rows=data.get("records", []),
                   columns=["code", "name1", "outstanding", "salesTotal", "collected", "lastInvoiceDate"])


@router.get("/suppliers")
async def supplier_balances(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    fin: FinanceConnector = Depends(get_finance),
):
    """Live supplier balances from a Nama report entity (pending Namasoft publish)."""
    data = await fin.supplier_balances(limit=limit)
    return respond(request, data, title="Supplier Balances", rows=data.get("records", []),
                   columns=["code", "name1", "outstanding", "purchaseTotal", "paid", "lastInvoiceDate"])
