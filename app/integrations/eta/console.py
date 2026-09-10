"""The portal browser's screen and controls, published through the hub.

Two proxies and nothing else:

- `/api/v1/eta/browser/*` → the agent's local API (read the page, click, fill).
- `/vnc/*` → the virtual screen the browser draws on, so the person can sign in
  to the portal with their own hands. The screen is where the password is
  typed; it passes from their keyboard to Chromium as pixels and keystrokes and
  is never parsed, logged or stored by this platform.

Both live behind the hub's own login and the `vat` permission — the HTTP paths
through the auth middleware, the WebSocket by checking the same session cookie
here, because middleware does not see WebSocket scopes.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import JSONResponse, Response

from ...auth import service as auth_service
from ...auth.sessions import COOKIE_NAME
from ...config import Settings, get_settings
from ...core.security import require_api_key

log = logging.getLogger("gateway.eta")

router = APIRouter(prefix="/eta/browser", tags=["eta"], dependencies=[Depends(require_api_key)])
#: Mounted at the root: noVNC asks for its own assets by relative path.
vnc_router = APIRouter(prefix="/vnc", tags=["eta"])

_AGENT_PATHS = {"status", "text", "tables", "find", "shot"}
_AGENT_POSTS = {"goto", "click", "fill", "ingest"}


async def _agent(settings: Settings, method: str, path: str, **kw):
    url = f"{settings.eta_agent_url.rstrip('/')}/{path}"
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.request(method, url, **kw)
        return JSONResponse(r.json() if r.content else {"ok": r.is_success}, status_code=r.status_code)
    except httpx.HTTPError as exc:
        return JSONResponse(
            {"ok": False, "error": f"البراوزر مش شغال على السيرفر: {type(exc).__name__}",
             "hint": "systemctl status stlix-portal — أو شغّل agents/eta-browser/install-vps.sh"},
            status_code=503)


@router.get("/read/{action}")
async def agent_get(action: str, request: Request, settings: Settings = Depends(get_settings)):
    """status · text · tables · find · shot — straight from the live browser."""
    if action not in _AGENT_PATHS:
        return JSONResponse({"error": f"unknown action {action}"}, status_code=404)
    return await _agent(settings, "GET", action, params=dict(request.query_params))


@router.post("/do/{action}")
async def agent_post(action: str, request: Request, settings: Settings = Depends(get_settings)):
    """goto · click · fill · ingest. `click` still refuses irreversible words
    without `confirm` — that rule lives in the agent, next to the browser."""
    if action not in _AGENT_POSTS:
        return JSONResponse({"error": f"unknown action {action}"}, status_code=404)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    return await _agent(settings, "POST", action, json=body)


# --- the screen ---------------------------------------------------------------------
@vnc_router.get("/{path:path}")
async def vnc_assets(path: str, request: Request, settings: Settings = Depends(get_settings)):
    """noVNC's own page and assets, proxied so they inherit the hub's login."""
    url = f"{settings.eta_vnc_url.rstrip('/')}/{path or 'vnc.html'}"
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(url, params=dict(request.query_params))
    except httpx.HTTPError as exc:
        return JSONResponse({"error": f"شاشة البراوزر مش شغالة: {type(exc).__name__}"}, status_code=503)
    keep = {k: v for k, v in r.headers.items()
            if k.lower() in ("content-type", "cache-control", "etag", "last-modified")}
    return Response(r.content, status_code=r.status_code, headers=keep)


@vnc_router.websocket("/websockify")
async def vnc_socket(ws: WebSocket, settings: Settings = Depends(get_settings)):
    """The screen itself. Authenticated here rather than by the middleware, which
    never sees WebSocket connections — an unguarded socket to a signed-in tax
    portal is exactly the hole this platform exists to close."""
    if settings.auth_enabled:
        user = auth_service.current_user_from_cookie(ws.cookies.get(COOKIE_NAME), settings)
        if not user or not auth_service.store(settings).allowed(user["username"], "vat", "edit"):
            await ws.close(code=4401)
            return
    await ws.accept(subprotocol="binary")
    try:
        import websockets
    except ImportError:  # pragma: no cover — dependency is pinned in requirements
        await ws.close(code=1011)
        return
    target = settings.eta_vnc_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    try:
        async with websockets.connect(f"{target}/websockify", subprotocols=["binary"],
                                      max_size=None, open_timeout=20) as up:
            async def to_up():
                while True:
                    await up.send(await ws.receive_bytes())

            async def to_down():
                while True:
                    await ws.send_bytes(await up.recv())

            done, pending = await asyncio.wait(
                [asyncio.create_task(to_up()), asyncio.create_task(to_down())],
                return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except Exception as exc:  # noqa: BLE001 — a dropped screen is not an outage
        log.info("vnc socket closed: %s", type(exc).__name__)
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass
