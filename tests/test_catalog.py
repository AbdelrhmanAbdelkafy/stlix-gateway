"""The catalogue must describe the app, exactly — in both directions.

Drift here is how the map quietly starts lying: an endpoint gets added and
appears on no map, or the catalogue promises a route nobody wrote. Both
happened before this file existed.
"""
from app import catalog
from app.main import app
from app.registry import SYSTEMS, Status

# FastAPI's own pages. Everything else must be accounted for.
_FRAMEWORK = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}


def _routed() -> set[str]:
    return set(app.openapi()["paths"])


def test_every_catalogued_path_is_a_real_route():
    missing = catalog.paths() - _routed()
    assert not missing, f"catalogue promises routes that do not exist: {sorted(missing)}"


def test_every_real_route_is_catalogued():
    extra = _routed() - catalog.paths() - _FRAMEWORK
    assert not extra, f"routes missing from the catalogue: {sorted(extra)}"


def test_adding_a_planned_system_cannot_create_an_uncatalogued_route():
    """`main.py` mounts /api/v1/<key> for every PLANNED system; the catalogue
    derives those rather than listing them, so the two cannot diverge."""
    planned = {f"/api/v1/{s.key}" for s in SYSTEMS if s.status is Status.PLANNED}
    assert planned <= catalog.paths()


def test_every_connector_system_exists_on_the_map():
    """A connector pointing at a system that is not in SYSTEMS renders a
    dangling edge on /connectors — five of them shipped that way once."""
    keys = {s.key for s in SYSTEMS}
    dangling = {c.key: c.system for c in catalog.CONNECTORS if c.system and c.system not in keys}
    assert not dangling, f"connectors pointing at unknown systems: {dangling}"


def test_every_endpoint_names_a_known_connector():
    keys = {c.key for c in catalog.CONNECTORS}
    bad = [e.path for e in catalog.ENDPOINTS if e.connector and e.connector not in keys]
    assert not bad, f"endpoints with an unknown connector: {bad}"


def test_paths_are_unique():
    seen = [e.path for e in catalog.ENDPOINTS]
    assert len(seen) == len(set(seen)), "duplicate path in the catalogue"


def test_write_endpoints_are_declared():
    """A write must be visible as one on the map — that is the read-only
    promise being auditable rather than assumed."""
    writes = [e for e in catalog.ENDPOINTS if e.write]
    # Every one deliberate: a punch reaching Nama; rotating the platform's own
    # keys (admin session only, and the value never comes back); a click on the
    # tax portal; and cancel/reject there, which is irreversible and gated by
    # ETA_ALLOW_STATE_CHANGES.
    assert sorted(e.path for e in writes) == sorted([
        "/api/v1/attendance/punch",
        "/api/v1/keys/{name}",
        "/api/v1/keys/{name}/generate",
        "/api/v1/eta/browser/do/{action}",
        "/api/v1/eta/{entity}/documents/{uuid}/state"])
    assert all(e.method != "GET" for e in writes)
