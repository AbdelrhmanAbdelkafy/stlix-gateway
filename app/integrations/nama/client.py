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
            # A *partial* success also comes back 400: Nama answers 400 when some
            # records fail to serialise, but still returns the ones that did. We
            # were discarding those - ReceiptVoucher/PaymentVoucher (the live
            # collections and payments) look empty for exactly this reason.
            #
            # The dropped records are NOT hidden: `_partial` travels with the data
            # so a caller summing money can tell it is looking at an incomplete
            # set rather than a true total.
            records = data.get("records") if isinstance(data, dict) else None
            if records and any(rows for rows in records.values()):
                data["_partial"] = {
                    "http_status": resp.status_code,
                    "returned": sum(len(r) for r in records.values()),
                    "failed": data.get("failed_records_count", 0),
                }
                return data
            raise UpstreamError(f"Nama HTTP {resp.status_code}: {str(data)[:200]}")
        return data

    # --- generic entity ops ---
    async def list(self, entity: str, max_records: int = 25) -> dict:
        return await self._request("POST", f"{entity}/list", {"maxRecords": max_records})

    async def list_query(
        self,
        entity: str,
        *,
        page_size: int = 25,
        order_by: str | None = None,
        text_criteria: str | None = None,
    ) -> dict:
        """Filtered/ordered list (Nama's richer `list` body).

        `text_criteria` is Nama's own filter grammar: `field,Operator,value,Conn;`
        where Operator is case-sensitive (`Equal`, not `Equals`/`LIKE`). Used by
        the item-builder for duplicate checks and code sequencing.

        NOTE: a *valid* filter that matches zero rows makes Nama answer HTTP 400
        with an empty body — see `find_first`, which treats that as "no match".
        """
        body: dict[str, Any] = {"pageSize": page_size}
        if order_by:
            body["orderBy"] = order_by
        if text_criteria:
            body["textCriteria"] = text_criteria
        return await self._request("POST", f"{entity}/list", body)

    async def find_first(self, entity: str, *, text_criteria: str) -> dict | None:
        """First record matching `text_criteria`, or None if none match.

        Nama quirk: a valid filter returning zero rows comes back as HTTP 400
        with an empty body (NOT 200 + empty list). We treat that specific shape
        as "no match"; a body carrying `failureOccurred` is still a real error.
        """
        url = f"{self._base}/{entity}/list"
        body = {"pageSize": 1, "textCriteria": text_criteria}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request("POST", url, headers=self._headers, json=body)
        except httpx.RequestError as exc:
            raise UpstreamError(f"Nama unreachable: {exc}") from exc
        if resp.status_code == 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = None
            if not payload:  # {} / empty => zero matches, not an error
                return None
        data = self._handle(resp)
        rows = data.get("records", {}).get(entity, [])
        return rows[0] if rows else None

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
