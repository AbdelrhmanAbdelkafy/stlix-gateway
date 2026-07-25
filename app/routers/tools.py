"""Front-end tools served by the gateway.

These are the module UIs (e.g. NameBuilder) served from the gateway so their
only credential is the gateway's own key — the sensitive Nama/Anthropic creds
they used to embed now live server-side behind the API. Read-only for now;
the item WRITE path stays gated behind a deliberate read_write workflow.
"""
from __future__ import annotations

import html as _html
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from ..config import Settings, get_settings
from ..core.render import html_page

router = APIRouter(prefix="/tools", tags=["tools"])

# Project root = parent of the `app` package -> modules/ lives beside it.
_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULES = _ROOT / "modules"


def _serve(rel_path: str, settings: Settings) -> HTMLResponse:
    """Read a module page and inject the gateway key so the browser can call the
    protected API. Sensitive upstream creds (Nama/Vtiger/Anthropic) stay server-side."""
    html = (_MODULES / rel_path).read_text(encoding="utf-8")
    key = next(iter(settings.api_keys), "")
    resp = HTMLResponse(html.replace("__GATEWAY_API_KEY__", key))
    if key:
        # A page full of links into /api/v1/* is useless if every click 401s:
        # a plain <a> cannot send X-API-Key. Hand the browser the same key it
        # already received, as a credential it can send by navigating.
        #
        # HttpOnly    - page scripts cannot read it back out (stricter than the
        #               injected key they already hold).
        # SameSite=lax- another site cannot use it for a cross-site request.
        # GET only    - enforced in require_api_key, so this can never write.
        resp.set_cookie(
            "sg_key", key, httponly=True, samesite="lax", path="/",
            max_age=8 * 3600, secure=settings.app_env not in ("dev", "test"),
        )
    return resp


@router.get("/name-builder", response_class=HTMLResponse)
async def name_builder(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Gateway-wired NameBuilder — replaces the Nama apiKey/secret and the Anthropic
    billing key the original embedded client-side."""
    return _serve("name-builder/demo.gateway.html", settings)


@router.get("/finance-os", response_class=HTMLResponse)
async def finance_os(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Gateway-wired Finance OS — role-based cockpit; Treasury (banks) + Customers
    (Nama) panels load live via the gateway, rest stays demo. Read-only."""
    return _serve("finance-os/demo.gateway.html", settings)


@router.get("/finance-reports", response_class=HTMLResponse)
async def finance_reports(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Financial reports (AR/AP/aging/KPIs) — real Nama figures from the SQL DB."""
    return _serve("finance-os/reports.html", settings)


@router.get("/engineer", response_class=HTMLResponse)
async def engineer(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Engineer's assistant — tanks/vessels (ASME thickness), sanitary piping,
    laser & forming, heat exchangers, BOQ. Offline calculator for now: it holds
    no credentials and calls nothing, so its BOM is copied out by hand rather
    than checked against Nama's item master (see modules/engineer/README.md)."""
    return _serve("engineer/demo.gateway.html", settings)


@router.get("/ideas", response_class=HTMLResponse)
async def ideas_board(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Every requirement the owner voiced, as a searchable board — reads
    BACKLOG.md live, so a new row there shows up here with no code change."""
    return _serve("platform/ideas.html", settings)


@router.get("/platform", response_class=HTMLResponse)
async def platform_hub(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Unified platform hub — the single entry point. Links every live module and
    shows placeholders for the planned domains/engines. SSO entry (placeholder)."""
    return _serve("platform/hub.html", settings)


@router.get("/certificate", response_class=HTMLResponse)
async def quality_certificate(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Product quality certificate for imported steel — Foshan Amax Pro.

    Offline, like the engineer's assistant: it holds no credentials and calls
    nothing. The QR is encoded in the page. Its fallback used to hand the
    certificate number, contract number and purchaser to a third-party QR
    service whenever the local encoder threw, without saying so; that path is
    gone and a failed QR now says it failed.

    Not yet reading Nama. The purchaser, contract and product all exist there,
    so the next step is filling them from the ERP instead of by hand (LG10).
    """
    return _serve("import/certificate.html", settings)


@router.get("/expert", response_class=HTMLResponse)
async def nama_expert(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """Nama Expert — ask about Nama or about this platform, in Egyptian Arabic.

    Text, a pasted screenshot of a Nama error, or voice. The page holds no
    secret beyond the gateway key every `/tools/*` page already gets: the
    Anthropic credential stays in the server's settings and the question is
    composed server-side. Speech-to-text is the browser's own Web Speech API,
    so voice costs no vendor and no key either.

    Its answers carry `[S#]` markers back to the passages they came from, and
    with no model configured it shows those passages instead of writing prose
    around them.
    """
    return _serve("expert/chat.html", settings)


@router.get("/platform/public", response_class=HTMLResponse)
async def platform_hub_public(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """The wide-audience view of the hub — same figures, fewer internals.

    It existed as an unrouted file carrying its own hand-typed copies of the AR
    and AP totals and a hand-typed as-of date beside them, so it reported one
    day's position permanently. Serving it from the same `/api/v1/map` and
    `/api/v1/finance/kpis` the main hub uses is what stops the two from ever
    disagreeing — the point of having a single graph in the first place.
    """
    return _serve("platform/hub.public.html", settings)


# --- the project's own documents ------------------------------------------
# `BACKLOG.md` was the only file in the repo the running platform could see;
# the runbook, the decision log and the vision were unreachable from inside the
# thing they describe. Served read-only, from a fixed allow-list.
_DOC_DIRS = ("", "docs", "docs/enterprise-platform", "reference/finance-mvp")


def _library() -> dict[str, Path]:
    """slug -> file. Built by scanning, so a request can never name a path."""
    out: dict[str, Path] = {}
    for rel in _DOC_DIRS:
        base = _ROOT / rel if rel else _ROOT
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.md")):
            out[str(f.relative_to(_ROOT)).replace("\\", "/")] = f
    return out


@router.get("/library", response_class=HTMLResponse)
async def library() -> HTMLResponse:
    """Every markdown document in the repo, reachable from inside the platform."""
    docs = _library()
    rows = [
        {"doc": f'<a href="/tools/library/{name}">{_html.escape(name)}</a>',
         "size_kb": round(path.stat().st_size / 1024, 1)}
        for name, path in docs.items()
    ]
    body = (
        '<p class="muted">وثائق المشروع — تُقرأ من نفس الريبو الشغّال.</p>'
        + "<table><thead><tr><th>doc</th><th>size_kb</th></tr></thead><tbody>"
        + "".join(f'<tr><td>{r["doc"]}</td><td>{r["size_kb"]}</td></tr>' for r in rows)
        + "</tbody></table>"
    )
    return html_page("مكتبة الوثائق", body, {"count": len(docs), "docs": list(docs)},
                     badges=f'<span class="badge">{len(docs)} docs</span>')


@router.get("/library/{name:path}", response_class=HTMLResponse)
async def library_doc(name: str) -> HTMLResponse:
    """One document, as text. Markdown is served raw — no renderer, no dependency."""
    path = _library().get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No document '{name}' in the library")
    text = path.read_text(encoding="utf-8", errors="replace")
    body = (f'<p class="links"><a href="/tools/library">← المكتبة</a></p>'
            f"<pre>{_html.escape(text)}</pre>")
    return html_page(name, body, {"doc": name, "bytes": len(text.encode("utf-8"))})
