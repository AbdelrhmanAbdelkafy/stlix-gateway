from fastapi import APIRouter, Depends, Query

from ...config import Settings, get_settings
from ...core.security import require_api_key
from .client import NamaClient

router = APIRouter(prefix="/nama", tags=["nama"], dependencies=[Depends(require_api_key)])


def get_nama(settings: Settings = Depends(get_settings)) -> NamaClient:
    return NamaClient(settings)


@router.get("/employees")
async def list_employees(
    max_records: int = Query(default=25, ge=1, le=500),
    nama: NamaClient = Depends(get_nama),
) -> dict:
    return await nama.list("Employee", max_records=max_records)


@router.get("/employees/{code}")
async def get_employee(code: str, nama: NamaClient = Depends(get_nama)) -> dict:
    return await nama.find("Employee", code)


@router.get("/{entity}/{code}")
async def get_entity(entity: str, code: str, nama: NamaClient = Depends(get_nama)) -> dict:
    """Generic passthrough read for any Nama entity by id/code."""
    return await nama.find(entity, code)
