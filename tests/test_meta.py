from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "Stlix Gateway"


def test_systems_lists_all():
    r = client.get("/systems")
    assert r.status_code == 200
    body = r.json()
    keys = {s["key"] for s in body["systems"]}
    # a few of the promised systems must be present
    assert {"nama", "attendance", "crm", "callcenter", "email", "ai"} <= keys
    assert body["live"] >= 2


def test_planned_system_returns_501():
    r = client.get("/api/v1/crm")
    assert r.status_code == 501


def test_health_ok_without_nama_creds():
    # No creds configured in test env -> still 200, nama.configured False
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
