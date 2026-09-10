"""ض.ق.م planner + portal documents — the API behind /tools/vat and the MCP."""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from ..eta import store as eta
from . import engine, store, watcher

router = APIRouter(prefix="/vat", tags=["vat"], dependencies=[Depends(require_api_key)])


def _who(request: Request) -> str:
    u = getattr(request.state, "user", None)
    return (u or {}).get("username", "") if isinstance(u, dict) else ""


def _entity(key: str, settings: Settings):
    try:
        return eta.entity(key, settings)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown entity {key}")


def _month(month: str) -> str:
    if len(month) != 7 or month[4] != "-" or not (month[:4] + month[5:]).isdigit():
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    return month


def _this_and_prev() -> list[str]:
    t = date.today()
    prev = f"{t.year - 1}-12" if t.month == 1 else f"{t.year}-{t.month - 1:02d}"
    return [f"{t.year}-{t.month:02d}", prev]


@router.get("")
async def overview(request: Request, settings: Settings = Depends(get_settings)):
    """Every entity, this month and last: the headline + where the return stands."""
    ents = eta.entities(settings)
    items = []
    for e in ents:
        for m in _this_and_prev():
            p = engine.plan(e, m, settings)
            items.append({"entity": e.key, "entity_name": e.name, "month": m, "status": p["status_ar"],
                          "headline": p["headline"], "action": p["action"], "gap_base": p["gap_base"],
                          "sales_net": p["sales"]["net"], "synced": p["synced"],
                          "deadline": p["calendar"]["filing_deadline"]})
    data = {"configured": bool(ents) and all(e.configured for e in ents), "k_mode": settings.vat_k_mode,
            "entities": [e.public() for e in ents], "items": items,
            "note": None if ents else "ETA_ENTITIES_JSON فاضي — حط بيانات الكيانين في .env"}
    return respond(request, data, title="ض.ق.م — التخطيط", rows=items,
                   columns=["entity_name", "month", "status", "headline", "deadline"])


@router.get("/log")
async def vat_log(request: Request, entity: str | None = None, limit: int = 100):
    """Who changed what (status moves, imports, credits)."""
    rows = store.log(entity, min(limit, 500))
    return respond(request, {"count": len(rows), "log": rows}, title="ض.ق.م — السجل", rows=rows,
                   columns=["at", "entity", "month", "who", "action", "detail"])


@router.get("/alerts")
async def vat_alerts(request: Request, entity: str | None = None, limit: int = 50, unseen: bool = False):
    """What the watcher decided is worth telling a human (newest first)."""
    rows = watcher.alerts(entity, min(limit, 200), unseen)
    return respond(request, {"count": len(rows), "alerts": rows}, title="ض.ق.م — التنبيهات", rows=rows,
                   columns=["day", "entity", "month", "level", "text"])


@router.post("/alerts/seen")
async def seen(request: Request):
    """Mark alerts read: {"ids": [1,2,3]}."""
    body = await request.json()
    return {"ok": True, "updated": watcher.mark_seen([int(i) for i in body.get("ids") or []])}


@router.post("/sweep")
async def sweep(settings: Settings = Depends(get_settings)):
    """Run one watcher pass now (the same one the background loop runs)."""
    return await watcher.sweep(settings)


@router.get("/codes")
async def codes(request: Request):
    """Item codes counted as manufacturing (AssemblyBOM items)."""
    c = sorted(engine.manufacturing_codes())
    return respond(request, {"count": len(c), "codes": c}, title="أكواد التصنيع",
                   rows=[{"code": x} for x in c], columns=["code"])


@router.put("/codes")
async def put_codes(request: Request):
    """Replace the manufacturing code list (body: {"codes": [...]})."""
    body = await request.json()
    n = engine.save_manufacturing_codes(list(body.get("codes") or []), source=f"manual:{_who(request)}")
    return {"ok": True, "count": n}


@router.post("/codes/refresh")
async def refresh_codes(settings: Settings = Depends(get_settings)):
    """Pull AssemblyBOM item codes from Nama (needs Nama keys)."""
    if not settings.nama_configured:
        return JSONResponse({"error": "مفاتيح نما مش متحطة"}, status_code=503)
    from ..nama.client import NamaClient
    client = NamaClient(settings)
    rows = await client.list_all("AssemblyBOM", order_by="code")
    codes_ = []
    for r in rows:
        item = r.get("item") or r.get("assembledItem") or {}
        code = item.get("code") if isinstance(item, dict) else None
        if code:
            codes_.append(code)
    n = engine.save_manufacturing_codes(codes_, source="nama:AssemblyBOM")
    return {"ok": True, "count": n, "boms": len(rows)}


