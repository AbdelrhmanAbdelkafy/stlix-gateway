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


_CUSTOMERS = """
SELECT TOP (?) c.code, c.name1,
       COUNT(*) AS invoices,
       CAST(SUM(s.total)     AS BIGINT) AS salesTotal,
       CAST(SUM(s.totalPaid) AS BIGINT) AS collected,
       CAST(SUM(s.remaining) AS BIGINT) AS outstanding,
       CONVERT(varchar(10), MAX(s.issueDate), 120) AS lastInvoiceDate
FROM SalesInvoice s JOIN Customer c ON c.id = s.customer_id
GROUP BY c.code, c.name1
ORDER BY SUM(s.total) DESC
"""

_SUPPLIERS = """
SELECT TOP (?) sup.code, sup.name1,
       COUNT(*) AS invoices,
       CAST(SUM(p.total)     AS BIGINT) AS purchaseTotal,
       CAST(SUM(p.totalPaid) AS BIGINT) AS paid,
       CAST(SUM(p.remaining) AS BIGINT) AS outstanding,
       CONVERT(varchar(10), MAX(p.issueDate), 120) AS lastInvoiceDate
FROM PurchaseInvoice p JOIN Supplier sup ON sup.id = p.supplier_id
GROUP BY sup.code, sup.name1
ORDER BY SUM(p.remaining) DESC
"""

_KPIS = """
SELECT (SELECT COUNT(*) FROM Customer)                        AS customers,
       (SELECT COUNT(*) FROM Supplier)                        AS suppliers,
       (SELECT COUNT(*) FROM SalesInvoice)                    AS salesInvoices,
       CAST((SELECT SUM(total)     FROM SalesInvoice) AS BIGINT)    AS salesTotal,
       CAST((SELECT SUM(remaining) FROM SalesInvoice) AS BIGINT)    AS arOutstanding,
       (SELECT COUNT(*) FROM PurchaseInvoice)                 AS purchaseInvoices,
       CAST((SELECT SUM(total)     FROM PurchaseInvoice) AS BIGINT) AS purchaseTotal,
       CAST((SELECT SUM(remaining) FROM PurchaseInvoice) AS BIGINT) AS apOutstanding,
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
