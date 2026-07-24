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
from ..integrations.crm.connector import CrmConnector
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


class Provider:
    key: str = "?"
    title: str = "?"

    async def collect(self, settings: Settings, limit: int) -> Section:  # pragma: no cover
        raise NotImplementedError


class OverviewProvider(Provider):
    key, title = "overview", "نظرة عامة · Overview"

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

    async def collect(self, settings: Settings, limit: int) -> Section:
        if not settings.crm_configured:
            return Section(self.key, self.title, "not_configured",
                           {"backend": settings.crm_backend, "configured": False})
        rows = await CrmConnector(settings).query("Contacts", limit=limit)
        return Section(self.key, self.title, "ok", {"mode": settings.crm_mode, "returned": len(rows)},
                       rows=rows, columns=["id", "firstname", "lastname", "email", "phone"])


class MonitoringProvider(Provider):
    key, title = "monitoring", "مراقبة · Monitoring"

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
    MonitoringProvider(),
]


def register(provider: Provider) -> None:
    PROVIDERS.append(provider)


async def collect_all(settings: Settings, limit: int = 8) -> list[Section]:
    """Collect every provider concurrently; a failing one becomes an error section."""
    results = await asyncio.gather(
        *[p.collect(settings, limit) for p in PROVIDERS], return_exceptions=True
    )
    sections: list[Section] = []
    for provider, res in zip(PROVIDERS, results):
        if isinstance(res, Exception):
            sections.append(Section(provider.key, provider.title, "error", {}, error=str(res)))
        else:
            sections.append(res)
    return sections
