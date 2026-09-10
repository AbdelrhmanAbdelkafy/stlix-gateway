"""The live-portal console: a proxy that must not become an open door.

The screen shows a browser already signed in to the tax authority, so the only
interesting questions are about the gate, not the pixels: who may open the
socket, what the proxy refuses to forward, and what happens when the browser on
the host is simply not running.
"""
from __future__ import annotations

import json

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import ConnectError, Response

from app import config

ENT = [{"key": "group", "name": "المجموعة", "rin": "100", "k_manufacturing": 7, "k_trading": 1}]
GW = {"X-API-Key": "gw-key-123456"}
AGENT = "http://host.docker.internal:8021"
VNC = "http://host.docker.internal:6081"


@pytest.fixture
def gw(tmp_path, monkeypatch):
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps(ENT))
    monkeypatch.setenv("ETA_DB_PATH", str(tmp_path / "eta.db"))
    monkeypatch.setenv("VAT_DB_PATH", str(tmp_path / "vat.db"))
    monkeypatch.setenv("GATEWAY_API_KEY", "gw-key-123456")
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.main import create_app
    yield TestClient(create_app())
    config.get_settings.cache_clear()


@respx.mock
def test_reads_and_actions_reach_the_agent(gw):
    respx.get(f"{AGENT}/status").mock(return_value=Response(200, json={"ok": True, "signed_in": True}))
    respx.get(f"{AGENT}/tables").mock(return_value=Response(200, json={"tables": [{"rows": [["a"]]}]}))
    goto = respx.post(f"{AGENT}/goto").mock(return_value=Response(200, json={"url": "x"}))
    assert gw.get("/api/v1/eta/browser/read/status", headers=GW).json()["signed_in"]
    assert gw.get("/api/v1/eta/browser/read/tables", headers=GW).json()["tables"]
    assert gw.post("/api/v1/eta/browser/do/goto", json={"path": "/"}, headers=GW).status_code == 200
    assert json.loads(goto.calls[0].request.content) == {"path": "/"}


def test_only_known_actions_are_proxied(gw):
    assert gw.get("/api/v1/eta/browser/read/evaluate", headers=GW).status_code == 404
    assert gw.post("/api/v1/eta/browser/do/screenshot_all", json={}, headers=GW).status_code == 404
    # a read verb cannot be smuggled through the write door and vice versa
    assert gw.post("/api/v1/eta/browser/do/tables", json={}, headers=GW).status_code == 404
    assert gw.get("/api/v1/eta/browser/read/click", headers=GW).status_code == 404


@respx.mock
def test_a_browser_that_is_not_running_says_so_and_says_how(gw):
    respx.get(f"{AGENT}/status").mock(side_effect=ConnectError("refused"))
    r = gw.get("/api/v1/eta/browser/read/status", headers=GW)
    assert r.status_code == 503
    assert "install-vps.sh" in r.json()["hint"]


@respx.mock
def test_the_screen_assets_are_proxied_from_novnc(gw):
    respx.get(f"{VNC}/vnc.html").mock(return_value=Response(
        200, content=b"<html>noVNC</html>", headers={"content-type": "text/html"}))
    r = gw.get("/vnc/vnc.html", headers=GW)
    assert r.status_code == 200 and b"noVNC" in r.content and r.headers["content-type"] == "text/html"


@respx.mock
def test_a_missing_screen_is_a_503_not_a_blank_page(gw):
    respx.get(f"{VNC}/vnc.html").mock(side_effect=ConnectError("no screen"))
    assert gw.get("/vnc/vnc.html", headers=GW).status_code == 503


def test_the_console_and_screen_sit_behind_the_vat_permission():
    from app.auth.resources import resource_for_path
    for p in ("/tools/portal", "/vnc/vnc.html", "/vnc/websockify", "/api/v1/eta/browser/read/status"):
        assert resource_for_path(p) == "vat", p


def test_the_screen_socket_refuses_anonymous_when_auth_is_on(tmp_path, monkeypatch):
    """The middleware never sees WebSockets, so the socket checks the cookie itself."""
    monkeypatch.setenv("AUTH_MODE", "on")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("AUTH_BOOTSTRAP_USER", "boss")
    monkeypatch.setenv("AUTH_BOOTSTRAP_PASSWORD", "boss-pass-123")
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps(ENT))
    monkeypatch.setenv("ETA_DB_PATH", str(tmp_path / "eta.db"))
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.main import create_app
    client = TestClient(create_app(), follow_redirects=False)
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/vnc/websockify"):
            pass
    assert e.value.code == 4401
    config.get_settings.cache_clear()


def test_a_viewer_without_vat_edit_cannot_open_the_screen(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "on")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth2.db"))
    monkeypatch.setenv("AUTH_BOOTSTRAP_USER", "boss")
    monkeypatch.setenv("AUTH_BOOTSTRAP_PASSWORD", "boss-pass-123")
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps(ENT))
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.main import create_app
    app = create_app()
    boss = TestClient(app, follow_redirects=False)
    boss.post("/login", data={"username": "boss", "password": "boss-pass-123", "to": "/hub/"})
    boss.post("/api/v1/auth/admin/users",
              json={"username": "sara", "password": "sara-pass-123", "roles": ["viewer"]})
    sara = TestClient(app, follow_redirects=False)
    sara.post("/login", data={"username": "sara", "password": "sara-pass-123", "to": "/hub/"})
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with sara.websocket_connect("/vnc/websockify"):
            pass
    assert e.value.code == 4401
    assert sara.get("/tools/portal", headers={"accept": "text/html"}).status_code == 403
    config.get_settings.cache_clear()
