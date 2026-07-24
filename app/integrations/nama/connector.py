"""Nama connector - the first real connector. Read ops pass through; write
ops are guarded by the connector mode (default read-only)."""
from __future__ import annotations

from ...config import Settings
from ..base import Connector, ConnectorMode
from .client import NamaClient


class NamaConnector(Connector):
    key = "nama"

    def __init__(self, settings: Settings) -> None:
        super().__init__(ConnectorMode(settings.nama_mode))
        self._client = NamaClient(settings)

    # ---- reads (always allowed) ----
    async def list(self, entity: str, max_records: int = 25) -> dict:
        return await self._client.list(entity, max_records=max_records)

    async def find(self, entity: str, code: str) -> dict:
        return await self._client.find(entity, code)

    async def ping(self) -> dict:
        return await self._client.ping()

    # ---- writes (blocked in read-only mode) ----
    async def save(self, entity: str, record: dict) -> dict:
        self.guard_write()
        return await self._client.save(entity, record)

    async def delete(self, entity: str, code: str) -> dict:
        self.guard_write()
        return await self._client.delete(entity, code)
