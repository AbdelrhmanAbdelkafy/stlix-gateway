"""Async client over the Stlix stocktake counting app (count/sync.php).

Protocol (observed live): POST {base}/sync.php?k=<KEY>&since=<rev>
Response: { rev, items: { <InvCode>: {q,u,counter,zone,ts,rev} }, manual: [ {name,newCode,q,u,counter,zone,ts,rev} ] }
`since=0` returns the full snapshot; a large `since` returns an empty delta (cheap ping).
"""
from __future__ import annotations

import httpx

from ...config import Settings
from ...core.errors import UpstreamError


class StocktakeClient:
    def __init__(self, settings: Settings) -> None:
        self._configured = settings.inventory_configured
        self._url = settings.inventory_base_url.rstrip("/") + "/sync.php"
        self._key = settings.inventory_key
        self._timeout = settings.inventory_timeout

    def _require(self) -> None:
        if not self._configured:
            raise UpstreamError(
                "Inventory (stocktake) not configured; set INVENTORY_BASE_URL / INVENTORY_KEY."
            )

    async def snapshot(self, since: int = 0) -> dict:
        self._require()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(self._url, params={"k": self._key, "since": since})
        except httpx.RequestError as exc:
            raise UpstreamError(f"Stocktake app unreachable: {exc}") from exc
        if r.status_code >= 400:
            raise UpstreamError(f"Stocktake HTTP {r.status_code}: {r.text[:160]}")
        try:
            return r.json()
        except ValueError as exc:
            raise UpstreamError(f"Stocktake non-JSON: {r.text[:160]}") from exc
