"""NameBuilder gateway module: tool page, item-builder read endpoints, and the
Nama zero-result quirk (a valid filter matching nothing => HTTP 400 empty body)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.integrations.nama.client import NamaClient
from app.main import app

client = TestClient(app)


def _bare(**kw):
    return Settings(_env_file=None, **kw)


# ---- tool page ----

def test_name_builder_page_served():
    r = client.get("/tools/name-builder")
    assert r.status_code == 200
    assert "NAME BUILDER" in r.text
    # Nama creds must never appear in the served page; the browser only ever
    # sees the (injected) gateway key, never the placeholder or Nama secrets.
    assert "__GATEWAY_API_KEY__" not in r.text
    assert "namasoft.net" not in r.text
    assert "X-API-SECRET" not in r.text


def test_name_builder_endpoints_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/nama/lists/{entity}" in paths
    assert "/api/v1/nama/invitem/exists" in paths


def test_finance_os_page_served():
    r = client.get("/tools/finance-os")
    assert r.status_code == 200
    assert "Finance OS" in r.text
    # gateway key injected; upstream creds never in the page
    assert "__GATEWAY_API_KEY__" not in r.text
    assert "namasoft.net" not in r.text
    # the two new roles are present
    assert "OPERATOR" in r.text and "PRESIDENT" in r.text


# ---- Nama zero-result quirk (unit, mocked transport) ----

class _Resp:
    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _patch_transport(monkeypatch, resp: _Resp):
    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **k):
            return resp

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)


@pytest.mark.asyncio
async def test_find_first_zero_result_is_none(monkeypatch):
    # Nama answers a valid but empty filter with HTTP 400 + empty body.
    _patch_transport(monkeypatch, _Resp(400, {}))
    got = await NamaClient(_bare()).find_first("InvItem", text_criteria="description1,Equal,NOPE,AND;")
    assert got is None


@pytest.mark.asyncio
async def test_find_first_hit_returns_record(monkeypatch):
    _patch_transport(monkeypatch, _Resp(200, {"records": {"InvItem": [{"code": "Inv000001"}]}}))
    got = await NamaClient(_bare()).find_first("InvItem", text_criteria="code,Equal,Inv000001,AND;")
    assert got == {"code": "Inv000001"}
