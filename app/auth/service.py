"""Glue between settings, the store and a request: who is this, what may they do."""
from __future__ import annotations

import logging
from pathlib import Path

from starlette.requests import Request

from ..config import Settings, get_settings
from . import sessions
from .store import AuthStore, get_store

_log = logging.getLogger("gateway.auth")
_ROOT = Path(__file__).resolve().parent.parent.parent


def db_path(settings: Settings) -> Path:
    return Path(settings.auth_db_path) if settings.auth_db_path else _ROOT / "data" / "auth" / "auth.db"


def store(settings: Settings | None = None) -> AuthStore:
    settings = settings or get_settings()
    st = get_store(db_path(settings))
    _ensure_bootstrap(st, settings)
    return st


_bootstrapped: set[str] = set()


def _ensure_bootstrap(st: AuthStore, settings: Settings) -> None:
    key = str(st.path)
    if key in _bootstrapped:
        return
    _bootstrapped.add(key)
    if st.user_count():
        return
    pw = settings.auth_bootstrap_password
    if not pw:
        import secrets
        pw = secrets.token_urlsafe(12)
        marker = st.path.parent / "bootstrap-password.txt"
        marker.write_text(pw, encoding="utf-8")
        _log.warning("auth: no users — created '%s' with a generated password saved in %s",
                     settings.auth_bootstrap_user, marker)
    if st.bootstrap(settings.auth_bootstrap_user, pw):
        _log.info("auth: bootstrap admin '%s' created", settings.auth_bootstrap_user)


def current_user(request: Request, settings: Settings | None = None) -> dict | None:
    """The session user for this request, or None. Cached on request.state."""
    cached = getattr(request.state, "user", None)
    if cached is not None:
        return cached or None
    settings = settings or get_settings()
    st = store(settings)
    data = sessions.parse(st.secret(), request.cookies.get(sessions.COOKIE_NAME))
    user = None
    if data:
        u = st.get_user(data.get("u", ""))
        if u and u["active"] and u["session_version"] == data.get("v"):
            user = u
    request.state.user = user or {}
    return user


def issue_cookie(settings: Settings, user: dict) -> tuple[str, dict]:
    """(token, cookie kwargs) for a freshly authenticated user."""
    st = store(settings)
    token = sessions.issue(st.secret(), user["username"], user["session_version"],
                           settings.auth_session_hours)
    kw = dict(key=sessions.COOKIE_NAME, value=token, httponly=True, samesite="lax", path="/",
              max_age=int(settings.auth_session_hours * 3600),
              secure=settings.app_env not in ("dev", "test"))
    if settings.auth_cookie_domain:
        kw["domain"] = settings.auth_cookie_domain
    return token, kw


def clear_cookie_kwargs(settings: Settings) -> dict:
    kw = dict(key=sessions.COOKIE_NAME, path="/")
    if settings.auth_cookie_domain:
        kw["domain"] = settings.auth_cookie_domain
    return kw


def me(request: Request, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    user = current_user(request, settings)
    if not user:
        return {"authenticated": False, "auth_enabled": settings.auth_enabled}
    st = store(settings)
    return {"authenticated": True, "auth_enabled": settings.auth_enabled,
            "username": user["username"], "display_name": user["display_name"],
            "roles": user["roles"], "permissions": st.effective(user["username"]),
            "is_admin": st.allowed(user["username"], "users", "admin")}
