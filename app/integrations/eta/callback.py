"""The endpoint ETA itself calls — needed to register our ERP in the first place.

Registering a taxpayer system on `profile.eta.gov.eg` asks for a base URL and a
pre-shared key, then ETA calls `PUT {base}/ping` with `{"rin": "…"}` and expects
the same `rin` back. Until that ping succeeds there are no API credentials, so
this small endpoint is the first thing that has to exist, not the last.

It is deliberately outside every other gate: no session, no gateway key. Its own
key is `ETA_ERP_CALLBACK_KEY`, sent by ETA as `Authorization: ApiKey <key>`, and
it can do exactly one thing — echo a registration number we already know.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from ...config import Settings, get_settings
from . import store

log = logging.getLogger("gateway.eta")

#: Mounted at the app root (not under /api/v1) because the base URL registered
#: with ETA should stay short and stable: https://gw.…/eta/erp
router = APIRouter(prefix="/eta/erp", tags=["eta"])


def _key_ok(header: str | None, settings: Settings) -> bool:
    if not settings.eta_erp_callback_key:
        return False
    value = (header or "").strip()
    if value.lower().startswith("apikey "):
        value = value[7:].strip()
    return value == settings.eta_erp_callback_key


@router.put("/ping")
async def ping(request: Request, authorization: str | None = Header(default=None),
               settings: Settings = Depends(get_settings)):
    """ETA's reachability check during system registration."""
    if not settings.eta_erp_callback_key:
        log.warning("eta.ping refused: ETA_ERP_CALLBACK_KEY not set")
        return JSONResponse({"error": "callback key not configured"}, status_code=503)
    if not _key_ok(authorization, settings):
        log.warning("eta.ping refused: bad key")
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    rin = str((body or {}).get("rin") or "").strip()
    known = {e.rin for e in store.entities(settings) if e.rin}
    if not rin:
        return JSONResponse({"error": "rin missing"}, status_code=400)
    if known and rin not in known:
        # Answering for a taxpayer we do not represent would be a lie ETA acts on.
        log.warning("eta.ping unknown rin")
        return JSONResponse({"error": "unknown rin"}, status_code=400)
    log.info("eta.ping ok")
    return {"rin": rin}
