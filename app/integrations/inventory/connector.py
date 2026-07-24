"""Inventory / Stocktake connector (الجرد) - reads the count app (read-only)."""
from __future__ import annotations

from ...config import Settings
from ..base import Connector, ConnectorMode
from .client import StocktakeClient


class InventoryConnector(Connector):
    key = "inventory"

    def __init__(self, settings: Settings) -> None:
        super().__init__(ConnectorMode(settings.inventory_mode))
        self.configured = settings.inventory_configured
        self._client = StocktakeClient(settings)

    async def snapshot(self) -> dict:
        return await self._client.snapshot(0)

    async def progress(self) -> dict:
        snap = await self.snapshot()
        items = snap.get("items", {}) or {}
        manual = snap.get("manual", []) or []
        counted = [
            {"code": k, "q": v.get("q"), "u": v.get("u"), "counter": v.get("counter"), "zone": v.get("zone")}
            for k, v in items.items()
            if v.get("q") is not None
        ]
        counters = sorted(
            {(v.get("counter") or "؟") for v in items.values()}
            | {(m.get("counter") or "؟") for m in manual}
        )
        return {
            "rev": snap.get("rev"),
            "tracked": len(items),
            "counted": len(counted),
            "manual": len(manual),
            "counters": counters,
            "counted_items": counted,
            "manual_items": manual,
        }

    async def ping(self) -> dict:
        # large `since` => empty, cheap delta
        return await self._client.snapshot(10**12)
