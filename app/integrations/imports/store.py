"""ملف الشحنة — SQLite. One row per shipment, plus its steps, docs, costs, containers.

Same shape as the VAT store: a file under `data/`, a Docker volume, and an audit
`log` table that records who moved what. The shipment reference is issued here
(`IMP-YYYY-NNN`) rather than typed, because the SOP opens the file on a unified
name and two people opening the same shipment on different days is exactly how
a file ends up duplicated.

Fields that Nama owns (`nama_*` and everything in `NAMA_FIELDS`) are written by
the sync and are read-only in the UI: نما هي سجل الشحنة، والهَب بيضيف عليها طبقة
الـ SOP. A field is never silently overwritten — the sync records what it
changed in the log.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path

from ...config import Settings, get_settings

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LOCK = threading.Lock()

STATUSES = ("open", "closed", "cancelled")
STEP_STATES = ("pending", "done", "na", "blocked")
CHECK_STATES = ("", "ok", "fix", "na")

#: Fields the Nama LCShipment owns. The hub shows them, never edits them.
NAMA_FIELDS = ("bl_no", "containers_no", "customs_declaration", "etd", "eta", "ata",
               "value_fob", "currency", "port_loading", "port_discharge", "shipping_line",
               "docs_delivery_date", "store_delivery_date", "transit_days", "nama_state")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
  ref TEXT PRIMARY KEY,
  entity TEXT, supplier TEXT, origin TEXT, goods TEXT, hs_code TEXT,
  incoterm TEXT, payment_term TEXT, bl_type TEXT,
  acid TEXT, nafeza_accepted INTEGER DEFAULT 0,
  consignee TEXT, bl_no TEXT, vessel TEXT, shipping_line TEXT, broker TEXT,
  port_loading TEXT, port_discharge TEXT,
  containers INTEGER, qty_ton REAL,
  currency TEXT DEFAULT 'EGP', fx_rate REAL,
  value_fob REAL, freight REAL, insurance REAL,
  etd TEXT, eta TEXT, ata TEXT, free_days INTEGER, free_time_start TEXT,
  released_at TEXT, customs_declaration TEXT,
  weight_checked INTEGER DEFAULT 0, endorsed INTEGER DEFAULT 0, telex_verified INTEGER DEFAULT 0,
  po_code TEXT, grn_code TEXT, nama_code TEXT, nama_state TEXT, nama_synced_at REAL,
  docs_delivery_date TEXT, store_delivery_date TEXT, transit_days REAL, containers_no TEXT,
  est_landed_per_ton REAL, demurrage_tariff TEXT,
  status TEXT DEFAULT 'open', notes TEXT,
  created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS steps (
  ref TEXT NOT NULL, sop TEXT NOT NULL, no INTEGER NOT NULL,
  state TEXT DEFAULT 'pending', who TEXT, at REAL, note TEXT,
  PRIMARY KEY (ref, sop, no));
CREATE TABLE IF NOT EXISTS docs (
  ref TEXT NOT NULL, kind TEXT NOT NULL, number TEXT, acid_on_doc TEXT,
  received INTEGER DEFAULT 0, note TEXT, at REAL, PRIMARY KEY (ref, kind));
CREATE TABLE IF NOT EXISTS costs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL, kind TEXT NOT NULL,
  amount REAL NOT NULL, currency TEXT DEFAULT 'EGP', invoice_no TEXT, vendor TEXT,
  note TEXT, source TEXT DEFAULT 'manual', at REAL);
CREATE TABLE IF NOT EXISTS containers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL, container_no TEXT, seal TEXT,
  out_at TEXT, returned_at TEXT, free_return_days INTEGER, deposit REAL, deposit_back REAL, note TEXT);
CREATE TABLE IF NOT EXISTS checklist (
  ref TEXT NOT NULL, key TEXT NOT NULL, state TEXT DEFAULT '', note TEXT, who TEXT, at REAL,
  PRIMARY KEY (ref, key));
CREATE TABLE IF NOT EXISTS log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, ref TEXT, who TEXT, action TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS idx_costs_ref ON costs(ref);
CREATE INDEX IF NOT EXISTS idx_cont_ref ON containers(ref);
CREATE INDEX IF NOT EXISTS idx_log_ref ON log(ref);
"""

