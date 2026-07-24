"""CRM connector (Vtiger backend). Read ops pass through; writes guarded by
connector mode (default read-only)."""
from __future__ import annotations

from ...config import Settings
from ..base import Connector, ConnectorMode
from .client import VtigerClient


class CrmConnector(Connector):
    key = "crm"

    def __init__(self, settings: Settings) -> None:
        super().__init__(ConnectorMode(settings.crm_mode))
        self.backend = settings.crm_backend
        self.configured = settings.crm_configured
        self._client = VtigerClient(settings)

    # ---- reads ----
    async def query(self, module: str, limit: int = 20) -> list[dict]:
        return await self._client.query(module, limit=limit)

    async def ping(self) -> dict:
        return await self._client.ping()

    # ---- writes (blocked in read-only mode) ----
    async def create(self, module: str, record: dict) -> dict:
        self.guard_write()
        raise NotImplementedError("CRM write path not implemented yet.")
