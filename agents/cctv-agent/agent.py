#!/usr/bin/env python3
"""STLIX CCTV agent — runs on a PC inside the factory LAN.

Polls every Hikvision DVR/NVR in `config.json` over ISAPI (the HTTP API every
Hikvision recorder ships with, usually port 80) and pushes to the gateway:

    device info      GET /ISAPI/System/deviceInfo
    device status    GET /ISAPI/System/status                (cpu, memory, uptime)
    storage          GET /ISAPI/ContentMgmt/Storage          (HDDs: capacity/free/status)
    channels         GET /ISAPI/System/Video/inputs/channels (analog) +
                     GET /ISAPI/ContentMgmt/InputProxy/channels (IP cams on hybrid DVRs)
    snapshot         GET /ISAPI/Streaming/channels/<ch>01/picture   (sub-stream <ch>02 if main fails)
    events           GET /ISAPI/Event/notification/alertStream (long-poll, optional)

DVR passwords stay in this PC's config.json. The gateway only ever gets state
and JPEGs, authenticated with CCTV_AGENT_KEY. Nothing here opens a port.

Usage:  python agent.py [config.json]      (or run-cctv-agent.bat on Windows)
Deps:   pip install requests
"""
from __future__ import annotations

import json
import logging
import re
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPDigestAuth, HTTPBasicAuth
except ImportError:  # pragma: no cover
    print("pip install requests", file=sys.stderr)
    raise

VERSION = "1.0.0"
log = logging.getLogger("cctv-agent")
_NS = re.compile(r"\{[^}]+\}")  # strip XML namespaces


def _xml(text: str) -> ET.Element | None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    for el in root.iter():
        el.tag = _NS.sub("", el.tag)
    return root


def _t(el: ET.Element | None, tag: str, default=None):
    if el is None:
        return default
    f = el.find(f".//{tag}")
    return f.text.strip() if f is not None and f.text else default


