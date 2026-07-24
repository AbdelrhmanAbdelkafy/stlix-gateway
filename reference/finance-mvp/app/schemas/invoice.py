from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=64)
    vendor_id: int
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=512)


class WorkflowAction(BaseModel):
    reason: str | None = Field(default=None, max_length=512)


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    vendor_id: int
    amount: Decimal
    currency: str
    description: str | None = None
    status: str
    submitted_by: int | None = None
    approved_by: int | None = None
    rejected_by: int | None = None
    posted_by: int | None = None
    erp_document_id: str | None = None
    created_by: int | None = None
