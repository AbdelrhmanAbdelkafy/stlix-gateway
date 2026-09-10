"""Local cache of portal documents + the entities' settings.

SQLite at `data/eta/eta.db`. `sync(entity, month)` pulls the month from the
portal and upserts; a document's status is *replaced* on every sync, so a
cancellation or rejection that happens on the portal shows up here on the
next pull without anyone re-checking on day 7.
"""
from __future__ import annotations

import calendar
import json
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path

import httpx

from ...config import Settings, get_settings
from .client import Entity, EtaClient, EtaError, lines_of, vat_of

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  entity TEXT NOT NULL, uuid TEXT NOT NULL, direction TEXT NOT NULL, doc_type TEXT NOT NULL,
  status TEXT NOT NULL, internal_id TEXT, issuer_id TEXT, issuer_name TEXT,
  receiver_id TEXT, receiver_name TEXT, issued_at TEXT, received_at TEXT,
  total_sales REAL, net REAL, total REAL, vat REAL, vat_known INTEGER DEFAULT 0,
  cancel_at TEXT, reject_at TEXT, reason TEXT, month TEXT, lines TEXT, raw TEXT, synced_at REAL,
  PRIMARY KEY (entity, uuid));
CREATE INDEX IF NOT EXISTS idx_docs_month ON documents(entity, month, direction, status);
CREATE TABLE IF NOT EXISTS syncs (
  entity TEXT NOT NULL, month TEXT NOT NULL, at REAL, ok INTEGER, error TEXT, count INTEGER,
  PRIMARY KEY (entity, month));