class Dvr:
    def __init__(self, cfg: dict, timeout: float):
        self.cfg = cfg
        self.id = cfg["id"]
        self.base = f"{cfg.get('scheme', 'http')}://{cfg['host']}:{cfg.get('port', 80)}"
        self.timeout = timeout
        self.s = requests.Session()
        self.s.verify = False
        # Hikvision defaults to digest; some firmware accepts basic. Try digest first.
        self.auths = [HTTPDigestAuth(cfg["user"], cfg["password"]), HTTPBasicAuth(cfg["user"], cfg["password"])]
        self.auth = self.auths[0]

    def get(self, path: str, **kw) -> requests.Response:
        r = self.s.get(self.base + path, auth=self.auth, timeout=self.timeout, **kw)
        if r.status_code == 401 and self.auth is self.auths[0]:
            self.auth = self.auths[1]
            r = self.s.get(self.base + path, auth=self.auth, timeout=self.timeout, **kw)
        return r

    def xml(self, path: str) -> ET.Element | None:
        r = self.get(path)
        return _xml(r.text) if r.ok else None

    # --- pieces ---------------------------------------------------------------
    def info(self) -> dict:
        x = self.xml("/ISAPI/System/deviceInfo")
        if x is None:
            raise RuntimeError("deviceInfo unreachable")
        return {"model": _t(x, "model"), "serial": _t(x, "serialNumber"),
                "firmware": _t(x, "firmwareVersion"), "device_name": _t(x, "deviceName")}

    def status(self) -> dict:
        x = self.xml("/ISAPI/System/status")
        if x is None:
            return {}
        out = {"device_time": _t(x, "currentDeviceTime"), "uptime_s": _t(x, "deviceUpTime")}
        cpu = x.find(".//CPU/cpuUtilization")
        mem = x.find(".//Memory/memoryUsage")
        out["cpu_pct"] = int(cpu.text) if cpu is not None and cpu.text and cpu.text.isdigit() else None
        out["mem_pct"] = int(mem.text) if mem is not None and mem.text and mem.text.isdigit() else None
        try:
            out["uptime_s"] = int(out["uptime_s"]) if out["uptime_s"] else None
        except ValueError:
            out["uptime_s"] = None
        return out

    def storage(self) -> list[dict]:
        x = self.xml("/ISAPI/ContentMgmt/Storage")
        if x is None:
            return []
        out = []
        for h in x.iter("hdd"):
            out.append({"name": _t(h, "hddName") or f"HDD{_t(h, 'id')}", "status": _t(h, "status"),
                        "capacity_mb": int(_t(h, "capacity", 0) or 0), "free_mb": int(_t(h, "freeSpace", 0) or 0)})
        for n in x.iter("nas"):
            out.append({"name": _t(n, "ipAddress") or "NAS", "status": _t(n, "status"),
                        "capacity_mb": int(_t(n, "capacity", 0) or 0), "free_mb": int(_t(n, "freeSpace", 0) or 0)})
        return out

    def channels(self) -> list[dict]:
        chans: dict[str, dict] = {}
        x = self.xml("/ISAPI/System/Video/inputs/channels")
        if x is not None:
            for c in x.iter("VideoInputChannel"):
                cid = _t(c, "id")
                if not cid:
                    continue
                enabled = (_t(c, "videoInputEnabled", "true") or "true").lower() == "true"
                chans[cid] = {"id": cid, "name": _t(c, "name") or f"Camera {cid}", "enabled": enabled,
                              "online": None, "resolution": _t(c, "resDesc")}
        x = self.xml("/ISAPI/ContentMgmt/InputProxy/channels")
        if x is not None:
            for c in x.iter("InputProxyChannel"):
                cid = _t(c, "id")
                if not cid:
                    continue
                chans[cid] = {"id": cid, "name": _t(c, "name") or f"IPC {cid}", "enabled": True,
                              "online": None, "resolution": None}
            st = self.xml("/ISAPI/ContentMgmt/InputProxy/channels/status")
            if st is not None:
                for c in st.iter("InputProxyChannelStatus"):
                    cid = _t(c, "id")
                    if cid in chans:
                        chans[cid]["online"] = (_t(c, "online", "false") or "false").lower() == "true"
        # analog channels have no online flag; videoloss is the closest signal
        x = self.xml("/ISAPI/System/Video/inputs/channels/videoLoss")  # not on all firmware
        only = self.cfg.get("channels")
        out = [c for c in chans.values() if not only or c["id"] in {str(i) for i in only}]
        return sorted(out, key=lambda c: int(c["id"]) if c["id"].isdigit() else 0)

    def snapshot(self, cid: str) -> bytes | None:
        for stream in ("01", "02"):
            try:
                r = self.get(f"/ISAPI/Streaming/channels/{cid}{stream}/picture",
                             params={"videoResolutionWidth": 640, "videoResolutionHeight": 360})
            except requests.RequestException:
                continue
            if r.ok and r.content.startswith(b"\xff\xd8"):
                return r.content
        return None


