"""Gateway-level auth: optional shared X-API-Key (one or many keys)."""
from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from ..config import Settings, get_settings


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
    sg_key: str | None = Cookie(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce the key only when at least one is configured (else no-op).

    Accepts any key in GATEWAY_API_KEY or the comma-separated GATEWAY_API_KEYS,
    sent either as the `X-API-Key` header (apps, scripts, AI clients) or as the
    `sg_key` cookie the gateway sets when it serves a `/tools/*` page.

    The cookie exists because the platform is a web of links: a plain
    `<a href="/api/v1/...">` cannot send a header, so without it every endpoint
    link on the hub and the ideas board 401s the moment a key is configured.
    It is deliberately narrower than the header:

    - **GET/HEAD only** — a write must carry the header, so an ambient
      credential can never mutate an upstream system even if a connector is
      later switched to read_write.
    - HttpOnly (page scripts cannot read it back out) + SameSite=lax, and it is
      only ever set by a page that was already handed the key.
    """
    keys = settings.api_keys
    if not keys:
        return
    if x_api_key in keys:
        return
    if sg_key in keys and request.method in ("GET", "HEAD"):
        return
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-Key."
    )
