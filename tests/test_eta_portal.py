"""The portal's whole surface through our API — and the lock on the two writes."""
from __future__ import annotations

import json

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app import config

ENT = [{"key": "group", "name": "المجموعة", "client_id": "cid", "client_secret": "sec",
        "k_manufacturing": 7, "k_trading": 1}]
GW = {"X-API-Key": "gw-key-123456"}
ID = "https://id.eta.gov.eg/connect/token"
API = "https://api.invoicing.eta.gov.eg/api/v1.0"


@pytest.fixture
def eta(tmp_path, monkeypatch):
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps(ENT))
    monkeypatch.setenv("ETA_DB_PATH", str(tmp_path / "eta.db"))
    monkeypatch.setenv("VAT_DB_PATH", str(tmp_path / "vat.db"))
    monkeypatch.setenv("GATEWAY_API_KEY", "gw-key-123456")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr("app.integrations.eta.portal.THROTTLE_S", 0)
    monkeypatch.setattr("app.integrations.eta.client.THROTTLE_S", 0)
    config.get_settings.cache_clear()
    from app.main import create_app
    yield TestClient(create_app())
    config.get_settings.cache_clear()


def _token():
    respx.post(ID).mock(return_value=Response(200, json={"access_token": "tok", "expires_in": 3600}))


@respx.mock
def test_reads_reach_the_real_portal_paths(eta):
    _token()
    respx.get(f"{API}/documents/recent").mock(return_value=Response(200, json={
        "result": [{"internalId": "INV-1", "total": 1140, "status": "Valid"}],
        "metadata": {"totalCount": 1}}))
    respx.get(f"{API}/notifications").mock(return_value=Response(200, json={"result": [{"id": 1}]}))
    respx.get(f"{API}/documenttypes").mock(return_value=Response(200, json={"result": [{"name": "I"}]}))
    respx.get(f"{API}/documents/u1/raw").mock(return_value=Response(200, json={"transformationStatus": "original"}))
    respx.get(f"{API}/documents/u1/pdf").mock(return_value=Response(200, content=b"%PDF-1.7 x"))

    assert eta.get("/api/v1/eta/group/recent", headers=GW).json()["result"][0]["internalId"] == "INV-1"
    assert eta.get("/api/v1/eta/group/notifications", headers=GW).status_code == 200
    assert eta.get("/api/v1/eta/group/document-types", headers=GW).status_code == 200
    assert eta.get("/api/v1/eta/group/documents/u1", headers=GW).json()["transformationStatus"] == "original"
    pdf = eta.get("/api/v1/eta/group/documents/u1/pdf", headers=GW)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


@respx.mock
def test_a_month_package_is_requested_listed_and_downloaded(eta):
    _token()
    seen = {}

    def _req(request):
        seen["body"] = json.loads(request.content)
        return Response(201, json={"requestId": "pkg-9"})
    respx.post(f"{API}/documentpackages/requests").mock(side_effect=_req)
    respx.get(f"{API}/documentpackages/requests").mock(return_value=Response(200, json={
        "result": [{"requestId": "pkg-9", "status": "Ready"}]}))
    respx.get(f"{API}/documentPackages/pkg-9").mock(return_value=Response(200, content=b"PK\x03\x04zip"))

    r = eta.post("/api/v1/eta/group/packages", json={"month": "2026-08"}, headers=GW)
    assert r.status_code == 200 and r.json()["requestId"] == "pkg-9"
    q = seen["body"]["queryParameters"]
    assert q["dateFrom"].startswith("2026-08-01") and q["dateTo"].startswith("2026-08-31")
    assert eta.get("/api/v1/eta/group/packages", headers=GW).json()["result"][0]["status"] == "Ready"
    z = eta.get("/api/v1/eta/group/packages/pkg-9", headers=GW)
    assert z.status_code == 200 and z.content.startswith(b"PK")
    assert eta.post("/api/v1/eta/group/packages", json={}, headers=GW).status_code == 400


@respx.mock
def test_cancel_is_refused_while_the_switch_is_off(eta):
    _token()
    route = respx.put(f"{API}/documents/state/u1/state").mock(return_value=Response(200, json={}))
    r = eta.put("/api/v1/eta/group/documents/u1/state",
                json={"status": "cancelled", "reason": "بيانات المشتري غلط"}, headers=GW)
    assert r.status_code == 403 and "ETA_ALLOW_STATE_CHANGES" in r.json()["detail"]
    assert not route.called, "nothing may reach the portal while the switch is off"


