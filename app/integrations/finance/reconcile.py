"""Compare a rebuilt live figure against SQL, document by document.

This is the shared core: `scripts/reconcile_live_vs_sql.py` drives it from the
command line, and `guard.py` runs it after every background sweep. One
implementation, so the thing that gates a release and the thing that watches
production cannot drift apart from each other.

**What is invariant, and what is not.** For a month that has closed, the set of
invoices issued into it is fixed, and a posted invoice's gross and net do not
change. Its `paid` very much does — a May invoice gets settled in July. So:

    document set          fixed      -> any document on one side only is drift
    gross / net per doc   fixed      -> any movement is drift
    paid per doc          grows      -> growth is a settlement, not drift

That asymmetry is the whole design. It is also what makes the check usable
against a restored backup at all: the backup is behind on payments by
construction, and pretending otherwise would either bury real problems or cry
wolf every hour.

Payment moving *backwards* is the one case with no benign reading — it means a
voucher was cancelled after the backup. It is not waved through: the document
has to be named explicitly (`allowed_reversals`), so a human has looked at it.

Read-only throughout: REST `/list` and SQL `SELECT`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from ..nama.client import NamaClient, is_draft

ENTITIES = {
    "SalesInvoice": ("Customer", "AR"),
    "PurchaseInvoice": ("Supplier", "AP"),
}

#: A rounding gap this size is arithmetic, not a discrepancy. Nama rounds per
#: line; summing the lines and rounding the sum are not the same operation, and
#: the measured spread over 302 documents was 1.49 EGP in total.
TOLERANCE = 1.00

_SQL = """
SELECT code,
       CONVERT(varchar(10), issueDate, 23) AS issueDate,
       CAST(total     AS FLOAT) AS total,
       CAST(netValue  AS FLOAT) AS netValue,
       CAST(totalPaid AS FLOAT) AS totalPaid,
       documentFileStatus
