"""Async client over the Vtiger CRM Web Services API (read paths).

Vtiger auth is a two-step handshake:
  1. GET  operation=getchallenge&username=U         -> { result: { token } }
  2. POST operation=login  username=U  accessKey=md5(token + ACCESS_KEY)
     -> { result: { sessionName } }
Then queries use VtigerQL: `SELECT ... FROM Module LIMIT o, n;` (must end with ;).
"""
from __future__ import annotations

import hashlib
import re

import httpx

from ...config import Settings
from ...core.errors import UpstreamError

_MODULE_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _safe_module(module: str) -> str:
    if not _MODULE_RE.match(module):
        raise UpstreamError(f"Invalid CRM module name: {module!r}")
    return module


class VtigerClient:
    def __init__(self, settings: Settings) -> None:
        self._configured = settings.crm_configured
        self._ws = f"{settings.vtiger_url.rstrip('/')}/webservice.php"
        self._user = settings.vtiger_username
        self._key = settings.vtiger_access_key
        self._timeout = settings.crm_timeout

    def _require_config(self) -> None:
        if not self._configured:
            raise UpstreamError(
                "CRM (Vtiger) not configured; set VTIGER_URL / VTIGER_USERNAME / VTIGER_ACCESS_KEY."
            )

    async def _login(self, client: httpx.AsyncClient) -> str:
        try:
            r = await client.get(self._ws, params={"operation": "getchallenge", "username": self._user})
            token = self._unwrap(r)["token"]
            access = hashlib.md5((token + self._key).encode()).hexdigest()
            r2 = await client.post(
                self._ws, data={"operation": "login", "username": self._user, "accessKey": access}
            )
            return self._unwrap(r2)["sessionName"]
        except httpx.RequestError as exc:
            raise UpstreamError(f"Vtiger unreachable: {exc}") from exc

    @staticmethod
    def _unwrap(resp: httpx.Response) -> dict:
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError(f"Vtiger non-JSON ({resp.status_code}): {resp.text[:160]}") from exc
        if not data.get("success"):
            err = data.get("error", {})
            raise UpstreamError(f"Vtiger error: {err.get('message') or err or data}")
        return data["result"]

    async def query(self, module: str, limit: int = 20) -> list[dict]:
        self._require_config()
        module = _safe_module(module)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            session = await self._login(client)
            q = f"SELECT * FROM {module} LIMIT 0, {int(limit)};"
            r = await client.get(self._ws, params={"operation": "query", "sessionName": session, "query": q})
            result = self._unwrap(r)
            return result if isinstance(result, list) else []

    async def ping(self) -> dict:
        self._require_config()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            await self._login(client)
        return {"ok": True}
