"""CRM (Vtiger) connector: config gating, read-only mode, clean errors.

Uses Settings(_env_file=None) so these checks don't depend on a local .env.
"""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.core.errors import UpstreamError
from app.integrations.base import ReadOnlyError
from app.integrations.crm.connector import CrmConnector
from app.main import app

client = TestClient(app)


def _bare(**kw) -> Settings:
    """Settings with no .env and no OS creds -> deterministic 'unconfigured'."""
    return Settings(_env_file=None, **kw)


def _conn(**kw) -> CrmConnector:
    return CrmConnector(_bare(**kw))


def test_crm_default_read_only():
    assert _bare().crm_mode == "read_only"
    assert _conn().read_only is True


def test_crm_not_configured_without_creds():
    assert _bare().crm_configured is False


def test_crm_configured_when_all_present():
    s = _bare(vtiger_url="https://crm.x", vtiger_username="u", vtiger_access_key="k")
    assert s.crm_configured is True


@pytest.mark.asyncio
async def test_query_raises_clean_error_when_unconfigured():
    with pytest.raises(UpstreamError):
        await _conn().query("Contacts")


@pytest.mark.asyncio
async def test_write_blocked_in_read_only():
    with pytest.raises(ReadOnlyError):
        await _conn().create("Contacts", {"lastname": "x"})


def test_crm_info_endpoint_unconfigured():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        r = client.get("/api/v1/crm?format=json")
        assert r.status_code == 200
        body = r.json()
        assert body["backend"] == "vtiger"
        assert body["configured"] is False
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_crm_query_unconfigured_returns_502():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        r = client.get("/api/v1/crm/contacts?format=json")
        assert r.status_code == 502
        assert "not configured" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_crm_is_live_in_systems():
    systems = client.get("/systems?format=json").json()["systems"]
    crm = next(s for s in systems if s["key"] == "crm")
    assert crm["status"] == "live"
