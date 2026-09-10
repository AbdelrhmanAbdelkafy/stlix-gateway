"""HTTP client for the ETA e-invoicing API (SDK v1.0).

Here: the calls the VAT planner makes every hour —

- token: POST {identity}/connect/token, client_credentials, scope InvoicingAPI
  (cached until ~5 min before expiry)
- documents: GET /api/v1.0/documents/search — 30-day windows, continuation
  token paging, 1 request / 2 s throttle (the portal's own limit)
- details:   GET /api/v1.0/documents/{uuid}/details — lines + taxTotals

Everything else the portal offers — recent, raw, PDF, notifications, document
types, month packages, and the two state changes — is in `portal.py`, mixed in.
"""
from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import httpx

from .portal import PortalOps

ENVS = {
    "prod": ("https://id.eta.gov.eg", "https://api.invoicing.eta.gov.eg"),
    "preprod": ("https://id.preprod.eta.gov.eg", "https://api.preprod.invoicing.eta.gov.eg"),
}
THROTTLE_S = 2.1
WINDOW_DAYS = 30


@dataclass
class Entity:
    """One legal entity = one ETA taxpayer system."""
    key: str
    name: str
    rin: str = ""                    # tax registration number (shown, never secret)
    client_id: str = ""
    client_secret: str = ""
    k_manufacturing: float = 0.0     # ‰ of sales to end up paying — manufacturing part
    k_trading: float = 0.0           # ‰ of sales — trading part
    customs_issuer_ids: list[str] = field(default_factory=list)  # Received docs from these = imports

    @property
    def k_total(self) -> float:
        return self.k_manufacturing + self.k_trading

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def public(self) -> dict:
        return {"key": self.key, "name": self.name, "rin": self.rin, "configured": self.configured,
                "k_manufacturing": self.k_manufacturing, "k_trading": self.k_trading, "k_total": self.k_total}


class EtaError(RuntimeError):
    pass


class EtaClient(PortalOps):
    def __init__(self, entity: Entity, env: str = "prod", timeout: float = 30.0):
        if env not in ENVS:
            raise EtaError(f"unknown ETA env {env!r}")
        self.entity = entity
        self.identity, self.api = ENVS[env]
        self.timeout = timeout
        self._token: str | None = None
        self._token_exp = 0.0
        self._last_call = 0.0

    # --- auth -----------------------------------------------------------------
    async def token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_exp - 300:
            return self._token
        if not self.entity.configured:
            raise EtaError(f"{self.entity.key}: client_id/secret missing")
        basic = base64.b64encode(f"{self.entity.client_id}:{self.entity.client_secret}".encode()).decode()
        r = await client.post(f"{self.identity}/connect/token",
                              headers={"Authorization": f"Basic {basic}"},
                              data={"grant_type": "client_credentials", "scope": "InvoicingAPI"},
                              timeout=self.timeout)
        if r.status_code != 200:
            raise EtaError(f"token {r.status_code}: {r.text[:200]}")
        j = r.json()
        self._token = j["access_token"]
        self._token_exp = time.time() + float(j.get("expires_in", 3600))
        return self._token

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        wait = THROTTLE_S - (time.time() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        tok = await self.token(client)
        r = await client.get(f"{self.api}{path}", params=params,
                             headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                             timeout=self.timeout)
        self._last_call = time.time()
        if r.status_code == 429:
            await asyncio.sleep(5)
            return await self._get(client, path, params)
        if r.status_code != 200:
            raise EtaError(f"GET {path} {r.status_code}: {r.text[:300]}")
        return r.json()

    # --- reads ----------------------------------------------------------------
    async def ping(self) -> dict:
        async with httpx.AsyncClient() as client:
            await self.token(client)
        return {"ok": True, "entity": self.entity.key}

    async def search(self, client: httpx.AsyncClient, *, issue_from: date, issue_to: date,
                     direction: str | None = None, status: str | None = None,
                     page_size: int = 100) -> list[dict]:
        """All documents issued in [issue_from, issue_to] — windows of 30 days,
        continuation-token paging, both directions unless narrowed."""
        out: list[dict] = []
        start = issue_from
        while start <= issue_to:
            end = min(start + timedelta(days=WINDOW_DAYS - 1), issue_to)
            token = ""
            while True:
                params = {
                    "issueDateFrom": datetime.combine(start, datetime.min.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "issueDateTo": datetime.combine(end, datetime.max.time().replace(microsecond=0), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pageSize": page_size,
                }
                if token:
                    params["continuationToken"] = token
                if direction:
                    params["direction"] = direction
                if status:
                    params["status"] = status
                j = await self._get(client, "/api/v1.0/documents/search", params)
                out.extend(j.get("result") or [])
                token = (j.get("metadata") or {}).get("continuationToken") or "EndofResultSet"
                if token == "EndofResultSet":
                    break
            start = end + timedelta(days=1)
        return out

    async def details(self, client: httpx.AsyncClient, uuid: str) -> dict:
        return await self._get(client, f"/api/v1.0/documents/{uuid}/details")


def vat_of(details: dict) -> float:
    """VAT (T1) amount from a details payload; 0 when the document has none."""
    doc = details.get("document") or {}
    for t in doc.get("taxTotals") or []:
        if str(t.get("taxType", "")).upper() == "T1":
            return float(t.get("amount") or 0)
    return 0.0


def lines_of(details: dict) -> list[dict]:
    """Compact invoice lines: codes + net + VAT, for the manufacturing/trading split."""
    doc = details.get("document") or {}
    out = []
    for ln in doc.get("invoiceLines") or []:
        vat = sum(float(t.get("amount") or 0) for t in (ln.get("taxableItems") or [])
                  if str(t.get("taxType", "")).upper() == "T1")
        out.append({"item_code": ln.get("itemCode"), "internal_code": ln.get("internalCode"),
                    "description": (ln.get("description") or "")[:120], "qty": ln.get("quantity"),
                    "net": float(ln.get("netTotal") or 0), "vat": vat})
    return out
