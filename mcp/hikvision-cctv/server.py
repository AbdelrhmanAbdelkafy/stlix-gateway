#!/usr/bin/env python3
"""Hikvision CCTV MCP server — the cameras as tools for Claude.

Talks to the STLIX gateway (`/api/v1/cctv/*`), never to a DVR directly, so it
works from anywhere the gateway is reachable and needs only a gateway key.
Same stdio pattern as the WeChat/WhatsApp MCPs in D:\\WECHAT.

Claude Desktop (claude_desktop_config.json):
    "stlix-cctv": {
      "command": "python",
      "args": ["D:/Nama Code project/stlix-gateway/mcp/hikvision-cctv/server.py"],
      "env": {"STLIX_GATEWAY_URL": "https://gw.stlixvalley.com",
              "STLIX_GATEWAY_KEY": "<gateway key>"}
    }

Deps: pip install mcp httpx
"""
from __future__ import annotations

import base64
import os

import httpx
from mcp.server.fastmcp import FastMCP, Image

GW = os.environ.get("STLIX_GATEWAY_URL", "https://gw.stlixvalley.com").rstrip("/")
KEY = os.environ.get("STLIX_GATEWAY_KEY", "")
H = {"X-API-Key": KEY, "Accept": "application/json", "User-Agent": "stlix-cctv-mcp/1"}

mcp = FastMCP("stlix-cctv", instructions=(
    "Cameras of STLIX (Hikvision DVRs) as reported by the LAN agent. Always mention "
    "`age_s`/`stale` — a snapshot is the last frame the agent uploaded, not live video."))


def _get(path: str, **params):
    with httpx.Client(timeout=20) as c:
        r = c.get(GW + path, headers=H, params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
def cctv_status() -> dict:
    """Overview: agent freshness (age_s, stale), DVR/channel counts, recent events."""
    ov = _get("/api/v1/cctv")
    ov.pop("devices", None)
    return ov


@mcp.tool()
def cctv_devices() -> list[dict]:
    """Every DVR/NVR: model, firmware, host, online, storage (HDD capacity/free/status), channel counts."""
    return [{k: v for k, v in d.items() if k != "channels"} for d in _get("/api/v1/cctv/devices")["devices"]]


@mcp.tool()
def cctv_channels(device: str) -> dict:
    """Channels of one DVR (by device id) with online flag and snapshot age in seconds."""
    return _get(f"/api/v1/cctv/devices/{device}/channels")


@mcp.tool()
def cctv_events(limit: int = 50, device: str | None = None) -> list[dict]:
    """Recent DVR events: VMD (motion), linedetection, videoloss, diskfull… newest first."""
    params = {"limit": limit}
    if device:
        params["device"] = device
    return _get("/api/v1/cctv/events", **params)["events"]


@mcp.tool()
def cctv_snapshot(device: str, channel: str) -> Image:
    """Last frame of one channel as an image (look at it to answer 'what's at the gate?')."""
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{GW}/api/v1/cctv/snapshot/{device}/{channel}.jpg", headers={"X-API-Key": KEY})
        r.raise_for_status()
    return Image(data=r.content, format="jpeg")


@mcp.tool()
def cctv_snapshot_b64(device: str, channel: str) -> dict:
    """Same frame as base64 (for clients that cannot render Image content)."""
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{GW}/api/v1/cctv/snapshot/{device}/{channel}.jpg", headers={"X-API-Key": KEY})
        r.raise_for_status()
    return {"device": device, "channel": channel, "age_s": r.headers.get("X-Snapshot-Age"),
            "jpeg_base64": base64.b64encode(r.content).decode()}


if __name__ == "__main__":
    mcp.run()
