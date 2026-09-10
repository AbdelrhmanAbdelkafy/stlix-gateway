"""Per entity × month: state of the return, imports, carried credit, log."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from ...config import Settings, get_settings

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LOCK = threading.Lock()

#: The procedure, as states. Transitions are explicit (see `advance`).
STATES = ("open", "closing", "packaged", "draft_review", "ready_to_pay", "paid", "closed")
STATE_AR = {"open": "الشهر مفتوح — بنغطي", "closing": "الشهر خلص — مراجعة الملغي/المرفوض",
            "packaged": "باكدج الإقرار جاهزة", "draft_review": "مراجعة الدرافت",
            "ready_to_pay": "الإقرار متطابق — جاهز للدفع", "paid": "اتدفع — الإيصال مسجّل", "closed": "الفترة مقفولة"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS months (
  entity TEXT NOT NULL, month TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
  credit_in REAL DEFAULT 0, credit_out REAL, draft TEXT, paid_amount REAL, paid_at TEXT,
  receipt TEXT, notes TEXT, updated_at REAL, PRIMARY KEY (entity, month));
CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT NOT NULL, month TEXT NOT NULL,
  release_no TEXT, vat REAL NOT NULL, base REAL, source TEXT DEFAULT 'manual', note TEXT, at REAL);
CREATE TABLE IF NOT EXISTS log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, entity TEXT, month TEXT, who TEXT, action TEXT, detail TEXT);
"""


def db_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    p = Path(settings.vat_db_path) if settings.vat_db_path else _ROOT / "data" / "vat" / "vat.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _conn(settings=None) -> sqlite3.Connection:
    c = sqlite3.connect(db_path(settings), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def month_row(entity: str, month: str, settings=None) -> dict:
    with _conn(settings) as c:
        r = c.execute("SELECT * FROM months WHERE entity=? AND month=?", (entity, month)).fetchone()
        if r:
            d = dict(r)
        else:
            # carried credit = previous month's credit_out when it exists
            prev = _prev(month)
            p = c.execute("SELECT credit_out FROM months WHERE entity=? AND month=?", (entity, prev)).fetchone()
            d = {"entity": entity, "month": month, "status": "open",
                 "credit_in": float(p["credit_out"]) if p and p["credit_out"] is not None else 0.0,
                 "credit_out": None, "draft": None, "paid_amount": None, "paid_at": None,
                 "receipt": None, "notes": None, "updated_at": None}
    d["draft"] = json.loads(d["draft"]) if d.get("draft") else None
    d["status_ar"] = STATE_AR.get(d["status"], d["status"])
    return d


def _prev(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def save_month(entity: str, month: str, who: str = "", **fields) -> dict:
    allowed = {"status", "credit_in", "credit_out", "draft", "paid_amount", "paid_at", "receipt", "notes"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown fields {sorted(bad)}")
    if "status" in fields and fields["status"] not in STATES:
        raise ValueError(f"unknown status {fields['status']}")
    if "draft" in fields and fields["draft"] is not None:
        fields["draft"] = json.dumps(fields["draft"], ensure_ascii=False)
    cur = month_row(entity, month)
    with _LOCK, _conn() as c:
        c.execute("INSERT OR IGNORE INTO months (entity, month, status, credit_in, updated_at) VALUES (?,?,?,?,?)",
                  (entity, month, cur["status"], cur["credit_in"], time.time()))
        for k, v in fields.items():
            c.execute(f"UPDATE months SET {k}=?, updated_at=? WHERE entity=? AND month=?",
                      (v, time.time(), entity, month))
        c.execute("INSERT INTO log (at, entity, month, who, action, detail) VALUES (?,?,?,?,?,?)",
                  (time.time(), entity, month, who, "month.update", json.dumps(fields, ensure_ascii=False)))
    return month_row(entity, month)


def add_import(entity: str, month: str, vat: float, release_no: str = "", note: str = "",
               source: str = "manual", who: str = "", vat_rate: float = 0.14) -> dict:
    base = round(vat / vat_rate, 2) if vat_rate else None
    with _LOCK, _conn() as c:
        cur = c.execute("INSERT INTO imports (entity, month, release_no, vat, base, source, note, at) VALUES (?,?,?,?,?,?,?,?)",
                        (entity, month, release_no, float(vat), base, source, note, time.time()))
        c.execute("INSERT INTO log (at, entity, month, who, action, detail) VALUES (?,?,?,?,?,?)",
                  (time.time(), entity, month, who, "import.add", f"{release_no} vat={vat}"))
        return {"id": cur.lastrowid, "release_no": release_no, "vat": float(vat), "base": base, "source": source}


def delete_import(entity: str, month: str, import_id: int, who: str = "") -> bool:
    with _LOCK, _conn() as c:
        n = c.execute("DELETE FROM imports WHERE id=? AND entity=? AND month=?", (import_id, entity, month)).rowcount
        if n:
            c.execute("INSERT INTO log (at, entity, month, who, action, detail) VALUES (?,?,?,?,?,?)",
                      (time.time(), entity, month, who, "import.delete", str(import_id)))
    return bool(n)


def imports(entity: str, month: str, settings=None) -> list[dict]:
    with _conn(settings) as c:
        return [dict(r) for r in c.execute("SELECT * FROM imports WHERE entity=? AND month=? ORDER BY id", (entity, month))]


def log(entity: str | None = None, limit: int = 100) -> list[dict]:
    with _conn() as c:
        if entity:
            rows = c.execute("SELECT * FROM log WHERE entity=? ORDER BY id DESC LIMIT ?", (entity, limit))
        else:
            rows = c.execute("SELECT * FROM log ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def months(entity: str, settings=None) -> list[dict]:
    with _conn(settings) as c:
        return [dict(r) for r in c.execute("SELECT entity, month, status, credit_in, credit_out, paid_amount, paid_at "
                                           "FROM months WHERE entity=? ORDER BY month DESC", (entity,))]
