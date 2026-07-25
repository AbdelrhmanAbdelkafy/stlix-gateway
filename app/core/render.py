"""Content negotiation: same endpoint returns HTML (browser) or JSON (API).

- Browser (Accept: text/html) -> styled HTML page, with the raw JSON kept in a
  collapsible <details> so nothing is lost.
- curl / apps (Accept: application/json or */*) -> plain JSON.
- Force either way with ?format=json or ?format=html.
"""
from __future__ import annotations

import html
import json
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response


def wants_html(request: Request) -> bool:
    fmt = request.query_params.get("format")
    if fmt == "json":
        return False
    if fmt == "html":
        return True
    return "text/html" in request.headers.get("accept", "")


def _link(target: str) -> str:
    label = target if len(target) <= 64 else target[:61] + "…"
    external = target.startswith("http")
    rel = ' target="_blank" rel="noopener noreferrer"' if external else ""
    return f'<a href="{html.escape(target, quote=True)}"{rel}>{html.escape(label)}</a>'


def _is_target(s: str) -> bool:
    """A URL or an in-app path — something a person can open."""
    return (s.startswith(("http://", "https://")) or s.startswith("/")) and " " not in s


def _cell(v: Any) -> str:
    """Render one cell — and if it is somewhere you can go, make it go there.

    Every table on the platform runs through here, so an address printed as dead
    text was dead in all of them at once: the CRM's own URL, a system's home, the
    endpoints beside a requirement. One rule fixes the lot, and new rows inherit
    it without anyone remembering to.
    """
    if v is None:
        return '<span class="muted">—</span>'
    s = str(v)
    if not s:
        return '<span class="muted">—</span>'
    if _is_target(s):
        return _link(s)
    # `data_endpoints` and friends arrive joined: link each part, not the blob.
    if ", " in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) > 1 and all(_is_target(p) for p in parts if p):
            return " · ".join(_link(p) for p in parts if p)
    return html.escape(s)


def table(rows: list[dict], columns: list[str] | None = None) -> str:
    """Public: render a list of dicts as an HTML table (for composing pages)."""
    return _table(rows, columns)


def _table(rows: list[dict], columns: list[str] | None) -> str:
    if not rows:
        return '<p class="muted">No rows.</p>'
    cols = columns or list(rows[0].keys())
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f'<td dir="auto">{_cell(r.get(c))}</td>' for c in cols) + "</tr>"
        for r in rows
    )
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


_PAGE = """<!doctype html>
<html lang="ar" dir="auto"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Stlix Gateway</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, "Segoe UI", Tahoma, sans-serif; margin: 0; padding: 1.5rem;
         background: Canvas; color: CanvasText; }}
  header {{ display:flex; align-items:baseline; gap:.75rem; flex-wrap:wrap; margin-bottom:1rem; }}
  h1 {{ font-size: 1.25rem; margin: 0; }}
  .badge {{ font-size:.72rem; padding:.15rem .5rem; border-radius:999px; background:#2563eb; color:#fff; }}
  .badge.ro {{ background:#b45309; }}
  nav a {{ margin-inline-end:.75rem; font-size:.85rem; text-decoration:none; color:#2563eb; }}
  table {{ border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; font-size:.9rem; }}
  th, td {{ border: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
           padding: .45rem .6rem; text-align: start; }}
  th {{ background: color-mix(in srgb, CanvasText 8%, transparent); font-weight:600; }}
  tr:hover td {{ background: color-mix(in srgb, CanvasText 5%, transparent); }}
  .muted {{ opacity:.55; }}
  details {{ margin-top: 1rem; }}
  summary {{ cursor:pointer; font-size:.85rem; color:#2563eb; }}
  pre {{ background: color-mix(in srgb, CanvasText 6%, transparent); padding:1rem; border-radius:8px;
        overflow:auto; font-size:.82rem; direction:ltr; text-align:left; }}
  .links {{ font-size:.8rem; margin-top:1.5rem; opacity:.7; }}
</style></head>
<body>
<header>
  <h1>{title}</h1>{badges}
</header>
<nav>
  <a href="/tools/platform">الهَب</a><a href="/tools/ideas">الأفكار</a><a href="/api/v1/map">الخريطة</a>
  <a href="/api/v1/workspace">workspace</a><a href="/systems">systems</a><a href="/connectors">connectors</a>
  <a href="/health">health</a><a href="/metrics">metrics</a><a href="/docs">docs</a>
</nav>
{context}
{body}
<details><summary>عرض JSON الخام / raw JSON</summary>
<pre>{raw}</pre></details>
<p class="links">Tip: أضف <code>?format=json</code> لأي رابط للحصول على JSON مباشرة.</p>
<!-- The platform-wide voice layer. There are two HTML renderers here — this one
     and `_serve()` in routers/tools.py — and voice belongs to the platform, not
     to whichever of the two someone remembered. Injected in both; a page cannot
     opt out by being generated rather than authored. -->
<script src="/tools/voice.js" defer></script>
</body></html>"""


def html_page(title: str, body_html: str, data: Any, badges: str = "",
              context: str = "") -> HTMLResponse:
    raw = html.escape(json.dumps(data, ensure_ascii=False, indent=2))
    return HTMLResponse(
        _PAGE.format(title=html.escape(title), body=body_html, raw=raw,
                     badges=badges, context=context)
    )


def _context_for(path: str) -> str:
    """Where this endpoint sits in the platform — shown above the data.

    Without it an API page is a leaf: it shows rows and tells you nothing about
    which system it belongs to or which requirements it feeds.
    """
    from .. import catalog  # local import: catalog imports config, not render

    ep = catalog.get_endpoint(path)
    if ep is None:
        return ""
    conn = catalog.get_connector(ep.connector)
    bits = [f'<a href="/tools/ideas?ep={html.escape(path)}">الأفكار اللي بتتغذّى من هنا</a>']
    if conn:
        bits.append(f'<a href="/connectors/{conn.key}">كنكتور: {html.escape(conn.name_ar)}</a>')
        if conn.system:
            bits.append(f'<a href="/systems/{conn.system}">نظام: {html.escape(conn.system)}</a>')
    return ('<p class="links" style="margin:.2rem 0 .8rem">'
            + " &nbsp;·&nbsp; ".join(bits) + "</p>")


def respond(
    request: Request,
    data: Any,
    *,
    title: str,
    rows: list[dict] | None = None,
    columns: list[str] | None = None,
    badges: str = "",
) -> Response:
    if not wants_html(request):
        return JSONResponse(data)
    body = _table(rows, columns) if rows is not None else ""
    return html_page(title, body, data, badges=badges,
                     context=_context_for(request.url.path))
