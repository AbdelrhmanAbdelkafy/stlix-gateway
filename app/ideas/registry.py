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

# Source text -> the connector it needs, and whether that connector exists yet.
# This is what answers "which of these could we build today?": an idea whose
# connectors are all live only needs a report on top; one with a missing
# connector needs the integration built first.
# Checked in order, so specific tokens come before generic ones.
_CONNECTOR_MAP: tuple[tuple[str, str, bool], ...] = (
    # (substring in source, connector key, is it live today)
    ("vtiger", "crm", True),
    ("sql", "sql", True),
    ("nama", "nama", True),
    ("gateway", "gateway", True),
    ("front-end", "front-end", True),
    ("bank feed", "bank-feed", False),
    ("imap", "email", False),
    ("email", "email", False),
    ("whatsapp", "omnichannel", False),
    ("wechat", "omnichannel", False),
    ("stt", "voice", False),
    ("idp", "sso", False),
    ("oauth", "sso", False),
    ("telco", "telco", False),
    ("portal", "portal", False),
    ("nafeza", "portal", False),
    ("custody", "custody", False),
    ("analytics", "external", False),
    ("research", "external", False),
    ("external", "external", False),
    ("api", "external", False),
    ("ai", "ai-layer", False),
    ("new", "new-system", False),
    ("all", "all-connectors", True),   # "all" = reads across every live connector
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
# it is built.
_BUILT_LINKS = {
    "T25": "/api/v1/banks",
    "T1": "/tools/finance-reports",
    "UX1": "/tools/name-builder",
}

# The closest thing that already exists for a still-planned idea. Shown as a
# secondary "nearest live endpoint" hint, never as the idea's own link.
_RELATED = {
    "T14": "/tools/finance-reports",
    "T9": "/tools/finance-reports",
    "T21": "/tools/finance-reports",
    "S5": "/api/v1/crm/leads",
    "S4": "/api/v1/crm/accounts",
    "S9": "/api/v1/crm/accounts",
    "UX1b": "/tools/name-builder",
    "AT1": "/api/v1/nama/employees",
    "AT2": "/api/v1/nama/employees",
    "H1": "/api/v1/nama/employees",
    "H9": "/api/v1/nama/employees",
    "WH3": "/api/v1/inventory",
    "WH9": "/api/v1/inventory",
    "WH13": "/api/v1/inventory/counts",
    "WH15": "/api/v1/inventory",
    "A1": "/tools/platform",
    "A2": "/tools/name-builder",
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
    related: str | None  # nearest existing endpoint, for a still-planned idea
    api: str             # always addressable as JSON
    connectors: list[str]       # the connectors this idea reads from
    missing_connectors: list[str]  # …of those, the ones not built yet
    readiness: str       # done | ready | partial | blocked


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
    for token, key, is_live in _CONNECTOR_MAP:
        if key in needed:
            continue
        if re.search(rf"\b{re.escape(token)}\b", low):
            needed.append(key)
            if not is_live:
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
                related=None if built else _RELATED.get(idea_id),
                api=f"/api/v1/ideas/{idea_id}",
                connectors=needed,
                missing_connectors=missing,
                readiness=_readiness(status, needed, missing),
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
    """One entry per domain, in backlog order, with its counts."""
    out: dict[str, dict] = {}
    for i in all_ideas():
        d = out.setdefault(
            i.prefix,
            {"prefix": i.prefix, "domain": i.domain, "domain_en": i.domain_en,
             "icon": i.icon, "total": 0, "live": 0, "next": 0, "planned": 0},
        )
        d["total"] += 1
        d[i.status] += 1
    return list(out.values())


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
