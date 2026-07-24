from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    tax_id: str | None = None
    email: str | None = None
    erp_ref: str | None = None


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tax_id: str | None = None
    email: str | None = None
    erp_ref: str | None = None
    is_active: bool
