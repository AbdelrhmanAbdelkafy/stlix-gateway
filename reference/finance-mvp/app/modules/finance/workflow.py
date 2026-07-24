"""Invoice workflow state machine (Chapters 58-59 + Constitution).

Enforces:
- Valid state transitions only.
- Segregation of Duties: the approver cannot be the creator.
- ERP posting happens ONLY here, only for APPROVED invoices, only via the
  integration adapter — never a direct write elsewhere.
- Every transition writes an append-only audit record.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import record_action
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.modules.integration import erp_adapter


class WorkflowError(Exception):
    """Raised on an illegal transition or a policy violation (mapped to HTTP 409)."""


def _guard(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowError(message)


def submit(db: Session, invoice: Invoice, actor: User, reason: str | None = None) -> Invoice:
    _guard(invoice.status == InvoiceStatus.DRAFT, f"Cannot submit an invoice in status {invoice.status}")
    before = invoice.status
    invoice.status = InvoiceStatus.SUBMITTED
    invoice.submitted_by = actor.id
    invoice.updated_by = actor.id
    record_action(db, actor=actor, action="invoice.submit", entity_type="invoice",
                  entity_id=invoice.id, reason=reason,
                  before={"status": before}, after={"status": invoice.status})
    return invoice


def approve(db: Session, invoice: Invoice, actor: User, reason: str | None = None) -> Invoice:
    _guard(invoice.status == InvoiceStatus.SUBMITTED, f"Cannot approve an invoice in status {invoice.status}")
    # Segregation of Duties.
    _guard(invoice.created_by != actor.id, "Segregation of Duties: the creator cannot approve their own invoice")
    before = invoice.status
    invoice.status = InvoiceStatus.APPROVED
    invoice.approved_by = actor.id
    invoice.updated_by = actor.id
    record_action(db, actor=actor, action="invoice.approve", entity_type="invoice",
                  entity_id=invoice.id, reason=reason,
                  before={"status": before}, after={"status": invoice.status})
    return invoice


def reject(db: Session, invoice: Invoice, actor: User, reason: str | None = None) -> Invoice:
    _guard(invoice.status == InvoiceStatus.SUBMITTED, f"Cannot reject an invoice in status {invoice.status}")
    before = invoice.status
    invoice.status = InvoiceStatus.REJECTED
    invoice.rejected_by = actor.id
    invoice.updated_by = actor.id
    record_action(db, actor=actor, action="invoice.reject", entity_type="invoice",
                  entity_id=invoice.id, reason=reason,
                  before={"status": before}, after={"status": invoice.status})
    return invoice


def post_to_erp(db: Session, invoice: Invoice, actor: User, vendor_erp_ref: str | None,
                reason: str | None = None) -> Invoice:
    _guard(invoice.status == InvoiceStatus.APPROVED, f"Only APPROVED invoices can be posted (status={invoice.status})")
    # The single, workflow-gated write path to the ERP (System of Record).
    doc_id = erp_adapter.post_invoice(
        invoice_number=invoice.invoice_number,
        vendor_erp_ref=vendor_erp_ref,
        amount=str(invoice.amount),
        currency=invoice.currency,
    )
    before = invoice.status
    invoice.status = InvoiceStatus.POSTED
    invoice.posted_by = actor.id
    invoice.erp_document_id = doc_id
    invoice.updated_by = actor.id
    record_action(db, actor=actor, action="invoice.post", entity_type="invoice",
                  entity_id=invoice.id, reason=reason,
                  before={"status": before}, after={"status": invoice.status, "erp_document_id": doc_id})
    return invoice
