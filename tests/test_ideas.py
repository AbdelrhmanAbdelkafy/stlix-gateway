"""The ideas board must reflect BACKLOG.md exactly — it is the owner's list."""
from fastapi.testclient import TestClient

from app.ideas import registry
from app.main import app

client = TestClient(app)
KEY = {"X-API-Key": "test-key"}


def test_every_backlog_row_is_parsed():
    ideas = registry.all_ideas()
    # The backlog is hand-edited and only grows; guard the floor, not an exact
    # count, so adding a row never breaks the suite.
    assert len(ideas) >= 180
    assert len({i.id for i in ideas}) == len(ideas), "duplicate backlog ids"


def test_ids_domains_and_statuses_are_sane():
    for i in registry.all_ideas():
        assert i.id and i.title, f"{i.id} missing title"
        assert i.domain, f"{i.id} has no domain"
        assert i.status in ("live", "next", "planned")
        assert i.readiness in ("done", "ready", "partial", "blocked")


def test_planned_ideas_never_link_as_if_built():
    """A planned idea linking to a real page would claim work that isn't done."""
    for i in registry.all_ideas():
        if i.status == "planned":
            assert i.link == f"/tools/ideas#{i.id}", f"{i.id} links to {i.link}"


def test_readiness_follows_missing_connectors():
    for i in registry.all_ideas():
        if i.readiness == "ready":
            assert not i.missing_connectors, f"{i.id} is 'ready' but misses {i.missing_connectors}"
        if i.missing_connectors:
            assert i.readiness in ("partial", "blocked")


def test_email_source_is_not_read_as_ai():
    """'Email / IMAP' contains the letters 'ai' — must not imply the AI layer."""
    cm1 = registry.get("CM1")
    assert "ai-layer" not in cm1["connectors"]


def test_ai_tagged_ideas_require_the_ai_layer():
    for i in registry.all_ideas():
        if i.engine == "AI":
            assert "ai-layer" in i.missing_connectors, f"{i.id} tagged AI but not blocked on Layer 4"


def test_list_endpoint_returns_everything():
    r = client.get("/api/v1/ideas", headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["returned"] == body["summary"]["total"]
    assert len(body["ideas"]) == body["returned"]


def test_filters_narrow_the_list():
    total = client.get("/api/v1/ideas", headers=KEY).json()["returned"]
    ready = client.get("/api/v1/ideas?readiness=ready", headers=KEY).json()
    assert 0 < ready["returned"] < total
    assert all(i["readiness"] == "ready" for i in ready["ideas"])

    warehouse = client.get("/api/v1/ideas?domain=WH", headers=KEY).json()
    assert all(i["prefix"] == "WH" for i in warehouse["ideas"])

    found = client.get("/api/v1/ideas?q=aging", headers=KEY).json()
    assert any(i["id"] == "T14" for i in found["ideas"])


def test_single_idea_and_404():
    r = client.get("/api/v1/ideas/T14", headers=KEY)
    assert r.status_code == 200
    assert r.json()["id"] == "T14"
    assert client.get("/api/v1/ideas/ZZ999", headers=KEY).status_code == 404


def test_ideas_require_the_gateway_key(monkeypatch):
    """Auth is a no-op until a key is configured — so configure one and check."""
    from app.config import get_settings

    monkeypatch.setenv("GATEWAY_API_KEY", "secret-key")
    get_settings.cache_clear()
    try:
        assert client.get("/api/v1/ideas").status_code == 401
        assert client.get("/api/v1/ideas", headers={"X-API-Key": "secret-key"}).status_code == 200
    finally:
        get_settings.cache_clear()


def test_board_page_is_served():
    r = client.get("/tools/ideas")
    assert r.status_code == 200
    assert "الأفكار والمتطلبات" in r.text
    assert "__GATEWAY_API_KEY__" not in r.text, "gateway key placeholder left uninjected"


def test_workspace_exposes_the_ideas_section():
    r = client.get("/api/v1/workspace", headers=KEY)
    assert r.status_code == 200
    sections = {s["key"]: s for s in r.json()["sections"]}
    assert "ideas" in sections
    assert sections["ideas"]["summary"]["total"] >= 180
