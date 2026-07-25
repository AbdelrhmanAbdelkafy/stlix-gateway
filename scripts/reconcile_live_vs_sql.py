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
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings  # noqa: E402
from app.integrations.finance.connector import FinanceConnector, pyodbc  # noqa: E402
from app.integrations.nama.client import NamaClient  # noqa: E402

# The comparison itself lives in the app, not here, because the drift guard runs
# the same code after every sweep. Two copies of "what counts as a difference"
# would eventually disagree, and the one that mattered would be whichever nobody
# was reading. Re-exported so the CLI's own names keep working.
from app.integrations.finance.reconcile import (  # noqa: E402,F401
    ENTITIES,
    TOLERANCE,
    _keyed,
    compare,
    document_money,
    period_bounds,
    rest_rows,
    sql_rows,
    verdict,
)


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