"""


def entities(settings: Settings | None = None) -> list[Entity]:
    settings = settings or get_settings()
    raw = settings.eta_entities_json.strip()
    if not raw:
        return []
    out = []
    for e in json.loads(raw):
        out.append(Entity(key=e["key"], name=e.get("name", e["key"]), rin=str(e.get("rin", "")),
                          client_id=e.get("client_id", ""), client_secret=e.get("client_secret", ""),
                          k_manufacturing=float(e.get("k_manufacturing", 0)),
                          k_trading=float(e.get("k_trading", 0)),
                          customs_issuer_ids=[str(x) for x in e.get("customs_issuer_ids", [])]))
    return out


def entity(key: str, settings: Settings | None = None) -> Entity:
    for e in entities(settings):
        if e.key == key:
            return e
    raise KeyError(key)


def db_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    p = Path(settings.eta_db_path) if settings.eta_db_path else _ROOT / "data" / "eta" / "eta.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _conn(settings: Settings | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(db_path(settings), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def month_bounds(month: str) -> tuple[date, date]:
    y, m = int(month[:4]), int(month[5:7])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def _month_of(iso: str | None) -> str:
    return (iso or "")[:7]


def upsert(entity_key: str, docs: list[dict], settings: Settings | None = None) -> int:
    now = time.time()
    with _LOCK, _conn(settings) as c:
        for d in docs:
            dt = (d.get("typeName") or d.get("documentType") or "I").upper()
            direction = d.get("direction") or ""
            c.execute("""INSERT INTO documents (entity, uuid, direction, doc_type, status, internal_id, issuer_id,
                issuer_name, receiver_id, receiver_name, issued_at, received_at, total_sales, net, total, vat,
                vat_known, cancel_at, reject_at, reason, month, lines, raw, synced_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(entity, uuid) DO UPDATE SET status=excluded.status, cancel_at=excluded.cancel_at,
                reject_at=excluded.reject_at, reason=excluded.reason, total_sales=excluded.total_sales,
                net=excluded.net, total=excluded.total, raw=excluded.raw, synced_at=excluded.synced_at,
                direction=CASE WHEN excluded.direction='' THEN documents.direction ELSE excluded.direction END,
                vat=CASE WHEN excluded.vat_known=1 THEN excluded.vat ELSE documents.vat END,
                vat_known=MAX(documents.vat_known, excluded.vat_known),
                lines=COALESCE(excluded.lines, documents.lines)""",
                      (entity_key, d["uuid"], direction, dt, (d.get("status") or "").lower(),
                       d.get("internalId"), d.get("issuerId"), d.get("issuerName"), d.get("receiverId"),
                       d.get("receiverName"), d.get("dateTimeIssued"), d.get("dateTimeReceived"),
                       _f(d.get("totalSales")), _f(d.get("netAmount")), _f(d.get("total")),
                       _f(d.get("vat")), 1 if d.get("vat") is not None else 0,
                       d.get("cancelRequestDate"), d.get("rejectRequestDate"), d.get("documentStatusReason"),
                       _month_of(d.get("dateTimeIssued")),
                       json.dumps(d["lines"], ensure_ascii=False) if d.get("lines") is not None else None,
                       json.dumps(d, ensure_ascii=False), now))
    return len(docs)


def _f(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


async def sync(entity_key: str, month: str, settings: Settings | None = None,
               with_details: bool = True, client_factory=None) -> dict:
    """Pull one month (both directions) for one entity into the cache."""
    settings = settings or get_settings()
    ent = entity(entity_key, settings)
    start, end = month_bounds(month)
    eta = (client_factory or EtaClient)(ent, settings.eta_env)
    docs: list[dict] = []
    try:
        async with httpx.AsyncClient() as http:
            for direction in ("Sent", "Received"):
                for d in await eta.search(http, issue_from=start, issue_to=end, direction=direction):
                    d["direction"] = direction
                    docs.append(d)
            if with_details:
                known = _known_vat(entity_key, settings)
                for d in docs:
                    if d["uuid"] in known and (d.get("status") or "").lower() == known[d["uuid"]]:
                        continue  # already have lines + VAT for this status
                    try:
                        det = await eta.details(http, d["uuid"])
                        d["vat"] = vat_of(det)
                        d["lines"] = lines_of(det)
                        doc = det.get("document") or {}
                        d.setdefault("activityCode", doc.get("taxpayerActivityCode"))
                    except EtaError:
                        pass
        n = upsert(entity_key, docs, settings)
        _mark(entity_key, month, True, None, n, settings)
        return {"ok": True, "entity": entity_key, "month": month, "documents": n}
    except (EtaError, httpx.HTTPError) as exc:
        _mark(entity_key, month, False, str(exc)[:300], 0, settings)
        return {"ok": False, "entity": entity_key, "month": month, "error": str(exc)[:300]}


def _known_vat(entity_key: str, settings: Settings | None) -> dict[str, str]:
    with _conn(settings) as c:
        return {r["uuid"]: r["status"] for r in
                c.execute("SELECT uuid, status FROM documents WHERE entity=? AND vat_known=1", (entity_key,))}


def _mark(entity_key: str, month: str, ok: bool, err: str | None, n: int, settings) -> None:
    with _LOCK, _conn(settings) as c:
        c.execute("INSERT OR REPLACE INTO syncs (entity, month, at, ok, error, count) VALUES (?,?,?,?,?,?)",
                  (entity_key, month, time.time(), int(ok), err, n))


def last_sync(entity_key: str, month: str, settings: Settings | None = None) -> dict | None:
    with _conn(settings) as c:
        r = c.execute("SELECT * FROM syncs WHERE entity=? AND month=?", (entity_key, month)).fetchone()
        return dict(r) if r else None


def documents(entity_key: str, month: str, direction: str | None = None, status: str | None = None,
              settings: Settings | None = None) -> list[dict]:
    q = "SELECT * FROM documents WHERE entity=? AND month=?"
    args: list = [entity_key, month]
    if direction:
        q += " AND direction=?"
        args.append(direction)
    if status:
        q += " AND status=?"
        args.append(status.lower())
    q += " ORDER BY issued_at"
    with _conn(settings) as c:
        rows = [dict(r) for r in c.execute(q, args)]
    for r in rows:
        r["lines"] = json.loads(r["lines"]) if r.get("lines") else None
        r.pop("raw", None)
    return rows
