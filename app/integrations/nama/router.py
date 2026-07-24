from fastapi import APIRouter, Depends, Query, Request

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from .connector import NamaConnector

router = APIRouter(prefix="/nama", tags=["nama"], dependencies=[Depends(require_api_key)])

# Columns surfaced in the HTML employee table (JSON always has the full record).
_EMP_COLS = ["code", "name1", "attendanceMachineCode", "jobTitle", "employeeState", "hiring"]


def get_nama(settings: Settings = Depends(get_settings)) -> NamaConnector:
    return NamaConnector(settings)


@router.get("/employees")
async def list_employees(
    request: Request,
    max_records: int = Query(default=25, ge=1, le=500),
    nama: NamaConnector = Depends(get_nama),
):
    data = await nama.list("Employee", max_records=max_records)
    rows = data.get("records", {}).get("Employee", [])
    return respond(request, data, title="Employees", rows=rows, columns=_EMP_COLS)


@router.get("/employees/{code}")
async def get_employee(request: Request, code: str, nama: NamaConnector = Depends(get_nama)):
    data = await nama.find("Employee", code)
    return respond(request, data, title=f"Employee {code}")


@router.get("/lists/{entity}")
async def list_entity(
    request: Request,
    entity: str,
    page_size: int = Query(default=300, ge=1, le=1000),
    nama: NamaConnector = Depends(get_nama),
):
    """Generic read of a Nama list entity (e.g. ItemClass3..10) — powers the
    item-builder's live attribute lists without exposing Nama creds to the browser."""
    data = await nama.list_query(entity, page_size=page_size)
    rows = data.get("records", {}).get(entity, [])
    return respond(request, {"entity": entity, "count": len(rows), "records": rows},
                   title=f"{entity}", rows=rows, columns=["code", "name1"])


@router.get("/invitem/exists")
async def invitem_exists(
    request: Request,
    description1: str = Query(..., description="Descriptive identity code to check for duplicates"),
    nama: NamaConnector = Depends(get_nama),
):
    """Duplicate check by identity code (`description1`). Read-only; the actual
    item WRITE stays gated behind a deliberate read_write workflow."""
    hit = await nama.find_first(
        "InvItem", text_criteria=f"description1,Equal,{description1},AND;"
    )
    payload = {
        "description1": description1,
        "exists": bool(hit),
        "item": {"code": hit.get("code"), "name1": hit.get("name1")} if hit else None,
    }
    return respond(request, payload, title="InvItem exists")


@router.get("/{entity}/{code}")
async def get_entity(request: Request, entity: str, code: str, nama: NamaConnector = Depends(get_nama)):
    """Generic passthrough read for any Nama entity by id/code."""
    data = await nama.find(entity, code)
    return respond(request, data, title=f"{entity} {code}")
