"""Parse BACKLOG.md into an addressable registry of ideas.

`BACKLOG.md` stays the single source of truth — it is hand-edited as the owner
voices new requirements. This module turns it into structured records so every
idea gets an id, a domain, a source, a status, an engine, and a **link**, and so
the workspace / hub can list them instead of the markdown living out of reach.

Adding an idea = add a row to BACKLOG.md. Nothing here needs touching.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .. import catalog
from . import wiring

_BACKLOG = Path(__file__).resolve().parent.parent.parent / "BACKLOG.md"

# A backlog id: one-to-three letters + digits (+ optional letter suffix). S1, WH13, UX1b.
_ID_RE = re.compile(r"^[A-Z]{1,3}\d+[a-z]?$")
_HEAD_RE = re.compile(r"^([^(]+?)\s*(?:\(([^)]*)\))?\s*(?:—.*)?$")
_SEP_CHARS = set("-: ")

# Status marker -> canonical status. Order matters: first marker found wins.
_STATUS = (("🟢", "live"), ("🟡", "next"), ("⚪", "planned"))

# The 6 reusable engines from VISION.md. An idea tagged "→ X" collapses into one
# of these — that is the whole point: build the engine once, many ideas land.
_ENGINE_KEYWORDS = (
    ("live-vs-pending", "Live-vs-Pending"),
    ("reconcil", "Reconciliation"),
    ("renewal", "Renewals"),
    ("planned", "Planned-vs-Actual"),
    ("watchlist", "Watchlist"),
    ("blacklist", "Watchlist"),
    ("market", "Market-Feeds"),
    ("data quality", "Data-Quality"),
    ("data", "Data-Quality"),
    ("ai", "AI"),
)

# Source text -> the connector it needs. Whether that connector exists is NOT
# repeated here: it is read from `catalog.is_live()`, so a connector going live
# updates every idea's readiness at once instead of drifting out of sync.
# Checked in order, so specific tokens come before generic ones.
_CONNECTOR_MAP: tuple[tuple[str, str], ...] = (
    # (substring in source, catalog connector key)
    ("vtiger", "crm"),
    ("sql", "sql"),
    ("nama", "nama"),
    ("gateway", "gateway"),
    ("front-end", "front-end"),
    ("bank feed", "bank-feed"),
    ("imap", "email"),
    ("email", "email"),
    ("whatsapp", "omnichannel"),
    ("wechat", "omnichannel"),
    ("stt", "voice"),
    ("idp", "sso"),
    ("oauth", "sso"),
    ("telco", "telco"),
    ("portal", "portal"),
    ("nafeza", "portal"),
    ("rep", "rep"),
    ("custody", "custody"),
    ("analytics", "external"),
    ("research", "external"),
    ("external", "external"),
    ("api", "external"),
    ("ai", "ai-layer"),
    ("new", "new-system"),
    ("all", "all-connectors"),   # "all" = reads across every live connector
)

# Domain icon by id prefix — purely cosmetic, keeps the grid scannable.
_ICONS = {
    "S": "💰", "P": "🛒", "T": "🏦", "M": "🔧", "FL": "🚚", "IT": "💻", "H": "👥",
    "MK": "📣", "I": "📈", "WH": "📦", "LG": "🚢", "SF": "🦺", "GV": "⚖️", "CM": "💬",
    "AT": "🕐", "MD": "🌍", "Q": "🔬", "AC": "📋", "OP": "🏭", "TR": "✈️", "L": "📜",
    "PD": "💡", "G": "🧭", "A": "🧠", "UX": "✨", "PA": "🔐",
}

# Where a *delivered* idea actually lives. Only ever populated for ideas whose
# backlog status is 🟢/🟡 — a planned idea must never link somewhere that implies
# it is built. The "nearest existing thing" for a planned idea is no longer a
# hand-kept hint list: `wiring.py` now names the exact endpoints holding its raw
# data, for all 181 rows, labelled as data sources rather than as the report.
_BUILT_LINKS = {
    "T25": "/api/v1/banks",
    "T1": "/tools/finance-reports",
    "UX1": "/tools/name-builder",
    "PD2": "/tools/engineer",
}


@dataclass(frozen=True)
class Idea:
    id: str
    title: str
    domain: str          # Arabic domain name (owner-facing)
    domain_en: str
    prefix: str          # id letters — groups the domain
    icon: str
    source: str          # where the data lives (Nama / Vtiger / SQL / external / new)
    status: str          # live | next | planned
    engine: str | None   # one of the 6 reusable engines, when tagged
    note: str            # trailing caveat from the status/notes cell
    link: str            # where to go: the built thing, else the idea's own card
    api: str             # always addressable as JSON
    connectors: list[str]       # the connectors this idea reads from
    missing_connectors: list[str]  # …of those, the ones not built yet
    readiness: str       # done | ready | partial | blocked
    # --- where it sits in the platform (app/ideas/wiring.py) ---
    systems: list[str]          # registry.SYSTEMS keys, most responsible first
    primary_system: str
    proposed_system: str | None  # a system worth adding that is not on the map
    data_endpoints: list[str]    # live routes holding its RAW data — never a report
    workspace_section: str       # the section that would surface it
    needs: str                   # the one missing thing, in Arabic
    # The built thing, or None. Separate from `link` so "is it delivered?" is a
    # field rather than a string comparison, and so it can never be set for a
    # planned idea.
    deliverable: str | None
    # Where to go to understand why this is not built. An idea with no data
    # endpoints would otherwise be a dead end saying only "nothing connected".
    unblock: str | None


def _split_heading(raw: str) -> tuple[str, str]:
    """`Sales & Collection (مبيعات وتحصيل)` -> (en, ar). A Latin-only parenthetical
    is a qualifier, not a translation (`Platform & AI (north star)`), so drop it."""
    m = _HEAD_RE.match(raw)
    if not m:
        return raw, ""
    en = (m.group(1) or raw).strip()
    ar = (m.group(2) or "").strip()
    if not re.search(r"[؀-ۿ]", ar):
        ar = ""
    return en, ar


def _status_of(cell: str) -> tuple[str, str]:
    """Return (status, note). The note keeps any caveat written beside the marker."""
    for marker, name in _STATUS:
        if marker in cell:
            return name, cell.replace(marker, "").strip(" ·-")
    return "planned", cell.strip()


def _connectors_of(source: str) -> tuple[list[str], list[str]]:
    """(all connectors this source needs, the ones not built yet).

    Whole-word matching matters: "Email / IMAP" must not match the token `ai`.
    """
    low = source.lower()
    needed: list[str] = []
    missing: list[str] = []
    for token, key in _CONNECTOR_MAP:
        if key in needed:
            continue
        if re.search(rf"\b{re.escape(token)}\b", low):
            needed.append(key)
            if not catalog.is_live(key):
                missing.append(key)
    return needed, missing


def _readiness(status: str, needed: list[str], missing: list[str]) -> str:
    """done = already delivered · ready = every connector exists, just build the
    report · partial = some data reachable, some not · blocked = no connector."""
    if status == "live":
        return "done"
    if not needed:
        return "blocked"
    if not missing:
        return "ready"
    return "partial" if len(missing) < len(needed) else "blocked"


def _engine_of(title: str) -> str | None:
    m = re.search(r"→\s*([^|]+)$", title)
    if not m:
        return None
    tail = m.group(1).lower()
    for needle, engine in _ENGINE_KEYWORDS:
        if needle in tail:
            return engine
    return None


def _parse(md: str) -> list[Idea]:
    ideas: list[Idea] = []
    domain_en = domain_ar = ""
    headers: list[str] = []

    for line in md.splitlines():
        s = line.strip()
        if s.startswith("## "):
            domain_en, domain_ar = _split_heading(s[3:].strip())
            headers = []
            continue
        if not s.startswith("|"):
            continue

        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= _SEP_CHARS:      # |---|---| separator
            continue
        if cells[0].lower() in ("#", "connector"):  # header row
            headers = [c.lower() for c in cells]
            continue
        if not _ID_RE.match(cells[0]):
            continue  # e.g. the Connectors table — those live in registry.py

        row = dict(zip(headers, cells))
        idea_id = cells[0]
        title = row.get("item", cells[1] if len(cells) > 1 else "")
        # "Notes"-style tables (Platform & AI) carry no source/status columns.
        source = row.get("source", "—")
        status, note = _status_of(row.get("status", ""))
        if "notes" in row:
            note = row["notes"]

        prefix = re.match(r"^[A-Z]+", idea_id).group(0)
        built = _BUILT_LINKS.get(idea_id) if status in ("live", "next") else None
        # Notes-only tables (Platform & AI) carry no Source column — the note
        # itself names the layer the idea needs.
        needed, missing = _connectors_of(source if source != "—" else note)
        engine = _engine_of(title)
        if engine == "AI" and "ai-layer" not in needed:
            needed.append("ai-layer")      # an AI-tagged idea always needs Layer 4
            missing.append("ai-layer")

        wire = wiring.wire_for(idea_id, prefix)
        # An endpoint that actually holds this idea's data proves its connector
        # is involved, whatever the Source cell happens to say. Only live
        # connectors can arrive this way, so readiness can improve but never
        # silently worsen.
        for path in wire.endpoints:
            ep = catalog.get_endpoint(path)
            if ep and ep.connector not in needed:
                needed.append(ep.connector)

        ideas.append(
            Idea(
                id=idea_id,
                title=title,
                domain=domain_ar or domain_en,
                domain_en=domain_en,
                prefix=prefix,
                icon=_ICONS.get(prefix, "•"),
                source=source or "—",
                status=status,
                engine=engine,
                note=note,
                link=built or f"/tools/ideas#{idea_id}",
                api=f"/api/v1/ideas/{idea_id}",
                connectors=needed,
                missing_connectors=missing,
                readiness=_readiness(status, needed, missing),
                systems=list(wire.systems),
                primary_system=wire.primary,
                proposed_system=wire.proposed_system or None,
                data_endpoints=list(wire.endpoints),
                workspace_section=wire.section,
                needs=wire.needs,
                deliverable=built,
                unblock=f"/connectors/{missing[0]}" if missing else None,
            )
        )
    return ideas


_cache: tuple[float, list[Idea]] | None = None


def all_ideas() -> list[Idea]:
    """Parsed backlog, re-read whenever BACKLOG.md changes on disk."""
    global _cache
    if not _BACKLOG.exists():
        return []
    mtime = _BACKLOG.stat().st_mtime
    if _cache is None or _cache[0] != mtime:
        _cache = (mtime, _parse(_BACKLOG.read_text(encoding="utf-8")))
    return _cache[1]


def as_dicts() -> list[dict]:
    return [asdict(i) for i in all_ideas()]


def get(idea_id: str) -> dict | None:
    wanted = idea_id.strip().upper()
    for i in all_ideas():
        if i.id.upper() == wanted:
            return asdict(i)
    return None


def domains() -> list[dict]:
    """One entry per domain, in backlog order, with its counts and its systems.

    The chip source for both the board and the hub, so it carries the edges too:
    which systems a domain sits on, and how much of it already has live data.
    """
    out: dict[str, dict] = {}
    for i in all_ideas():
        d = out.setdefault(
            i.prefix,
            {"prefix": i.prefix, "domain": i.domain, "domain_en": i.domain_en,
             "icon": i.icon, "total": 0, "live": 0, "next": 0, "planned": 0,
             "ready": 0, "with_data": 0, "systems": [],
             "page": f"/tools/ideas?dom={i.prefix}"},
        )
        d["total"] += 1
        d[i.status] += 1
        if i.readiness == "ready":
            d["ready"] += 1
        if i.data_endpoints:
            d["with_data"] += 1
        for s in i.systems:
            if s not in d["systems"]:
                d["systems"].append(s)
    return list(out.values())


def by_connector() -> dict[str, dict]:
    """The reverse of `Idea.connectors`: what each connector carries.

    Read forwards it says "this idea needs Vtiger"; read backwards it answers
    the question that actually drives sequencing — *what does building this
    connector unblock?*
    """
    out: dict[str, dict] = {}
    for i in all_ideas():
        for key in i.connectors:
            d = out.setdefault(
                key,
                {"connector": key, "total": 0, "done": 0, "ready": 0,
                 "partial": 0, "blocked": 0, "ids": []},
            )
            d["total"] += 1
            d[i.readiness] += 1
            d["ids"].append(i.id)
    return out


def summary() -> dict:
    ideas = all_ideas()
    engines: dict[str, int] = {}
    missing: dict[str, int] = {}
    for i in ideas:
        if i.engine:
            engines[i.engine] = engines.get(i.engine, 0) + 1
        for key in i.missing_connectors:
            missing[key] = missing.get(key, 0) + 1
    return {
        "total": len(ideas),
        "live": sum(1 for i in ideas if i.status == "live"),
        "next": sum(1 for i in ideas if i.status == "next"),
        "planned": sum(1 for i in ideas if i.status == "planned"),
        "domains": len(domains()),
        "engines": engines,
        # How much of the backlog is unblocked right now.
        "readiness": {
            r: sum(1 for i in ideas if i.readiness == r)
            for r in ("done", "ready", "partial", "blocked")
        },
        "missing_connectors": dict(sorted(missing.items(), key=lambda kv: -kv[1])),
        "source_file": "BACKLOG.md",
    }
