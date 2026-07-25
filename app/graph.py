"""The hub as one graph: systems × connectors × endpoints × ideas × engines.

Four maps already existed and never met: `registry.SYSTEMS` (what the company
runs), `catalog` (what the gateway built), `ideas.registry` (what the owner
asked for) and `workspace.providers` (what the dashboard shows). Each could
answer its own question and none could answer the one that matters — *given
this requirement, where does its data live, and what is stopping it?*

This module computes that join once and every view slices the same result, so
`/systems`, `/connectors`, `/api/v1/map` and the workspace cannot disagree
about how many ideas a connector unblocks.

Edges are embedded in each node rather than returned as a flat edge list: every
caller asks "given X, what hangs off it", and a flat list would just be
re-indexed client-side.
"""
from __future__ import annotations

from . import catalog
from .config import Settings
from .ideas import registry as ideas
from .registry import SYSTEMS

# Which unified-workspace section shows a system's data. Only live sections
# exist — a system with no section simply has nothing on the dashboard yet.
SECTION_OF_SYSTEM: dict[str, str] = {
    "nama": "nama",
    "attendance": "nama",
    "crm": "crm",
    "banks": "banks",
    "inventory": "inventory",
}

# The 6 reusable engines from VISION.md, plus the two cross-cutting tags the
# backlog also uses. `vision` marks the six that the "build the engine once,
# many ideas land" plan actually counts.
ENGINES: tuple[tuple[str, str, bool], ...] = (
    ("Planned-vs-Actual", "المخطط مقابل الفعلي", True),
    ("Renewals", "التجديدات والمواعيد", True),
    ("Reconciliation", "المطابقة", True),
    ("Live-vs-Pending", "اللحظي مقابل غير المُرحَّل", True),
    ("Watchlist", "قوائم الحظر", True),
    ("Market-Feeds", "أسعار السوق", True),
    ("Data-Quality", "جودة البيانات", False),
    ("AI", "الذكاء الاصطناعي", False),
)

_READINESS = ("done", "ready", "partial", "blocked")


def _rollup(rows: list[dict]) -> dict:
    """Idea counts by readiness — the shape every node reports."""
    out = {"total": len(rows)}
    for r in _READINESS:
        out[r] = sum(1 for i in rows if i["readiness"] == r)
    out["with_data"] = sum(1 for i in rows if i["data_endpoints"])
    return out


def _ids(rows: list[dict]) -> list[str]:
    return [i["id"] for i in rows]


def systems() -> list[dict]:
    """Every company system with what the gateway built on it and what waits on it."""
    all_ideas = ideas.as_dicts()
    out = []
    for s in SYSTEMS:
        conns = [c for c in catalog.CONNECTORS if c.system == s.key]
        mine = [i for i in all_ideas if s.key in i["systems"]]
        primary = [i for i in mine if i["primary_system"] == s.key]
        eps: list[str] = []
        for c in conns:
            eps += catalog.endpoints_of(c.key)
        out.append({
            "key": s.key,
            "name_en": s.name_en,
            "name_ar": s.name_ar,
            "status": s.status.value,
            "description": s.description,
            "connectors": [c.key for c in conns],
            "connectors_live": [c.key for c in conns if c.live],
            "endpoints": eps,
            "workspace_section": SECTION_OF_SYSTEM.get(s.key),
            "ideas": _rollup(mine),
            "ideas_owned": len(primary),
            "idea_ids": _ids(mine),
            "board": f"/tools/ideas?sys={s.key}",
            "api": f"/systems/{s.key}",
        })
    return out


def system(key: str) -> dict | None:
    wanted = key.strip().lower()
    for s in systems():
        if s["key"] == wanted:
            return s
    return None


