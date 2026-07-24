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


@router.get("/{entity}/{code}")
async def get_entity(request: Request, entity: str, code: str, nama: NamaConnector = Depends(get_nama)):
    """Generic passthrough read for any Nama entity by id/code."""
    data = await nama.find(entity, code)
    return respond(request, data, title=f"{entity} {code}")
