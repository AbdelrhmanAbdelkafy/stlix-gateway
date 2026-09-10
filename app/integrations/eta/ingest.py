"""What a browser agent scrapes off the portal, in the shape the planner reads.

The owner does not want a registered system, so there are no API credentials
and nothing can be pulled server-side. A browser on his own machine, signed in
as him, reads the portal's own pages and pushes the rows here — the same
reversed direction the CCTV agent uses, and for the same reason: the credential
stays where the person is.

Everything downstream (`vat.engine`, the planner screen, the watcher) reads the
same cache either way, so the routine does not care which door the documents
came through. What it does care about is not being lied to: a scraped row that
carries no VAT figure is stored as *unknown* rather than as zero, and the
engine estimates it and says so.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ...config import Settings, get_settings
from . import store

router = APIRouter(prefix="/eta", tags=["eta"])

_NUM = re.compile(r"-?[\d,]+(?:\.\d+)?")
_STATUS = {
    "valid": "valid", "صالحة": "valid", "مقبولة": "valid",
    "invalid": "invalid", "غير صالحة": "invalid", "مرفوضة من المنظومة": "invalid",
    "submitted": "submitted", "تم الإرسال": "submitted", "قيد المراجعة": "submitted",
    "cancelled": "cancelled", "ملغاة": "cancelled", "ملغية": "cancelled",
    "rejected": "rejected", "مرفوضة": "rejected",
}
_TYPE = {"i": "I", "invoice": "I", "فاتورة": "I", "c": "C", "credit": "C", "إشعار خصم": "C",
         "d": "D", "debit": "D", "إشعار إضافة": "D"}


def agent_auth(x_eta_browser_key: str | None = Header(default=None),
               x_api_key: str | None = Header(default=None),
               settings: Settings = Depends(get_settings)) -> None:
    """The browser agent's own key — it may write documents and nothing else."""
    if settings.eta_browser_key and x_eta_browser_key == settings.eta_browser_key:
        return
    if x_api_key and x_api_key in settings.api_keys:
        return
    if not settings.eta_browser_key and not settings.api_keys:
        return
    raise HTTPException(status_code=401, detail="browser agent key required")


def num(value) -> float | None:
    """'1,234.50 EGP' -> 1234.5 ; '' -> None. Never guess a zero."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUM.search(str(value).replace("٬", ",").replace("٫", "."))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _status(value) -> str:
    v = str(value or "").strip().lower()
    return _STATUS.get(v, _STATUS.get(v.replace("ة", "ه"), v or "valid"))


def _iso(value) -> str | None:
    """The portal writes dates in a few shapes; keep only what parses."""
    s = str(value or "").strip()
    if not s:
        return None
    s = s.replace("/", "-")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:len(fmt) + 2].strip(), fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return s if re.match(r"^\d{4}-\d{2}-\d{2}", s) else None


def _uuid(row: dict, direction: str, issued: str | None) -> str:
    """The list page does not always expose the real uuid. A stable synthetic one
    keeps re-scrapes idempotent instead of duplicating the month every run."""
    real = str(row.get("uuid") or row.get("electronicNumber") or "").strip()
    if real:
        return re.sub(r"[^A-Za-z0-9_.-]", "", real)[:64]
    seed = "|".join([str(row.get("internal_id") or row.get("internalId") or ""), direction,
                     issued or "", str(num(row.get("total")) or "")])
    return "scr-" + hashlib.sha1(seed.encode()).hexdigest()[:24]


def normalise(row: dict) -> dict:
    """One scraped row -> one document in the cache's own shape."""
    direction = str(row.get("direction") or "").strip().title()
    if direction not in ("Sent", "Received"):
        direction = "Sent" if str(row.get("direction") or "").strip() in ("مرسلة", "صادرة") else "Received"
    issued = _iso(row.get("issued_at") or row.get("dateTimeIssued") or row.get("date"))
    net, total, vat = num(row.get("net")), num(row.get("total")), num(row.get("vat"))
    if net is None and total is not None and vat is not None:
        net = round(total - vat, 2)
    if total is None and net is not None and vat is not None:
        total = round(net + vat, 2)
    t = str(row.get("doc_type") or row.get("typeName") or "I").strip().lower()
    out = {
        "uuid": _uuid(row, direction, issued), "direction": direction,
        "typeName": _TYPE.get(t, t.upper()[:3] or "I"), "status": _status(row.get("status")),
        "internalId": row.get("internal_id") or row.get("internalId"),
        "issuerId": row.get("issuer_id") or row.get("issuerId"),
        "issuerName": row.get("issuer_name") or row.get("issuerName"),
        "receiverId": row.get("receiver_id") or row.get("receiverId"),
        "receiverName": row.get("receiver_name") or row.get("receiverName"),
        "dateTimeIssued": issued, "dateTimeReceived": _iso(row.get("received_at")),
        "netAmount": net, "totalSales": num(row.get("total_sales")) or net, "total": total,
        "documentStatusReason": row.get("reason"),
    }
    if vat is not None:          # only a figure the page actually showed
        out["vat"] = vat
    if row.get("lines"):
        out["lines"] = [{"item_code": ln.get("item_code") or ln.get("code"),
                         "internal_code": ln.get("internal_code"),
                         "description": str(ln.get("description") or "")[:120],
                         "qty": ln.get("qty"), "net": num(ln.get("net")) or 0.0,
                         "vat": num(ln.get("vat")) or 0.0} for ln in row["lines"]]
    return out


@router.post("/{entity}/ingest", dependencies=[Depends(agent_auth)])
async def ingest(entity: str, request: Request, settings: Settings = Depends(get_settings)):
    """Body: {"documents": [ …scraped rows… ], "source": "browser"}.

    Idempotent: the same row scraped twice updates, never duplicates. Rows the
    page could not date are refused rather than filed under the wrong month.
    """
    try:
        store.entity(entity, settings)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown entity {entity}")
    body = await request.json()
    rows = body.get("documents")
    if not isinstance(rows, list):
        return JSONResponse({"error": "documents (list) مطلوبة"}, status_code=400)
    docs, skipped = [], []
    for r in rows:
        if not isinstance(r, dict):
            skipped.append("not an object")
            continue
        d = normalise(r)
        if not d["dateTimeIssued"]:
            skipped.append(str(d.get("internalId") or d["uuid"])[:40])
            continue
        docs.append(d)
    n = store.upsert(entity, docs, settings)
    months = sorted({d["dateTimeIssued"][:7] for d in docs})
    for m in months:
        store._mark(entity, m, True, None, sum(1 for d in docs if d["dateTimeIssued"][:7] == m), settings)
    return {"ok": True, "stored": n, "months": months, "skipped": skipped[:20],
            "skipped_count": len(skipped), "source": str(body.get("source") or "browser")}
