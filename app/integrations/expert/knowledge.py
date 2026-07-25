"""What Nama Expert is allowed to know.

The corpus is built out of two things that already exist in this repo, and
nothing else:

- **the project's own documents** — the same allow-listed markdown that
  `/tools/library` serves, so a rule written in the runbook is a rule the expert
  can quote verbatim (`docs/rep-integration.md` is how REP's hard-won Nama rules
  got in here);
- **the gateway's description of itself** — `registry.SYSTEMS`,
  `catalog.CONNECTORS`, `catalog.ENDPOINTS` and the ideas board, so *"where do I
  find X"* is answered with a real address instead of a plausible one.

Two consequences worth stating, because they are the point:

1. **Nothing is hand-copied into this file.** A rule changes in the runbook and
   the expert's answer changes with it. Duplicating the rules here would create
   exactly the drift the rest of the platform is built to avoid.
2. **Every chunk carries where it came from and a link a human can open.** An
   answer without a source is the same trap as a figure typed into a page by
   hand: it reads as true and cannot be checked.

The index is deterministic and offline — building it touches no network and no
credential, so `/api/v1/expert/search` works on a machine with nothing
configured at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ... import catalog
from ...ideas import registry as ideas
from ...registry import SYSTEMS

_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Same allow-list `/tools/library` uses. A request can never name a path; the
# library is built by scanning these directories, so the expert's reach and the
# library's reach cannot drift apart.
_DOC_DIRS = ("", "docs", "docs/enterprise-platform", "reference/finance-mvp")

# A section longer than this is split further, at blank lines, so retrieval
# returns the paragraph that answers the question rather than a whole chapter.
_MAX_CHARS = 1400
# A table with at least this many rows is indexed row-by-row: in BACKLOG.md one
# row is one requirement, and returning 200 of them together answers nothing.
_TABLE_ROW_SPLIT = 4

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage, and the address it came from."""

    id: str
    text: str
    title: str          # human-readable heading path
    ref: str            # stable identity, e.g. "doc:BACKLOG.md#الأفكار"
    link: str           # something a browser can open
    kind: str           # doc | system | connector | endpoint | idea
    source: str         # the file or map object

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "ref": self.ref,
                "link": self.link, "kind": self.kind, "source": self.source,
                "text": self.text}


# --- markdown ---------------------------------------------------------------

def _heading_path(stack: list[tuple[int, str]]) -> str:
    return " › ".join(t for _, t in stack)


def _split_long(text: str) -> list[str]:
    """Break an over-long section at blank lines, never mid-sentence."""
    if len(text) <= _MAX_CHARS:
        return [text]
    out, buf = [], ""
    for para in text.split("\n\n"):
        if buf and len(buf) + len(para) + 2 > _MAX_CHARS:
            out.append(buf.strip())
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf.strip():
        out.append(buf.strip())
    return out


def _emit_section(body: list[str], path: str, rel: str, out: list[Chunk]) -> None:
    """Turn one heading's body into chunks, splitting big tables per row."""
    lines = [ln for ln in body if ln.strip()]
    if not lines:
        return
    link = f"/tools/library/{rel}"

    table = [ln for ln in lines if ln.lstrip().startswith("|")]
    if len(table) >= _TABLE_ROW_SPLIT + 1:  # +1 for the header row
        header = table[0]
        prose = [ln for ln in lines if not ln.lstrip().startswith("|")]
        if prose:
            for i, piece in enumerate(_split_long("\n".join(prose))):
                out.append(Chunk(f"{rel}#{path}#p{i}", piece, path or rel,
                                 f"doc:{rel}#{path}", link, "doc", rel))
        for row in table[1:]:
            if _TABLE_SEP.match(row):
                continue
            # The header travels with the row: "| A4 | Nama Expert ... |" means
            # nothing without "| # | الفكرة | المصدر |" above it.
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            label = cells[0] if cells else ""
            out.append(Chunk(f"{rel}#{path}#{label or len(out)}",
                             f"{header}\n{row}", f"{path} · {label}".strip(" ·"),
                             f"doc:{rel}#{path}#{label}", link, "doc", rel))
        return

    for i, piece in enumerate(_split_long("\n".join(lines))):
        out.append(Chunk(f"{rel}#{path}#{i}", piece, path or rel,
                         f"doc:{rel}#{path}", link, "doc", rel))


def _read_markdown(path: Path, rel: str) -> list[Chunk]:
    out: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    body: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        m = _HEADING.match(line)
        if not m:
            body.append(line)
            continue
        _emit_section(body, _heading_path(stack), rel, out)
        body = []
        level = len(m.group(1))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, m.group(2).strip()))
    _emit_section(body, _heading_path(stack), rel, out)
    return out


