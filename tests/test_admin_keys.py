"""The keys screen: a place to replace a secret, never to read one.

The whole point of this module is what it refuses to do, so that is what the
tests are about — the value never coming back, the gateway's own API key not
being enough to rotate the platform's credentials, and the audit trail carrying
who and when but nothing else.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import config


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A throwaway `.env`, and the process environment put back afterwards.

    Writing a key deliberately updates `os.environ` so the change takes effect
    without a restart — which means a test that sets one would otherwise leave
    the whole suite thinking Nama or the CCTV agent is configured."""
    import os
    envfile = tmp_path / ".env"
    envfile.write_text("# STLIX\nGATEWAY_API_KEY=gw-key-123456\nCCTV_AGENT_KEY=old-cctv\n",
                       encoding="utf-8")
    from app.admin import keys
    monkeypatch.setattr(keys, "ENV_FILE", envfile)
    before = {k.name: os.environ.get(k.name) for k in keys.KEYS}
    yield envfile
    for name, value in before.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    config.get_settings.cache_clear()


@pytest.fixture
def app(tmp_path, monkeypatch, env):
    monkeypatch.setenv("AUTH_MODE", "on")
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("AUTH_BOOTSTRAP_USER", "boss")
    monkeypatch.setenv("AUTH_BOOTSTRAP_PASSWORD", "boss-pass-123")
    monkeypatch.setenv("GATEWAY_API_KEY", "gw-key-123456")
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.main import create_app
    yield create_app()
    config.get_settings.cache_clear()


def boss(app):
    c = TestClient(app, follow_redirects=False)
    c.post("/login", data={"username": "boss", "password": "boss-pass-123", "to": "/hub/"})
    return c


def test_the_api_key_every_page_carries_cannot_rotate_the_platforms_keys(app):
    """`_serve` injects the gateway key into every screen's HTML, so holding it
    proves only that someone opened a page. It must not open this door."""
    anon = TestClient(app, follow_redirects=False)
    key = {"X-API-Key": "gw-key-123456"}
    assert anon.get("/api/v1/keys", headers=key).status_code == 403
    assert anon.put("/api/v1/keys/CCTV_AGENT_KEY", json={"value": "x"}, headers=key).status_code == 403
    assert anon.post("/api/v1/keys/CCTV_AGENT_KEY/generate", headers=key).status_code == 403


def test_a_viewer_cannot_open_it_either(app):
    c = boss(app)
    c.post("/api/v1/auth/admin/users",
           json={"username": "sara", "password": "sara-pass-123", "roles": ["viewer"]})
    sara = TestClient(app, follow_redirects=False)
    sara.post("/login", data={"username": "sara", "password": "sara-pass-123", "to": "/hub/"})
    assert sara.get("/api/v1/keys").status_code == 403
    assert sara.get("/tools/keys", headers={"accept": "text/html"}).status_code == 403


def test_the_listing_says_whether_a_key_is_set_and_never_what_it_is(app, env):
    r = boss(app).get("/api/v1/keys")
    assert r.status_code == 200
    body = r.text
    assert "gw-key-123456" not in body and "old-cctv" not in body
    rows = {k["name"]: k for k in r.json()["keys"]}
    assert rows["GATEWAY_API_KEY"]["set"] is True
    assert rows["NAMA_CLIENT_SECRET"]["set"] is False


def test_a_change_lands_in_the_file_and_takes_effect_without_a_restart(app, env):
    c = boss(app)
    assert c.put("/api/v1/keys/CCTV_AGENT_KEY",
                 json={"value": "new-cctv-key", "reason": "rotating"}).status_code == 200
    text = env.read_text(encoding="utf-8")
    assert "CCTV_AGENT_KEY=new-cctv-key" in text
    assert "# STLIX" in text and "GATEWAY_API_KEY=gw-key-123456" in text   # nothing else disturbed
    config.get_settings.cache_clear()
    assert config.get_settings().cctv_agent_key == "new-cctv-key"


def test_a_generated_key_is_returned_once_and_then_never_again(app, env):
    c = boss(app)
    r = c.post("/api/v1/keys/CCTV_AGENT_KEY/generate")
    value = r.json()["value"]
    assert len(value) >= 32 and value in env.read_text(encoding="utf-8")
    again = c.get("/api/v1/keys")
    assert value not in again.text
    assert value not in json.dumps(c.get("/api/v1/keys/audit/log").json(), ensure_ascii=False)


def test_the_audit_records_who_and_when_but_not_the_value(app):
    c = boss(app)
    c.put("/api/v1/keys/NAMA_CLIENT_SECRET", json={"value": "s3cr3t-value", "reason": "first time"})
    log = c.get("/api/v1/keys/audit/log").json()["log"]
    assert log and log[0]["actor"] == "boss" and log[0]["target"] == "NAMA_CLIENT_SECRET"
    assert "s3cr3t-value" not in json.dumps(log, ensure_ascii=False)


def test_only_known_keys_may_be_written(app):
    c = boss(app)
    assert c.put("/api/v1/keys/PATH", json={"value": "/tmp"}).status_code == 404
    assert c.put("/api/v1/keys/AUTH_DB_PATH", json={"value": "/etc/x"}).status_code == 404
    assert c.put("/api/v1/keys/GATEWAY_API_KEY",
                 json={"value": "one\nTWO=injected"}).status_code == 400
    assert c.post("/api/v1/keys/NAMA_CLIENT_SECRET/generate").status_code == 404


def test_the_env_file_keeps_its_identity_so_a_bind_mount_still_works(app, env):
    """In production `.env` is a bind-mounted file inside the container.
    Renaming onto a mount point fails, so the writer copies over the existing
    file — and the file's inode must therefore survive a change."""
    before = env.stat().st_ino
    boss(app).put("/api/v1/keys/NAMA_CLIENT_ID", json={"value": "abc"})
    assert env.stat().st_ino == before
    assert "NAMA_CLIENT_ID=abc" in env.read_text(encoding="utf-8")
    assert oct(env.stat().st_mode)[-3:] == "600"
    assert list(env.parent.glob(".env.bak-*")), "a change without a backup is a change you cannot undo"
