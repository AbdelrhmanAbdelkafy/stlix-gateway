"""The image has to contain what the code reads — not just what it imports.

This file exists because the Dockerfile copied `app/` and nothing else. It
built, it started, `/health` answered 200, and then every single page 500'd:
`/tools/*` reads `modules/`, the ideas board parses `BACKLOG.md`, Nama Expert
indexes the markdown, the legal counsel reads `corpus/legal`. A container that
comes up green and fails on the first page a person opens is worse than one
that refuses to start.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import catalog
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
client = TestClient(app)


def _copied() -> set[str]:
    """Top-level paths the Dockerfile puts into the image."""
    out: set[str] = set()
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().rstrip("\\").strip()
        if not line.upper().startswith("COPY "):
            continue
        parts = line.split()[1:]
        out.update(p.strip("./") for p in parts[:-1])
    # continuation lines of a multi-line COPY
    body = DOCKERFILE.read_text(encoding="utf-8")
    for m in re.finditer(r"COPY ([^\n]*(?:\\\n[^\n]*)*)", body):
        toks = m.group(1).replace("\\\n", " ").split()
        out.update(t.strip("./") for t in toks[:-1])
    return out


#: Every directory the running code reads from the project root. Derived from
#: the modules that do the reading, so a new one cannot be forgotten silently.
RUNTIME_DIRS = ("modules", "docs", "reference", "corpus")
RUNTIME_FILES = ("BACKLOG.md",)


def test_the_image_ships_everything_the_app_reads():
    copied = _copied()
    missing = [p for p in RUNTIME_DIRS + RUNTIME_FILES if p not in copied]
    assert not missing, f"the app reads these at runtime but the image lacks them: {missing}"


def test_the_runtime_dirs_are_the_ones_the_code_actually_reads():
    """Guards the list above from going stale.

    If a module starts reading a new top-level directory, this fails rather
    than letting the Dockerfile quietly fall behind again.
    """
    read: set[str] = set()
    for py in (ROOT / "app").rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        read.update(re.findall(r'_ROOT / "([a-z]+)"', src))
        read.update(re.findall(r'_ROOT / rel if rel else _ROOT', src) and ["docs"] or [])
    # `_DOC_DIRS` in tools.py / knowledge.py names the doc roots as strings.
    for src_file in ("app/routers/tools.py", "app/integrations/expert/knowledge.py"):
        src = (ROOT / src_file).read_text(encoding="utf-8")
        m = re.search(r"_DOC_DIRS = \(([^)]*)\)", src, re.S)
        if m:
            for d in re.findall(r'"([^"]*)"', m.group(1)):
                if d:
                    read.add(d.split("/")[0])
    unlisted = read - set(RUNTIME_DIRS)
    assert not unlisted, f"code reads these too — add them to the Dockerfile: {unlisted}"


def test_every_page_the_catalogue_advertises_actually_answers():
    """The release check, run as a test: no advertised page may be broken."""
    broken = {}
    for e in catalog.ENDPOINTS:
        if e.kind != "page" or "{" in e.path:
            continue
        r = client.get(e.path)
        if r.status_code != 200:
            broken[e.path] = r.status_code
    assert not broken, f"advertised pages that do not answer: {broken}"


def test_the_read_only_default_survives_a_release():
    """Everything ships read-only. A demo is exactly when someone flips a mode
    and forgets."""
    from app.config import Settings
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.nama_mode == "read_only"
    assert s.crm_mode == "read_only"
    assert s.banks_mode == "read_only"
    assert s.inventory_mode == "read_only"