def _documents() -> list[Chunk]:
    out: list[Chunk] = []
    for rel_dir in _DOC_DIRS:
        base = _ROOT / rel_dir if rel_dir else _ROOT
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.md")):
            rel = str(f.relative_to(_ROOT)).replace("\\", "/")
            out.extend(_read_markdown(f, rel))
    return out


# --- the platform describing itself -----------------------------------------

def _map_chunks() -> list[Chunk]:
    """Systems, connectors, endpoints and requirements, as retrievable text.

    This is the half that makes the expert useful for *"where"* questions. The
    text is assembled from the same objects `/api/v1/map` serves, so an endpoint
    added to the catalogue is an endpoint the expert can point at, with no step
    in between.
    """
    out: list[Chunk] = []

    for s in SYSTEMS:
        out.append(Chunk(
            f"system:{s.key}",
            f"النظام «{s.name_ar}» ({s.name_en}) — مفتاحه `{s.key}` وحالته "
            f"{s.status.value}. {s.description}"
            + (f" العنوان: {s.url}" if s.url else ""),
            f"نظام: {s.name_ar}", f"map:system:{s.key}", f"/systems/{s.key}",
            "system", "registry.SYSTEMS"))

    for c in catalog.CONNECTORS:
        state = "موصّل وشغّال" if c.live else "لسه مش مبني"
        out.append(Chunk(
            f"connector:{c.key}",
            f"الكنكتور «{c.name_ar}» ({c.name_en}) — مفتاحه `{c.key}`، بيكلّم "
            f"{c.upstream}، {state}"
            + (f"، تابع لنظام {c.system}" if c.system else "")
            + (f". {c.note}" if c.note else "")
            + (f" الـ endpoints بتاعته: {', '.join(catalog.endpoints_of(c.key))}"
               if catalog.endpoints_of(c.key) else ""),
            f"كنكتور: {c.name_ar}", f"map:connector:{c.key}",
            f"/connectors/{c.key}", "connector", "catalog.CONNECTORS"))

    for e in catalog.ENDPOINTS:
        write = "عملية كتابة (مقفولة في وضع read_only)" if e.write else "قراءة فقط"
        out.append(Chunk(
            f"endpoint:{e.method}:{e.path}",
            f"`{e.method} {e.path}` — {e.title_ar}. {write}."
            + (f" كنكتور: {e.connector}." if e.connector else "")
            + (f" النوع: {e.kind}." if e.kind != "api" else ""),
            f"{e.method} {e.path}", f"map:endpoint:{e.path}",
            e.path if "{" not in e.path else "/systems",
            "endpoint", "catalog.ENDPOINTS"))

    for i in ideas.as_dicts():
        out.append(Chunk(
            f"idea:{i['id']}",
            f"المتطلب {i['id']} — {i['title']}. الدومين: {i.get('domain', '')}. "
            f"الحالة: {i.get('status', '')}. الجاهزية: {i.get('readiness', '')}."
            + (f" الناقص: {i['needs']}." if i.get("needs") else "")
            + (f" الأنظمة: {', '.join(i.get('systems', []))}." if i.get("systems") else ""),
            f"متطلب {i['id']}", f"map:idea:{i['id']}",
            f"/api/v1/ideas/{i['id']}", "idea", "BACKLOG.md"))

    return out


# --- the index ---------------------------------------------------------------

_INDEX: list[Chunk] | None = None


def build() -> list[Chunk]:
    return _documents() + _map_chunks()


def get_index() -> list[Chunk]:
    """The corpus, built once per process. `reset()` forces a rebuild."""
    global _INDEX
    if _INDEX is None:
        _INDEX = build()
    return _INDEX


def reset() -> int:
    """Drop the cached corpus so the next question re-reads the repo."""
    global _INDEX
    _INDEX = None
    return len(get_index())


def stats() -> dict:
    """What the expert can see — the honest answer to «إنت بتقرا منين؟»."""
    chunks = get_index()
    by_kind: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for c in chunks:
        by_kind[c.kind] = by_kind.get(c.kind, 0) + 1
        by_source[c.source] = by_source.get(c.source, 0) + 1
    return {
        "chunks": len(chunks),
        "by_kind": dict(sorted(by_kind.items())),
        "documents": sorted(k for k in by_source if k.endswith(".md")),
        "characters": sum(len(c.text) for c in chunks),
    }
