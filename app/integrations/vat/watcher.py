"""The part that runs without anybody asking.

Every `VAT_SYNC_INTERVAL_MINUTES` the gateway pulls the current month (and,
until its return is closed, the previous one) for every configured entity, then
decides whether anything is worth telling a human:

- an invoice slot passed uncovered, or one is due within two days
- the gap changed materially since the last alert
- a document was cancelled or rejected on the portal
- the month is over → day-7 recheck → package
- the filing deadline is close and the return is not paid

Alerts are written once per (entity, month, kind, day) — the same fact does not
nag twice in a day — and read back by `/api/v1/vat/alerts`. Delivery to
WhatsApp/the admin group is the Ops Bus's job; this decides *what* to say.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from datetime import date

from ...config import Settings, get_settings
from ..eta import store as eta
from . import engine, store

log = logging.getLogger("gateway.vat")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, day TEXT, entity TEXT, month TEXT,
  kind TEXT, level TEXT, text TEXT, amount REAL, seen INTEGER DEFAULT 0,
  UNIQUE(entity, month, kind, day));
"""


def _conn(settings=None) -> sqlite3.Connection:
    c = sqlite3.connect(store.db_path(settings), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def raise_alert(entity: str, month: str, kind: str, text: str, level: str = "info",
                amount: float | None = None, today: date | None = None, settings=None) -> bool:
    """True when this is new today."""
    day = (today or date.today()).isoformat()
    with _conn(settings) as c:
        cur = c.execute("INSERT OR IGNORE INTO alerts (at, day, entity, month, kind, level, text, amount) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (time.time(), day, entity, month, kind, level, text, amount))
        return bool(cur.rowcount)


def alerts(entity: str | None = None, limit: int = 50, unseen_only: bool = False, settings=None) -> list[dict]:
    q = "SELECT * FROM alerts"
    args: list = []
    where = []
    if entity:
        where.append("entity=?")
        args.append(entity)
    if unseen_only:
        where.append("seen=0")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _conn(settings) as c:
        return [dict(r) for r in c.execute(q, args)]


def mark_seen(ids: list[int], settings=None) -> int:
    if not ids:
        return 0
    with _conn(settings) as c:
        return c.execute(f"UPDATE alerts SET seen=1 WHERE id IN ({','.join('?' * len(ids))})", ids).rowcount


def _prev_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def months_in_play(settings: Settings, entity_key: str, today: date) -> list[str]:
    """This month always; last month until its return is closed."""
    cur = f"{today.year}-{today.month:02d}"
    out = [cur]
    prev = _prev_month(cur)
    if store.month_row(entity_key, prev, settings)["status"] != "closed":
        out.append(prev)
    return out


def review(plan: dict, today: date | None = None, settings=None) -> list[dict]:
    """Decide what is worth saying about one month. Pure — the caller files them."""
    today = today or date.today()
    ent, month = plan["entity"]["key"], plan["month"]
    out: list[dict] = []

    def say(kind, text, level="info", amount=None):
        out.append({"kind": kind, "text": text, "level": level, "amount": amount})

    if not plan["synced"]:
        say("not_synced", f"{plan['entity']['name']} {month}: ما اتسحبش من البورتال — الأرقام مش موثوقة", "warn")
        return out

    cal = plan["calendar"]
    if plan["action"] == "buy":
        due = [s for s in plan["slots"] if not s["covered"] and not s["past"]]
        nxt = due[0]["date"] if due else None
        say("gap", f"{plan['entity']['name']} {month}: محتاج فواتير مشتريات بقيمة "
                   f"{plan['gap_base']:,.0f} ج (ض.ق.م {plan['gap_vat']:,.0f})"
                   + (f" — أقرب ميعاد {nxt}" if nxt else " — مفيش مواعيد باقية في الشهر"),
            "warn" if not due else "info", plan["gap_base"])
        missed = [s for s in plan["slots"] if s["past"] and not s["covered"]]
        if missed:
            say("slot_missed", f"{plan['entity']['name']} {month}: فات {len(missed)} ميعاد من غير فاتورة "
                               f"({', '.join(s['date'] for s in missed[-3:])})", "warn")
    elif plan["action"] == "surplus":
        say("surplus", f"{plan['entity']['name']} {month}: رصيد مشتريات فايض "
                       f"{-plan['gap_vat']:,.0f} ج ض.ق.م — يتبعت لجروب الأدمن، مفيش شراء", "info", -plan["gap_vat"])

    if plan["problems"]:
        say("problems", f"{plan['entity']['name']} {month}: {len(plan['problems'])} مستند ملغي/مرفوض على البورتال "
                        f"({', '.join(p['internal_id'] or p['uuid'][:8] for p in plan['problems'][:3])})", "warn")

    st = plan["status"]
    if cal["month_over"] and st == "open":
        say("month_over", f"{plan['entity']['name']} {month}: الشهر خلص — ابدأ مراجعة الملغي/المرفوض", "info")
    if today.isoformat() >= cal["recheck_day"] and st in ("open", "closing"):
        say("recheck", f"{plan['entity']['name']} {month}: يوم {cal['recheck_day']} — المراجعة الأخيرة "
                       f"وباكدج الإقرار جاهزة للتجهيز", "warn")
    if st not in ("paid", "closed"):
        d = cal["days_to_deadline"]
        if d <= 7:
            say("deadline", f"{plan['entity']['name']} {month}: باقي {d} يوم على آخر ميعاد للإقرار "
                            f"({cal['filing_deadline']}) والحالة «{plan['status_ar']}»",
                "warn" if d > 2 else "critical")
    return out


async def sweep(settings: Settings | None = None, today: date | None = None) -> dict:
    """One pass: sync every entity's live months, then file the alerts they earn."""
    settings = settings or get_settings()
    today = today or date.today()
    done, fired = [], 0
    for e in eta.entities(settings):
        for month in months_in_play(settings, e.key, today):
            if e.configured:
                await eta.sync(e.key, month, settings)
            plan = engine.plan(e, month, settings, today)
            for a in review(plan, today, settings):
                if raise_alert(e.key, month, a["kind"], a["text"], a["level"], a["amount"], today, settings):
                    fired += 1
                    log.info("vat.alert", extra={"entity": e.key, "month": month, "kind": a["kind"]})
            done.append({"entity": e.key, "month": month, "action": plan["action"], "gap_base": plan["gap_base"]})
    return {"ok": True, "at": time.time(), "months": done, "alerts": fired}


async def loop(settings: Settings, minutes: float) -> None:
    while True:
        try:
            out = await sweep(settings)
            log.info("vat.sweep", extra={"months": len(out["months"]), "alerts": out["alerts"]})
        except Exception as exc:  # noqa: BLE001 — a watcher never takes the app down
            log.warning("vat.sweep failed: %s", exc)
        await asyncio.sleep(minutes * 60)
