"""Unified workspace: one aggregated view over all connectors (HTML or JSON)."""
from __future__ import annotations

import html as _html
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..core.render import html_page, table, wants_html
from ..core.security import require_api_key
from .providers import Section, collect_all

router = APIRouter(prefix="/workspace", tags=["workspace"], dependencies=[Depends(require_api_key)])

_BADGE = {"ok": "", "not_configured": "ro", "error": "ro", "degraded": "ro"}


def _links_html(sec: Section) -> str:
    """A section's way out: its raw endpoint, its system, its requirements."""
    bits = []
    if sec.api:
        bits.append(f'<a href="{_html.escape(sec.api)}">الداتا الخام</a>')
    if sec.system:
        bits.append(f'<a href="/systems/{_html.escape(sec.system)}">النظام</a>')
    if sec.connector:
        bits.append(f'<a href="/connectors/{_html.escape(sec.connector)}">الكنكتور</a>')
    if sec.board and sec.ideas:
        bits.append(f'<a href="{_html.escape(sec.board)}">{sec.ideas["total"]} فكرة '
                    f'({sec.ideas["ready"]} جاهزة)</a>')
    if not bits:
        return ""
    return ('<p class="links" style="margin:.1rem 0 .5rem">'
            + " &nbsp;·&nbsp; ".join(bits) + "</p>")


def _section_html(sec: Section) -> str:
    parts = [
        f'<h3 style="margin:1.3rem 0 .35rem;font-size:1.02rem;" id="ws-{_html.escape(sec.key)}">'
        f'{_html.escape(sec.title)} '
        f'<span class="badge {_BADGE.get(sec.status, "")}">{_html.escape(sec.status)}</span></h3>',
        _links_html(sec),
    ]
    if sec.summary:
        chips = " &nbsp;·&nbsp; ".join(
            f"{_html.escape(str(k))}: <b>{_html.escape(str(v))}</b>" for k, v in sec.summary.items()
        )
        parts.append(f'<p class="muted" style="font-size:.83rem;margin:.1rem 0 .5rem;">{chips}</p>')
    if sec.error:
        parts.append(f'<p style="color:#c2410c;font-size:.85rem;">⚠ {_html.escape(sec.error)}</p>')
    if sec.rows:
        parts.append(table(sec.rows, sec.columns))
    return "".join(parts)


@router.get("")
@router.get("/overview")
async def overview(
    request: Request,
    limit: int = Query(8, ge=1, le=100),
    settings: Settings = Depends(get_settings),
):
    """Aggregate every connector into one view. JSON for apps, HTML for browsers."""
    sections = await collect_all(settings, limit)
    data = {"sections": [asdict(s) for s in sections]}
    if not wants_html(request):
        return JSONResponse(data)
    body = "".join(_section_html(s) for s in sections)
    ok = sum(1 for s in sections if s.status == "ok")
    badges = f'<span class="badge">{ok}/{len(sections)} ok</span>'
    return html_page("Workspace", body, data, badges=badges)
