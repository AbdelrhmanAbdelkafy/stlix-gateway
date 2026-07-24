"""Integration read endpoints (Chapter 45). Read-only ERP access."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import rbac
from app.core.database import get_db
from app.core.rbac import require_permission
from app.models.user import User
from app.models.vendor import Vendor
from app.modules.integration import erp_adapter

router = APIRouter(prefix="/erp", tags=["integration"])


@router.get("/vendors/{vendor_id}/balance")
def vendor_balance(
    vendor_id: int,
    _: User = Depends(require_permission(rbac.P_VENDOR_READ)),
    db: Session = Depends(get_db),
):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    # Read-only lookup against the System of Record.
    return erp_adapter.get_vendor_balance(vendor.erp_ref)
