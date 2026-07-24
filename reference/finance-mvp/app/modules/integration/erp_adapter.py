"""ERP integration adapter (Chapters 44-45).

CONSTITUTIONAL GUARANTEE:
- The ERP is the System of Record.
- AI agents and services NEVER call `post_invoice` directly. The ONLY caller is
  the invoice workflow, and only AFTER a human with `invoice:post` authority has
  approved+posted the invoice. Write credentials live here, in the integration
  layer, never in the AI layer.
- Reads are unrestricted; writes are workflow-gated and idempotent.

This MVP uses an in-memory mock ERP so the platform runs end-to-end without a
real ERP. Swapping in a real ERP means implementing this one interface.
"""
from __future__ import annotations

import hashlib

from app.core.logging_config import logger

# Mock ERP "posted documents" keyed by an idempotency key so re-posting the same
# invoice never creates a duplicate ERP document.
_ERP_DOCUMENTS: dict[str, str] = {}


def get_vendor_balance(erp_ref: str | None) -> dict:
    """Read-only lookup against the ERP (System of Record)."""
    # Deterministic mock value derived from the reference.
    base = int(hashlib.sha256((erp_ref or "unknown").encode()).hexdigest(), 16) % 100000
    return {"erp_ref": erp_ref, "open_balance": round(base / 100, 2), "currency": "USD", "source": "ERP"}


def post_invoice(*, invoice_number: str, vendor_erp_ref: str | None, amount: str, currency: str) -> str:
    """Post an APPROVED invoice to the ERP and return the ERP document id.

    Idempotent: the same invoice_number+vendor yields the same ERP document id.
    MUST only be invoked by the workflow layer after human approval.
    """
    idem_key = f"{vendor_erp_ref or 'NA'}:{invoice_number}"
    if idem_key in _ERP_DOCUMENTS:
        logger.info("ERP post idempotent-hit key=%s", idem_key)
        return _ERP_DOCUMENTS[idem_key]

    doc_id = "ERP-" + hashlib.sha1(f"{idem_key}:{amount}:{currency}".encode()).hexdigest()[:12].upper()
    _ERP_DOCUMENTS[idem_key] = doc_id
    logger.info("ERP post created doc=%s key=%s amount=%s %s", doc_id, idem_key, amount, currency)
    return doc_id
