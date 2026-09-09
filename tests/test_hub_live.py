"""The hub's live board: one snapshot of every system, pushed over SSE."""
from __future__ import annotations

import json

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.auth.resources import RESOURCES
from app.hub import live as live_mod
from app.hub.live import SITES, snapshot
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_cache():
    live_mod.live.data = None
    yield
    live_mod.live.data = None


@respx.mock
async def test_snapshot_probes_every_site_and_every_connector():
    for url in SITES.values():
        respx.get(url).mock(return_value=Response(200))
    snap = await snapshot()
    assert set(snap["items"]) >= {"gateway", "nama", "crm", "inventory", "finance", "expert", "rep"} | {f"site:{k}" for k in SITES}
    assert snap["items"]["site:crm"]["up"] is True and snap["items"]["site:crm"]["kind"] == "site"
    # unconfigured connectors say so instead of pretending
    assert snap["items"]["nama"]["configured"] is False and snap["items"]["nama"]["up"] is False
    assert "مفاتيح" in snap["items"]["nama"]["error"]
    assert snap["items"]["gateway"]["up"] is True
    assert snap["items"]["rep"]["up"] is True and snap["items"]["rep"]["numbers"]["holders"] > 0
    assert snap["up"] <= snap["total"]


@respx.mock
async def test_a_dead_site_is_down_not_an_exception():
    for url in SITES.values():
        respx.get(url).mock(return_value=Response(503))
    snap = await snapshot()
    assert all(not snap["items"][f"site:{k}"]["up"] for k in SITES)


def test_every_live_key_on_a_card_exists_in_the_snapshot():
    keys = {"gateway", "nama", "crm", "inventory", "finance", "expert", "rep"} | {f"site:{k}" for k in SITES}
    dangling = [r.key for r in RESOURCES if r.live_key and r.live_key not in keys]
    assert not dangling, f"cards pointing at unknown live keys: {dangling}"


@respx.mock
def test_live_endpoint_and_catalog_answer_with_auth_off():
    for url in SITES.values():
        respx.get(url).mock(return_value=Response(200))
    r = client.get("/api/v1/hub/live")
    assert r.status_code == 200 and "items" in r.json()
    cat = client.get("/api/v1/hub/catalog").json()
    assert cat["filtered"] is False and len(cat["items"]) >= 20
    assert all("can_edit" in i for i in cat["items"])


@respx.mock
def test_sse_stream_sends_a_live_event():
    for url in SITES.values():
        respx.get(url).mock(return_value=Response(200))
    r = client.get("/api/v1/hub/events?once=1")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    buf = r.text
    payload = buf.split("event: live\ndata: ", 1)[1].split("\n\n", 1)[0]
    data = json.loads(payload)
    assert "items" in data and data["total"] >= 10


def test_hub_pages_render():
    for p in ("/hub/", "/hub/platform.html", "/hub/admin.html", "/login"):
        r = client.get(p)
        assert r.status_code == 200 and "/tools/voice.js" in r.text, p
    assert client.get("/hub/nope.html").status_code == 404