def connectors(settings: Settings) -> list[dict]:
    """Every connector, with the part of the backlog it carries and unblocks."""
    carried = ideas.by_connector()
    all_ideas = ideas.as_dicts()
    out = []
    for row in catalog.as_dicts(settings):
        key = row["key"]
        stat = carried.get(key, {})
        # The number that drives sequencing: ideas this connector alone blocks.
        sole = [i["id"] for i in all_ideas if i["missing_connectors"] == [key]]
        # Ideas that belong to the system this connector fronts, even when the
        # backlog's Source cell named the upstream instead of the connector.
        via_system = [i for i in all_ideas if row["system"] and row["system"] in i["systems"]]
        out.append({
            **row,
            "endpoints_count": len(row["endpoints"]),
            "ideas": stat.get("total", 0),
            "ideas_ready": stat.get("ready", 0),
            "idea_ids": stat.get("ids", []),
            "ideas_via_system": len(via_system),
            "sole_blocker_for": len(sole),
            "sole_blocker_ids": sole,
            "board": f"/tools/ideas?conn={key}",
            "api": f"/connectors/{key}",
        })
    return out


def connector(key: str, settings: Settings) -> dict | None:
    wanted = key.strip().lower()
    for c in connectors(settings):
        if c["key"] == wanted:
            return c
    return None


def endpoints() -> list[dict]:
    """Every route, and which requirements its raw data feeds."""
    all_ideas = ideas.as_dicts()
    out = []
    for e in catalog.ENDPOINTS:
        conn = catalog.get_connector(e.connector)
        feeds = [i["id"] for i in all_ideas if e.path in i["data_endpoints"]]
        out.append({
            "path": e.path,
            "title_ar": e.title_ar,
            "connector": e.connector,
            "system": e.system or (conn.system if conn else ""),
            "kind": e.kind,
            "method": e.method,
            "write": e.write,
            "live": bool(conn and conn.live),
            "feeds_ideas": feeds,
            "feeds_count": len(feeds),
            "board": f"/tools/ideas?ep={e.path}" if feeds else None,
        })
    return out


def engines() -> list[dict]:
    """The reusable patterns — build one, many requirements land."""
    all_ideas = ideas.as_dicts()
    out = []
    for key, name_ar, vision in ENGINES:
        mine = [i for i in all_ideas if i["engine"] == key]
        out.append({
            "key": key,
            "name_ar": name_ar,
            "vision": vision,
            "built": False,
            "ideas": _rollup(mine),
            "idea_ids": _ids(mine),
            "board": f"/tools/ideas?engine={key}",
        })
    return out


def coverage() -> dict:
    """The hub's own self-assessment: how connected is it, really?"""
    all_ideas = ideas.as_dicts()
    sys_rows = systems()
    linked = sum(1 for i in all_ideas if i["data_endpoints"])
    return {
        "ideas": len(all_ideas),
        "ideas_with_data": linked,
        "ideas_without_data": len(all_ideas) - linked,
        "ideas_unmapped": sum(1 for i in all_ideas if not i["systems"]),
        "systems": len(sys_rows),
        "systems_live": sum(1 for s in sys_rows if s["status"] == "live"),
        # A system nothing asks for is either off the backlog or off the map.
        "systems_without_ideas": [s["key"] for s in sys_rows if s["ideas"]["total"] == 0],
        "endpoints": len(catalog.ENDPOINTS),
        "endpoints_feeding_ideas": sum(1 for e in endpoints() if e["feeds_count"]),
        "engines_with_ideas": sum(1 for e in engines() if e["ideas"]["total"]),
    }


def build(settings: Settings) -> dict:
    """The whole graph. Every node carries its own edges."""
    return {
        "source_file": "BACKLOG.md",
        "data_endpoints_mean": "raw data already queryable here — NOT a built report",
        "counts": {
            "systems": len(SYSTEMS),
            "connectors": len(catalog.CONNECTORS),
            "endpoints": len(catalog.ENDPOINTS),
            "ideas": len(ideas.all_ideas()),
            "engines": len(ENGINES),
        },
        "coverage": coverage(),
        "systems": systems(),
        "connectors": connectors(settings),
        "endpoints": endpoints(),
        "engines": engines(),
        "ideas": ideas.as_dicts(),
    }
