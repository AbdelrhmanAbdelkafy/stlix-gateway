"""CRM (Vtiger) read endpoints - HTML or JSON."""
from fastapi import APIRouter, Depends, Query, Request

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from .connector import CrmConnector

router = APIRouter(prefix="/crm", tags=["crm"], dependencies=[Depends(require_api_key)])

# Curated columns for common modules (missing fields render as "—").
_COLS = {
    "Contacts": ["id", "firstname", "lastname", "email", "phone", "account_id"],
    "Leads": ["id", "firstname", "lastname", "company", "leadstatus", "email"],
    "Accounts": ["id", "accountname", "phone", "email1", "industry"],
}


def get_crm(settings: Settings = Depends(get_settings)) -> CrmConnector:
    return CrmConnector(settings)


@router.get("")
async def crm_info(request: Request, settings: Settings = Depends(get_settings)):
    """Connector status (no upstream call)."""
    data = {
        "connector": "crm",
        "backend": settings.crm_backend,
        "configured": settings.crm_configured,
        "mode": settings.crm_mode,
    }
    rows = [{"field": k, "value": v} for k, v in data.items()]
    return respond(request, data, title="CRM", rows=rows, columns=["field", "value"])


@router.get("/contacts")
async def contacts(request: Request, limit: int = Query(20, ge=1, le=200), crm: CrmConnector = Depends(get_crm)):
    rows = await crm.query("Contacts", limit=limit)
    return respond(request, {"module": "Contacts", "count": len(rows), "records": rows},
                   title="CRM · Contacts", rows=rows, columns=_COLS["Contacts"])


@router.get("/leads")
async def leads(request: Request, limit: int = Query(20, ge=1, le=200), crm: CrmConnector = Depends(get_crm)):
    rows = await crm.query("Leads", limit=limit)
    return respond(request, {"module": "Leads", "count": len(rows), "records": rows},
                   title="CRM · Leads", rows=rows, columns=_COLS["Leads"])


@router.get("/accounts")
async def accounts(request: Request, limit: int = Query(20, ge=1, le=200), crm: CrmConnector = Depends(get_crm)):
    rows = await crm.query("Accounts", limit=limit)
    return respond(request, {"module": "Accounts", "count": len(rows), "records": rows},
                   title="CRM · Accounts", rows=rows, columns=_COLS["Accounts"])


@router.get("/{module}")
async def module_query(
    request: Request,
    module: str,
    limit: int = Query(20, ge=1, le=200),
    crm: CrmConnector = Depends(get_crm),
):
    """Generic read for any Vtiger module (e.g. CTAttendance)."""
    rows = await crm.query(module, limit=limit)
    cols = _COLS.get(module)
    return respond(request, {"module": module, "count": len(rows), "records": rows},
                   title=f"CRM · {module}", rows=rows, columns=cols)
