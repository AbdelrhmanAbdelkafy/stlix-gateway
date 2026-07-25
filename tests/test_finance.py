"""Finance connector: SQL config gating, endpoints, and async data shaping."""
import pytest

from app.config import Settings
from app.integrations.finance import connector as fin_sql
from app.integrations.finance.connector import FinanceConnector
from app.main import app


def _bare(**kw):
    return Settings(_env_file=None, **kw)


def test_sql_config_gating():
    assert _bare().nama_sql_configured is False
    assert _bare(nama_sql_server="localhost", nama_sql_user="u",
                 nama_sql_password="p").nama_sql_configured is True


def test_finance_endpoints_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/finance/kpis" in paths
    assert "/api/v1/finance/customers" in paths
    assert "/api/v1/finance/suppliers" in paths


@pytest.mark.asyncio
async def test_unconfigured_is_pending_not_error():
    out = await FinanceConnector(_bare()).customer_balances()
    assert out["available"] is False and "not configured" in out["reason"]


def test_balances_join_on_the_real_party_and_exclude_drafts():
    """The party lives in `subsidiaryId`, not `customer_id`/`supplier_id`.

    `customer_id` is NULL on 5,263 of 6,845 posted sales invoices, so joining on
    it hid 19.8M of the 20.0M open AR and made the report look like a data-quality
    problem. `subsidiaryId` matches all 5,806 customer-typed invoices. Drafts are
    ordinary rows in these tables and must be excluded, or unposted documents get
    summed with posted ones.
    """
    for sql in (fin_sql._CUSTOMERS, fin_sql._SUPPLIERS):
        assert "subsidiaryId" in sql
        assert "customer_id" not in sql and "supplier_id" not in sql
        assert "documentFileStatus = 'Stable'" in sql
        assert "subsidiaryEntityType" in sql
    # KPIs must never mix drafts in, and must publish the customer/supplier slice
    # next to the total — the two disagree by ~9.5M of non-customer counterparties.
    assert fin_sql._KPIS.count("documentFileStatus='Stable'") >= 8
    assert "arFromCustomers" in fin_sql._KPIS and "apToSuppliers" in fin_sql._KPIS


@pytest.mark.asyncio
async def test_customer_balances_shape(monkeypatch):
    fin = FinanceConnector(_bare(nama_sql_server="x", nama_sql_user="u", nama_sql_password="p"))
    # bypass the real DB: stub the sync query with sample rows
    monkeypatch.setattr(fin, "_rows", lambda sql, params=(): [
        {"code": "C1000001", "name1": "MARS", "outstanding": 120996}])
    out = await fin.customer_balances(limit=5)
    assert out["available"] is True and out["source"] == "nama_sql"
    assert out["records"][0]["code"] == "C1000001"


def test_the_default_source_is_configuration_not_a_constant():
    """Moving the platform onto live figures has to be one switch, both ways.

    `sql` ships as the default so live figures cannot go out before
    `scripts/reconcile_live_vs_sql.py` has passed on the machine serving them.
    """
    from app.integrations.finance.router import _source

    sql_default = _bare(finance_default_source="sql")
    live_default = _bare(finance_default_source="live")
    assert Settings(_env_file=None).finance_default_source == "sql"
    assert _source(None, sql_default) == "sql"
    assert _source(None, live_default) == "live"
    # An explicit ?source= always wins, so a page can pin its own source.
    assert _source("live", sql_default) == "live"
    assert _source("sql", live_default) == "sql"
