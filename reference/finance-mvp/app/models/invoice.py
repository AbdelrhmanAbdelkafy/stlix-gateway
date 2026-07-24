from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class InvoiceStatus:
    """Workflow states (Chapter 58: Workflow Engine)."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POSTED = "POSTED"

    ALL = {DRAFT, SUBMITTED, APPROVED, REJECTED, POSTED}


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=InvoiceStatus.DRAFT, nullable=False, index=True)

    # SoD actor trail
    submitted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Set only after the approved workflow posts to the ERP (System of Record).
    erp_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