_BOOL = ("nafeza_accepted", "weight_checked", "endorsed", "telex_verified")
_EDITABLE = {
    "entity", "supplier", "origin", "goods", "hs_code", "incoterm", "payment_term", "bl_type",
    "acid", "nafeza_accepted", "consignee", "bl_no", "vessel", "shipping_line", "broker",
    "port_loading", "port_discharge", "containers", "qty_ton", "currency", "fx_rate",
    "value_fob", "freight", "insurance", "etd", "eta", "ata", "free_days", "free_time_start",
    "released_at", "customs_declaration", "weight_checked", "endorsed", "telex_verified",
    "po_code", "grn_code", "nama_code", "est_landed_per_ton", "demurrage_tariff", "status", "notes",
}


def db_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    p = (Path(settings.imports_db_path) if getattr(settings, "imports_db_path", "")
         else _ROOT / "data" / "imports" / "imports.db")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _conn(settings=None) -> sqlite3.Connection:
    c = sqlite3.connect(db_path(settings), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def _note(c, ref: str, who: str, action: str, detail: str = "") -> None:
    c.execute("INSERT INTO log (at, ref, who, action, detail) VALUES (?,?,?,?,?)",
              (time.time(), ref, who, action, detail))


# --- shipments ---------------------------------------------------------------
def next_ref(year: int | None = None, settings=None) -> str:
    """IMP-YYYY-NNN, continuing the year's own sequence."""
    year = year or date.today().year
    with _conn(settings) as c:
        rows = c.execute("SELECT ref FROM shipments WHERE ref LIKE ?", (f"IMP-{year}-%",)).fetchall()
    used = [int(r["ref"].rsplit("-", 1)[1]) for r in rows if r["ref"].rsplit("-", 1)[1].isdigit()]
    return f"IMP-{year}-{(max(used) + 1 if used else 1):03d}"


def create(fields: dict, who: str = "", settings=None) -> dict:
    ref = (fields.get("ref") or "").strip() or next_ref(settings=settings)
    clean = {k: v for k, v in fields.items() if k in _EDITABLE}
    clean.setdefault("status", "open")
    if isinstance(clean.get("demurrage_tariff"), (list, dict)):
        clean["demurrage_tariff"] = json.dumps(clean["demurrage_tariff"], ensure_ascii=False)
    cols = ["ref", "created_at", "updated_at", *clean]
    vals = [ref, time.time(), time.time(), *clean.values()]
    with _LOCK, _conn(settings) as c:
        if c.execute("SELECT 1 FROM shipments WHERE ref=?", (ref,)).fetchone():
            raise ValueError(f"ملف الشحنة {ref} موجود بالفعل")
        c.execute(f"INSERT INTO shipments ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        _note(c, ref, who, "shipment.create", json.dumps(clean, ensure_ascii=False)[:400])
    return get(ref, settings)


def get(ref: str, settings=None) -> dict | None:
    with _conn(settings) as c:
        r = c.execute("SELECT * FROM shipments WHERE ref=?", (ref,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for b in _BOOL:
        d[b] = bool(d.get(b))
    d["demurrage_tariff"] = json.loads(d["demurrage_tariff"]) if d.get("demurrage_tariff") else []
    return d


def listing(status: str | None = None, settings=None) -> list[dict]:
    q = "SELECT * FROM shipments"
    args: tuple = ()
    if status:
        q += " WHERE status=?"
        args = (status,)
    q += " ORDER BY ref DESC"
    with _conn(settings) as c:
        rows = [dict(r) for r in c.execute(q, args)]
    for d in rows:
        for b in _BOOL:
            d[b] = bool(d.get(b))
        d["demurrage_tariff"] = json.loads(d["demurrage_tariff"]) if d.get("demurrage_tariff") else []
    return rows


def update(ref: str, fields: dict, who: str = "", source: str = "manual", settings=None) -> dict:
    bad = set(fields) - _EDITABLE - set(NAMA_FIELDS)
    if bad:
        raise ValueError(f"حقول مش معروفة: {sorted(bad)}")
    if source != "nama":
        blocked = set(fields) & set(NAMA_FIELDS) - _EDITABLE
        if blocked:
            raise ValueError(f"الحقول دي بتيجي من نما ومش بتتعدل من هنا: {sorted(blocked)}")
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"حالة مش معروفة: {fields['status']}")
    clean = dict(fields)
    if isinstance(clean.get("demurrage_tariff"), (list, dict)):
        clean["demurrage_tariff"] = json.dumps(clean["demurrage_tariff"], ensure_ascii=False)
    for b in _BOOL:
        if b in clean:
            clean[b] = 1 if clean[b] else 0
    with _LOCK, _conn(settings) as c:
        if not c.execute("SELECT 1 FROM shipments WHERE ref=?", (ref,)).fetchone():
            raise KeyError(ref)
        for k, v in clean.items():
            c.execute(f"UPDATE shipments SET {k}=?, updated_at=? WHERE ref=?", (v, time.time(), ref))
        _note(c, ref, who, f"shipment.update:{source}", json.dumps(clean, ensure_ascii=False)[:400])
    return get(ref, settings)


# --- steps -------------------------------------------------------------------
def steps(ref: str, settings=None) -> dict[tuple[str, int], dict]:
    with _conn(settings) as c:
        return {(r["sop"], r["no"]): dict(r)
                for r in c.execute("SELECT * FROM steps WHERE ref=?", (ref,))}


def set_step(ref: str, sop_code: str, no: int, state: str, who: str = "", note: str = "",
             settings=None) -> dict:
    if state not in STEP_STATES:
        raise ValueError(f"حالة خطوة مش معروفة: {state}")
    with _LOCK, _conn(settings) as c:
        c.execute("INSERT INTO steps (ref, sop, no, state, who, at, note) VALUES (?,?,?,?,?,?,?) "
                  "ON CONFLICT(ref, sop, no) DO UPDATE SET state=?, who=?, at=?, note=?",
                  (ref, sop_code, no, state, who, time.time(), note, state, who, time.time(), note))
        _note(c, ref, who, "step", f"{sop_code}#{no} → {state} {note}".strip())
    return {"ref": ref, "sop": sop_code, "no": no, "state": state}


# --- documents ---------------------------------------------------------------
def docs(ref: str, settings=None) -> list[dict]:
    with _conn(settings) as c:
        return [dict(r) for r in c.execute("SELECT * FROM docs WHERE ref=?", (ref,))]


def set_doc(ref: str, kind: str, who: str = "", settings=None, **fields) -> dict:
    allowed = {"number", "acid_on_doc", "received", "note"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"حقول مستند مش معروفة: {sorted(bad)}")
    if "received" in fields:
        fields["received"] = 1 if fields["received"] else 0
    with _LOCK, _conn(settings) as c:
        c.execute("INSERT OR IGNORE INTO docs (ref, kind, at) VALUES (?,?,?)", (ref, kind, time.time()))
        for k, v in fields.items():
            c.execute(f"UPDATE docs SET {k}=?, at=? WHERE ref=? AND kind=?", (v, time.time(), ref, kind))
        _note(c, ref, who, "doc", f"{kind}: {json.dumps(fields, ensure_ascii=False)}"[:300])
        r = c.execute("SELECT * FROM docs WHERE ref=? AND kind=?", (ref, kind)).fetchone()
    return dict(r)


# --- costs -------------------------------------------------------------------
def costs(ref: str, settings=None) -> list[dict]:
    with _conn(settings) as c:
        return [dict(r) for r in c.execute("SELECT * FROM costs WHERE ref=? ORDER BY id", (ref,))]


def add_cost(ref: str, kind: str, amount: float, currency: str = "EGP", invoice_no: str = "",
             vendor: str = "", note: str = "", source: str = "manual", who: str = "",
             settings=None) -> dict:
    with _LOCK, _conn(settings) as c:
        cur = c.execute("INSERT INTO costs (ref, kind, amount, currency, invoice_no, vendor, note, source, at) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (ref, kind, float(amount), currency, invoice_no, vendor, note, source, time.time()))
        _note(c, ref, who, "cost.add", f"{kind} {amount} {currency} inv={invoice_no or '—'}")
        return {"id": cur.lastrowid, "ref": ref, "kind": kind, "amount": float(amount),
                "currency": currency, "invoice_no": invoice_no, "vendor": vendor, "source": source}


def delete_cost(ref: str, cost_id: int, who: str = "", settings=None) -> bool:
    with _LOCK, _conn(settings) as c:
        n = c.execute("DELETE FROM costs WHERE id=? AND ref=?", (cost_id, ref)).rowcount
        if n:
            _note(c, ref, who, "cost.delete", str(cost_id))
    return bool(n)


# --- containers --------------------------------------------------------------
def containers(ref: str, settings=None) -> list[dict]:
    with _conn(settings) as c:
        return [dict(r) for r in c.execute("SELECT * FROM containers WHERE ref=? ORDER BY id", (ref,))]


def add_container(ref: str, container_no: str, who: str = "", settings=None, **fields) -> dict:
    allowed = {"seal", "out_at", "returned_at", "free_return_days", "deposit", "deposit_back", "note"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    cols = ["ref", "container_no", *clean]
    with _LOCK, _conn(settings) as c:
        cur = c.execute(f"INSERT INTO containers ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                        [ref, container_no, *clean.values()])
        _note(c, ref, who, "container.add", container_no)
    return {"id": cur.lastrowid, "ref": ref, "container_no": container_no, **clean}


def update_container(ref: str, cid: int, who: str = "", settings=None, **fields) -> bool:
    allowed = {"seal", "out_at", "returned_at", "free_return_days", "deposit", "deposit_back", "note"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return False
    with _LOCK, _conn(settings) as c:
        for k, v in clean.items():
            c.execute(f"UPDATE containers SET {k}=? WHERE id=? AND ref=?", (v, cid, ref))
        _note(c, ref, who, "container.update", f"{cid}: {json.dumps(clean, ensure_ascii=False)}"[:200])
    return True


def delete_container(ref: str, cid: int, who: str = "", settings=None) -> bool:
    with _LOCK, _conn(settings) as c:
        n = c.execute("DELETE FROM containers WHERE id=? AND ref=?", (cid, ref)).rowcount
        if n:
            _note(c, ref, who, "container.delete", str(cid))
    return bool(n)


# --- BL checklist ------------------------------------------------------------
def checklist(ref: str, settings=None) -> dict[str, str]:
    with _conn(settings) as c:
        return {r["key"]: r["state"] for r in c.execute("SELECT key, state FROM checklist WHERE ref=?", (ref,))}


def set_check(ref: str, key: str, state: str, who: str = "", note: str = "", settings=None) -> dict:
    if state not in CHECK_STATES:
        raise ValueError(f"حالة بند مش معروفة: {state}")
    with _LOCK, _conn(settings) as c:
        c.execute("INSERT INTO checklist (ref, key, state, note, who, at) VALUES (?,?,?,?,?,?) "
                  "ON CONFLICT(ref, key) DO UPDATE SET state=?, note=?, who=?, at=?",
                  (ref, key, state, note, who, time.time(), state, note, who, time.time()))
        _note(c, ref, who, "checklist", f"{key} → {state} {note}".strip())
    return {"ref": ref, "key": key, "state": state}


# --- log ---------------------------------------------------------------------
def log(ref: str | None = None, limit: int = 100, settings=None) -> list[dict]:
    with _conn(settings) as c:
        if ref:
            rows = c.execute("SELECT * FROM log WHERE ref=? ORDER BY id DESC LIMIT ?", (ref, limit))
        else:
            rows = c.execute("SELECT * FROM log ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def mark_synced(ref: str, settings=None) -> None:
    """Stamp the last successful Nama pull. Not an editable field: it records a
    fact about the sync, so nothing on the screen may set it."""
    with _LOCK, _conn(settings) as c:
        c.execute("UPDATE shipments SET nama_synced_at=? WHERE ref=?", (time.time(), ref))