class Gateway:
    def __init__(self, cfg: dict):
        self.base = cfg["url"].rstrip("/")
        self.h = {"X-CCTV-Agent-Key": cfg["agent_key"], "User-Agent": f"stlix-cctv-agent/{VERSION}"}
        self.timeout = float(cfg.get("timeout", 20))

    def push(self, payload: dict) -> dict:
        r = requests.post(self.base + "/api/v1/cctv/push", json=payload, headers=self.h, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def snapshot(self, device: str, channel: str, jpeg: bytes) -> None:
        r = requests.post(f"{self.base}/api/v1/cctv/push/snapshot/{device}/{channel}", data=jpeg,
                          headers={**self.h, "Content-Type": "image/jpeg"}, timeout=self.timeout)
        r.raise_for_status()


class EventTail(threading.Thread):
    """Long-poll /ISAPI/Event/notification/alertStream and buffer events."""

    def __init__(self, dvr: Dvr):
        super().__init__(daemon=True, name=f"events-{dvr.id}")
        self.dvr, self.buf, self.lock = dvr, [], threading.Lock()

    def drain(self) -> list[dict]:
        with self.lock:
            out, self.buf = self.buf, []
        return out

    def run(self) -> None:
        while True:
            try:
                with self.dvr.s.get(self.dvr.base + "/ISAPI/Event/notification/alertStream",
                                    auth=self.dvr.auth, stream=True, timeout=(10, 90)) as r:
                    chunk = b""
                    for line in r.iter_lines():
                        if line.startswith(b"--boundary") or line.startswith(b"--"):
                            self._parse(chunk)
                            chunk = b""
                        else:
                            chunk += line + b"\n"
            except Exception as exc:  # noqa: BLE001
                log.debug("%s alertStream: %s", self.dvr.id, exc)
                time.sleep(15)

    def _parse(self, chunk: bytes) -> None:
        i = chunk.find(b"<")
        if i < 0:
            return
        x = _xml(chunk[i:].decode("utf-8", "ignore"))
        if x is None:
            return
        etype = _t(x, "eventType")
        if not etype or etype == "videoloss" and _t(x, "eventState") == "inactive":
            return
        if etype == "videoloss" and _t(x, "eventState") == "active" and self.dvr.cfg.get("ignore_heartbeat", True):
            # Hikvision sends a videoloss/inactive heartbeat every second; only real ones are 'active'
            pass
        with self.lock:
            self.buf.append({"ts": time.time(), "device": self.dvr.id,
                             "channel": _t(x, "channelID") or _t(x, "dynChannelID") or "",
                             "type": etype, "state": _t(x, "eventState") or "",
                             "detail": _t(x, "eventDescription") or ""})
            self.buf = self.buf[-200:]


def collect(dvr: Dvr, snap_every: int, tick: int) -> tuple[dict, list[tuple[str, bytes]]]:
    d = {"id": dvr.id, "name": dvr.cfg.get("name", dvr.id), "host": dvr.cfg["host"],
         "site": dvr.cfg.get("site"), "online": False, "channels": [], "storage": [], "error": None}
    frames: list[tuple[str, bytes]] = []
    try:
        d.update(dvr.info())
        d["online"] = True
        d.update(dvr.status())
        d["storage"] = dvr.storage()
        d["channels"] = dvr.channels()
        if snap_every and tick % snap_every == 0:
            for c in d["channels"]:
                if not c["enabled"] or c["online"] is False:
                    continue
                jpeg = dvr.snapshot(c["id"])
                if jpeg:
                    c["snapshot_at"] = time.time()
                    c["online"] = True if c["online"] is None else c["online"]
                    frames.append((c["id"], jpeg))
                elif c["online"] is None:
                    c["online"] = False  # analog channel that gives no picture = no signal
    except Exception as exc:  # noqa: BLE001
        d["error"] = f"{type(exc).__name__}: {exc}"[:200]
        log.warning("%s: %s", dvr.id, d["error"])
    return d, frames


def main(cfg_path: str) -> None:
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    logging.basicConfig(level=getattr(logging, cfg.get("log_level", "INFO")),
                        format="%(asctime)s %(levelname)s %(message)s")
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    gw = Gateway(cfg["gateway"])
    interval = int(cfg.get("interval_s", 60))
    snap_every = int(cfg.get("snapshot_every_n_ticks", 1))
    dvrs = [Dvr(d, float(cfg.get("dvr_timeout", 8))) for d in cfg["devices"] if d.get("enabled", True)]
    tails = [EventTail(d) for d in dvrs] if cfg.get("events", True) else []
    for t in tails:
        t.start()
    log.info("agent %s: %d DVRs -> %s every %ss", VERSION, len(dvrs), gw.base, interval)
    tick = 0
    while True:
        t0 = time.time()
        devices, all_frames = [], []
        for dvr in dvrs:
            d, frames = collect(dvr, snap_every, tick)
            devices.append(d)
            all_frames += [(dvr.id, cid, jpeg) for cid, jpeg in frames]
        events = [e for t in tails for e in t.drain()]
        payload = {"agent_id": cfg.get("agent_id", "cctv-agent"), "agent_version": VERSION,
                   "agent_host": socket.gethostname(), "interval_s": interval, "sent_at": time.time(),
                   "devices": devices, "events": events}
        try:
            out = gw.push(payload)
            for dev, cid, jpeg in all_frames:
                try:
                    gw.snapshot(dev, cid, jpeg)
                except Exception as exc:  # noqa: BLE001
                    log.warning("snapshot %s/%s: %s", dev, cid, exc)
            log.info("pushed %s (+%d frames) in %.1fs", out, len(all_frames), time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            log.error("push failed: %s", exc)
        tick += 1
        time.sleep(max(5, interval - (time.time() - t0)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("config.json")))
