"""Finance module: vendors + AP invoice lifecycle (Chapters 60, 64)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import rbac
from app.core.audit import record_action
from app.core.database import get_db
from app.core.rbac import require_permission
from app.models.invoice import Invoice
from app.models.user import User
from app.models.vendor import Vendor
from app.modules.finance import workflow
from app.modules.finance.workflow import WorkflowError
from app.schemas.invoice import InvoiceCreate, InvoiceOut, WorkflowAction
from app.schemas.vendor import VendorCreate, VendorOut

router = APIRouter(tags=["finance"])


# ------------------------- Vendors -------------------------
@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(
    _: User = Depends(require_permission(rbac.P_VENDOR_READ)),
    db: Session = Depends(get_db),
):
    return db.query(Vendor).order_by(Vendor.id).all()


@router.post("/vendors", response_model=VendorOut, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    actor: User = Depends(require_permission(rbac.P_VENDOR_WRITE)),
    db: Session = Depends(get_db),
):
    vendor = Vendor(**payload.model_dump(), created_by=actor.id)
    db.add(vendor)
    db.flush()
    record_action(db, actor=actor, action="vendor.create", entity_type="vendor",
                  entity_id=vendor.id, after={"name": vendor.name})
    db.commit()
    db.refresh(vendor)
    return vendor


# ------------------------- Invoices -------------------------
def _get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(
    _: User = Depends(require_permission(rbac.P_INVOICE_READ)),
    db: Session = Depends(get_db),
):
    return db.query(Invoice).order_by(Invoice.id).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    _: User = Depends(require_permission(rbac.P_INVOICE_READ)),
    db: Session = Depends(get_db),
):
    return _get_invoice(db, invoice_id)


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    actor: User = Depends(require_permission(rbac.P_INVOICE_CREATE)),
    db: Session = Depends(get_db),
):
    if db.get(Vendor, payload.vendor_id) is None:
        raise HTTPException(status_code=400, detail="Vendor does not exist")
    invoice = Invoice(**payload.model_dump(), created_by=actor.id)
    db.add(invoice)
    db.flush()
    record_action(db, actor=actor, action="invoice.create", entity_type="invoice",
                  entity_id=invoice.id, after={"invoice_number": invoice.invoice_number,
                                               "amount": str(invoice.amount)})
    db.commit()
    db.refresh(invoice)
    return invoice


def _run(db: Session, invoice: Invoice) -> Invoice:
    try:
        db.commit()
    except Exception:  # pragma: no cover
        db.rollback()
        raise
    db.refresh(invoice)
    return invoice


@router.post("/invoices/{invoice_id}/submit", response_model=InvoiceOut)
def submit_invoice(
    invoice_id: int,
    body: WorkflowAction = WorkflowAction(),
    actor: User = Depends(require_permission(rbac.P_INVOICE_SUBMIT)),
    db: Session = Depends(get_db),
):
    invoice = _get_invoice(db, invoice_id)
    try:
        workflow.submit(db, invoice, actor, body.reason)
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _run(db, invoice)


@router.post("/invoices/{invoice_id}/approve", response_model=InvoiceOut)
def approve_invoice(
    invoice_id: int,
    body: WorkflowAction = WorkflowAction(),
    actor: User = Depends(require_permission(rbac.P_INVOICE_APPROVE)),
    db: Session = Depends(get_db),
):
    invoice = _get_invoice(db, invoice_id)
    try:
        workflow.approve(db, invoice, actor, body.reason)
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _run(db, invoice)


@router.post("/invoices/{invoice_id}/reject", response_model=InvoiceOut)
def reject_invoice(
    invoice_id: int,
    body: WorkflowAction = WorkflowAction(),
    actor: User = Depends(require_permission(rbac.P_INVOICE_APPROVE)),
    db: Session = Depends(get_db),
):
    invoice = _get_invoice(db, invoice_id)
    try:
        workflow.reject(db, invoice, actor, body.reason)
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _run(db, invoice)


@router.post("/invoices/{invoice_id}/post", response_model=InvoiceOut)
def post_invoice(
    invoice_id: int,
    body: WorkflowAction = WorkflowAction(),
    actor: User = Depends(require_permission(rbac.P_INVOICE_POST)),
    db: Session = Depends(get_db),
):
    invoice = _get_invoice(db, invoice_id)
    vendor = db.get(Vendor, invoice.vendor_id)
    try:
        workflow.post_to_erp(db, invoice, actor, vendor.erp_ref if vendor else None, body.reason)
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _run(db, invoice)
