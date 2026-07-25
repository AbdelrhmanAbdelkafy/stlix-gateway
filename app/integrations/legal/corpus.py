"""What the legal counsel is allowed to have read.

The corpus is built from files on disk under `corpus/legal/`, in three tiers
that are kept apart because they carry completely different weight:

| tier | what | weight |
|------|------|--------|
| `statute` | نصّ قانون أو دستور أو معاهدة | **authority** — the only thing an article may be cited from |
| `precedent` | عقود الشركة الموقّعة فعلًا | practice: how we have actually written this before |
| `internal` | لوائح الشركة | our own rules — binding on us, not on anyone else |

The tier is not decoration. `citations.py` will only ever confirm an article
against a `statute` chunk: a clause copied out of one of our own old contracts
proves what we signed, not what the law says, and the two get conflated by
anyone reading quickly — including a language model.

## The empty corpus is a designed state, not a broken one

`manifest.py` lists the laws this advisor is *supposed* to have. Each one is
either loaded or **named as missing**. That is the whole point: asked about
something governed by a law it does not hold, the counsel says *"دي محكومة
بقانون العمل، وأنا مش شايف نصّه"* — which is useful and true — instead of
answering from a memory of the statute, which is neither.

Note what the manifest does *not* record: law numbers and years. Those get
filled in when the text is loaded and the number is read out of it. Writing
«القانون المدني 131 لسنة 1948» into a Python file from memory would be the
same act this platform spent its time deleting from the finance pages, in the
one domain where being wrong costs the most.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..expert.knowledge import Chunk
from .manifest import EXPECTED, Expected

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CORPUS = _ROOT / "corpus" / "legal"

TIERS = ("statute", "precedent", "internal", "template")

#: `مادة 12` · `المادة ١٢ مكرر` · `مادة (147)` — the head of an article, at the
#: start of a line. Arabic-Indic digits are accepted because scanned Egyptian
#: statutes are typeset with them.
_ARTICLE = re.compile(
    r"^\s*(?:الماده|المادة|ماده|مادة)\s*[\(\[]?\s*"
    r"([0-9٠-٩]+)\s*[\)\]]?\s*"
    r"(مكرر(?:\s*[0-9٠-٩]+)?)?\s*[:\-–—.]?\s*(.*)$"
)
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def arabic_int(s: str) -> str:
    """`١٤٧` -> `147`. One representation, so a lookup cannot miss on typeface."""
    return s.translate(_AR_DIGITS).strip()


def article_key(law_slug: str, number: str, suffix: str = "") -> str:
    """The identity a citation is checked against: law + article, normalised."""
    n = arabic_int(number)
    sfx = re.sub(r"\s+", "", arabic_int(suffix or ""))
    return f"{law_slug}#{n}{('/' + sfx) if sfx else ''}"


@dataclass(frozen=True)
class Source:
    """One file in the corpus, and what it claims to be."""

    slug: str
    title: str
    tier: str
    path: Path
    jurisdiction: str = ""
    articles: int = 0


def _front_matter(text: str) -> tuple[dict, str]:
    """A tiny `key: value` header, terminated by `---`.

    Deliberately not YAML: adding a parser dependency to read four keys is how
    an ingestion path acquires a failure mode nobody tests.
    """
    if not text.lstrip().startswith("---"):
        return {}, text
    body = text.lstrip()[3:]
    end = body.find("\n---")
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in body[:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()
    return meta, body[end + 4:]


def _split_articles(text: str) -> list[tuple[str, str, str]]:
    """`(number, suffix, body)` per article. Text before article 1 is dropped
    into a synthetic `0` so a preamble is still searchable."""
    out: list[tuple[str, str, str]] = []
    num, sfx, buf = "0", "", []
    for line in text.splitlines():
        m = _ARTICLE.match(line)
        if m:
            if buf and "".join(buf).strip():
                out.append((num, sfx, "\n".join(buf).strip()))
            num, sfx = arabic_int(m.group(1)), (m.group(2) or "").strip()
            buf = [m.group(3)] if m.group(3).strip() else []
        else:
            buf.append(line)
    if buf and "".join(buf).strip():
        out.append((num, sfx, "\n".join(buf).strip()))
    return out


def _read(path: Path) -> tuple[Source, list[Chunk]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _front_matter(raw)
    slug = meta.get("slug") or path.stem
    tier = meta.get("tier", "statute")
    if tier not in TIERS:
        tier = "statute"
    title = meta.get("title") or slug
    juris = meta.get("jurisdiction", "")
    link = f"/api/v1/legal/law/{slug}"

    chunks: list[Chunk] = []
    if tier == "statute":
        for num, sfx, text in _split_articles(body):
            label = f"مادة {num}" + (f" {sfx}" if sfx else "")
            if num == "0":
                label = "الديباجة"
            chunks.append(Chunk(
                id=article_key(slug, num, sfx),
                text=f"{title} — {label}\n{text}",
                title=f"{title} · {label}",
                ref=f"{tier}:{slug}#{label}",
                link=link, kind=tier, source=title))
    else:
        # A contract or a bylaw has no articles worth addressing individually;
        # split on blank lines into readable blocks.
        blocks, buf = [], []
        for para in body.split("\n\n"):
            if sum(len(b) for b in buf) + len(para) > 1400 and buf:
                blocks.append("\n\n".join(buf))
                buf = [para]
            else:
                buf.append(para)
        if buf:
            blocks.append("\n\n".join(buf))
        for i, b in enumerate(blocks, 1):
            if not b.strip():
                continue
            chunks.append(Chunk(
                id=f"{slug}#{i}", text=b.strip(), title=f"{title} · جزء {i}",
                ref=f"{tier}:{slug}#{i}", link=link, kind=tier, source=title))

    return Source(slug, title, tier, path, juris, len(chunks)), chunks


_SOURCES: list[Source] | None = None
_CHUNKS: list[Chunk] | None = None


def _build() -> tuple[list[Source], list[Chunk]]:
    sources: list[Source] = []
    chunks: list[Chunk] = []
    if CORPUS.is_dir():
        for f in sorted(CORPUS.rglob("*")):
            if f.suffix.lower() not in (".txt", ".md") or f.name.startswith("_"):
                continue
            if f.name.upper() == "README.MD":
                continue
            src, ch = _read(f)
            sources.append(src)
            chunks.extend(ch)
    return sources, chunks


def load() -> tuple[list[Source], list[Chunk]]:
    global _SOURCES, _CHUNKS
    if _SOURCES is None or _CHUNKS is None:
        _SOURCES, _CHUNKS = _build()
    return _SOURCES, _CHUNKS


def reset() -> int:
    global _SOURCES, _CHUNKS
    _SOURCES = _CHUNKS = None
    return len(load()[1])


def chunks() -> list[Chunk]:
    return load()[1]


def sources() -> list[Source]:
    return load()[0]


def loaded_slugs() -> set[str]:
    return {s.slug for s in sources()}


def statute_articles() -> set[str]:
    """Every `law#article` the corpus can actually vouch for.

    `citations.py` checks against exactly this set, and nothing else.
    """
    return {c.id for c in chunks() if c.kind == "statute"}


def law(slug: str) -> tuple[Source | None, list[Chunk]]:
    src = next((s for s in sources() if s.slug == slug), None)
    return src, [c for c in chunks() if c.ref.split(":", 1)[-1].split("#")[0] == slug]


def coverage() -> list[dict]:
    """Every expected law, loaded or not. The missing ones are the useful half."""
    have = {s.slug: s for s in sources()}
    rows = []
    for e in EXPECTED:
        s = have.get(e.slug)
        rows.append({
            "slug": e.slug, "name": e.name, "jurisdiction": e.jurisdiction,
            "covers": e.covers, "tier": e.tier,
            "loaded": s is not None,
            "articles": s.articles if s else 0,
        })
    for s in sources():  # anything loaded that the manifest did not anticipate
        if not any(r["slug"] == s.slug for r in rows):
            rows.append({"slug": s.slug, "name": s.title,
                         "jurisdiction": s.jurisdiction, "covers": "",
                         "tier": s.tier, "loaded": True, "articles": s.articles})
    return rows


def _pretty_dir() -> str:
    """`corpus/legal` normally; the absolute path when it has been pointed
    elsewhere (a test fixture), rather than raising on the way out."""
    try:
        return str(CORPUS.relative_to(_ROOT)).replace("\\", "/")
    except ValueError:
        return str(CORPUS).replace("\\", "/")


def stats() -> dict:
    srcs, chs = load()
    by_tier: dict[str, int] = {}
    for c in chs:
        by_tier[c.kind] = by_tier.get(c.kind, 0) + 1
    cov = coverage()
    return {
        "sources": len(srcs),
        "chunks": len(chs),
        "by_tier": dict(sorted(by_tier.items())),
        "statute_articles": len(statute_articles()),
        "expected": len(EXPECTED),
        "loaded_of_expected": sum(1 for r in cov if r["loaded"]),
        "missing": [r["name"] for r in cov if not r["loaded"]],
        "corpus_dir": _pretty_dir(),
    }


__all__ = ["Chunk", "Expected", "Source", "CORPUS", "TIERS", "arabic_int",
           "article_key", "chunks", "coverage", "law", "load", "loaded_slugs",
           "reset", "sources", "statute_articles", "stats"]
