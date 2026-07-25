"""Finance connector — real customer/supplier balances from the Nama SQL DB.

Nama REST exposes no computed balances, so finance reads them straight from the
restored Nama database over a **read-only** SQL login (db_datareader). Queries are
SELECT-only; the login itself cannot write. pyodbc is synchronous, so calls run in
a threadpool. If SQL isn't configured, methods return `available: False` gracefully.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from starlette.concurrency import run_in_threadpool

from ...config import Settings

try:  # pyodbc is optional at import time (driver may be absent in some envs)
    import pyodbc
except Exception:  # pragma: no cover
    pyodbc = None


# --- how the party is stored, and why the obvious join is wrong -------------
#
# `SalesInvoice.customer_id` is NULL on 5,263 of 6,845 posted invoices — it is
# only filled on the minority of documents raised through the customer-order
# route. Joining on it silently dropped 19,843,457 of the 20,021,266 open AR,
# which is why the customer report used to add up to ~178K and the KPI to 20M.
#
# The party every document actually carries is the polymorphic *subsidiary*
# (`subsidiaryId` + `subsidiaryEntityType`), and it resolves against
# Customer.id with zero misses on all 5,806 customer-typed sales invoices.
# `subsidiaryCode` is NOT usable: 4,950 of those rows carry a legacy code that
# no longer matches Customer.code.
#
# Two more rules hold for every figure below:
#   * `documentFileStatus = 'Stable'` — unposted drafts are ordinary rows here
#     and would otherwise be summed with posted documents.
#   * `remaining = netValue - totalPaid` (6,829 of 6,848 rows), NOT
#     `total - totalPaid` — `total` is the gross before tax. So each row's
#     invoicedNet / collected / outstanding tie out; `salesTotal` is kept
#     alongside for continuity but is not the basis of the balance.

_CUSTOMERS = """
SELECT TOP (?) c.code, c.name1,
       COUNT(*) AS invoices,
       CAST(SUM(s.total)     AS FLOAT) AS salesTotal,
       CAST(SUM(s.netValue)  AS FLOAT) AS invoicedNet,
       CAST(SUM(s.totalPaid) AS FLOAT) AS collected,
       CAST(SUM(s.remaining) AS FLOAT) AS outstanding,
       CONVERT(varchar(10), MAX(s.issueDate), 120) AS lastInvoiceDate
FROM SalesInvoice s JOIN Customer c ON c.id = s.subsidiaryId
WHERE s.documentFileStatus = 'Stable' AND s.subsidiaryEntityType = 'Customer'
GROUP BY c.code, c.name1
ORDER BY SUM(s.remaining) DESC
"""

_SUPPLIERS = """
SELECT TOP (?) sup.code, sup.name1,
       COUNT(*) AS invoices,
       CAST(SUM(p.total)     AS FLOAT) AS purchaseTotal,
       CAST(SUM(p.netValue)  AS FLOAT) AS invoicedNet,
       CAST(SUM(p.totalPaid) AS FLOAT) AS paid,
       CAST(SUM(p.remaining) AS FLOAT) AS outstanding,
       CONVERT(varchar(10), MAX(p.issueDate), 120) AS lastInvoiceDate
