"""Client-facing shapes use ISO dates/times; converted to Nama formats on save."""
from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field


def to_nama_date(d: date) -> str:
    """date -> 'DD-MM-YYYY' (Nama's required format)."""
    return d.strftime("%d-%m-%Y")


def to_nama_time(t: time) -> str:
    """time -> 'HH:MM'."""
    return t.strftime("%H:%M")


class AttendancePunch(BaseModel):
    employee: str = Field(..., description="Nama employee CODE, e.g. E000001")
    day: date = Field(..., description="Work day (ISO YYYY-MM-DD).")
    check_in: time = Field(..., description="Check-in (HH:MM).")
    check_out: time | None = Field(default=None, description="Check-out (HH:MM).")

    def to_nama_line(self) -> dict:
        line = {
            "employee": self.employee,
            "fromDate": to_nama_date(self.day),
            "fromTime": to_nama_time(self.check_in),
        }
        if self.check_out is not None:
            line["toDate"] = to_nama_date(self.day)
            line["toTime"] = to_nama_time(self.check_out)
        return line


class AttendanceBatch(BaseModel):
    punches: list[AttendancePunch] = Field(..., min_length=1)

    def to_time_attendance(self) -> dict:
        return {"attendanceLines": [p.to_nama_line() for p in self.punches]}


class SaveResult(BaseModel):
    saved: int
    code: str | None = None
    raw: dict
