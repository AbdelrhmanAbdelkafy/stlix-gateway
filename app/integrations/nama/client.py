"""Async client over Namasoft ERP REST v1 (verified protocol).

Quirks handled here so the rest of the app never sees them:
  * auth via `clientId` + `clientSecret` headers (NOT apiKey/secretKey)
  * save body shape: {"<Entity>": [ {...} ]}
  * dates MUST be DD-MM-YYYY (YYYY-MM-DD is silently mis-parsed by Nama)
"""
from __future__ import annotations

from typing import Any

import httpx

from ...config import Settings
from ...core.errors import UpstreamError


class NamaClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.nama_base
        self._headers = {
            "clientId": settings.nama_client_id,
            "clientSecret": settings.nama_client_secret,
            "Content-Type": "application/json",
        }
        self._timeout = settings.nama_timeout

    async def _request(self, method: str, path: str, json: Any | None = None) -> dict:
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(method, url, headers=self._headers, json=json)
        except httpx.RequestError as exc:
            raise UpstreamError(f"Nama unreachable: {exc}") from exc
        return self._handle(resp)

    @staticmethod
    def _handle(resp: httpx.Response) -> dict:
        if resp.status_code == 401:
            raise UpstreamError("Nama auth failed (401) - check clientId/clientSecret.")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError(f"Nama non-JSON ({resp.status_code}): {resp.text[:200]}") from exc
        if isinstance(data, dict) and data.get("failureOccurred"):
            raise UpstreamError(str(data.get("failureMessage") or data))
        if resp.status_code >= 400:
            raise UpstreamError(f"Nama HTTP {resp.status_code}: {str(data)[:200]}")
        return data

    # --- generic entity ops ---
    async def list(self, entity: str, max_records: int = 25) -> dict:
        return await self._request("POST", f"{entity}/list", {"maxRecords": max_records})

    async def find(self, entity: str, code: str) -> dict:
        return await self._request("GET", f"{entity}/findByIdOrCode/{code}")

    async def save(self, entity: str, record: dict) -> dict:
        data = await self._request("POST", f"{entity}/save", {entity: [record]})
        if not data.get("saved_records_count"):
            raise UpstreamError(f"Nama save reported 0 records: {data}")
        return data

    async def delete(self, entity: str, code: str) -> dict:
        return await self._request("POST", f"{entity}/delete/{code}", {})

    async def ping(self) -> dict:
        """Cheap auth check - lists one Employee."""
        return await self.list("Employee", max_records=1)
