"""Front-end tools served by the gateway.

These are the module UIs (e.g. NameBuilder) served from the gateway so their
only credential is the gateway's own key — the sensitive Nama/Anthropic creds
they used to embed now live server-side behind the API. Read-only for now;
the item WRITE path stays gated behind a deliberate read_write workflow.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from ..config import Settings, get_settings

router = APIRouter(prefix="/tools", tags=["tools"])

# Project root = parent of the `app` package -> modules/ lives beside it.
_MODULES = Path(__file__).resolve().parent.parent.parent / "modules"


def _serve(rel_path: str, settings: Settings) -> HTMLResponse:
    """Read a module page and inject the gateway key so the browser can call the
    protected API. Sensitive upstream creds (Nama/Vtiger/Anthropic) stay server-side."""
    html = (_MODULES / rel_path).read_text(encoding="utf-8")
    key = next(iter(settings.api_keys), "")
    return HTMLResponse(html.replace("__GATEWAY_API_KEY__", key))


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
