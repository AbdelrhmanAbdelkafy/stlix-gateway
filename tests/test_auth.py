"""Users, sessions, permissions — PA2/PA3.

The suite's default app has auth *off* (dev). These tests build a second app
with `AUTH_MODE=on` and a throwaway SQLite file, so they prove the gate is
real without making every other test log in.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config
from app.auth import store as store_mod
from app.auth.resources import BY_KEY, resource_for_path


@pytest.fixture
def gate(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "on")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("AUTH_BOOTSTRAP_USER", "boss")
    monkeypatch.setenv("AUTH_BOOTSTRAP_PASSWORD", "boss-pass-123")
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.main import create_app
    app = create_app()
    client = TestClient(app, follow_redirects=False)
    yield client
    config.get_settings.cache_clear()


def _login(c: TestClient, u: str, p: str) -> TestClient:
    r = c.post("/login", data={"username": u, "password": p, "to": "/hub/"})
    assert r.status_code == 303, r.text
    return c


# --- the gate ------------------------------------------------------------------
def test_anonymous_browser_is_sent_to_login(gate):
    r = gate.get("/hub/", headers={"accept": "text/html"})
    assert r.status_code == 302 and r.headers["location"].startswith("/login?to=%2Fhub%2F")


def test_anonymous_api_gets_401_json(gate):
    r = gate.get("/api/v1/hub/live")
    assert r.status_code == 401 and r.json()["error"] == "Unauthorized"


def test_public_paths_need_no_login(gate):
    for p in ("/health", "/login", "/tools/voice.js", "/api/v1/auth/me"):
        assert gate.get(p).status_code == 200, p


def test_bootstrap_admin_can_log_in_and_reach_everything(gate):
    _login(gate, "boss", "boss-pass-123")
    assert "stlix_session" in gate.cookies
    me = gate.get("/api/v1/auth/me").json()
    assert me["authenticated"] and me["is_admin"] and "admin" in me["roles"]
    for p in ("/hub/", "/hub/admin.html", "/tools/name-builder", "/api/v1/hub/catalog",
              "/api/v1/auth/admin/users", "/systems"):
        assert gate.get(p).status_code == 200, p


def test_wrong_password_bounces_back_with_error_flag(gate):
    r = gate.post("/login", data={"username": "boss", "password": "nope", "to": "/hub/"})
    assert r.status_code == 303 and r.headers["location"].startswith("/login?e=1")
    assert "stlix_session" not in gate.cookies


def test_open_redirects_are_refused(gate):
    r = gate.post("/login", data={"username": "boss", "password": "boss-pass-123",
                                  "to": "https://evil.example/"})
    assert r.headers["location"] == "/hub/"


def test_logout_kills_the_cookie(gate):
    _login(gate, "boss", "boss-pass-123")
    r = gate.get("/logout")
    assert r.status_code == 303
    assert gate.get("/api/v1/hub/live").status_code == 401


def test_api_key_header_still_opens_the_machine_door(gate, monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", "k-123456789")
    config.get_settings.cache_clear()
    assert gate.get("/api/v1/hub/live", headers={"X-API-Key": "k-123456789"}).status_code == 200
    assert gate.get("/api/v1/hub/live", headers={"X-API-Key": "wrong"}).status_code == 401


# --- roles and overrides, the Nama way -----------------------------------------
def test_sales_sees_only_sales_cards_and_cannot_edit_name_builder(gate):
    _login(gate, "boss", "boss-pass-123")
    r = gate.post("/api/v1/auth/admin/users", json={
        "username": "ali", "password": "ali-pass-123", "display_name": "علي", "roles": ["sales"]})
    assert r.status_code == 201, r.text
    ali = TestClient(gate.app, follow_redirects=False)
    _login(ali, "ali", "ali-pass-123")
    keys = {i["key"] for i in ali.get("/api/v1/hub/catalog").json()["items"]}
    assert "platform" in keys and "rep" in keys and "crm-site" in keys
    assert "finance" not in keys and "users" not in keys and "hpanel" not in keys
    # view yes, edit no
    assert ali.get("/tools/name-builder").status_code == 200
    r = ali.post("/api/v1/nama/items", json={})
    assert r.status_code == 403 and r.json()["resource"] == "name-builder"
    # finance is invisible AND blocked
    assert ali.get("/tools/finance-os", headers={"accept": "text/html"}).status_code == 403
    assert ali.get("/hub/admin.html").status_code == 403


def test_deny_override_beats_the_role(gate):
    _login(gate, "boss", "boss-pass-123")
    gate.post("/api/v1/auth/admin/users", json={
        "username": "mona", "password": "mona-pass-123", "roles": ["mgmt"]})
    r = gate.put("/api/v1/auth/admin/users/mona/overrides",
                 json=[{"resource": "finance", "action": "view", "effect": "deny"},
                       {"resource": "users", "action": "admin", "effect": "allow"}])
    assert r.status_code == 200
    eff = r.json()["effective"]
    assert "view" not in eff.get("finance", []) and "admin" in eff["users"]
    mona = TestClient(gate.app, follow_redirects=False)
    _login(mona, "mona", "mona-pass-123")
    assert mona.get("/tools/finance-os").status_code == 403
    assert mona.get("/api/v1/auth/admin/roles").status_code == 200


def test_editing_a_role_reaches_its_holders_on_the_next_request(gate):
    _login(gate, "boss", "boss-pass-123")
    gate.post("/api/v1/auth/admin/users", json={
        "username": "sara", "password": "sara-pass-123", "roles": ["viewer"]})
    sara = TestClient(gate.app, follow_redirects=False)
    _login(sara, "sara", "sara-pass-123")
    assert sara.get("/tools/engineer").status_code == 403
    role = gate.get("/api/v1/auth/admin/roles").json()["roles"]
    viewer = next(r for r in role if r["key"] == "viewer")
    viewer["perms"]["engineer"] = ["view"]
    gate.put("/api/v1/auth/admin/roles/viewer", json={"name": viewer["name"], "desc": "", "perms": viewer["perms"]})
    # the session version bumped -> sara must log in again, which is the point
    assert sara.get("/tools/engineer").status_code in (302, 401)
    _login(sara, "sara", "sara-pass-123")
    assert sara.get("/tools/engineer").status_code == 200


def test_disabling_a_user_revokes_the_live_session(gate):
    _login(gate, "boss", "boss-pass-123")
    gate.post("/api/v1/auth/admin/users", json={"username": "tmp", "password": "tmp-pass-123", "roles": ["viewer"]})
    tmp = TestClient(gate.app, follow_redirects=False)
    _login(tmp, "tmp", "tmp-pass-123")
    assert tmp.get("/hub/").status_code == 200
    gate.patch("/api/v1/auth/admin/users/tmp", json={"active": False})
    assert tmp.get("/api/v1/hub/live").status_code == 401


def test_the_last_admin_cannot_be_deleted_or_self_disabled(gate):
    _login(gate, "boss", "boss-pass-123")
    assert gate.delete("/api/v1/auth/admin/users/boss").status_code == 400
    assert gate.patch("/api/v1/auth/admin/users/boss", json={"active": False}).status_code == 400


def test_builtin_roles_cannot_be_deleted_but_custom_ones_can(gate):
    _login(gate, "boss", "boss-pass-123")
    assert gate.delete("/api/v1/auth/admin/roles/sales").status_code == 400
    assert gate.put("/api/v1/auth/admin/roles/warehouse",
                    json={"name": "مخزن", "desc": "", "perms": {"count-app": ["view", "edit"]}}).status_code == 200
    assert gate.delete("/api/v1/auth/admin/roles/warehouse").status_code == 200


def test_audit_records_logins_and_changes(gate):
    _login(gate, "boss", "boss-pass-123")
    gate.post("/api/v1/auth/admin/users", json={"username": "z", "password": "z-pass-1234"})
    actions = [a["action"] for a in gate.get("/api/v1/auth/admin/audit").json()["audit"]]
    assert "login.ok" in actions and "user.create" in actions


# --- the model itself -----------------------------------------------------------
def test_password_hashes_verify_and_never_repeat():
    h1, h2 = store_mod.hash_password("secret-1"), store_mod.hash_password("secret-1")
    assert h1 != h2 and store_mod.verify_password("secret-1", h1) and not store_mod.verify_password("x", h1)


def test_every_guarded_path_maps_to_a_known_resource():
    for p, key in (("/tools/name-builder", "name-builder"), ("/api/v1/nama/items", "name-builder"),
                   ("/tools/finance-reports", "finance"), ("/api/v1/banks", "finance"),
                   ("/api/v1/auth/admin/users", "users"), ("/hub/admin.html", "users"),
                   ("/api/v1/crm/leads", "crm-site"), ("/api/v1/attendance/punch", "attendance-site"),
                   ("/hub/platform.html", "platform"), ("/", "gateway"), ("/whatever", "gateway")):
        assert resource_for_path(p) == key, p
        assert key in BY_KEY


def test_default_roles_only_name_real_resources():
    for key, r in store_mod.DEFAULT_ROLES.items():
        bad = [res for res in r["perms"] if res != "*" and res not in BY_KEY]
        assert not bad, f"{key}: {bad}"