FROM {entity}
WHERE documentFileStatus = 'Stable'
"""

_SQL_PERIOD = " AND issueDate >= ? AND issueDate < ?"


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


def period_bounds(period: str) -> tuple[str, str, str, str]:
    """SQL ISO bounds + Nama DD-MM-YYYY bounds for a YYYYMM period."""
    if len(period) != 6 or not period.isdigit():
        raise ValueError("period must be YYYYMM, e.g. 202606")
    year, month = int(period[:4]), int(period[4:])
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return (
        start.isoformat(),
        end.isoformat(),
        start.strftime("%d-%m-%Y"),
        end.strftime("%d-%m-%Y"),
    )


def closed_period(today: date, *, months_back: int = 2) -> str:
    """A YYYYMM far enough back that no new invoice will be issued into it.

    Two months by default. One month back is not safe: an invoice dated the last
    day of a month can be entered days later, so "last month" is still moving.
    Going back further only makes the window staler without making it safer.
    """
    year, month = today.year, today.month - months_back
    while month < 1:
        month += 12
        year -= 1
    return f"{year}{month:02d}"


def _iso(value: str | None) -> str:
    if not value:
        return "?"
    if len(value) == 10 and value[2] == "-" and value[5] == "-":
        day, month, year = value.split("-")
        return f"{year}-{month}-{day}"
    return value


def _keyed(rows: list[dict], *, rest: bool) -> dict[str, dict]:
    """Preserve duplicate codes by keying on code + date + stable ordinal.

    Nama reuses invoice numbers across legal entities: S2026070001 and
    S2026070002 each exist twice live. Keying on `{code: row}` silently erased
    two real documents — exactly the kind of false pass this control exists to
    prevent.
    """
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        code = (row.get("code") or "").strip()
        if not code:
            continue
        groups[(code, _iso(row.get("issueDate")))].append(row)

    keyed: dict[str, dict] = {}
    for (code, issued), members in groups.items():
        if rest:
            members.sort(key=lambda row: document_money(row)[:2])
        else:
            members.sort(key=lambda row: (row.get("total") or 0, row.get("netValue") or 0))
        for ordinal, row in enumerate(members, start=1):
            keyed[f"{code}|{issued}|{ordinal}"] = row
    return keyed


def sql_rows(fin, entity: str, period: str | None) -> dict[str, dict]:
    """Posted documents from the restored database, keyed like the REST side."""
    sql = _SQL.format(entity=entity) + (_SQL_PERIOD if period else "")
    params: tuple = ()
    if period:
        start, end, _, _ = period_bounds(period)
        params = (start, end)
    return _keyed(fin._rows(sql, params), rest=False)


async def rest_rows(
    client: NamaClient, entity: str, period: str | None
) -> tuple[dict, list[str], list[dict]]:
    """Every identifiable posted document, preserving duplicate codes.

    Drafts are dropped here rather than filtered in the query: Nama's
    `textCriteria` has no operator for "code does not end with", and doing it
    client-side keeps the one definition of "unposted" (`is_draft`) that the
    rest of the app uses.
    """
    criteria = None
    if period:
        _, _, start, end = period_bounds(period)
        criteria = (
            f"issueDate,GreaterThanOrEqual,{start},AND;"
            f"issueDate,LessThan,{end},AND;"
        )
    out = await client.list_all(entity, text_criteria=criteria)
    posted: list[dict] = []
    invalid: list[dict] = []
    for index, rec in enumerate(out["records"], start=1):
        if is_draft(rec):
            continue
        code = (rec.get("code") or "").strip()
        if not code or not rec.get("details"):
            invalid.append({
                "index": index,
                "issueDate": rec.get("issueDate"),
                "reason": "missing code" if not code else "missing details",
            })
            continue
        posted.append(rec)
    return _keyed(posted, rest=True), out["inaccessible"], invalid


def compare(
    sql: dict[str, dict],
    rest: dict[str, dict],
    *,
    strict: bool,
    allowed_reversals: set[str] | None = None,
) -> dict[str, Any]:
    allowed_reversals = allowed_reversals or set()
    explained: list[dict] = []
    unexplained: list[dict] = []
    checked = 0

    for key in sorted(sql.keys() & rest.keys()):
        s, r = sql[key], rest[key]
        gross, net, paid = document_money(r)
        checked += 1
        d_gross = gross - s["total"]
        d_net = net - s["netValue"]
        d_paid = paid - s["totalPaid"]
        if max(abs(d_gross), abs(d_net), abs(d_paid)) <= TOLERANCE:
            continue
        row = {"key": key, "code": r.get("code"), "issueDate": r.get("issueDate"),
               "dGross": round(d_gross, 2),
               "dNet": round(d_net, 2), "dPaid": round(d_paid, 2),
               "sqlNet": s["netValue"], "restNet": round(net, 2),
               "sqlPaid": s["totalPaid"], "restPaid": round(paid, 2)}
        settled_since_backup = (
            not strict
            and abs(d_gross) <= TOLERANCE
            and abs(d_net) <= TOLERANCE
            and d_paid > TOLERANCE
        )
        reviewed_reversal = (
            not strict
            and abs(d_gross) <= TOLERANCE
            and abs(d_net) <= TOLERANCE
            and d_paid < -TOLERANCE
            and (r.get("code") or "") in allowed_reversals
        )
        if settled_since_backup or reviewed_reversal:
            row["reason"] = (
                "reviewed payment reversal/cancellation"
                if reviewed_reversal
                else "settled after the backup was taken"
            )
            explained.append(row)
        else:
            row["reason"] = (
                "gross/net moved" if abs(d_gross) > TOLERANCE or abs(d_net) > TOLERANCE
                else "payment moved backwards — a voucher was cancelled or reversed"
            )
            unexplained.append(row)

    # A document on one side and not the other is never "a small difference".
    only_sql = sorted(sql.keys() - rest.keys())
    only_rest = sorted(rest.keys() - sql.keys())
    return {"checked": checked, "explained": explained, "unexplained": unexplained,
            "onlyInSql": only_sql, "onlyInRest": only_rest}


def verdict(result: dict[str, Any]) -> tuple[bool, str]:
    """(clean, one-line reason) for a single entity's comparison.

    Named so the guard and the CLI agree on what "failed" means. A document
    present on one side only counts, and counts loudly: it is how a narrowed
    credential or a changed posting convention shows up, and unlike a value
    difference it never has a benign reading.
    """
    bad_docs = len(result["unexplained"])
    only_sql, only_rest = len(result["onlyInSql"]), len(result["onlyInRest"])
    if not (bad_docs or only_sql or only_rest):
        return True, f"{result['checked']} documents agree"
    parts = []
    if bad_docs:
        parts.append(f"{bad_docs} unexplained difference(s)")
    if only_sql:
        parts.append(f"{only_sql} in SQL but absent from REST")
    if only_rest:
        parts.append(f"{only_rest} in REST but absent from SQL")
    return False, " · ".join(parts)
