"""Finance read endpoints — customer / supplier balances.

Two sources answer the same three questions and say which one they are:

* `?source=sql` — the restored Nama database. Complete, and as old as the last
  restore.
* `?source=live` — rebuilt from live Nama REST documents. Current to the minute,
  but only as of the last snapshot sweep, and it carries the list of documents
  the API credential is not allowed to read.

Omitting `source` uses `FINANCE_DEFAULT_SOURCE` (ships as `sql`). The default is
config rather than a constant so the platform moves onto live figures the moment
`scripts/reconcile_live_vs_sql.py` passes — and moves back just as fast.

Neither is silently preferred. `freshness` travels on every response so a figure
can never be shown without its age.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from .connector import FinanceConnector
from .live import LiveFinance

router = APIRouter(prefix="/finance", tags=["finance"], dependencies=[Depends(require_api_key)])


def get_finance(settings: Settings = Depends(get_settings)) -> FinanceConnector:
    return FinanceConnector(settings)


def get_live(settings: Settings = Depends(get_settings)) -> LiveFinance:
    return LiveFinance(settings)


SOURCE = Query(None, pattern="^(sql|live)$",
               description="sql = restored backup (complete); live = swept from Nama REST now. "
                           "Omit to use FINANCE_DEFAULT_SOURCE.")


def _source(explicit: str | None, settings: Settings) -> str:
    """Which source answers this request.

    The default is configuration, not a constant, so moving the whole platform
    onto live figures is one env var once the reconciliation script passes —
    and moving back is the same one env var if a sweep ever looks wrong.
    """
    return explicit or settings.finance_default_source


@router.get("/live")
async def live_status(request: Request, live: LiveFinance = Depends(get_live)):
    """Is there a live snapshot, how old is it, and what did the sweep miss?"""
    snap = LiveFinance.snapshot()
    data = {"freshness": LiveFinance.freshness(),
            "swept": (snap or {}).get("swept"),
            "excludes": (snap or {}).get("excludes")}
    return respond(request, data, title="Live finance snapshot",
                   rows=[{"field": k, "value": v} for k, v in data["freshness"].items()],
                   columns=["field", "value"])


@router.post("/live/refresh")
async def refresh_live(background: BackgroundTasks, live: LiveFinance = Depends(get_live)):
    """Start a live sweep in the background.

    Deliberately a POST that returns immediately: the sweep is ~14,000 documents
    over ~8 minutes, so holding a request open for it would just time out. Only
    Nama `/list` is called — nothing is written.
    """
    if not live.configured:
        return {"started": False, "reason": "Nama REST not configured."}
    if LiveFinance._building:
        return {"started": False, "reason": "a sweep is already running",
                "freshness": LiveFinance.freshness()}
    background.add_task(live.refresh)
    return {"started": True, "note": "sweep takes several minutes; poll /api/v1/finance/live"}


@router.get("/kpis")
async def kpis(request: Request, source: str | None = SOURCE,
               settings: Settings = Depends(get_settings),
               fin: FinanceConnector = Depends(get_finance),
               live: LiveFinance = Depends(get_live)):
    """Company financial KPIs — from the restored DB, or live from Nama REST."""
    data = live.kpis() if _source(source, settings) == "live" else await fin.kpis()
    rows = [{"metric": k, "value": v} for k, v in data.items() if k not in ("available", "source")]
    return respond(request, data, title="Finance KPIs", rows=rows, columns=["metric", "value"])


@router.get("/customers")
async def customer_balances(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    source: str | None = SOURCE,
    settings: Settings = Depends(get_settings),
    fin: FinanceConnector = Depends(get_finance),
    live: LiveFinance = Depends(get_live),
):
    """Customer balances (AR)."""
    data = live.customer_balances(limit=limit) if _source(source, settings) == "live" \
        else await fin.customer_balances(limit=limit)
    return respond(request, data, title="Customer Balances", rows=data.get("records", []),
                   columns=["code", "name1", "outstanding", "invoicedNet", "collected",
                            "salesTotal", "lastInvoiceDate"])


@router.get("/suppliers")
async def supplier_balances(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    source: str | None = SOURCE,
    settings: Settings = Depends(get_settings),
    fin: FinanceConnector = Depends(get_finance),
    live: LiveFinance = Depends(get_live),
):
    """Supplier balances (AP)."""
    data = live.supplier_balances(limit=limit) if _source(source, settings) == "live" \
        else await fin.supplier_balances(limit=limit)
    return respond(request, data, title="Supplier Balances", rows=data.get("records", []),
                   columns=["code", "name1", "outstanding", "invoicedNet", "paid",
                            "purchaseTotal", "lastInvoiceDate"])
