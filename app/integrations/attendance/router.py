"""Attendance / fingerprint - currently routes to Nama TimeAttendance."""
from fastapi import APIRouter, Depends, status

from ...config import Settings, get_settings
from ...core.security import require_api_key
from ..nama.client import NamaClient
from ..nama.schemas import AttendanceBatch, SaveResult

router = APIRouter(
    prefix="/attendance", tags=["attendance"], dependencies=[Depends(require_api_key)]
)


def get_nama(settings: Settings = Depends(get_settings)) -> NamaClient:
    return NamaClient(settings)


@router.post("/punch", response_model=SaveResult, status_code=status.HTTP_201_CREATED)
async def push_attendance(batch: AttendanceBatch, nama: NamaClient = Depends(get_nama)) -> SaveResult:
    """Push punches as one Nama TimeAttendance document.

    Client sends ISO dates/times; gateway converts to Nama DD-MM-YYYY / HH:MM.
    """
    raw = await nama.save("TimeAttendance", batch.to_time_attendance())
    code = None
    ids = raw.get("saved_ids") or raw.get("savedIds")
    if isinstance(ids, list) and ids:
        first = ids[0]
        code = first.get("code") if isinstance(first, dict) else str(first)
    return SaveResult(saved=int(raw.get("saved_records_count", 0)), code=code, raw=raw)
