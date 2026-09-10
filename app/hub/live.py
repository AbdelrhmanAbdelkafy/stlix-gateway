"""One snapshot of every system's health, refreshed in the background.

Two kinds of probe, both bounded by a short timeout so a dead upstream costs
seconds, never a hang:

- **connector probes** — Nama, CRM, stocktake, banks, finance, expert, rep,
  the gateway itself: `configured` from settings, `reachable` from a real
  ping, plus a couple of numbers the card can show.
- **site probes** — HTTPS HEAD/GET against our own web systems (CRM, ERP,
  attendance, payroll, websites): status code + latency.

The snapshot is cached; `/api/v1/hub/live` returns the last one instantly and
`/api/v1/hub/events` streams a new one every `HUB_LIVE_INTERVAL` seconds.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from ..config import Settings, get_settings
from ..core.metrics import metrics

PROBE_TIMEOUT = 5.0

#: Our own web systems — key → URL. Keys match `Resource.live_key` ("site:<key>").
SITES: dict[str, str] = {
    "crm": "https://crm.stlixvalley.com/",
    "erp": "https://stlixvalley.namasoft.net/erp",
    "attendance": "https://attendance.stlixvalley.com/ping",
    "payroll": "https://payroll.stlixvalley.com/",
    "website": "https://stlixvalley.com/",
    "egygrouphs": "https://egygrouphs.com/",
}


async def _timed(coro, timeout: float = PROBE_TIMEOUT) -> tuple[Any, str | None, float]:
    t0 = time.perf_counter()
    try:
        out = await asyncio.wait_for(coro, timeout)
        return out, None, (time.perf_counter() - t0) * 1000
    except asyncio.TimeoutError:
        return None, "timeout", (time.perf_counter() - t0) * 1000
    except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
        return None, f"{type(exc).__name__}: {exc}"[:200], (time.perf_counter() - t0) * 1000


async def _probe_site(client: httpx.AsyncClient, key: str, url: str) -> dict:
    async def go():
        r = await client.get(url, follow_redirects=True)
        return r.status_code
    code, err, ms = await _timed(go())
    up = err is None and code is not None and code < 500
    return {"key": f"site:{key}", "kind": "site", "url": url, "up": up,
            "status": code, "error": err, "latency_ms": round(ms)}


async def _probe_nama(settings: Settings) -> dict:
    from ..integrations.nama.connector import NamaConnector
    out = {"key": "nama", "kind": "connector", "configured": settings.nama_configured,
           "mode": settings.nama_mode, "up": False}
    if not settings.nama_configured:
        out.update(error="مفاتيح نما مش متحطة في .env", latency_ms=0)
        return out
    _, err, ms = await _timed(NamaConnector(settings).ping())
    out.update(up=err is None, error=err, latency_ms=round(ms))
    return out


async def _probe_crm(settings: Settings) -> dict:
    from ..integrations.crm.connector import CrmConnector
    out = {"key": "crm", "kind": "connector", "configured": settings.crm_configured,
           "mode": settings.crm_mode, "up": False}
    if not settings.crm_configured:
        out.update(error="مفاتيح vTiger مش متحطة في .env", latency_ms=0)
        return out
    conn = CrmConnector(settings)
    _, err, ms = await _timed(conn.ping())
    out.update(up=err is None, error=err, latency_ms=round(ms))
    if err is None:
        leads, err2, _ = await _timed(conn.query("Leads", limit=100))
        if err2 is None and isinstance(leads, list):
            out["numbers"] = {"leads": len(leads)}
    return out


async def _probe_inventory(settings: Settings) -> dict:
    from ..integrations.inventory.connector import InventoryConnector
    out = {"key": "inventory", "kind": "connector", "configured": settings.inventory_configured,
           "mode": settings.inventory_mode, "up": False}
    if not settings.inventory_configured:
        out.update(error="مفتاح تطبيق الجرد مش متحط في .env", latency_ms=0)
        return out
    prog, err, ms = await _timed(InventoryConnector(settings).progress())
    out.update(up=err is None, error=err, latency_ms=round(ms))
    if prog:
        out["numbers"] = {"tracked": prog.get("tracked"), "counted": prog.get("counted"),
                          "manual": prog.get("manual"), "counters": len(prog.get("counters") or [])}
    return out


async def _probe_finance(settings: Settings) -> dict:
    out = {"key": "finance", "kind": "connector", "configured": settings.nama_sql_configured,
           "mode": settings.finance_default_source, "up": settings.nama_sql_configured or False,
           "latency_ms": 0}
    if not settings.nama_sql_configured:
        out["error"] = "SQL مش متاح من السيرفر — الأرقام snapshot"
    return out


async def _probe_expert(settings: Settings) -> dict:
    from ..integrations.expert import knowledge
    st, err, ms = await _timed(asyncio.to_thread(knowledge.stats))
    out = {"key": "expert", "kind": "connector", "configured": settings.expert_grounded,
           "mode": "grounded" if settings.expert_grounded else "sources_only",
           "up": err is None, "error": err, "latency_ms": round(ms)}
    if isinstance(st, dict):
        out["numbers"] = {k: v for k, v in st.items() if isinstance(v, (int, float))}
    return out


async def _probe_rep() -> dict:
    from ..integrations.rep import store as rep
    ov, err, ms = await _timed(asyncio.to_thread(rep.overview))
    out = {"key": "rep", "kind": "connector", "configured": True, "mode": "read_only",
           "up": err is None, "error": err, "latency_ms": round(ms)}
    if isinstance(ov, dict):
        out["numbers"] = {"holders": ov.get("custody", {}).get("holders"),
                          "vehicles": ov.get("custody", {}).get("vehicles_held"),
                          "team": ov.get("movement", {}).get("team"),
                          "alerts": len(ov.get("alerts") or [])}
    return out


async def _probe_cctv(settings: Settings) -> dict:
    from ..integrations.cctv import store as cctv
    ov, err, ms = await _timed(asyncio.to_thread(cctv.overview, settings))
    out = {"key": "cctv", "kind": "connector", "configured": settings.cctv_configured,
           "mode": "push", "up": False, "error": err, "latency_ms": round(ms)}
    if isinstance(ov, dict):
        out["up"] = not ov["stale"]
        out["error"] = ov.get("note")
        out["numbers"] = {"devices": ov["summary"]["devices_online"], "channels": ov["summary"]["channels_online"],
                          "channels_total": ov["summary"]["channels"], "age_s": ov["age_s"]}
    return out


async def _probe_vat(settings: Settings) -> dict:
    from ..integrations.eta import store as eta_store
    out = {"key": "vat", "kind": "connector", "configured": settings.eta_configured, "mode": settings.vat_k_mode,
           "up": False, "latency_ms": 0}
    if not settings.eta_configured:
        out["error"] = "ETA_ENTITIES_JSON مش متحط في .env"
        return out
    try:
        ents = eta_store.entities(settings)
        t = time.strftime("%Y-%m")
        syncs = [eta_store.last_sync(e.key, t, settings) for e in ents]
        ok = [s for s in syncs if s and s.get("ok")]
        out["up"] = bool(ents) and all(e.configured for e in ents)
        out["numbers"] = {"entities": len(ents), "synced_this_month": len(ok)}
        if not ok:
            out["error"] = "لسه ما اتسحبش الشهر الحالي من البورتال"
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def _probe_gateway() -> dict:
    from .. import __version__
    return {"key": "gateway", "kind": "connector", "configured": True, "up": True, "latency_ms": 0,
            "numbers": {"uptime_h": round(metrics.uptime_seconds / 3600, 1),
                        "requests": metrics.total}, "version": __version__}


async def snapshot(settings: Settings | None = None) -> dict:
    """Probe everything in parallel and return one dict keyed by `live_key`."""
    settings = settings or get_settings()
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT, headers={"User-Agent": "stlix-hub-live/1"}) as client:
        tasks = [
            _probe_nama(settings), _probe_crm(settings), _probe_inventory(settings),
            _probe_finance(settings), _probe_expert(settings), _probe_rep(), _probe_cctv(settings), _probe_vat(settings),
            *[_probe_site(client, k, u) for k, u in SITES.items()],
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    items: dict[str, dict] = {"gateway": _probe_gateway()}
    for r in results:
        if isinstance(r, dict):
            items[r["key"]] = r
    up = sum(1 for v in items.values() if v.get("up"))
    return {"ts": time.time(), "up": up, "total": len(items), "items": items}


class LiveCache:
    """Last snapshot + a background refresher started lazily on first use."""

    def __init__(self) -> None:
        self.data: dict | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._subs: set[asyncio.Queue] = set()

    async def get(self, max_age: float = 20.0) -> dict:
        if self.data and time.time() - self.data["ts"] < max_age:
            return self.data
        async with self._lock:
            if self.data and time.time() - self.data["ts"] < max_age:
                return self.data
            self.data = await snapshot()
            self._publish()
            return self.data

    def _publish(self) -> None:
        for q in list(self._subs):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(self.data)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2)
        self._subs.add(q)
        if self.data:
            q.put_nowait(self.data)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def ensure_loop(self, interval: float) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(interval))

    async def _loop(self, interval: float) -> None:
        while True:
            try:
                await self.get(max_age=interval * 0.5)
            except Exception:  # noqa: BLE001
                pass
            if not self._subs:  # nobody listening — stop, restart on next subscribe
                self._task = None
                return
            await asyncio.sleep(interval)


live = LiveCache()
