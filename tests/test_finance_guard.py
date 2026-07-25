"""The drift guard: what it must catch, and what it must not cry wolf over.

The figure is live and the sweep repeats hourly. These tests hold in place the
three ways a *successful* sweep can still come back wrong, and the two ways an
over-eager guard would take finance offline for no reason.
"""
import pytest

from app.config import Settings
from app.integrations.finance.guard import DRIFT, PASS, UNKNOWN, DriftGuard, compare_entity
from app.integrations.finance.reconcile import closed_period, period_bounds, verdict
from app.integrations.finance.router import _source
from datetime import date


def _bare(**kw):
    return Settings(_env_file=None, **kw)


def _sql(key, *, total, net, paid, code=None, issued="2026-05-04"):
    return {key: {"code": code or key.split("|")[0], "issueDate": issued,
                  "total": total, "netValue": net, "totalPaid": paid}}


def _rest(key, *, gross, net, paid, code=None, issued="04-05-2026"):
    return {key: {"code": code or key.split("|")[0], "issueDate": issued,
                  "details": [{"price": {"price": gross, "netValue": net}}],
                  "externalPaymentLines": ([{"paymentValue": paid}] if paid else [])}}


# --- the window -------------------------------------------------------------

def test_the_window_is_two_months_back_not_last_month():
    """An invoice dated the last day of a month can be entered days later, so
    "last month" is still moving and would drift for no reason."""
    assert closed_period(date(2026, 7, 25)) == "202605"
    assert closed_period(date(2026, 2, 3)) == "202512"
    assert closed_period(date(2026, 1, 9)) == "202511"


def test_the_window_is_one_month_wide():
    assert period_bounds("202605")[:2] == ("2026-05-01", "2026-06-01")
    assert period_bounds("202612")[:2] == ("2026-12-01", "2027-01-01")


# --- what must be caught ----------------------------------------------------

def test_a_renamed_value_field_reads_as_drift_not_as_a_smaller_company():
    """If Nama renames `netValue`, the line sums to nothing and no error is
    raised — the total just comes out short. That is the failure this exists for."""
    sql = _sql("S1|2026-05-04|1", total=100, net=114, paid=0)
    rest = {"S1|2026-05-04|1": {"code": "S1", "issueDate": "04-05-2026",
                                "details": [{"price": {"price": 100}}],  # netValue gone
                                "externalPaymentLines": []}}
    ok, reason = verdict(compare_entity(sql, rest, set()))
    assert ok is False and "unexplained" in reason


def test_a_document_the_credential_can_no_longer_read_is_drift():
    """A narrowed permission never shows up as a value difference — the document
    simply stops arriving, and the sum quietly loses it."""
    sql = {**_sql("S1|2026-05-04|1", total=100, net=100, paid=0),
           **_sql("S2|2026-05-05|1", total=900, net=900, paid=0, issued="2026-05-05")}
    rest = _rest("S1|2026-05-04|1", gross=100, net=100, paid=0)
    ok, reason = verdict(compare_entity(sql, rest, set()))
    assert ok is False and "absent from REST" in reason


def test_an_extra_document_on_the_live_side_is_drift():
    """The mirror case: a draft that stops being marked as one starts being
    summed as posted, and the total comes out too big."""
    sql = _sql("S1|2026-05-04|1", total=100, net=100, paid=0)
    rest = {**_rest("S1|2026-05-04|1", gross=100, net=100, paid=0),
            **_rest("S9|2026-05-06|1", gross=5000, net=5000, paid=0, issued="06-05-2026")}
    ok, reason = verdict(compare_entity(sql, rest, set()))
    assert ok is False and "absent from SQL" in reason


# --- what must NOT be flagged ----------------------------------------------

