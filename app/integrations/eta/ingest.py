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


#: The portal puts an icon glyph in the same cell as the word ("\ue930 Valid"),
#: and those live in the private-use area, so they are stripped before matching
#: rather than turning a perfectly valid invoice into an unknown status.
_GLYPHS = re.compile(r"[\u0000-\u001f\ue000-\uf8ff\ufe00-\ufe0f\u200b-\u200f]+")


def clean(value) -> str:
    return re.sub(r"\s+", " ", _GLYPHS.sub(" ", str(value or ""))).strip()


def _status(value) -> str:
    v = clean(value).lower()
    if v in _STATUS:
        return _STATUS[v]
    if v.replace("ة", "ه") in _STATUS:
        return _STATUS[v.replace("ة", "ه")]
    # "invalid" contains "valid", so the longest name wins.
    for name in sorted(_STATUS, key=len, reverse=True):
        if name in v:
            return _STATUS[name]
    return v or "valid"


def _iso(value) -> str | None:
    """The portal writes dates in a few shapes; keep only what parses.

    The document grid says `8/9/2026 9:57 AM` — day first, 12-hour clock — so
    trailing pieces are trimmed one token at a time until something parses,
    rather than guessing at a fixed width.
    """
    s = re.sub(r"\s+", " ", str(value or "").replace("/", "-").strip())
    if not s:
        return None
    tokens = s.split(" ")
    for n in range(len(tokens), 0, -1):
        candidate = " ".join(tokens[:n])
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                    "%d-%m-%Y %I:%M %p", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                return datetime.strptime(candidate, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
    return s if re.match(r"^\d{4}-\d{2}-\d{2}", s) else None


# --- the portal's own document grid -------------------------------------------------
#
# The list page is an Angular grid, not a <table>, and it carries no export
# button, so the agent hands over whatever headers and cells it could read and
# the mapping lives here — in the repo, under test — rather than in the browser
# on the server. Its columns (English UI) are:
#
#   ID / Internal ID · Date Time Received · Type / Version · Total Value (EGP)
#   Issuer (From) · Receiver (To) · Submission · Status
#
# Several of those are two facts in one cell, which is why the splitting below
# is deliberate rather than a `split()[0]` guess.

_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ids", ("internal id", "الرقم الداخلي", "رقم المستند")),
    ("date", ("date time", "date", "التاريخ", "تاريخ")),
    ("type", ("type", "النوع", "نوع المستند")),
    ("total", ("total value", "total", "الإجمالي", "القيمة الإجمالية", "اجمالي")),
    ("vat", ("vat", "tax", "ض.ق.م", "ضريبة القيمة المضافة", "الضريبة")),
    ("net", ("net", "الصافي", "القيمة الصافية")),
    ("issuer", ("issuer", "from", "المرسل", "البائع", "جهة الإصدار")),
    ("receiver", ("receiver", "to", "المستلم", "المشتري", "جهة الاستلام")),
    ("submission", ("submission", "الإرسال", "رقم الإرسال")),
    ("status", ("status", "الحالة")),
)
#: What the ETA grid shows, in order, when the headers could not be read.
_FALLBACK = ("ids", "date", "type", "total", "issuer", "receiver", "submission", "status")
_TRAILING_ID = re.compile(r"(\d{6,})\s*$")
_LONG_ID = re.compile(r"^[A-Z0-9]{16,}$", re.I)


def _col_key(header) -> str | None:
    h = re.sub(r"\s+", " ", str(header or "")).strip().lower()
    if not h:
        return None
    for key, needles in _COLUMNS:
        if any(n in h for n in needles):
            return key
    return "ids" if h.startswith("id") or h == "#" else None


def _split_ids(cell: str) -> tuple[str | None, str | None]:
    """'CKP4XT…ZW1M10 FA2609-4002' -> (uuid, internal id). Either may be absent."""
    parts = [p for p in re.split(r"\s+", clean(cell)) if p]
    uuid = next((p for p in parts if _LONG_ID.match(p)), None)
    rest = [p for p in parts if p != uuid]
    return uuid, (" ".join(rest) or None)


def _split_party(cell: str) -> tuple[str | None, str | None]:
    """'<اسم الشركة> 504685740' -> (name, registration number)."""
    text = clean(cell)
    m = _TRAILING_ID.search(text)
    if not m:
        return (text or None), None
    return (text[:m.start()].strip() or None), m.group(1)


def map_grid(headers, rows, rin: str | None = None) -> list[dict]:
    """The grid as the agent read it -> rows `normalise` understands.

    `rin` is our own registration number: it is what decides whether a document
    is a sale or a purchase, which the grid never states outright. Without it
    the direction is left unset rather than guessed.
    """
    keys = [_col_key(h) for h in (headers or [])]
    if not any(keys):
        keys = list(_FALLBACK)
    out: list[dict] = []
    for cells in rows or []:
        row: dict = {}
        for key, cell in zip(keys, cells):
            text = clean(cell)
            if not key or not text:
                continue
            if key == "ids":
                row["uuid"], row["internal_id"] = _split_ids(text)
            elif key == "date":
                row["received_at"] = text
            elif key == "type":
                row["doc_type"] = text.split()[0]
            elif key in ("issuer", "receiver"):
                row[f"{key}_name"], row[f"{key}_id"] = _split_party(text)
            elif key in ("total", "vat", "net"):
                row[key] = text
            elif key == "status":
                row["status"] = text
        if not row:
            continue
        # The grid dates by receipt; the issue date lives on the detail page. Use
        # receipt as the month, and say so, rather than dropping the document.
        row.setdefault("issued_at", row.get("received_at"))
        row["date_basis"] = "received"
        if rin:
            if str(row.get("issuer_id") or "") == str(rin):
                row["direction"] = "Sent"
            elif str(row.get("receiver_id") or "") == str(rin):
                row["direction"] = "Received"
        out.append(row)
    return out


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
        ent = store.entity(entity, settings)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown entity {entity}")
    body = await request.json()
    grid = body.get("grid")
    if isinstance(grid, dict):
        rows = map_grid(grid.get("headers"), grid.get("rows"), getattr(ent, "rin", None))
    else:
        rows = body.get("documents")
    if not isinstance(rows, list):
        return JSONResponse({"error": "documents (list) أو grid مطلوبة"}, status_code=400)
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
