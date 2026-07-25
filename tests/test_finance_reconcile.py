"""The repeatable live-vs-SQL control must not create false passes."""
from scripts.reconcile_live_vs_sql import _keyed, compare, period_bounds


def test_period_uses_real_issue_date_bounds_not_a_missing_fiscal_period_column():
    assert period_bounds("202612") == (
        "2026-12-01", "2027-01-01", "01-12-2026", "01-01-2027"
    )


def test_reconciliation_preserves_duplicate_document_codes():
    rows = [
        {"code": "S1", "issueDate": "01-07-2026",
         "details": [{"price": {"price": 10, "netValue": 10}}]},
        {"code": "S1", "issueDate": "01-07-2026",
         "details": [{"price": {"price": 20, "netValue": 20}}]},
    ]
    assert len(_keyed(rows, rest=True)) == 2


def test_a_reversal_needs_an_explicit_reviewed_code():
    key = "P1|2026-06-01|1"
    sql = {key: {"code": "P1", "issueDate": "2026-06-01",
                 "total": 100, "netValue": 100, "totalPaid": 100}}
    rest = {key: {"code": "P1", "issueDate": "01-06-2026",
                  "details": [{"price": {"price": 100, "netValue": 100}}],
                  "externalPaymentLines": []}}
    blocked = compare(sql, rest, strict=False)
    assert len(blocked["unexplained"]) == 1

    reviewed = compare(sql, rest, strict=False, allowed_reversals={"P1"})
    assert not reviewed["unexplained"]
    assert reviewed["explained"][0]["reason"] == "reviewed payment reversal/cancellation"
