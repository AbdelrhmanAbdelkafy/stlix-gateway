"""CCTV endpoints — the hub reads, the LAN agent writes.

Two doors:

- `/api/v1/cctv/*` reads: the usual gateway key or a logged-in session
  (permission resource `cameras`).
- `/api/v1/cctv/push*` writes: the agent's own key (`X-CCTV-Agent-Key` =
  `CCTV_AGENT_KEY`). Least privilege — a leaked agent key can only upload
  camera state, never read Nama or the CRM. A gateway key is accepted too, so
  a person can test with curl.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from . import store

router = APIRouter(prefix="/cctv", tags=["cctv"], dependencies=[Depends(require_api_key)])
push_router = APIRouter(prefix="/cctv", tags=["cctv"])


def _agent_auth(x_cctv_agent_key: str | None = Header(default=None),
                x_api_key: str | None = Header(default=None),
                settings: Settings = Depends(get_settings)) -> None:
    if settings.cctv_agent_key and x_cctv_agent_key == settings.cctv_agent_key:
        return
    if x_api_key and x_api_key in settings.api_keys:
        return
    if not settings.cctv_agent_key and not settings.api_keys:
        return  # dev: nothing configured, nothing to check
    raise HTTPException(status_code=401, detail="agent key required")


# --- reads -------------------------------------------------------------------
@router.get("")
async def overview(request: Request, settings: Settings = Depends(get_settings)):
    """Everything the cameras card needs: agent freshness, devices, channels, storage."""
    ov = store.overview(settings)
    rows = [{"metric": "أجهزة DVR", "value": f"{ov['summary']['devices_online']}/{ov['summary']['devices']} online"},
            {"metric": "قنوات", "value": f"{ov['summary']['channels_online']}/{ov['summary']['channels']} online"},
            {"metric": "آخر تقرير من الـ agent", "value": f"{ov['age_s']} ث" if ov["age_s"] is not None else "—"},
            {"metric": "الحالة", "value": "قديم/ساكت" if ov["stale"] else "لايف"},
            {"metric": "الصفحة", "value": "/tools/cctv"}]
    return respond(request, ov, title="CCTV · الكاميرات", rows=rows, columns=["metric", "value"])


@router.get("/devices")
async def devices(request: Request, settings: Settings = Depends(get_settings)):
    """DVR list with model, firmware, storage and channel counts."""
    ov = store.overview(settings)
    rows = [{"id": d["id"], "name": d["name"], "model": d["model"], "host": d["host"],
             "online": d["online"], "channels": f"{d['channels_online']}/{d['channels_total']}",
             "storage": ", ".join(f"{s.get('name')} {s.get('status')}" for s in d["storage"]) or "—"}
            for d in ov["devices"]]
    return respond(request, {"count": len(rows), "stale": ov["stale"], "devices": ov["devices"]},
                   title="CCTV devices", rows=rows,
                   columns=["id", "name", "model", "host", "online", "channels", "storage"])


@router.get("/devices/{device}/channels")
async def channels(device: str, request: Request, settings: Settings = Depends(get_settings)):
    """Channels of one DVR, each with its last snapshot URL and age."""
    ov = store.overview(settings)
    d = next((x for x in ov["devices"] if x["id"] == device), None)
    if not d:
        raise HTTPException(status_code=404, detail=f"unknown device {device}")
    return respond(request, {"device": d["id"], "name": d["name"], "channels": d["channels"]},
                   title=f"CCTV · {d['name']}", rows=d["channels"],
                   columns=["id", "name", "online", "resolution", "snapshot_age_s", "snapshot_url"])


@router.get("/events")
async def recent_events(request: Request, limit: int = 100, device: str | None = None,
                        settings: Settings = Depends(get_settings)):
    """Motion / line-crossing / video-loss / disk events the agent relayed."""
    evs = store.events(min(max(limit, 1), 500), device, settings)
    return respond(request, {"count": len(evs), "events": evs}, title="CCTV events", rows=evs,
                   columns=["ts", "device", "channel", "type", "state", "detail"])


@router.get("/snapshot/{device}/{channel}.jpg")
async def snapshot(device: str, channel: str, settings: Settings = Depends(get_settings)):
    """Last frame the agent uploaded for this channel (JPEG)."""
    try:
        p = store.snapshot_path(device, channel, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not p.exists():
        raise HTTPException(status_code=404, detail="no snapshot yet")
    return FileResponse(p, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store", "X-Snapshot-Age": str(round(store.snapshot_age(device, channel, settings) or 0))})


# --- writes (agent) ----------------------------------------------------------
@push_router.post("/push", dependencies=[Depends(_agent_auth)])
async def push(request: Request, settings: Settings = Depends(get_settings)):
    """The agent's periodic report: devices, channels, storage, events."""
    try:
        payload = await request.json()
        out = store.push(payload, settings)
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": "bad payload", "detail": str(exc)}, status_code=400)
    return out


@push_router.post("/push/snapshot/{device}/{channel}", dependencies=[Depends(_agent_auth)])
async def push_snapshot(device: str, channel: str, request: Request,
                        settings: Settings = Depends(get_settings)):
    """One JPEG frame, raw body (`Content-Type: image/jpeg`)."""
    body = await request.body()
    if len(body) > 4 * 1024 * 1024:
        return JSONResponse({"error": "snapshot too large (4 MB max)"}, status_code=413)
    try:
        return store.save_snapshot(device, channel, body, settings)
    except ValueError as exc:
        return JSONResponse({"error": "bad snapshot", "detail": str(exc)}, status_code=400)
