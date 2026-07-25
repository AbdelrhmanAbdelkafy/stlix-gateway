"""Live AR/AP rebuilt from Nama documents — the rules that make the sum honest.

The reconstruction itself (net − paid per invoice) was validated against SQL
document by document over June 2026: 302 invoices, zero gross differences, 1.49
EGP of rounding on net, and every paid difference traced to a settlement made
after the backup was taken. What these tests hold in place is the arithmetic
around it — the parts that silently produce a wrong number rather than an error.
"""
import pytest

from app.config import Settings
from app.integrations.finance.live import LiveFinance, document_money, summarise


def _inv(code, lines, payments=(), party=("Customer", "C1"), issued="01-06-2026"):
    return {
        "code": code,
        "issueDate": issued,
        "subsidiary": {"entityType": party[0], "code": party[1]},
        "details": [{"price": p} for p in lines],
        "externalPaymentLines": [{"paymentValue": v} for v in payments],
    }


def test_money_tolerates_omitted_zero_fields():
    """Nama drops zero-valued keys instead of sending 0 — an absent key is not an error."""
    rec = _inv("S1", [{"price": 100, "netValue": 114}, {"price": 50}], payments=[14])
    assert document_money(rec) == (150.0, 114.0, 14.0)


def test_money_ignores_non_numeric_values():
    rec = _inv("S1", [{"price": "n/a", "netValue": 114}])
    assert document_money(rec) == (0.0, 114.0, 0.0)


def test_drafts_are_kept_out_of_the_balance_but_still_reported():
    """`@draft` is an unposted document that shares a posted document's number.

    It sorts first in Nama's default order, so anything sampling the head of the
    list hits it immediately. Dropping it silently would be just as wrong as
    counting it — the count is published alongside.
    """
    out = summarise([
        _inv("S2026030001", [{"price": 100, "netValue": 100}]),
        _inv("S2026030001@draft", [{"price": 5000, "netValue": 5000}]),
    ], "Customer")
    assert out["totals"]["count"] == 1
    assert out["totals"]["open"] == 100
    assert out["drafts"] == {"count": 1, "net": 5000.0}


def test_non_customer_invoices_count_in_the_total_but_not_in_customer_ar():
    """1,016 sales invoices are raised on suppliers, 23 on employees — 9.5M of the
    20.0M open. Real money owed, but not customer receivables, so it is reported
    beside the customer figure instead of inside it."""
    out = summarise([
        _inv("S1", [{"price": 100, "netValue": 100}], party=("Customer", "C1")),
        _inv("S2", [{"price": 900, "netValue": 900}], party=("Supplier", "S9")),
    ], "Customer")
    assert out["totals"]["open"] == 1000
    assert out["scoped"]["open"] == 100
    assert [p["code"] for p in out["parties"]] == ["C1"]


def test_duplicate_document_codes_are_two_documents_not_an_upsert_key():
    out = summarise([
        _inv("S2026070001", [{"price": 10, "netValue": 10}],
             party=("Customer", "C1"), issued="01-07-2026"),
        _inv("S2026070001", [{"price": 20, "netValue": 20}],
             party=("Customer", "C2"), issued="16-07-2026"),
    ], "Customer")
    assert out["totals"]["count"] == 2
    assert out["totals"]["open"] == 30
    assert {row["code"] for row in out["parties"]} == {"C1", "C2"}


def test_parties_are_ranked_by_what_they_still_owe():
    out = summarise([
        _inv("S1", [{"price": 100, "netValue": 100}], payments=[100], party=("Customer", "PAID")),
        _inv("S2", [{"price": 50, "netValue": 50}], party=("Customer", "OWES")),
    ], "Customer")
    assert [p["code"] for p in out["parties"]] == ["OWES", "PAID"]
    assert out["parties"][0]["outstanding"] == 50 and out["parties"][1]["outstanding"] == 0


def test_last_invoice_date_is_iso_and_is_the_latest():
    out = summarise([
        _inv("S1", [{"price": 1, "netValue": 1}], issued="03-02-2026"),
        _inv("S2", [{"price": 1, "netValue": 1}], issued="28-11-2025"),
    ], "Customer")
    assert out["parties"][0]["lastInvoiceDate"] == "2026-02-03"


