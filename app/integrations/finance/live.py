"""AR/AP computed from the LIVE Nama REST tenant, not from a restored backup.

Nama's REST API publishes no computed balance — that is why finance has been
reading a restored SQL copy, eleven days behind. It does, however, publish the
documents, and the balance can be rebuilt from them:

    invoice net  = SUM(details[].price.netValue)
    invoice paid = SUM(externalPaymentLines[].paymentValue)
    open         = net - paid

That reconstruction was checked against SQL document by document over June 2026:
302 invoices, **zero** differences in gross, 2 differences in net totalling 1.49
EGP of rounding, and 20 differences in paid — every one of which is an invoice
settled after the backup was taken, in the right direction and to the cent. The
one that moved backwards (FP22026060000105, -230,500) is a payment voucher that
was cancelled in Nama after the backup; the PaymentVoucher sweep found the same
document missing on the live side. Nothing was left unexplained.

Cost is the reason this is a snapshot and not a per-request query: a full sweep
of both invoice entities is ~14,000 documents over 14 pages at ~36 s a page, so
roughly eight minutes. It runs in the background; requests read whatever
snapshot is current, and are told exactly how old it is.

Read-only: `/list` only. Nothing here can write to the ERP.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from ...config import Settings
from ..nama.client import NamaClient, is_draft

SALES = "SalesInvoice"
PURCHASE = "PurchaseInvoice"
CUSTOMER = "Customer"
SUPPLIER = "Supplier"


def document_money(record: dict) -> tuple[float, float, float]:
    """(gross, net, paid) for one invoice, in local currency.

    Nama omits zero-valued fields from its JSON entirely rather than sending 0,
    so every read has to tolerate an absent key — `price.netValue` is missing on
    a line worth nothing, not present-and-zero.
    """
    gross = net = 0.0
    for line in record.get("details") or []:
        price = line.get("price") or {}
        g, n = price.get("price"), price.get("netValue")
        if isinstance(g, (int, float)):
            gross += g
        if isinstance(n, (int, float)):
            net += n
    paid = 0.0
    for pay in record.get("externalPaymentLines") or []:
        v = pay.get("paymentValue")
        if isinstance(v, (int, float)):
            paid += v
    return gross, net, paid


def _party(record: dict) -> tuple[str, str]:
    sub = record.get("subsidiary") or {}
    return (sub.get("entityType") or "?"), (sub.get("code") or "?")


def _master_index(records: list[dict]) -> dict[str, Any]:
    """Names/count from the live party master, never from the stale SQL copy."""
    names: dict[str, str | None] = {}
    invalid: list[dict[str, Any]] = []
    for index, rec in enumerate(records, start=1):
        code = rec.get("code")
        if not code:
            invalid.append({"index": index, "reason": "missing code"})
            continue
        names[code] = rec.get("name1") or rec.get("name2")
    return {"count": len(names), "names": names, "invalid": invalid}


def summarise(
    records: list[dict],
    party_type: str,
    party_names: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Roll documents up into a balance, keeping drafts and other parties apart.

    Two separations that a naive SUM gets wrong:

    * **drafts.** `@draft` on a code marks an unposted document. It is a
      separate row that can share a posted document's number, it sorts *first*
      in the default order, and it has never reached the ledger. Summed in, it
      reports money that has not moved.
    * **counterparty.** Sales invoices are not all raised on customers — 1,016
      of them are raised on suppliers and 23 on employees, together 9.5M of the
      20.0M open. Real documents, but not customer receivables, so they are
      reported next to the total rather than inside it.
    """
    parties: dict[str, dict[str, Any]] = {}
    totals = {"gross": 0.0, "net": 0.0, "paid": 0.0, "open": 0.0, "count": 0}
    scoped = {"net": 0.0, "paid": 0.0, "open": 0.0, "count": 0}
    drafts = {"count": 0, "net": 0.0}
    invalid: list[dict[str, Any]] = []
    party_names = party_names or {}

    for index, rec in enumerate(records, start=1):
        if is_draft(rec):
            _, net, _ = document_money(rec)
            drafts["count"] += 1
            drafts["net"] += net
            continue
        # Nama returned one PurchaseInvoice as an empty shell: issue date and
        # dimensions, but no code and no lines. Counting it as a zero invoice
        # makes the sweep look complete when the document cannot be identified
        # or valued. Keep the anomaly with the result and exclude it.
        if not rec.get("code") or not rec.get("details"):
            invalid.append({
                "index": index,
                "issueDate": rec.get("issueDate"),
                "reason": "missing code" if not rec.get("code") else "missing details",
            })
            continue
        gross, net, paid = document_money(rec)
        totals["gross"] += gross
        totals["net"] += net
        totals["paid"] += paid
        totals["open"] += net - paid
        totals["count"] += 1

        etype, code = _party(rec)
        if etype != party_type:
            continue
        scoped["net"] += net
        scoped["paid"] += paid
        scoped["open"] += net - paid
        scoped["count"] += 1
        p = parties.setdefault(
            code,
            {
                "code": code,
                "name1": party_names.get(code),
                "invoices": 0,
                "gross": 0.0,
                "invoicedNet": 0.0,
                "paid": 0.0,
                "outstanding": 0.0,
                "lastInvoiceDate": None,
            },
        )
        p["invoices"] += 1
        p["gross"] += gross
        p["invoicedNet"] += net
        p["paid"] += paid
        p["outstanding"] += net - paid
        issued = rec.get("issueDate")  # DD-MM-YYYY
        if issued and (p["lastInvoiceDate"] is None or _iso(issued) > p["lastInvoiceDate"]):
            p["lastInvoiceDate"] = _iso(issued)

    rows = sorted(parties.values(), key=lambda r: r["outstanding"], reverse=True)
    for r in rows:
        for k in ("gross", "invoicedNet", "paid", "outstanding"):
            r[k] = round(r[k], 2)
    return {
        "totals": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in totals.items()},
        "scoped": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in scoped.items()},
        "drafts": {"count": drafts["count"], "net": round(drafts["net"], 2)},
        "invalid": invalid,
        "parties": rows,
    }


