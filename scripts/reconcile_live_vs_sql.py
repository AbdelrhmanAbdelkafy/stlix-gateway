"""Reconcile the live REST balance against SQL, document by document.

The rule this exists to enforce: **no money figure ships before it matches SQL
for the same period.** That was checked once, by hand, over June 2026. A check
you cannot re-run is a claim, not a control — so it lives here instead, and it
fails loudly.

What it compares
----------------
For every invoice in the window, the figure Nama's SQL tables hold against the
one rebuilt from the REST document:

    gross = SUM(details[].price.price)            vs  SalesInvoice.total
    net   = SUM(details[].price.netValue)         vs  SalesInvoice.netValue
    paid  = SUM(externalPaymentLines[].paymentValue) vs SalesInvoice.totalPaid

Which differences are allowed
-----------------------------
Depends on what REST is pointed at, and the script will not let you confuse the
two:

* ``--rest local`` — REST and SQL read the *same* database. Nothing may differ.
  Any difference at all is a bug in the reconstruction. This is the strict mode
  and the one to run first.
* ``--rest cloud`` — REST is the live tenant, SQL is a restored backup taken
  days earlier. `paid` may legitimately have grown since the backup; that is a
  settlement, and it is reported as *explained*. Everything else is unexplained:
  gross or net moving at all, or `paid` moving **backwards** (which means a
  voucher was cancelled after the backup — real, but not something to wave
  through silently: it is printed by document code so it can be looked at).

Exit code is 0 only when there is nothing unexplained.

Read-only throughout: REST `/list` and SQL `SELECT`. Neither can write.

Usage
-----
    .venv/Scripts/python.exe scripts/reconcile_live_vs_sql.py --rest local
    .venv/Scripts/python.exe scripts/reconcile_live_vs_sql.py --rest cloud --period 202606 \
        --allow-reversal FP22026060000105
    .venv/Scripts/python.exe scripts/reconcile_live_vs_sql.py --rest cloud --all --json out.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings  # noqa: E402
from app.integrations.finance.connector import FinanceConnector, pyodbc  # noqa: E402
from app.integrations.nama.client import NamaClient, is_draft  # noqa: E402
from app.integrations.finance.live import document_money  # noqa: E402

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


def period_bounds(period: str) -> tuple[str, str, str, str]:
    """SQL ISO bounds + Nama DD-MM-YYYY bounds for a YYYYMM period."""
    if len(period) != 6 or not period.isdigit():
        raise ValueError("--period must be YYYYMM, e.g. 202606")
    year, month = int(period[:4]), int(period[4:])
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return (
        start.isoformat(),
        end.isoformat(),
        start.strftime("%d-%m-%Y"),
        end.strftime("%d-%m-%Y"),
    )


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
    S2026070002 each exist twice live. The old reconciliation used `{code: row}`
    and silently erased two real documents — exactly the kind of false pass this
    control exists to prevent.
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


def sql_rows(fin: FinanceConnector, entity: str, period: str | None) -> dict[str, dict]:
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


async def run(args) -> int:
    settings: Settings = get_settings()
    if args.rest == "local":
        settings = settings.model_copy(update={"nama_base_url": args.local_base})
    if pyodbc is None:
        print("pyodbc is not installed — SQL side unavailable.", file=sys.stderr)
        return 2
    fin = FinanceConnector(settings)
    if not fin.configured:
        print("Nama SQL is not configured (NAMA_SQL_*).", file=sys.stderr)
        return 2
    client = NamaClient(settings)

    period = None if args.all else args.period
    strict = args.rest == "local"
    print(f"REST: {settings.nama_base}")
    print(f"SQL : {settings.nama_sql_server}/{settings.nama_sql_database}")
    print(f"mode: {'STRICT (same data — nothing may differ)' if strict else 'BACKUP-LAG (later settlements allowed)'}")
    print(f"window: {period or 'ALL PERIODS'}\n")

    failures = 0
    report: dict[str, Any] = {"rest": settings.nama_base, "strict": strict,
                              "period": period, "entities": {}}

    for entity, (_party, label) in ENTITIES.items():
        sql = sql_rows(fin, entity, period)
        rest, inaccessible, invalid = await rest_rows(client, entity, period)
        res = compare(
            sql,
            rest,
            strict=strict,
            allowed_reversals=set(args.allow_reversal),
        )
        res["inaccessible"] = inaccessible
        res["invalid"] = invalid
        report["entities"][entity] = res

        bad = (
            len(res["unexplained"])
            + len(res["onlyInSql"])
            + len(res["onlyInRest"])
            + len(inaccessible)
            + len(invalid)
        )
        failures += bad
        print(f"--- {entity} ({label}) ---")
        print(f"  SQL {len(sql)} posted · REST {len(rest)} posted · compared {res['checked']}")
        print(f"  explained differences : {len(res['explained'])}")
        print(f"  UNEXPLAINED           : {len(res['unexplained'])}")
        print(f"  only in SQL / only in REST: {len(res['onlyInSql'])} / {len(res['onlyInRest'])}")
        if inaccessible:
            print(f"  unreadable by this credential: {len(inaccessible)} -> {inaccessible[:5]}")
        if invalid:
            print(f"  invalid/unidentifiable REST rows: {len(invalid)} -> {invalid[:5]}")
        for row in res["unexplained"][:20]:
            print(f"    ! {row['code']}: dNet={row['dNet']} dPaid={row['dPaid']} ({row['reason']})")
        for code in res["onlyInSql"][:10]:
            print(f"    ! {code}: in SQL, absent from REST")
        for code in res["onlyInRest"][:10]:
            print(f"    ! {code}: in REST, absent from SQL")
        print()

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")

    if failures:
        print(f"RESULT: {failures} unexplained difference(s). Do NOT ship live figures.")
        return 1
    print("RESULT: reconciled. Live figures may be published for this window.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rest", choices=("local", "cloud"), default="cloud",
                   help="local = the Nama instance on this machine, reading the same DB as SQL "
                        "(strict); cloud = the live tenant (later settlements allowed)")
    p.add_argument("--local-base", default="http://localhost:8080/erp/rest/v1",
                   help="REST base used when --rest local")
    p.add_argument("--period", default="202606", help="issue-date month, e.g. 202606")
    p.add_argument("--all", action="store_true",
                   help="every period (full sweep — minutes, thousands of documents)")
    p.add_argument("--json", help="also write the full report to this file")
    p.add_argument(
        "--allow-reversal",
        action="append",
        default=[],
        metavar="CODE",
        help="reviewed voucher cancellation/reversal to classify as explained; repeatable",
    )
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
