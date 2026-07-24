"""Finance connector: SQL config gating, endpoints, and async data shaping."""
import pytest

from app.config import Settings
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


@pytest.mark.asyncio
async def test_customer_balances_shape(monkeypatch):
    fin = FinanceConnector(_bare(nama_sql_server="x", nama_sql_user="u", nama_sql_password="p"))
    # bypass the real DB: stub the sync query with sample rows
    monkeypatch.setattr(fin, "_rows", lambda sql, params=(): [
        {"code": "C1000001", "name1": "MARS", "outstanding": 120996}])
    out = await fin.customer_balances(limit=5)
    assert out["available"] is True and out["source"] == "nama_sql"
    assert out["records"][0]["code"] == "C1000001"
