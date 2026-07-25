"""Does the live figure still add up? Checked after every sweep.

The reconciliation proved the method once, at 0.17 EGP on AR and 0.16 on AP.
Then the platform was switched onto live figures and the sweep started repeating
hourly with nothing verifying it again. Three things can change underneath a
sweep that is otherwise succeeding:

* **Nama changes a field.** `maxRecords` turned out to be ignored; `fiscalPeriod`
  turned out not to be a column. A renamed `netValue` would not raise — the line
  would simply read as nothing, and the total would come out smaller.
* **The credential loses reach.** Documents start answering "not accessible from
  this context" and drop out of the sum.
* **A posting convention changes.** One unposted PurchaseInvoice already carries
  no `@draft` and no code at all. A new variant would be summed as posted, and
  the total would come out *larger*.

In all three the sweep succeeds, returns a number, and the page shows it with a
fresh timestamp. Age was made visible months ago. Correctness was not: a figure
that is quietly short looks exactly like a figure after a good week of
collections.

So: re-reconcile one closed month after each sweep and publish the verdict beside
the money. A month two back is used because no new invoice will be issued into
it and because it is a few hundred documents rather than fourteen thousand — the
check has to be cheap enough to run every time, or it will end up running never.

On `drift` the reads fall back to the restored database **and say so**. A
complete figure that is a few days old beats a live figure missing an unknown
slice of itself.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from starlette.concurrency import run_in_threadpool

from ...config import Settings
from ..nama.client import NamaClient
from .connector import FinanceConnector
from .reconcile import ENTITIES, closed_period, rest_rows, sql_rows, verdict

log = logging.getLogger("stlix.finance.guard")

PASS = "pass"
DRIFT = "drift"
UNKNOWN = "unknown"


class DriftGuard:
    """One verdict, refreshed by the sweep loop, read by every finance response."""

    _state: dict[str, Any] | None = None
    _lock = asyncio.Lock()

    # --- reading -----------------------------------------------------------
    @classmethod
    def state(cls) -> dict[str, Any]:
        if cls._state is None:
            return {"status": UNKNOWN, "reason": "not checked yet"}
        return cls._state

    @classmethod
    def status(cls) -> str:
        return cls.state()["status"]

    @classmethod
    def drifted(cls) -> bool:
        """Only an actual `drift` diverts reads.

        `unknown` deliberately does not: the guard being unavailable (no SQL on
        this host, first boot, a network blip) is not evidence that the figure is
        wrong, and treating it as such would take finance offline for a reason
        that has nothing to do with finance.
        """
        return cls.status() == DRIFT

    @classmethod
    def reset(cls) -> None:
        cls._state = None

    # --- checking ----------------------------------------------------------
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fin = FinanceConnector(settings)
        self.configured = settings.nama_configured and self.fin.configured

    def period(self, today: date | None = None) -> str:
        return self.settings.finance_guard_period or closed_period(today or date.today())

    async def check(self, today: date | None = None) -> dict[str, Any]:
        """Re-reconcile the closed window and publish the verdict.

        A failure to *run* the check is reported as `unknown`, never as `pass`.
        Nothing here can conclude that the numbers are fine because it could not
        look at them.
        """
        if not self.settings.finance_guard_enabled:
            return self._publish(UNKNOWN, "guard disabled (FINANCE_GUARD_ENABLED=false)")
        if not self.configured:
            missing = "Nama REST" if not self.settings.nama_configured else "Nama SQL"
            return self._publish(UNKNOWN, f"cannot check: {missing} is not configured")

        period = self.period(today)
        async with self._lock:
            try:
                return await self._run(period)
            except Exception as exc:  # noqa: BLE001 — a watchdog must outlive its errors
                log.warning("drift check failed for %s: %s", period, exc)
                return self._publish(UNKNOWN, f"check errored: {exc}", period=period)

    async def _run(self, period: str) -> dict[str, Any]:
        client = NamaClient(self.settings)
        allowed = self.settings.allowed_reversals
        entities: dict[str, Any] = {}
        clean = True
        reasons: list[str] = []

        for entity, (_party, label) in ENTITIES.items():
            sql = await run_in_threadpool(sql_rows, self.fin, entity, period)
            rest, inaccessible, invalid = await rest_rows(client, entity, period)
            result = compare_entity(sql, rest, allowed)
            ok, reason = verdict(result)
            # Unreadable documents are a narrowing credential caught in the act;
            # they never show up as a value difference, so they are judged here.
            if inaccessible:
                ok = False
                reason = f"{reason} · {len(inaccessible)} document(s) unreadable by this credential"
            clean = clean and ok
            reasons.append(f"{label}: {reason}")
            entities[entity] = {
                "label": label,
                "ok": ok,
                "reason": reason,
                "checked": result["checked"],
                "sqlDocuments": len(sql),
                "restDocuments": len(rest),
                "explained": len(result["explained"]),
                "unexplained": result["unexplained"][:10],
                "onlyInSql": result["onlyInSql"][:10],
                "onlyInRest": result["onlyInRest"][:10],
                "inaccessible": inaccessible[:10],
                "unidentifiable": invalid[:10],
            }

        return self._publish(PASS if clean else DRIFT, " · ".join(reasons),
                             period=period, entities=entities)

    def _publish(self, status: str, reason: str, *, period: str | None = None,
                 entities: dict | None = None) -> dict[str, Any]:
        state = {
            "status": status,
            "reason": reason,
            "period": period,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checked_at_epoch": time.time(),
        }
        if entities:
            state["entities"] = entities
        if status == DRIFT:
            log.error("LIVE FIGURES DRIFTED (%s): %s — falling back to SQL", period, reason)
        type(self)._state = state
        return state


def compare_entity(sql: dict, rest: dict, allowed_reversals: set[str]) -> dict[str, Any]:
    """`compare` with the guard's own standard.

    `strict=False` on purpose, and it is the substance of the check rather than a
    loosening of it. The comparison is production REST against a restored backup,
    so a payment that has grown since the restore is a settlement — real,
    expected, and not a defect. What must not move for a closed month is the set
    of documents and each one's gross and net. That is what this catches.
    """
    from .reconcile import compare

    return compare(sql, rest, strict=False, allowed_reversals=allowed_reversals)
