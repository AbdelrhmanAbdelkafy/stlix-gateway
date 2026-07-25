"""Async client over Namasoft ERP REST v1 (verified protocol).

Quirks handled here so the rest of the app never sees them:
  * auth via `clientId` + `clientSecret` headers (NOT apiKey/secretKey)
  * save body shape: {"<Entity>": [ {...} ]}
  * dates MUST be DD-MM-YYYY (YYYY-MM-DD is silently mis-parsed by Nama)
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ...config import Settings
from ...core.errors import UpstreamError

#: Nama's hard page ceiling. pageSize=2000 kills the connection outright, and
#: pageSize=5000 silently returns the same 1000 rows.
PAGE_SIZE_MAX = 1000

#: A 1000-row invoice page takes 34-42 seconds on the live tenant. The normal
#: interactive timeout is intentionally shorter, so full sweeps get their own.
SWEEP_TIMEOUT = 180.0

#: A document code ending in this suffix is an unposted draft. Drafts are
#: ordinary rows in /list output and sit *first* in the default order, so any
#: total that does not filter them mixes unapproved money with posted money.
DRAFT_SUFFIX = "@draft"


def is_draft(record: dict) -> bool:
    """True for any document that has not been posted.

    The `@draft` suffix is the usual marker, not the only one. Measured against
    the restored database: of the four unposted invoices, three carry `@draft`
    and one PurchaseInvoice carries **no code at all** — Nama had not assigned
    it a number yet. Matching the suffix alone let that one through and summed
    it as posted.

    Requiring a code is safe: **zero** of the 13,686 posted
    SalesInvoice/PurchaseInvoice rows have an empty code, so "no number yet" and
    "not posted" are the same state. The document that prompted this was worth
    0 EGP — which is exactly why it needed a rule rather than someone noticing a
    wrong total.
    """
    code = (record.get("code") or "").strip()
    return not code or code.endswith(DRAFT_SUFFIX)


class NamaClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.nama_base
        self._headers = {
            "clientId": settings.nama_client_id,
            "clientSecret": settings.nama_client_secret,
            "Content-Type": "application/json",
        }
        self._timeout = settings.nama_timeout

    async def _request(
        self,
        method: str,
        path: str,
        json: Any | None = None,
        *,
        timeout: float | None = None,
        retries: int = 0,
    ) -> dict:
        url = f"{self._base}/{path.lstrip('/')}"
        last: Exception | None = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout or self._timeout) as client:
                    resp = await client.request(
                        method, url, headers=self._headers, json=json
                    )
                return self._handle(
                    resp,
                    empty_400_ok=(
                        method == "POST" and path.rstrip("/").endswith("/list")
                    ),
                )
            except httpx.RequestError as exc:
                last = exc
                if attempt < retries:
                    await asyncio.sleep(2 + 3 * attempt)
        raise UpstreamError(f"Nama unreachable: {last}") from last

    @staticmethod
    def _handle(resp: httpx.Response, *, empty_400_ok: bool = False) -> dict:
        if resp.status_code == 401:
            raise UpstreamError("Nama auth failed (401) - check clientId/clientSecret.")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError(f"Nama non-JSON ({resp.status_code}): {resp.text[:200]}") from exc
        if isinstance(data, dict) and data.get("failureOccurred"):
            raise UpstreamError(str(data.get("failureMessage") or data))
        if resp.status_code >= 400:
            if resp.status_code == 400 and empty_400_ok and not data:
                return {}
            # A *partial* success also comes back 400: Nama answers 400 when some
            # records fail to serialise, but still returns the ones that did. We
            # were discarding those - ReceiptVoucher/PaymentVoucher (the live
            # collections and payments) look empty for exactly this reason.
            #
            # The dropped records are NOT hidden: `_partial` travels with the data
            # so a caller summing money can tell it is looking at an incomplete
            # set rather than a true total.
            records = data.get("records") if isinstance(data, dict) else None
            failed = (data.get("failed_records") or []) if isinstance(data, dict) else []
            if isinstance(records, dict) and (any(records.values()) or failed):
                data["_partial"] = {
                    "http_status": resp.status_code,
                    "returned": sum(len(r) for r in records.values()),
                    "failed": data.get("failed_records_count", len(failed)),
                }
                return data
            raise UpstreamError(f"Nama HTTP {resp.status_code}: {str(data)[:200]}")
        return data

    # --- generic entity ops ---
    async def list(self, entity: str, max_records: int = 25) -> dict:
        """First page of an entity.

        `maxRecords` — the parameter this used to send — is *ignored* by the
        tenant: maxRecords=5, 50 and 1000 all came back with the same 25-row
        default page, so every caller was silently capped at 25 no matter what
        it asked for. The parameters Nama honours are `startPage` (1-based) and
        `pageSize` (max 1000); both are marked required in the entity's OpenAPI
        contract. `list_all` pages beyond the first.
        """
        return await self._request(
            "POST", f"{entity}/list",
            {"startPage": 1, "pageSize": min(max(max_records, 1), PAGE_SIZE_MAX)},
        )

    async def list_page(
        self,
        entity: str,
        *,
        start_page: int = 1,
        page_size: int = PAGE_SIZE_MAX,
        order_by: str | None = None,
        text_criteria: str | None = None,
        timeout: float | None = None,
        retries: int = 0,
    ) -> dict:
        body: dict[str, Any] = {
            "startPage": start_page,
            "pageSize": min(max(page_size, 1), PAGE_SIZE_MAX),
        }
        if order_by:
            body["orderBy"] = order_by
        if text_criteria:
            body["textCriteria"] = text_criteria
        return await self._request(
            "POST", f"{entity}/list", body, timeout=timeout, retries=retries
        )

    async def list_all(
        self,
        entity: str,
        *,
        order_by: str = "code",
        text_criteria: str | None = None,
        max_pages: int = 50,
    ) -> dict:
        """Every record of an entity, paged to exhaustion.

        Three things make this harder than a loop, all measured against the live
        tenant rather than assumed:

        * `records_count` is the count of *this page*, not a total, and Nama
          publishes no total anywhere — exhaustion is the only way to know.
        * a page is the last one when `returned + failed < pageSize`. Counting
          `records` alone is wrong: records that fail to serialise still occupy
          their slot, so a 982-record page can still be full.
        * some records are permanently unreadable by this credential ("not
          accessible from this context"). They are counted and their codes kept
          in `inaccessible` — a sum built from an incomplete set must never be
          able to pass itself off as a true total.
        """
        records: list[dict] = []
        inaccessible: list[str] = []
        pages = 0
        exhausted = False
        for page in range(1, max_pages + 1):
            data = await self.list_page(entity, start_page=page, page_size=PAGE_SIZE_MAX,
                                        order_by=order_by, text_criteria=text_criteria,
                                        timeout=SWEEP_TIMEOUT, retries=3)
            rows = (data.get("records") or {}).get(entity) or []
            failed = data.get("failed_records") or []
            if not rows and not failed:
                exhausted = True
                break  # past the last page: Nama answers 400 with an empty body
            pages += 1
            records.extend(rows)
            inaccessible.extend(
                (f.get("errors") or [{}])[0].get("extraInfo", {}).get("code") or "?"
                for f in failed
            )
            if len(rows) + len(failed) < PAGE_SIZE_MAX:
                exhausted = True
                break
        return {
            "entity": entity,
            "records": records,
            "count": len(records),
            "failed_count": len(inaccessible),
            "pages": pages,
            "inaccessible": inaccessible,
            "truncated": not exhausted,
            "complete": exhausted and not inaccessible,
        }

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
        body: dict[str, Any] = {"startPage": 1, "pageSize": page_size}
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
        body = {"startPage": 1, "pageSize": 1, "textCriteria": text_criteria}
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
