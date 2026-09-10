"""The rest of the portal's surface, mixed into `EtaClient`.

`client.py` holds what the VAT planner needs every hour (token, search,
details). This holds everything else the taxpayer API offers, so that
"anything you can do on the portal" is reachable from here instead of from a
browser: recent documents, the raw submission, ETA's own PDF, notifications,
document types (where the cancellation window is written), the bulk package
ETA prepares for a whole month, and the two state changes.

Submitting invoices is deliberately absent: submission requires the eSeal
X.509 certificate signing each document (CAdES-BES), the seal lives on a
hardware token, and the system that holds it is the one that must sign. The
gateway reads the portal and changes state; it does not issue.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timezone

import httpx

THROTTLE_S = 2.1


class PortalOps:
    """Requires the host class to provide `_get`, `token`, `api`, `timeout`,
    `_last_call` and an `EtaError` — i.e. `EtaClient`."""

    async def _pace(self) -> None:
        wait = THROTTLE_S - (time.time() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)

    def _err(self, msg: str):
        from .client import EtaError
        return EtaError(msg)

    # --- reads -----------------------------------------------------------------
    async def recent(self, client: httpx.AsyncClient, *, page_no: int = 1, page_size: int = 100,
                     direction: str | None = None, status: str | None = None,
                     document_type: str | None = None) -> dict:
        """`documents/recent` — page-numbered and needs no date window, which is
        what makes it the right call for "what landed since I last looked"."""
        params: dict = {"pageNo": page_no, "pageSize": page_size}
        for k, v in (("direction", direction), ("status", status), ("documentType", document_type)):
            if v:
                params[k] = v
        return await self._get(client, "/api/v1.0/documents/recent", params)

    async def raw(self, client: httpx.AsyncClient, uuid: str) -> dict:
        """The original submission as its issuer sent it, plus ETA's metadata."""
        return await self._get(client, f"/api/v1.0/documents/{uuid}/raw")

    async def notifications(self, client: httpx.AsyncClient, *, page_no: int = 1, page_size: int = 50) -> dict:
        """ETA's own messages to this taxpayer — the portal's inbox."""
        return await self._get(client, "/api/v1.0/notifications", {"pageNo": page_no, "pageSize": page_size})

    async def document_types(self, client: httpx.AsyncClient) -> dict:
        """Types + workflow parameters — this is where the real cancellation
        window (in hours) is published, rather than in anyone's memory."""
        return await self._get(client, "/api/v1.0/documenttypes")

    async def printout(self, client: httpx.AsyncClient, uuid: str) -> bytes:
        """ETA's own PDF of the document (QR + status watermark)."""
        await self._pace()
        tok = await self.token(client)
        r = await client.get(f"{self.api}/api/v1.0/documents/{uuid}/pdf",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=self.timeout)
        self._last_call = time.time()
        if r.status_code != 200:
            raise self._err(f"pdf {uuid} {r.status_code}: {r.text[:200]}")
        return r.content

    # --- bulk: a whole month prepared by ETA, in one file ----------------------
    async def request_package(self, client: httpx.AsyncClient, *, date_from: date, date_to: date,
                              fmt: str = "JSON", type_: str = "full",
                              document_types: list[str] | None = None,
                              statuses: list[str] | None = None) -> dict:
        """Ask ETA to prepare a package; returns its id. CSV is summary-only."""
        if fmt.upper() == "CSV" and type_ == "full":
            raise self._err("CSV packages are summary-only")
        body = {
            "type": type_, "format": fmt.upper(),
            "queryParameters": {
                "dateFrom": _utc(date_from, False), "dateTo": _utc(date_to, True),
                "documentTypeNames": document_types or [],
                "statuses": statuses or [],
                "truncateifexceeded": True,
            },
        }
        await self._pace()
        tok = await self.token(client)
        r = await client.post(f"{self.api}/api/v1.0/documentpackages/requests", json=body,
                              headers={"Authorization": f"Bearer {tok}"}, timeout=self.timeout)
        self._last_call = time.time()
        if r.status_code not in (200, 201):
            raise self._err(f"package request {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {"ok": True}

    async def package_requests(self, client: httpx.AsyncClient, *, page_no: int = 1, page_size: int = 20) -> dict:
        return await self._get(client, "/api/v1.0/documentpackages/requests",
                               {"pageNo": page_no, "pageSize": page_size})

    async def package(self, client: httpx.AsyncClient, package_id: str) -> bytes:
        """Download a package ETA has finished preparing (zip)."""
        await self._pace()
        tok = await self.token(client)
        r = await client.get(f"{self.api}/api/v1.0/documentPackages/{package_id}",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=self.timeout * 4)
        self._last_call = time.time()
        if r.status_code != 200:
            raise self._err(f"package {package_id} {r.status_code}: {r.text[:200]}")
        return r.content

    # --- the only writes this gateway ever makes -------------------------------
    async def set_state(self, client: httpx.AsyncClient, uuid: str, status: str, reason: str) -> dict:
        """Cancel one of our own documents, or reject one issued to us.

        Both are irreversible on the portal and both expire (the window is in
        `document_types`). This method refuses nothing beyond shape; the gate
        lives in the router — `ETA_ALLOW_STATE_CHANGES` plus a named reason —
        so that "the machine does everything" never quietly means "the machine
        cancels tax documents on its own".
        """
        status = status.lower()
        if status not in ("cancelled", "rejected"):
            raise self._err("status must be cancelled or rejected")
        if not reason or len(reason.strip()) < 3:
            raise self._err("a reason is required")
        await self._pace()
        tok = await self.token(client)
        r = await client.put(f"{self.api}/api/v1.0/documents/state/{uuid}/state",
                             json={"status": status, "reason": reason.strip()},
                             headers={"Authorization": f"Bearer {tok}"}, timeout=self.timeout)
        self._last_call = time.time()
        if r.status_code not in (200, 202):
            raise self._err(f"set_state {uuid} {r.status_code}: {r.text[:300]}")
        return {"ok": True, "uuid": uuid, "status": status, "reason": reason.strip()}


def _utc(d: date, end: bool) -> str:
    t = datetime.max.time().replace(microsecond=0) if end else datetime.min.time()
    return datetime.combine(d, t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
