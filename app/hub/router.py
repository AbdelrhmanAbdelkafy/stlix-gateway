"""`/hub/*` pages and `/api/v1/hub/*` (catalog, live snapshot, SSE)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from ..auth import service
from ..auth.resources import BY_KEY, as_dicts as resources_as_dicts
from ..config import Settings, get_settings
from .live import live

_ROOT = Path(__file__).resolve().parent.parent.parent
_HUB = _ROOT / "modules" / "hub"
_VOICE = '<script src="/tools/voice.js" defer></script>'
#: Files the hub may serve by name. Login is served by `/login`; nothing else.
_PAGES = {"index.html", "platform.html", "admin.html", "resets.html"}

pages = APIRouter(prefix="/hub", tags=["hub"])
api = APIRouter(prefix="/hub", tags=["hub"])


def _page(name: str) -> HTMLResponse:
    if name not in _PAGES:
        raise HTTPException(404, f"no such hub page: {name}")
    body = (_HUB / name).read_text(encoding="utf-8")
    if "/tools/voice.js" not in body:
        body = body.replace("</body>", _VOICE + "\n</body>", 1)
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


@pages.get("/", response_class=HTMLResponse)
async def hub_index() -> HTMLResponse:
    """STLIX Hub — الباب الواحد (الكروت بتتفلتر حسب صلاحيات اللي داخل)."""
    return _page("index.html")


@pages.get("/{name}", response_class=HTMLResponse)
async def hub_page(name: str) -> HTMLResponse:
    """صفحة من صفحات الهَب: platform.html · admin.html."""
    return _page(name)


@api.get("/catalog")
async def catalog(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """الكروت اللي المستخدم الحالي يقدر يشوفها، مع can_edit لكل واحدة.

    Auth off (dev) → everything, so the page works locally with no users."""
    items = resources_as_dicts()
    if not settings.auth_enabled:
        for it in items:
            it["can_edit"] = it["editable"]
        return {"items": [i for i in items if i["key"] != "hub"], "filtered": False}
    user = service.current_user(request, settings)
    perms = service.store(settings).effective(user["username"]) if user else {}
    out = []
    for it in items:
        acts = perms.get(it["key"], [])
        if "view" not in acts or it["key"] == "hub":
            continue
        it["can_edit"] = it["editable"] and "edit" in acts
        out.append(it)
    return {"items": out, "filtered": True}


@api.get("/live")
async def live_snapshot(settings: Settings = Depends(get_settings)) -> dict:
    """لقطة حالة كل الأنظمة (cache لثواني) — up/down، latency، أرقام."""
    return await live.get(max_age=settings.hub_live_interval)


@api.get("/events")
async def live_events(request: Request, once: bool = False,
                      settings: Settings = Depends(get_settings)):
    """Server-Sent Events: نفس اللقطة بتتبعت لوحدها كل HUB_LIVE_INTERVAL ثانية.

    `?once=1` sends a single event and closes — for curl checks and tests."""
    q = live.subscribe()
    if not once:
        live.ensure_loop(settings.hub_live_interval)
    else:
        await live.get(max_age=settings.hub_live_interval)

    async def gen():
        try:
            yield "retry: 5000\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: live\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    if once:
                        return
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            live.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def resource_keys() -> list[str]:
    return list(BY_KEY)
