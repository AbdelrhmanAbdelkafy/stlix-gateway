"""Cameras: the agent pushes, the hub reads, and staleness is never hidden."""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app import config

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"

REPORT = {
    "agent_id": "factory-pc", "agent_version": "1.0.0", "agent_host": "FACTORY-PC", "interval_s": 60,
    "sent_at": time.time(),
    "devices": [
        {"id": "factory-main", "name": "المصنع", "host": "192.168.1.64", "model": "iDS-7232HQHI",
         "online": True, "storage": [{"name": "HDD1", "capacity_mb": 4000000, "free_mb": 120000, "status": "ok"}],
         "channels": [{"id": "1", "name": "البوابة", "online": True}, {"id": "2", "name": "المخزن", "online": False}]},
        {"id": "warehouse", "name": "المخازن", "host": "192.168.1.66", "online": False,
         "error": "deviceInfo unreachable", "channels": []},
    ],
    "events": [{"ts": time.time(), "device": "factory-main", "channel": "1", "type": "VMD", "state": "active"}],
}


@pytest.fixture
def cctv(tmp_path, monkeypatch):
    monkeypatch.setenv("CCTV_AGENT_KEY", "agent-secret-1")
    monkeypatch.setenv("CCTV_DATA_DIR", str(tmp_path / "cctv"))
    monkeypatch.setenv("GATEWAY_API_KEY", "gw-key-123456")
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.main import create_app
    yield TestClient(create_app())
    config.get_settings.cache_clear()


AGENT = {"X-CCTV-Agent-Key": "agent-secret-1"}
GW = {"X-API-Key": "gw-key-123456"}


def test_empty_state_says_no_agent_yet(cctv):
    r = cctv.get("/api/v1/cctv", headers=GW)
    assert r.status_code == 200
    ov = r.json()
    assert ov["stale"] and ov["received_at"] is None and ov["summary"]["devices"] == 0 and "agent" in ov["note"]


def test_agent_push_then_hub_reads_it(cctv):
    r = cctv.post("/api/v1/cctv/push", json=REPORT, headers=AGENT)
    assert r.status_code == 200 and r.json() == {"ok": True, "devices": 2, "channels": 2, "events": 1}
    ov = cctv.get("/api/v1/cctv", headers=GW).json()
    assert not ov["stale"] and ov["age_s"] == 0
    assert ov["summary"] == {"devices": 2, "devices_online": 1, "channels": 2, "channels_online": 1, "events_recent": 1}
    assert ov["agent"]["host"] == "FACTORY-PC"
    devs = cctv.get("/api/v1/cctv/devices", headers=GW).json()["devices"]
    assert devs[1]["error"] == "deviceInfo unreachable"
    ch = cctv.get("/api/v1/cctv/devices/factory-main/channels", headers=GW).json()["channels"]
    assert ch[0]["snapshot_url"] == "/api/v1/cctv/snapshot/factory-main/1.jpg" and ch[0]["snapshot_age_s"] is None
    assert cctv.get("/api/v1/cctv/devices/nope/channels", headers=GW).status_code == 404
    ev = cctv.get("/api/v1/cctv/events", headers=GW).json()["events"]
    assert ev[0]["type"] == "VMD" and ev[0]["device"] == "factory-main"


def test_snapshot_roundtrip_and_age_header(cctv):
    cctv.post("/api/v1/cctv/push", json=REPORT, headers=AGENT)
    assert cctv.get("/api/v1/cctv/snapshot/factory-main/1.jpg", headers=GW).status_code == 404
    r = cctv.post("/api/v1/cctv/push/snapshot/factory-main/1", content=JPEG,
                  headers={**AGENT, "Content-Type": "image/jpeg"})
    assert r.status_code == 200 and r.json()["bytes"] == len(JPEG)
    r = cctv.get("/api/v1/cctv/snapshot/factory-main/1.jpg", headers=GW)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content == JPEG
    assert r.headers["cache-control"] == "no-store" and "x-snapshot-age" in r.headers
    ch = cctv.get("/api/v1/cctv/devices/factory-main/channels", headers=GW).json()["channels"]
    assert ch[0]["snapshot_age_s"] == 0
    # not a jpeg -> refused, nothing overwritten
    r = cctv.post("/api/v1/cctv/push/snapshot/factory-main/1", content=b"<html>", headers=AGENT)
    assert r.status_code == 400
    assert cctv.get("/api/v1/cctv/snapshot/factory-main/1.jpg", headers=GW).content == JPEG


def test_agent_key_only_opens_the_push_door(cctv):
    assert cctv.post("/api/v1/cctv/push", json=REPORT).status_code == 401
    assert cctv.post("/api/v1/cctv/push", json=REPORT, headers={"X-CCTV-Agent-Key": "wrong"}).status_code == 401
    assert cctv.post("/api/v1/cctv/push", json=REPORT, headers=GW).status_code == 200  # gateway key also fine
    # the agent key cannot read anything
    assert cctv.get("/api/v1/cctv", headers=AGENT).status_code == 401
    assert cctv.get("/api/v1/rep", headers=AGENT).status_code == 401


def test_bad_ids_are_refused_not_written_as_paths(cctv):
    bad = dict(REPORT, devices=[{"id": "../etc", "channels": []}])
    assert cctv.post("/api/v1/cctv/push", json=bad, headers=AGENT).status_code == 400
    assert cctv.get("/api/v1/cctv/snapshot/..%2F..%2Fx/1.jpg", headers=GW).status_code in (400, 404)


def test_stale_when_the_agent_goes_quiet(cctv, monkeypatch):
    cctv.post("/api/v1/cctv/push", json=REPORT, headers=AGENT)
    from app.integrations.cctv import store
    f = store._state_file(config.get_settings())
    st = json.loads(f.read_text()); st["received_at"] -= 600; f.write_text(json.dumps(st))
    ov = cctv.get("/api/v1/cctv", headers=GW).json()
    assert ov["stale"] and ov["age_s"] >= 600 and "ساكت" in ov["note"]


def test_hub_live_probe_reports_cctv(cctv):
    cctv.post("/api/v1/cctv/push", json=REPORT, headers=AGENT)
    from app.hub.live import live as cache
    cache.data = None  # the snapshot is a process-wide singleton; drop what another test cached
    live = cctv.get("/api/v1/hub/live", headers=GW).json()["items"]["cctv"]
    assert live["up"] and live["numbers"]["channels"] == 1 and live["numbers"]["devices"] == 1


def test_wall_page_is_served_and_wired(cctv):
    r = cctv.get("/tools/cctv", headers=GW)
    assert r.status_code == 200 and "/api/v1/cctv" in r.text and "gw-key-123456" in r.text


def test_cameras_card_now_points_at_the_gateway():
    from app.auth.resources import BY_KEY, resource_for_path
    cam = BY_KEY["cameras"]
    assert cam.url == "/tools/cctv" and cam.live_key == "cctv" and not cam.external
    assert resource_for_path("/api/v1/cctv/devices") == "cameras"
    assert resource_for_path("/tools/cctv") == "cameras"


def test_events_file_is_trimmed(cctv):
    from app.integrations.cctv import store
    big = dict(REPORT, events=[{"ts": 1, "device": "d", "type": "VMD"}] * 500)
    for _ in range(5):
        cctv.post("/api/v1/cctv/push", json=big, headers=AGENT)
    lines = store._events_file(config.get_settings()).read_text().splitlines()
    assert len(lines) <= store.MAX_EVENTS
    assert len(json.loads(lines[-1])) == 7
