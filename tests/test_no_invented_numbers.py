"""No page may show a figure it made up, and no page may sit unrouted.

Both failures shipped here, and neither announced itself:

* `hub.public.html` held the AR and AP totals as typed-in text beside a typed-in
  as-of date, and was routed from nowhere. It reported one day's position for
  months, and looked fine the whole time.
* The Finance OS cockpit rendered invented bank balances, AP invoices, customer
  ledgers and journal entries. Real figures were laid over part of it, which is
  worse than none of it being real: real money beside invented money is what
  makes the invented money look real.

The rule these hold in place: a figure comes from an endpoint or it is not shown.
A section with nothing behind it says what it is waiting for.
"""
import re
from pathlib import Path

from app.main import app
from app.routers import tools

MODULES = Path(tools.__file__).resolve().parent.parent.parent / "modules"

#: Pages where a figure is a money figure. The engineer's assistant is excluded on
#: purpose: it is a calculator, not a view of company data — its numbers are
#: physical constants (E = 193000 MPa for stainless) and results it derives on the
#: spot, and it holds no credentials and calls nothing.
FINANCE_PAGES = (
    "finance-os/demo.gateway.html",
    "finance-os/reports.html",
    "platform/hub.html",
    "platform/hub.public.html",
)

_STYLE = re.compile(r"<style\b.*?</style>", re.S | re.I)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"(?<![:'\"])//[^\n]*")

#: Two shapes that are only ever a written-down amount: a thousands-grouped
#: number, and a bare run of six or more digits. Six because page sizes, limits
#: and years are shorter, and the smallest figure that mattered here — 178,000 of
#: AR attributed against 20.0M — is longer.
#:
#: The lookarounds keep two innocents out, both found while writing this: a
#: grouped match must not begin inside an argument list, or `slice(0, 120)` reads
#: as 0,120; and a long run must not follow a hyphen, or the model id
#: `claude-sonnet-4-5-20250929` reads as money.
_GROUPED = re.compile(r"(?<![\d(,])\d{1,3}(?:,\d{3})+(?![\d)])")
_LONG = re.compile(r"(?<![\d\-])\b\d{6,}\b")


def _code(path: Path) -> str:
    """The page with styling and prose removed — what actually renders."""
    text = path.read_text(encoding="utf-8")
    for pattern in (_STYLE, _HTML_COMMENT, _BLOCK_COMMENT, _LINE_COMMENT):
        text = pattern.sub(" ", text)
    return text


def test_every_module_page_is_reachable_or_says_it_is_not():
    """An unrouted page cannot be corrected by a later fix.

    Nothing links to it, so nobody notices it is stale — until someone opens it
    and believes it. Any HTML under `modules/` is either served by a route or has
    been emptied of figures and says so.
    """
    routed = set(re.findall(r'_serve\("([^"]+)"', Path(tools.__file__).read_text(encoding="utf-8")))
    # the hub's pages are served by app/hub/router.py (and /login by app/auth)
    from app.hub import router as hub_router
    routed |= {f"hub/{n}" for n in hub_router._PAGES} | {"hub/login.html"}
    orphans = []
    for page in sorted(MODULES.rglob("*.html")):
        rel = page.relative_to(MODULES).as_posix()
        if rel in routed:
            continue
        body = _code(page)
        if _GROUPED.search(body) or _LONG.search(body):
            orphans.append(rel)
    assert not orphans, f"unrouted pages still carrying figures: {orphans}"


def test_finance_pages_hold_no_written_down_figures():
    """Every money figure on these pages arrives over the wire."""
    offenders = {}
    for rel in FINANCE_PAGES:
        body = _code(MODULES / rel)
        found = sorted(set(_GROUPED.findall(body)) | set(_LONG.findall(body)))
        if found:
            offenders[rel] = found
    assert not offenders, f"figures written into the page instead of fetched: {offenders}"


def test_every_cockpit_section_has_a_source_or_is_declared_a_gap():
    """The exact failure the prototype had: a section with neither.

    It shipped `banks`, `invoices`, `customers`, `ledger` and `recs` as rows in
    the file. When the gateway answered they were partly overlaid; when it did not
    answer for a given section, the rows rendered anyway, under a banner reading
    "connected". A section now declares `ep:` — a route it reads — or it lives in
    the gap list and states what it is waiting for. Neither is optional.
    """
    body = _code(MODULES / "finance-os/demo.gateway.html")
    sections = re.findall(r'\{id:\s*"(\w+)"(.*?)(?=\n \{id:|\n\];)', body, re.S)
    assert len(sections) >= 5, f"only found {len(sections)} sections — the parse is wrong"
    sourceless = [name for name, block in sections
                  if 'ep:"' not in block and "gaps:" not in block]
    assert not sourceless, f"cockpit sections with neither an endpoint nor a stated gap: {sourceless}"


def test_the_cockpit_holds_no_rows_of_its_own():
    """Its old data keys were `amt`, `v` (a balance), `dr`/`cr`, and `led`."""
    body = _code(MODULES / "finance-os/demo.gateway.html")
    leftovers = [k for k in ("amt:", "led:", "dr:", "cr:", "invSeq", "recSeq") if k in body]
    assert not leftovers, f"prototype data still in the cockpit: {leftovers}"


def test_the_cockpit_names_the_endpoint_behind_every_section():
    """A section either points at a route that exists, or is listed as a gap."""
    body = _code(MODULES / "finance-os/demo.gateway.html")
    endpoints = {"/api/v1/" + e.split("?")[0] for e in re.findall(r'ep:"([^"]+)"', body)}
    assert endpoints, "the cockpit declares no endpoints at all"
    routed = set(app.openapi()["paths"])
    unknown = {
        e for e in endpoints
        if e not in routed and not any(
            re.fullmatch(r.replace("{entity}", "[^/]+").replace("{module}", "[^/]+"), e)
            for r in routed if "{" in r
        )
    }
    assert not unknown, f"cockpit sections pointing at routes that do not exist: {unknown}"


def test_the_cockpit_states_what_is_missing_rather_than_filling_it_in():
    """Bank balances, the approval workflow and AI recommendations have no data.

    Each was previously a screen of invented rows. The standard is the one the
    treasury already met: say "pending" instead of showing a number.
    """
    body = _code(MODULES / "finance-os/demo.gateway.html")
    assert "gaps:" in body, "no gap section — the missing parts have to be named"
    for expected in ("أرصدة البنوك", "الاعتماد", "طبقة الذكاء", "RBAC"):
        assert expected in body, f"gap not declared: {expected}"
