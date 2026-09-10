"""Everything the portal can do, as our own API — so nobody opens a browser.

Reads are plain. The two writes the portal allows (cancel one of ours, reject
one sent to us) are behind three locks at once: `ETA_ALLOW_STATE_CHANGES` must
be on, the caller must name a reason, and the call is written to the VAT audit
log with the username. They are irreversible at ETA and they expire, so they
are the one place in this platform where "automatic" stops meaning "unattended".

Issuing documents is not here at all: submission must be signed with the eSeal
certificate, which lives on a hardware token in the system that issues.
"""
from __future__ import annotations

from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from ..vat import store as vat_store
from . import store
from .client import EtaClient, EtaError

router = APIRouter(prefix="/eta", tags=["eta"], dependencies=[Depends(require_api_key)])


def _who(request: Request) -> str:
    u = getattr(request.state, "user", None)
    return (u or {}).get("username", "") if isinstance(u, dict) else ""


def _client(key: str, settings: Settings) -> EtaClient:
    try:
        ent = store.entity(key, settings)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown entity {key}")
    if not ent.configured:
        raise HTTPException(status_code=503, detail=f"{key}: client_id/secret مش متحطين في .env")
    return EtaClient(ent, settings.eta_env)


async def _call(key: str, settings: Settings, fn):
    eta = _client(key, settings)
    try:
        async with httpx.AsyncClient() as http:
            return await fn(eta, http)
    except EtaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:300])


@router.get("/{entity}/ping")
async def ping(entity: str, settings: Settings = Depends(get_settings)):
    """Can we get a token for this entity right now?"""
    return await _call(entity, settings, lambda e, h: e.ping())


@router.get("/{entity}/recent")
async def recent(entity: str, request: Request, page: int = 1, page_size: int = 50,
                 direction: str | None = None, status: str | None = None,
                 settings: Settings = Depends(get_settings)):
    """What landed lately, straight from the portal (no date window needed)."""
    j = await _call(entity, settings, lambda e, h: e.recent(h, page_no=page, page_size=min(page_size, 100),
                                                            direction=direction, status=status))
    rows = j.get("result") or []
    return respond(request, j, title=f"آخر المستندات · {entity}", rows=rows,
                   columns=["dateTimeIssued", "internalId", "issuerName", "receiverName", "total", "status"])


@router.get("/{entity}/notifications")
async def notifications(entity: str, request: Request, page: int = 1, page_size: int = 50,
                        settings: Settings = Depends(get_settings)):
    """ETA's own messages to this taxpayer — the inbox nobody opens."""
    j = await _call(entity, settings, lambda e, h: e.notifications(h, page_no=page, page_size=min(page_size, 100)))
    rows = j.get("result") or j.get("notifications") or []
    return respond(request, j, title=f"إشعارات المصلحة · {entity}", rows=rows if isinstance(rows, list) else [])


@router.get("/{entity}/document-types")
async def document_types(entity: str, request: Request, settings: Settings = Depends(get_settings)):
    """Types + workflow parameters — including the real cancellation window."""
    j = await _call(entity, settings, lambda e, h: e.document_types(h))
    return respond(request, j, title="أنواع المستندات")


@router.get("/{entity}/documents/{uuid}")
async def document_raw(entity: str, uuid: str, request: Request, settings: Settings = Depends(get_settings)):
    """The original submission as its issuer sent it."""
    j = await _call(entity, settings, lambda e, h: e.raw(h, uuid))
    return respond(request, j, title=f"المستند الأصلي · {uuid[:8]}")


@router.get("/{entity}/documents/{uuid}/details")
async def document_details(entity: str, uuid: str, request: Request, settings: Settings = Depends(get_settings)):
    """Lines, taxes and validation results for one document."""
    j = await _call(entity, settings, lambda e, h: e.details(h, uuid))
    return respond(request, j, title=f"تفاصيل المستند · {uuid[:8]}")


@router.get("/{entity}/documents/{uuid}/pdf")
async def document_pdf(entity: str, uuid: str, settings: Settings = Depends(get_settings)):
    """ETA's own PDF — the printable copy, with its QR."""
    data = await _call(entity, settings, lambda e, h: e.printout(h, uuid))
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{uuid}.pdf"'})


# --- month packages: ETA prepares the whole month as one file --------------------
@router.post("/{entity}/packages")
async def request_package(entity: str, request: Request, settings: Settings = Depends(get_settings)):
    """Ask ETA to prepare a package: {"month": "2026-08"} or {"date_from","date_to"},
    optional {"format": "JSON|XML|CSV", "type": "full|summary"}."""
    body = await request.json()
    if body.get("month"):
        d_from, d_to = store.month_bounds(str(body["month"]))
    else:
        try:
            d_from = date.fromisoformat(str(body["date_from"]))
            d_to = date.fromisoformat(str(body["date_to"]))
        except (KeyError, ValueError):
            raise HTTPException(status_code=400, detail="month أو date_from/date_to مطلوبين")
    fmt, type_ = str(body.get("format", "JSON")), str(body.get("type", "full"))
    out = await _call(entity, settings, lambda e, h: e.request_package(
        h, date_from=d_from, date_to=d_to, fmt=fmt, type_=type_,
        document_types=body.get("document_types"), statuses=body.get("statuses")))
    return out


@router.get("/{entity}/packages")
async def package_requests(entity: str, request: Request, page: int = 1,
                           settings: Settings = Depends(get_settings)):
    """Which packages we asked for and whether they are ready."""
    j = await _call(entity, settings, lambda e, h: e.package_requests(h, page_no=page))
    rows = j.get("result") or []
    return respond(request, j, title="حزم المستندات", rows=rows)


@router.get("/{entity}/packages/{package_id}")
async def package(entity: str, package_id: str, settings: Settings = Depends(get_settings)):
    """Download a prepared package (zip)."""
    data = await _call(entity, settings, lambda e, h: e.package(h, package_id))
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{package_id}.zip"'})


# --- the two writes ---------------------------------------------------------------
@router.put("/{entity}/documents/{uuid}/state")
async def set_state(entity: str, uuid: str, request: Request, settings: Settings = Depends(get_settings)):
    """Cancel ours / reject theirs: {"status": "cancelled|rejected", "reason": "…"}.

    Refused unless ETA_ALLOW_STATE_CHANGES=true. Irreversible at ETA, and only
    valid inside the document type's window — so it is logged with who asked.
    """
    body = await request.json()
    status, reason = str(body.get("status", "")).lower(), str(body.get("reason", ""))
    if not settings.eta_allow_state_changes:
        return JSONResponse({"error": "معطّل", "detail":
                             "إلغاء/رفض المستندات على البورتال مقفول — ETA_ALLOW_STATE_CHANGES=false في .env",
                             "uuid": uuid, "status": status}, status_code=403)
    if status not in ("cancelled", "rejected"):
        raise HTTPException(status_code=400, detail="status لازم cancelled أو rejected")
    if len(reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="السبب (reason) مطلوب")
    who = _who(request)
    out = await _call(entity, settings, lambda e, h: e.set_state(h, uuid, status, reason))
    vat_store.save_month(entity, (body.get("month") or date.today().strftime("%Y-%m")), who=who,
                         notes=f"{status} {uuid}: {reason.strip()[:120]}")
    return out