@router.get("/{entity}/{month}")
async def month_plan(entity: str, month: str, request: Request, settings: Settings = Depends(get_settings)):
    """The plan: sales, purchases, imports, credit, target, gap, slots, problems."""
    p = engine.plan(_entity(entity, settings), _month(month), settings)
    rows = [{"البند": "مبيعات (صافي)", "القيمة": p["sales"]["net"]},
            {"البند": "ض.ق.م مبيعات", "القيمة": p["sales"]["vat"]},
            {"البند": "ض.ق.م مشتريات موجودة", "القيمة": p["purchases"]["vat"]},
            {"البند": "ض.ق.م استيراد", "القيمة": p["imports"]["vat"]},
            {"البند": "رصيد مرحّل", "القيمة": p["credit_in"]},
            {"البند": "المستهدف دفعه", "القيمة": p["target_payable"]},
            {"البند": "الفجوة (قاعدة فواتير)", "القيمة": p["gap_base"]},
            {"البند": "الخلاصة", "القيمة": p["headline"]}]
    return respond(request, p, title=f"ض.ق.م · {p['entity']['name']} · {month}", rows=rows, columns=["البند", "القيمة"])


@router.post("/{entity}/{month}/sync")
async def sync(entity: str, month: str, request: Request, settings: Settings = Depends(get_settings)):
    """Pull the month from the portal (both directions) into the cache."""
    e = _entity(entity, settings)
    if not e.configured:
        return JSONResponse({"ok": False, "error": f"{e.key}: client_id/secret مش متحطين"}, status_code=503)
    return await eta.sync(e.key, _month(month), settings)


@router.get("/{entity}/{month}/documents")
async def documents(entity: str, month: str, request: Request, direction: str | None = None,
                    status: str | None = None, settings: Settings = Depends(get_settings)):
    """Cached portal documents of the month."""
    _entity(entity, settings)
    rows = eta.documents(entity, _month(month), direction, status, settings)
    return respond(request, {"count": len(rows), "documents": rows}, title=f"مستندات البورتال · {month}",
                   rows=rows, columns=["issued_at", "direction", "doc_type", "internal_id", "issuer_name",
                                       "receiver_name", "net", "vat", "status"])


@router.post("/{entity}/{month}/imports")
async def add_import(entity: str, month: str, request: Request, settings: Settings = Depends(get_settings)):
    """Record a customs release: body {"vat": 12345.67, "release_no": "...", "note": "..."}."""
    _entity(entity, settings)
    body = await request.json()
    try:
        vat = float(body.get("vat"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="vat (رقم) مطلوب")
    return store.add_import(entity, _month(month), vat, str(body.get("release_no") or ""),
                            str(body.get("note") or ""), who=_who(request))


@router.delete("/{entity}/{month}/imports/{import_id}")
async def delete_import(entity: str, month: str, import_id: int, request: Request,
                        settings: Settings = Depends(get_settings)):
    _entity(entity, settings)
    if not store.delete_import(entity, _month(month), import_id, who=_who(request)):
        raise HTTPException(status_code=404, detail="import not found")
    return {"ok": True}


@router.patch("/{entity}/{month}")
async def update_month(entity: str, month: str, request: Request, settings: Settings = Depends(get_settings)):
    """Move the return along the procedure / set credit_in / record payment."""
    _entity(entity, settings)
    body = await request.json()
    try:
        row = store.save_month(entity, _month(month), who=_who(request), **body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return row


@router.post("/{entity}/{month}/draft")
async def draft(entity: str, month: str, request: Request, settings: Settings = Depends(get_settings)):
    """Rami's draft figures → compare; a full match moves the month to ready_to_pay."""
    e = _entity(entity, settings)
    body = await request.json()
    p = engine.plan(e, _month(month), settings)
    cmp = engine.compare_draft(p, body)
    store.save_month(entity, month, who=_who(request), draft=body,
                     status="ready_to_pay" if cmp["match"] else "draft_review")
    return cmp


@router.get("/{entity}/{month}/package")
async def package(entity: str, month: str, request: Request, settings: Settings = Depends(get_settings)):
    """The return package (figures + problem list) — what used to be typed by hand."""
    p = engine.plan(_entity(entity, settings), _month(month), settings)
    return engine.package(p)


@router.get("/{entity}/{month}/package.csv")
async def package_csv(entity: str, month: str, settings: Settings = Depends(get_settings)):
    """Same package as a CSV (documents sheet for the accountant)."""
    e = _entity(entity, settings)
    docs = eta.documents(e.key, _month(month), settings=settings)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["direction", "type", "status", "internal_id", "issued_at", "issuer", "receiver", "net", "vat", "total", "uuid"])
    for d in docs:
        w.writerow([d["direction"], d["doc_type"], d["status"], d.get("internal_id"), d.get("issued_at"),
                    d.get("issuer_name"), d.get("receiver_name"), d.get("net"), d.get("vat"), d.get("total"), d["uuid"]])
    buf.seek(0)
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="vat-{e.key}-{month}.csv"'})