@respx.mock
def test_cancel_needs_a_named_reason_even_when_allowed(eta, monkeypatch):
    monkeypatch.setenv("ETA_ALLOW_STATE_CHANGES", "true")
    config.get_settings.cache_clear()
    _token()
    route = respx.put(f"{API}/documents/state/u1/state").mock(return_value=Response(200, json={"ok": True}))
    assert eta.put("/api/v1/eta/group/documents/u1/state", json={"status": "cancelled"}, headers=GW).status_code == 400
    assert eta.put("/api/v1/eta/group/documents/u1/state",
                   json={"status": "burned", "reason": "لأ"}, headers=GW).status_code == 400
    assert not route.called
    ok = eta.put("/api/v1/eta/group/documents/u1/state",
                 json={"status": "cancelled", "reason": "بيانات المشتري غلط", "month": "2026-08"}, headers=GW)
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"
    body = json.loads(route.calls[0].request.content)
    assert body == {"status": "cancelled", "reason": "بيانات المشتري غلط"}
    # and it is on the record, not just on the portal
    log = eta.get("/api/v1/vat/log?entity=group", headers=GW).json()["log"]
    assert any("cancelled u1" in (l["detail"] or "") for l in log)


@respx.mock
def test_portal_errors_surface_as_502_not_as_silence(eta):
    _token()
    respx.get(f"{API}/documents/recent").mock(return_value=Response(403, text="forbidden"))
    r = eta.get("/api/v1/eta/group/recent", headers=GW)
    assert r.status_code == 502 and "403" in r.json()["detail"]


def test_unknown_and_unconfigured_entities(eta, monkeypatch):
    assert eta.get("/api/v1/eta/nope/recent", headers=GW).status_code == 404
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps([dict(ENT[0], client_id="", client_secret="")]))
    config.get_settings.cache_clear()
    assert eta.get("/api/v1/eta/group/recent", headers=GW).status_code == 503


def test_submission_is_not_offered_anywhere(eta):
    """Issuing needs the eSeal on a hardware token — the gateway must not pretend."""
    from app import catalog
    assert not [e for e in catalog.ENDPOINTS if "submit" in e.path.lower()]
    from app.integrations.eta.client import EtaClient
    assert not any(m.startswith("submit") for m in dir(EtaClient))


# --- the endpoint ETA calls back, which registration itself depends on -----------
def _cb(client, key="cb-secret-123", rin="123456789", auth=True):
    h = {"Authorization": f"ApiKey {key}"} if auth else {}
    return client.put("/eta/erp/ping", json={"rin": rin}, headers=h)


def test_eta_ping_echoes_our_rin_and_needs_its_own_key(eta, monkeypatch):
    monkeypatch.setenv("ETA_ERP_CALLBACK_KEY", "cb-secret-123")
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps([dict(ENT[0], rin="123456789")]))
    config.get_settings.cache_clear()
    r = _cb(eta)
    assert r.status_code == 200 and r.json() == {"rin": "123456789"}
    assert _cb(eta, auth=False).status_code == 401
    assert _cb(eta, key="wrong").status_code == 401
    # a taxpayer we do not represent gets no answer at all
    assert _cb(eta, rin="999999999").status_code == 400
    assert eta.put("/eta/erp/ping", json={}, headers={"Authorization": "ApiKey cb-secret-123"}).status_code == 400


def test_eta_ping_is_refused_until_the_key_is_configured(eta):
    assert _cb(eta).status_code == 503


def test_eta_ping_needs_no_gateway_key_or_login(eta, monkeypatch):
    """ETA has neither our API key nor a session — the path must be public."""
    from app.auth.resources import is_public
    assert is_public("/eta/erp/ping")
    monkeypatch.setenv("ETA_ERP_CALLBACK_KEY", "cb-secret-123")
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps([dict(ENT[0], rin="123456789")]))
    config.get_settings.cache_clear()
    assert _cb(eta).status_code == 200      # no X-API-Key anywhere above
