"""Unified workspace aggregation."""
from fastapi.testclient import TestClient

from app.main import app
from app.workspace.providers import PROVIDERS

client = TestClient(app)


def test_workspace_json_has_all_sections():
    r = client.get("/api/v1/workspace?format=json")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["sections"]}
    assert {"overview", "nama", "crm", "monitoring"} <= keys


def test_workspace_section_count_matches_registry():
    r = client.get("/api/v1/workspace?format=json")
    assert len(r.json()["sections"]) == len(PROVIDERS)


def test_workspace_html_view():
    r = client.get("/api/v1/workspace?format=html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Overview" in r.text


def test_workspace_unconfigured_sections_are_graceful():
    # With no creds in the test env, nama/crm report not_configured, not error.
    sections = {s["key"]: s for s in client.get("/api/v1/workspace?format=json").json()["sections"]}
    assert sections["nama"]["status"] in {"not_configured", "ok"}
    assert sections["crm"]["status"] in {"not_configured", "ok"}
    assert sections["overview"]["status"] == "ok"