FROM PurchaseInvoice p JOIN Supplier sup ON sup.id = p.subsidiaryId
WHERE p.documentFileStatus = 'Stable' AND p.subsidiaryEntityType = 'Supplier'
GROUP BY sup.code, sup.name1
ORDER BY SUM(p.remaining) DESC
"""

# arOutstanding counts every open sales invoice; arFromCustomers is the slice the
# customer report can name. They differ by ~9.5M because 1,016 sales invoices are
# raised against a Supplier and 23 against an Employee — real documents, just not
# customer receivables. Publishing only the total made the report look broken.
_KPIS = """
SELECT (SELECT COUNT(*) FROM Customer) AS customers,
       (SELECT COUNT(*) FROM Supplier) AS suppliers,
       (SELECT COUNT(*) FROM SalesInvoice WHERE documentFileStatus='Stable') AS salesInvoices,
       CAST((SELECT SUM(total)    FROM SalesInvoice WHERE documentFileStatus='Stable') AS FLOAT) AS salesTotal,
       CAST((SELECT SUM(netValue) FROM SalesInvoice WHERE documentFileStatus='Stable') AS FLOAT) AS salesNet,
       CAST((SELECT SUM(remaining) FROM SalesInvoice
             WHERE documentFileStatus='Stable') AS FLOAT) AS arOutstanding,
       CAST((SELECT SUM(remaining) FROM SalesInvoice
             WHERE documentFileStatus='Stable' AND subsidiaryEntityType='Customer') AS FLOAT) AS arFromCustomers,
       (SELECT COUNT(*) FROM PurchaseInvoice WHERE documentFileStatus='Stable') AS purchaseInvoices,
       CAST((SELECT SUM(total)    FROM PurchaseInvoice WHERE documentFileStatus='Stable') AS FLOAT) AS purchaseTotal,
       CAST((SELECT SUM(netValue) FROM PurchaseInvoice WHERE documentFileStatus='Stable') AS FLOAT) AS purchaseNet,
       CAST((SELECT SUM(remaining) FROM PurchaseInvoice
             WHERE documentFileStatus='Stable') AS FLOAT) AS apOutstanding,
       CAST((SELECT SUM(remaining) FROM PurchaseInvoice
             WHERE documentFileStatus='Stable' AND subsidiaryEntityType='Supplier') AS FLOAT) AS apToSuppliers,
       (SELECT CONVERT(varchar(10), MAX(issueDate), 120) FROM SalesInvoice) AS asOf
"""

_AS_OF = "SELECT CONVERT(varchar(10), MAX(issueDate), 120) AS asOf FROM SalesInvoice"


class FinanceConnector:
    key = "finance"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.configured = settings.nama_sql_configured and pyodbc is not None

    # --- sync core (runs in threadpool) ---
    def _connect(self):
        s = self.settings
        cs = (
            f"DRIVER={{{s.nama_sql_driver}}};SERVER={s.nama_sql_server};"
            f"DATABASE={s.nama_sql_database};UID={s.nama_sql_user};PWD={s.nama_sql_password};"
            "Encrypt=yes;TrustServerCertificate=yes;"
        )
        return pyodbc.connect(cs, timeout=15, readonly=True)

    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()

    # --- async API ---
    async def freshness(self) -> dict[str, Any]:
        """How old is this money?

        Every figure here comes from a **restored backup**, not the live ERP —
        direct SQL to the Namasoft cloud tenant is not reachable. That was
        invisible: the reports rendered eleven-day-old balances with no as-of
        label at all, which reads as "this is today's position".
        """
        if not self.configured:
            return {"available": False}
        rows = await run_in_threadpool(self._rows, _AS_OF, ())
        as_of = rows[0].get("asOf") if rows else None
        age = None
        if as_of:
            try:
                age = (date.today() - date.fromisoformat(as_of)).days
            except ValueError:
                age = None
        return {
            "available": True,
            "as_of": as_of,
            "age_days": age,
            "live": False,
            "source": "restored backup of the Nama production DB (cloud SQL is not reachable)",
            "stale": age is not None and age > 1,
        }

    async def _report(self, sql: str, params: tuple, key: str) -> dict[str, Any]:
        if not self.configured:
            return {"available": False, "reason": "Nama SQL not configured "
                    "(set NAMA_SQL_* in .env).", "records": []}
        rows = await run_in_threadpool(self._rows, sql, params)
        return {"available": True, "source": "nama_sql", "count": len(rows),
                "freshness": await self.freshness(), "records": rows}

    async def customer_balances(self, limit: int = 200) -> dict:
        return await self._report(_CUSTOMERS, (limit,), "customers")

    async def supplier_balances(self, limit: int = 200) -> dict:
        return await self._report(_SUPPLIERS, (limit,), "suppliers")

    async def kpis(self) -> dict:
        if not self.configured:
            return {"available": False, "reason": "Nama SQL not configured."}
        rows = await run_in_threadpool(self._rows, _KPIS, ())
        return {"available": True, "source": "nama_sql",
                "freshness": await self.freshness(), **(rows[0] if rows else {})}
