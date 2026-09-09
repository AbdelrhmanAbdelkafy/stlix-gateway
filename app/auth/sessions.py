"""Stateless signed session cookie.

`<base64url(json)>.<hmac-sha256>` carrying the username, the user's
`session_version` (bumped on password change / disable / role edit, which is
how a cookie is revoked without a session table) and an expiry.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

COOKIE_NAME = "stlix_session"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue(secret: str, username: str, version: int, hours: float) -> str:
    payload = json.dumps({"u": username, "v": version, "exp": int(time.time() + hours * 3600)},
                         separators=(",", ":")).encode("utf-8")
    body = _b64(payload)
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def parse(secret: str, token: str | None) -> dict | None:
    """Return {"u","v","exp"} for a valid, unexpired token; else None."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    good = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig):
        return None
    try:
        data = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < time.time():
        return None
    return data
