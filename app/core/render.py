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


def _cell(v: Any) -> str:
    if v is None:
        return '<span class="muted">—</span>'
    return html.escape(str(v))


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
  <a href="/api/v1/workspace">workspace</a><a href="/systems">systems</a><a href="/connectors">connectors</a>
  <a href="/health">health</a><a href="/metrics">metrics</a><a href="/docs">docs</a>
</nav>
{body}
<details><summary>عرض JSON الخام / raw JSON</summary>
<pre>{raw}</pre></details>
<p class="links">Tip: أضف <code>?format=json</code> لأي رابط للحصول على JSON مباشرة.</p>
</body></html>"""


def html_page(title: str, body_html: str, data: Any, badges: str = "") -> HTMLResponse:
    raw = html.escape(json.dumps(data, ensure_ascii=False, indent=2))
    return HTMLResponse(
        _PAGE.format(title=html.escape(title), body=body_html, raw=raw, badges=badges)
    )


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
    return html_page(title, body, data, badges=badges)
