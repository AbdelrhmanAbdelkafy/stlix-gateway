"""Scalable workspace aggregation.

Each connector contributes a Section via a Provider. The workspace collects
all providers CONCURRENTLY, so adding a new system = add one Provider to
PROVIDERS (or register()) - the dashboard/API pick it up automatically.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..config import Settings
from ..core.metrics import metrics
from ..ideas import registry as ideas
from ..integrations.banks.connector import BanksConnector
from ..integrations.crm.connector import CrmConnector
from ..integrations.finance.connector import FinanceConnector
from ..integrations.inventory.connector import InventoryConnector
from ..integrations.nama.connector import NamaConnector
from ..registry import as_dicts


@dataclass
class Section:
    key: str
    title: str
    status: str  # ok | not_configured | error
    summary: dict = field(default_factory=dict)
    rows: list | None = None
    columns: list | None = None
    error: str | None = None
    # Where this section sits in the platform. Filled in by `collect_all`, so a
    # section is never just a table: you can walk from it to the endpoint that
    # produced it, the system it belongs to, and the requirements it serves.
    api: str | None = None
    system: str | None = None
    connector: str | None = None
    ideas: dict | None = None
    board: str | None = None


class Provider:
    key: str = "?"
    title: str = "?"
    api: str | None = None       # the endpoint a reader can open for the raw data
    system: str | None = None    # registry.SYSTEMS key this section shows
    connector: str | None = None  # catalog connector behind it

    async def collect(self, settings: Settings, limit: int) -> Section:  # pragma: no cover
        raise NotImplementedError


class OverviewProvider(Provider):
    key, title = "overview", "نظرة عامة · Overview"
    api, system, connector = "/systems", None, None

    async def collect(self, settings: Settings, limit: int) -> Section:
        systems = as_dicts()
        live = sum(1 for s in systems if s["status"] == "live")
        summary = {
            "systems_total": len(systems),
            "systems_live": live,
            "systems_planned": len(systems) - live,
            "nama_mode": settings.nama_mode,
            "crm_configured": settings.crm_configured,
            "requests_total": metrics.total,
            "uptime_seconds": metrics.uptime_seconds,
        }
        return Section(self.key, self.title, "ok", summary, rows=systems,
                       columns=["key", "name_en", "name_ar", "status"])


class NamaProvider(Provider):
    key, title = "nama", "موظفو نما · Nama"
    api, system, connector = "/api/v1/nama/employees", "nama", "nama"

    async def collect(self, settings: Settings, limit: int) -> Section:
        if not settings.nama_configured:
            return Section(self.key, self.title, "not_configured", {"configured": False})
        data = await NamaConnector(settings).list("Employee", max_records=limit)
        rows = data.get("records", {}).get("Employee", [])
        summary = {"mode": settings.nama_mode, "available": data.get("records_count")}
        return Section(self.key, self.title, "ok", summary, rows=rows,
                       columns=["code", "name1", "attendanceMachineCode", "employeeState"])


class CrmProvider(Provider):
    key, title = "crm", "CRM · Vtiger"
    api, system, connector = "/api/v1/crm/contacts", "crm", "crm"

    async def collect(self, settings: Settings, limit: int) -> Section:
        if not settings.crm_configured:
            return Section(self.key, self.title, "not_configured",
                           {"backend": settings.crm_backend, "configured": False})
        rows = await CrmConnector(settings).query("Contacts", limit=limit)
        return Section(self.key, self.title, "ok", {"mode": settings.crm_mode, "returned": len(rows)},
                       rows=rows, columns=["id", "firstname", "lastname", "email", "phone"])


class BanksProvider(Provider):
    key, title = "banks", "حسابات البنوك · Bank Accounts"
    api, system, connector = "/api/v1/banks", "banks", "banks"

    async def collect(self, settings: Settings, limit: int) -> Section:
        if not settings.nama_configured:
            return Section(self.key, self.title, "not_configured", {"configured": False})
        rows = await BanksConnector(settings).accounts(limit=limit)
        return Section(self.key, self.title, "ok", {"accounts": len(rows), "mode": settings.banks_mode},
                       rows=rows, columns=["code", "name1", "_bankName", "_currency"])


class InventoryProvider(Provider):
    key, title = "inventory", "الجرد · Stocktake"
    api, system, connector = "/api/v1/inventory", "inventory", "inventory"

    async def collect(self, settings: Settings, limit: int) -> Section:
        if not settings.inventory_configured:
            return Section(self.key, self.title, "not_configured", {"configured": False})
        p = await InventoryConnector(settings).progress()
        summary = {"rev": p["rev"], "tracked": p["tracked"], "counted": p["counted"], "manual": p["manual"]}
        return Section(self.key, self.title, "ok", summary,
                       rows=p["counted_items"][:limit], columns=["code", "q", "u", "counter"])


class FinanceProvider(Provider):
    """Real money, from the Nama SQL connector.

    The unified workspace shipped without it — the one source of true balances,
    and the thing `/tools/finance-reports` is built on, was missing from the
    dashboard that claims to unify everything.
    """

    key, title = "finance", "المالية · Finance (SQL)"
    api, system, connector = "/api/v1/finance/kpis", "nama", "sql"

    async def collect(self, settings: Settings, limit: int) -> Section:
        if not settings.nama_sql_configured:
            return Section(self.key, self.title, "not_configured",
                           {"configured": False, "why": "NAMA_SQL_* not set in .env"})
        data = await FinanceConnector(settings).kpis()
        if not data.get("available"):
            return Section(self.key, self.title, "not_configured", data)
        rows = [{"metric": k, "value": v} for k, v in data.items()
                if k not in ("available", "source")]
        return Section(self.key, self.title, "ok",
                       {"source": data.get("source"), "metrics": len(rows)},
                       rows=rows, columns=["metric", "value"])


class IdeasProvider(Provider):
    key, title = "ideas", "الأفكار والمتطلبات · Ideas"
    api, system, connector = "/api/v1/ideas", None, "gateway"

    async def collect(self, settings: Settings, limit: int) -> Section:
        s = ideas.summary()
        # Surface what is unblocked first — those need a report, not an integration.
        rows = [i for i in ideas.as_dicts() if i["readiness"] == "ready"][:limit]
        summary = {
            "total": s["total"],
            "domains": s["domains"],
            **{f"readiness_{k}": v for k, v in s["readiness"].items()},
            "board": "/tools/ideas",
        }
        return Section(self.key, self.title, "ok", summary, rows=rows,
                       columns=["id", "title", "domain", "source", "readiness", "link"])


class MonitoringProvider(Provider):
    key, title = "monitoring", "مراقبة · Monitoring"
    api, system, connector = "/metrics", None, "gateway"

    async def collect(self, settings: Settings, limit: int) -> Section:
        snap = metrics.snapshot()
        rows = [{"path": p, **v} for p, v in snap["by_path"].items()]
        rows.sort(key=lambda r: r["count"], reverse=True)
        summary = {
            "uptime_seconds": snap["uptime_seconds"],
            "requests_total": snap["requests_total"],
            "rate_limited": snap["rate_limited_total"],
            **{f"status_{k}": v for k, v in snap["by_status_class"].items()},
        }
        return Section(self.key, self.title, "ok", summary, rows=rows[:limit],
                       columns=["path", "count", "errors", "avg_ms"])


# The registry. Append a Provider here (or via register()) to add a section.
PROVIDERS: list[Provider] = [
    OverviewProvider(),
    NamaProvider(),
    CrmProvider(),
    BanksProvider(),
    InventoryProvider(),
    FinanceProvider(),
    IdeasProvider(),
    MonitoringProvider(),
]


def register(provider: Provider) -> None:
    PROVIDERS.append(provider)


def _place(section: Section, provider: Provider) -> Section:
    """Give a section its coordinates: its endpoint, system, and requirements.

    A section used to be a title and a table with no way out of it.
    """
    section.api = provider.api
    section.system = provider.system
    section.connector = provider.connector
    mine = [i for i in ideas.as_dicts() if i["workspace_section"] == section.key]
    if mine:
        section.ideas = {
            "total": len(mine),
            "ready": sum(1 for i in mine if i["readiness"] == "ready"),
            "done": sum(1 for i in mine if i["readiness"] == "done"),
        }
        section.board = f"/tools/ideas?section={section.key}"
    return section


async def collect_all(settings: Settings, limit: int = 8) -> list[Section]:
    """Collect every provider concurrently; a failing one becomes an error section."""
    results = await asyncio.gather(
        *[p.collect(settings, limit) for p in PROVIDERS], return_exceptions=True
    )
    sections: list[Section] = []
    for provider, res in zip(PROVIDERS, results):
        if isinstance(res, Exception):
            res = Section(provider.key, provider.title, "error", {}, error=str(res))
        sections.append(_place(res, provider))
    return sections
