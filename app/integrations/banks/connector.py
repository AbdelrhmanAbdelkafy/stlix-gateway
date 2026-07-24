"""Banks connector (Nama-backed, read-only).

Nama's REST exposes bank master data (Bank) and bank accounts (BankAccount),
each linked to a GL account via subsidiaryAccounts.mainAccount. Numeric
balances are computed from journal entries and are NOT on these entities, so
this connector serves the accounts enriched with bank name / GL account /
currency; the numeric balance is a separate (GL/SQL) path.
"""
from __future__ import annotations

from ...config import Settings
from ..base import Connector, ConnectorMode
from ..nama.client import NamaClient


class BanksConnector(Connector):
    key = "banks"

    def __init__(self, settings: Settings) -> None:
        super().__init__(ConnectorMode(settings.banks_mode))
        self.configured = settings.nama_configured
        self._client = NamaClient(settings)

    async def banks(self, limit: int = 50) -> list[dict]:
        data = await self._client.list("Bank", max_records=limit)
        return data.get("records", {}).get("Bank", [])

    async def accounts(self, limit: int = 50) -> list[dict]:
        data = await self._client.list("BankAccount", max_records=limit)
        rows = data.get("records", {}).get("BankAccount", [])
        name_by_code = {b["code"]: b.get("name1") for b in await self.banks(limit=200)}
        for r in rows:
            sub = r.get("subsidiaryAccounts") or {}
            r["_bankName"] = name_by_code.get(r.get("bank"))
            r["_glAccount"] = sub.get("mainAccount")
            r["_currency"] = sub.get("currency")
        return rows

    async def ping(self) -> dict:
        return await self._client.list("Bank", max_records=1)