def test_no_snapshot_is_a_stated_absence_not_a_zero():
    """A missing snapshot must never render as 0 EGP owed."""
    LiveFinance._snapshot = None
    live = LiveFinance(Settings(_env_file=None, nama_client_id="i", nama_client_secret="s"))
    out = live.kpis()
    assert out["available"] is False and "arOutstanding" not in out
    assert live.customer_balances()["records"] == []


@pytest.mark.asyncio
async def test_refresh_reports_what_the_sweep_could_not_read(monkeypatch):
    """Documents the credential is refused are carried with the figure, not dropped."""
    async def fake_list_all(self, entity, **kw):
        return {"entity": entity, "count": 1, "pages": 1,
                "records": [_inv("S1", [{"price": 10, "netValue": 10}])],
                "inaccessible": ["S2024040005"], "complete": False}

    monkeypatch.setattr("app.integrations.nama.client.NamaClient.list_all", fake_list_all)
    live = LiveFinance(Settings(_env_file=None, nama_client_id="i", nama_client_secret="s"))
    snap = await live.refresh()
    assert snap["excludes"]["complete"] is False
    assert live.kpis()["excludedDocuments"] == 2
    LiveFinance._snapshot = None


@pytest.mark.asyncio
async def test_live_reports_keep_the_sql_shape_and_use_master_names(monkeypatch):
    async def fake_list_all(self, entity, **kw):
        if entity == "Customer":
            records = [{"code": "C1", "name1": "عميل واحد"},
                       {"code": "C2", "name1": "عميل بدون فواتير"}]
        elif entity == "Supplier":
            records = [{"code": "S1", "name1": "مورد واحد"}]
        elif entity == "SalesInvoice":
            records = [_inv("SI1", [{"price": 100, "netValue": 114}],
                            payments=[14], party=("Customer", "C1"))]
        else:
            records = [_inv("PI1", [{"price": 50, "netValue": 50}],
                            payments=[10], party=("Supplier", "S1"))]
        return {"entity": entity, "count": len(records), "pages": 1,
                "records": records, "inaccessible": [], "complete": True}

    monkeypatch.setattr("app.integrations.nama.client.NamaClient.list_all", fake_list_all)
    live = LiveFinance(Settings(_env_file=None, nama_client_id="i", nama_client_secret="s"))
    await live.refresh()
    assert live.kpis()["customers"] == 2
    customer = live.customer_balances()["records"][0]
    assert customer["name1"] == "عميل واحد"
    assert customer["salesTotal"] == 100 and customer["collected"] == 14
    supplier = live.supplier_balances()["records"][0]
    assert supplier["name1"] == "مورد واحد"
    assert supplier["purchaseTotal"] == 50 and supplier["paid"] == 10
    LiveFinance._snapshot = None


def test_a_numbered_invoice_without_lines_is_an_anomaly_not_zero_money():
    out = summarise([
        {"code": "P-BROKEN", "issueDate": "03-02-2026",
         "subsidiary": {"entityType": "Supplier", "code": "S1"}},
        _inv("P1", [{"price": 10, "netValue": 11}], party=("Supplier", "S1")),
    ], "Supplier")
    assert out["totals"]["count"] == 1
    assert out["totals"]["open"] == 11
    assert out["invalid"] == [
        {"index": 1, "issueDate": "03-02-2026", "reason": "missing details"}
    ]


def test_an_unnumbered_invoice_never_reaches_the_balance():
    """The draft rule the summary uses is the client's, so both sides agree.

    A PurchaseInvoice with no code at all is unposted — it is simply one Nama
    has not numbered yet. Before `is_draft` required a code, this row was summed
    as posted money.
    """
    out = summarise([
        _inv("P2026030001", [{"price": 100, "netValue": 100}]),
        _inv("", [{"price": 9999, "netValue": 9999}]),
    ], "Customer")
    assert out["totals"]["count"] == 1
    assert out["totals"]["open"] == 100
    assert out["drafts"] == {"count": 1, "net": 9999.0}