def _iso(ddmmyyyy: str) -> str:
    d, m, y = ddmmyyyy.split("-")
    return f"{y}-{m}-{d}"


class LiveFinance:
    """Holds one snapshot and refreshes it on request.

    The snapshot is deliberately never built lazily inside a web request: the
    sweep takes minutes, and a page that hangs for eight minutes is worse than a
    page that says "no live snapshot yet".
    """

    _snapshot: dict[str, Any] | None = None
    _lock = asyncio.Lock()
    _building = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.configured = bool(settings.nama_client_id and settings.nama_client_secret)

    # --- reading ---
    @classmethod
    def snapshot(cls) -> dict[str, Any] | None:
        return cls._snapshot

    @classmethod
    def freshness(cls) -> dict[str, Any]:
        snap = cls._snapshot
        if not snap:
            return {"available": False, "live": True, "building": cls._building,
                    "reason": "no live snapshot yet — POST /api/v1/finance/live/refresh"}
        age = time.time() - snap["computed_at_epoch"]
        return {
            "available": True,
            "live": True,
            "as_of": snap["computed_at"],
            "age_days": 0,
            "age_minutes": round(age / 60, 1),
            "source": "Nama REST documents (invoices + their settlements), swept live",
            "stale": age > 6 * 3600,
            "excludes": snap["excludes"],
            "building": cls._building,
        }

    # --- building ---
    async def refresh(self) -> dict[str, Any]:
        if not self.configured:
            return {"available": False, "reason": "Nama REST not configured."}
        async with self._lock:
            type(self)._building = True
            try:
                client = NamaClient(self.settings)
                sales = await client.list_all(SALES)
                purchase = await client.list_all(PURCHASE)
                customers = await client.list_all(CUSTOMER)
                suppliers = await client.list_all(SUPPLIER)
                customer_index = _master_index(customers["records"])
                supplier_index = _master_index(suppliers["records"])
                sales_summary = summarise(
                    sales["records"], CUSTOMER, customer_index["names"]
                )
                purchase_summary = summarise(
                    purchase["records"], SUPPLIER, supplier_index["names"]
                )
                snap = {
                    "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "computed_at_epoch": time.time(),
                    "sales": sales_summary,
                    "purchase": purchase_summary,
                    "masters": {
                        "customers": customer_index,
                        "suppliers": supplier_index,
                    },
                    # A figure built from an incomplete sweep must carry the gap
                    # with it. These documents are not unreadable by accident:
                    # the API credential is refused them ("not accessible from
                    # this context") and no retry recovers them.
                    "excludes": {
                        "salesInvoices": sales["inaccessible"],
                        "purchaseInvoices": purchase["inaccessible"],
                        "invalidSalesInvoices": sales_summary["invalid"],
                        "invalidPurchaseInvoices": purchase_summary["invalid"],
                        "customers": customers["inaccessible"],
                        "suppliers": suppliers["inaccessible"],
                        "invalidCustomers": customer_index["invalid"],
                        "invalidSuppliers": supplier_index["invalid"],
                        "complete": all(
                            result["complete"]
                            for result in (sales, purchase, customers, suppliers)
                        )
                        and not any(
                            (
                                sales_summary["invalid"],
                                purchase_summary["invalid"],
                                customer_index["invalid"],
                                supplier_index["invalid"],
                            )
                        ),
                    },
                    "swept": {"salesInvoices": sales["count"], "salesPages": sales["pages"],
                              "purchaseInvoices": purchase["count"],
                              "purchasePages": purchase["pages"],
                              "customers": customers["count"],
                              "customerPages": customers["pages"],
                              "suppliers": suppliers["count"],
                              "supplierPages": suppliers["pages"]},
                }
                type(self)._snapshot = snap
                return snap
            finally:
                type(self)._building = False

    # --- the same three reports the SQL connector serves ---
    def kpis(self) -> dict[str, Any]:
        snap = self._snapshot
        if not snap:
            return {"available": False, **self.freshness()}
        s, p = snap["sales"], snap["purchase"]
        return {
            "available": True,
            "source": "nama_rest_live",
            "freshness": self.freshness(),
            "customers": snap["masters"]["customers"]["count"],
            "suppliers": snap["masters"]["suppliers"]["count"],
            "salesInvoices": s["totals"]["count"],
            "salesTotal": s["totals"]["gross"],
            "salesNet": s["totals"]["net"],
            "arOutstanding": s["totals"]["open"],
            "arFromCustomers": s["scoped"]["open"],
            "purchaseInvoices": p["totals"]["count"],
            "purchaseTotal": p["totals"]["gross"],
            "purchaseNet": p["totals"]["net"],
            "apOutstanding": p["totals"]["open"],
            "apToSuppliers": p["scoped"]["open"],
            "asOf": snap["computed_at"][:10],
            "excludedDocuments": (
                len(snap["excludes"]["salesInvoices"])
                + len(snap["excludes"]["purchaseInvoices"])
                + len(snap["excludes"]["invalidSalesInvoices"])
                + len(snap["excludes"]["invalidPurchaseInvoices"])
            ),
        }

    def _balances(self, side: str, limit: int) -> dict[str, Any]:
        snap = self._snapshot
        if not snap:
            return {"available": False, "records": [], **self.freshness()}
        rows = []
        for original in snap[side]["parties"][:limit]:
            row = dict(original)
            if side == "sales":
                row["salesTotal"] = row["gross"]
                row["collected"] = row["paid"]
            else:
                row["purchaseTotal"] = row["gross"]
            rows.append(row)
        return {
            "available": True,
            "source": "nama_rest_live",
            "freshness": self.freshness(),
            "count": min(limit, len(snap[side]["parties"])),
            "records": rows,
        }

    def customer_balances(self, limit: int = 200) -> dict[str, Any]:
        return self._balances("sales", limit)

    def supplier_balances(self, limit: int = 200) -> dict[str, Any]:
        return self._balances("purchase", limit)


REFRESH_EVERY_SECONDS = 3600


async def refresh_loop(settings: Settings, every: int = REFRESH_EVERY_SECONDS) -> None:
    """Keep the snapshot warm — one sweep an hour, starting at boot.

    A failed sweep must not kill the loop: Nama drops roughly one rapid request
    in ten, and losing the refresher on the first ConnectError would leave the
    snapshot frozen while still claiming to be live. On failure it keeps the
    previous snapshot — whose `age_minutes` then simply keeps growing, which is
    the honest signal — and tries again next hour.
    """
    live = LiveFinance(settings)
    if not live.configured:
        return
    while True:
        try:
            await live.refresh()
        except Exception as exc:  # noqa: BLE001 - a refresher must outlive its errors
            logging.getLogger("stlix.finance.live").warning("live sweep failed: %s", exc)
        await asyncio.sleep(every)
