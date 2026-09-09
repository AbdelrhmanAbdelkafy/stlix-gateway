"""Last-known CCTV state on disk — written by the LAN agent, read by the hub.

Layout (under `CCTV_DATA_DIR`, default `data/cctv/`):

    state.json                      one document: agent + devices + channels
    events.jsonl                    append-only, newest last, trimmed to 2000
    snapshots/<device>/<channel>.jpg last frame per channel

Every read answers "how old is this?" — a wall of frozen frames that looks
live is worse than an honest "agent silent for 12 min".
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

from ...config import Settings, get_settings

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LOCK = threading.Lock()
_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MAX_EVENTS = 2000


def data_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    p = Path(settings.cctv_data_dir) if settings.cctv_data_dir else _ROOT / "data" / "cctv"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_file(settings: Settings | None = None) -> Path:
    return data_dir(settings) / "state.json"


def _events_file(settings: Settings | None = None) -> Path:
    return data_dir(settings) / "events.jsonl"


def safe_id(value: str) -> str:
    """Device/channel ids come from the agent's config — keep them path-safe."""
    v = str(value).strip()
    if not _SAFE.match(v):
        raise ValueError(f"bad id: {value!r}")
    return v


def load(settings: Settings | None = None) -> dict:
    f = _state_file(settings)
    if not f.exists():
        return {"agent": None, "devices": [], "received_at": None}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"agent": None, "devices": [], "received_at": None, "error": "state.json corrupt"}


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def push(payload: dict, settings: Settings | None = None) -> dict:
    """Accept one full report from the agent. Devices replace the previous set
    (the agent's config is the source of truth); events append."""
    devices = []
    for d in payload.get("devices") or []:
        did = safe_id(d.get("id") or d.get("name") or "")
        chans = []
        for c in d.get("channels") or []:
            cid = safe_id(c.get("id") or "")
            chans.append({
                "id": cid, "name": str(c.get("name") or f"CH{cid}")[:80],
                "enabled": bool(c.get("enabled", True)),
                "online": c.get("online"),               # None = unknown (DVR did not say)
                "resolution": c.get("resolution"),
                "snapshot_at": c.get("snapshot_at"),
            })
        devices.append({
            "id": did, "name": str(d.get("name") or did)[:80],
            "model": d.get("model"), "serial": d.get("serial"),
            "firmware": d.get("firmware"), "host": d.get("host"),
            "site": d.get("site"), "online": bool(d.get("online")),
            "error": d.get("error"),
            "device_time": d.get("device_time"), "uptime_s": d.get("uptime_s"),
            "cpu_pct": d.get("cpu_pct"), "mem_pct": d.get("mem_pct"),
            "storage": d.get("storage") or [],           # [{name, capacity_mb, free_mb, status}]
            "channels": chans,
            "channels_online": sum(1 for c in chans if c["online"]),
            "channels_total": len(chans),
        })
    now = time.time()
    state = {
        "agent": {
            "id": str(payload.get("agent_id") or "cctv-agent")[:64],
            "version": payload.get("agent_version"),
            "host": payload.get("agent_host"),
            "interval_s": payload.get("interval_s"),
            "sent_at": payload.get("sent_at"),
        },
        "received_at": now,
        "devices": devices,
    }
    with _LOCK:
        _atomic_write(_state_file(settings), json.dumps(state, ensure_ascii=False, indent=1))
        evs = payload.get("events") or []
        if evs:
            _append_events(evs, now, settings)
    return {"ok": True, "devices": len(devices),
            "channels": sum(d["channels_total"] for d in devices), "events": len(evs)}


def _append_events(events: list[dict], now: float, settings: Settings | None) -> None:
    f = _events_file(settings)
    lines = []
    for e in events[:500]:
        lines.append(json.dumps({
            "ts": e.get("ts") or now, "received_at": now,
            "device": str(e.get("device") or "")[:64], "channel": str(e.get("channel") or "")[:64],
            "type": str(e.get("type") or "event")[:64],     # VMD | linedetection | videoloss | diskfull | ...
            "state": str(e.get("state") or "")[:32],
            "detail": str(e.get("detail") or "")[:300],
        }, ensure_ascii=False))
    existing = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    keep = (existing + lines)[-MAX_EVENTS:]
    _atomic_write(f, "\n".join(keep) + "\n")


def events(limit: int = 100, device: str | None = None, settings: Settings | None = None) -> list[dict]:
    f = _events_file(settings)
    if not f.exists():
        return []
    out = []
    for line in reversed(f.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if device and e.get("device") != device:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


def snapshot_path(device: str, channel: str, settings: Settings | None = None) -> Path:
    d = data_dir(settings) / "snapshots" / safe_id(device)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe_id(channel)}.jpg"


def save_snapshot(device: str, channel: str, data: bytes, settings: Settings | None = None) -> dict:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("not a JPEG")
    p = snapshot_path(device, channel, settings)
    with _LOCK:
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)
    return {"ok": True, "device": device, "channel": channel, "bytes": len(data)}


def snapshot_age(device: str, channel: str, settings: Settings | None = None) -> float | None:
    p = snapshot_path(device, channel, settings)
    return (time.time() - p.stat().st_mtime) if p.exists() else None


def overview(settings: Settings | None = None) -> dict:
    """The one document the hub card and the MCP server read."""
    settings = settings or get_settings()
    st = load(settings)
    age = (time.time() - st["received_at"]) if st.get("received_at") else None
    stale = age is None or age > settings.cctv_stale_seconds
    devs = st.get("devices") or []
    for d in devs:
        for c in d["channels"]:
            c["snapshot_age_s"] = (lambda a: round(a) if a is not None else None)(
                snapshot_age(d["id"], c["id"], settings))
            c["snapshot_url"] = f"/api/v1/cctv/snapshot/{d['id']}/{c['id']}.jpg"
    online = sum(1 for d in devs if d.get("online"))
    ch_total = sum(d["channels_total"] for d in devs)
    ch_online = sum(d["channels_online"] for d in devs)
    recent = events(20, settings=settings)
    return {
        "configured": settings.cctv_configured,
        "agent": st.get("agent"),
        "received_at": st.get("received_at"),
        "age_s": round(age) if age is not None else None,
        "stale": stale,
        "stale_after_s": settings.cctv_stale_seconds,
        "summary": {"devices": len(devs), "devices_online": online,
                    "channels": ch_total, "channels_online": ch_online,
                    "events_recent": len(recent)},
        "devices": devs,
        "recent_events": recent,
        "note": ("لسه مفيش agent بعت حاجة — شغّل agents/cctv-agent على جهاز في شبكة المصنع"
                 if st.get("received_at") is None else
                 ("الـ agent ساكت — آخر تقرير من {} ثانية".format(round(age)) if stale else None)),
    }