def test_a_payment_arriving_after_the_backup_is_not_drift():
    """The comparison is production against a restored copy, so the copy is
    behind on payments by construction. A closed month still collects: flagging
    that would make the guard fire every hour and teach everyone to ignore it."""
    sql = _sql("S1|2026-05-04|1", total=100, net=100, paid=0)
    rest = _rest("S1|2026-05-04|1", gross=100, net=100, paid=100)
    result = compare_entity(sql, rest, set())
    ok, _ = verdict(result)
    assert ok is True
    assert result["explained"][0]["reason"] == "settled after the backup was taken"


def test_rounding_below_a_pound_is_arithmetic_not_a_discrepancy():
    sql = _sql("S1|2026-05-04|1", total=100, net=114.00, paid=0)
    rest = _rest("S1|2026-05-04|1", gross=100, net=114.40, paid=0)
    assert verdict(compare_entity(sql, rest, set()))[0] is True


def test_a_payment_moving_backwards_needs_a_named_document():
    """A cancelled voucher is real but has no benign reading, so it does not pass
    on its own — someone has to have looked at it."""
    sql = _sql("P1|2026-05-04|1", total=100, net=100, paid=100)
    rest = _rest("P1|2026-05-04|1", gross=100, net=100, paid=0)
    assert verdict(compare_entity(sql, rest, set()))[0] is False
    assert verdict(compare_entity(sql, rest, {"P1"}))[0] is True


# --- the verdict, and what it does to reads --------------------------------

def test_no_check_yet_is_unknown_and_does_not_divert_reads():
    """Being unable to check is not evidence the figure is wrong. Treating it as
    drift would take finance offline for a reason unrelated to finance."""
    DriftGuard.reset()
    assert DriftGuard.status() == UNKNOWN
    assert DriftGuard.drifted() is False
    assert _source(None, _bare(finance_default_source="live")) == "live"


def test_drift_diverts_the_default_to_sql():
    DriftGuard.reset()
    DriftGuard._state = {"status": DRIFT, "reason": "AR: 3 unexplained difference(s)"}
    try:
        assert _source(None, _bare(finance_default_source="live")) == "sql"
        # ...but never overrides someone asking for the live figure by name:
        # that is how you look at the thing that broke.
        assert _source("live", _bare(finance_default_source="live")) == "live"
    finally:
        DriftGuard.reset()


def test_a_pass_leaves_the_live_default_alone():
    DriftGuard.reset()
    DriftGuard._state = {"status": PASS, "reason": "AR: 214 documents agree"}
    try:
        assert _source(None, _bare(finance_default_source="live")) == "live"
    finally:
        DriftGuard.reset()


def test_the_verdict_travels_with_the_figure():
    """Age has been visible for a while; correctness was not. Both are claims,
    and only one of them was being made."""
    from app.integrations.finance.live import LiveFinance

    DriftGuard.reset()
    LiveFinance._snapshot = None
    fresh = LiveFinance.freshness()
    assert fresh["guard"]["status"] == UNKNOWN


@pytest.mark.asyncio
async def test_an_unconfigured_guard_reports_unknown_never_pass():
    """Nothing may conclude the numbers are fine because it could not look."""
    DriftGuard.reset()
    out = await DriftGuard(_bare()).check()
    assert out["status"] == UNKNOWN and "not configured" in out["reason"]
    DriftGuard.reset()


@pytest.mark.asyncio
async def test_a_disabled_guard_is_unknown_too():
    DriftGuard.reset()
    out = await DriftGuard(_bare(finance_guard_enabled=False)).check()
    assert out["status"] == UNKNOWN and "disabled" in out["reason"]
    DriftGuard.reset()


def test_reversals_are_configured_as_a_list_the_guard_can_read():
    """The CLI took --allow-reversal as an argument; an automatic guard has no
    command line, so the reviewed cancellations have to live in config."""
    s = _bare(finance_allowed_reversals="FP22026060000105, S2025010001 ,")
    assert s.allowed_reversals == {"FP22026060000105", "S2025010001"}
    assert Settings(_env_file=None).allowed_reversals == {"FP22026060000105"}
