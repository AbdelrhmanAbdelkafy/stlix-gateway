"""الاستيراد والشحن — the API behind /tools/imports.

Nothing here computes: the router reads the store, hands it to `engine.plan`,
and returns. That is deliberate — the same plan feeds the screen, the fleet view
and the CSV, so the three can never tell different stories about a shipment.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from . import engine, nama_link, sop, store

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(require_api_key)])


def _who(request: Request) -> str:
    u = getattr(request.state, "user", None)
    return (u or {}).get("username", "") if isinstance(u, dict) else ""


def _plan(ref: str) -> dict:
    s = store.get(ref)
    if s is None:
        raise HTTPException(status_code=404, detail=f"مفيش ملف شحنة بالرقم {ref}")
    return engine.plan(s, store.docs(ref), store.costs(ref), store.containers(ref),
                       store.checklist(ref), store.steps(ref))


# --- الإجراء نفسه -------------------------------------------------------------
@router.get("/sop")
async def procedure(request: Request):
    """SOP-IMP-001 و SOP-IMP-002 كـ data — نفس اللي الشاشة والـ gates بيشتغلوا عليه."""
    data = sop.as_dict()
    rows = [{"sop": s["sop"], "no": s["no"], "phase": s["phase"], "title": s["title"],
             "owner": s["owner"], "gate": "🔒" if s["gate"] else ""}
            for d in data["sops"] for s in d["steps"]]
    return respond(request, data, title="إجراءات الاستيراد", rows=rows,
                   columns=["sop", "no", "phase", "title", "owner", "gate"])


# --- الشحنات ------------------------------------------------------------------
@router.get("")
async def overview(request: Request, status: str | None = "open"):
    """كل الشحنات المفتوحة: فين كل واحدة، إيه اللي واقف، والمؤشرات."""
    plans = []
    for s in store.listing(status or None):
        plans.append(engine.plan(s, store.docs(s["ref"]), store.costs(s["ref"]),
                                 store.containers(s["ref"]), store.checklist(s["ref"]),
                                 store.steps(s["ref"])))
    items = [{
        "ref": p["shipment"]["ref"], "supplier": p["shipment"].get("supplier"),
        "goods": p["shipment"].get("goods"), "nama_code": p["shipment"].get("nama_code"),
        "progress": p["progress"]["pct"], "state": p["clock"]["state"],
        "days_left": p["clock"]["days_left"], "overdue_days": p["clock"]["overdue_days"],
        "eta": p["clock"]["arrival"], "acid_ok": p["acid_check"]["ok"],
        "alerts": len(p["alerts"]),
        "critical": sum(1 for a in p["alerts"] if a["level"] == "critical"),
        "next": (p["next"] or {}).get("title"), "next_owner": (p["next"] or {}).get("owner"),
        "per_ton": p["landed"]["per_ton"],
    } for p in plans]
    data = {"count": len(items), "shipments": items, "kpis": engine.kpis(plans),
            "alerts": [dict(a, ref=p["shipment"]["ref"])
                       for p in plans for a in p["alerts"] if a["level"] == "critical"],
            "sop_counts": sop.as_dict()["counts"]}
    return respond(request, data, title="ملفات الاستيراد", rows=items,
                   columns=["ref", "supplier", "goods", "progress", "state", "days_left", "next"])


@router.post("")
async def create(request: Request):
    """افتح ملف شحنة. الرقم بيتولد (IMP-YYYY-NNN) إلا لو اتبعت."""
    body = await request.json()
    try:
        return store.create(body, who=_who(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/alerts")
async def all_alerts(request: Request, level: str | None = None):
    """كل التنبيهات على كل الشحنات المفتوحة — الأخطر الأول."""
    rows = []
    for s in store.listing("open"):
        p = engine.plan(s, store.docs(s["ref"]), store.costs(s["ref"]), store.containers(s["ref"]),
                        store.checklist(s["ref"]), store.steps(s["ref"]))
        rows += [dict(a, ref=s["ref"]) for a in p["alerts"] if not level or a["level"] == level]
    rank = {"critical": 0, "warn": 1, "info": 2}
    rows.sort(key=lambda a: rank[a["level"]])
    return respond(request, {"count": len(rows), "alerts": rows}, title="تنبيهات الاستيراد",
                   rows=rows, columns=["level", "ref", "text", "do", "who"])


@router.get("/nama/shipments")
async def nama_shipments(request: Request, limit: int = 100,
                         settings: Settings = Depends(get_settings)):
    """شحنات الشحن البحري في نما (LCShipment) — اللي ينفع نربط الملف بيها."""
    data = await nama_link.candidates(settings, limit)
    return respond(request, data, title="شحنات نما (LCShipment)", rows=data.get("rows"),
                   columns=["code", "name", "bl_no", "eta", "ata", "port_discharge", "state"])


@router.post("/nama/{code}/open")
async def open_from_nama(code: str, request: Request, settings: Settings = Depends(get_settings)):
    """افتح ملف شحنة من شحنة موجودة في نما — من غير إعادة إدخال."""
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — an empty body is the normal case
        pass
    try:
        return await nama_link.create_from_nama(code, settings, who=_who(request), **body)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"مفيش شحنة بالكود {code} في نما")


# --- ملف شحنة واحد ------------------------------------------------------------
@router.get("/{ref}")
async def one(ref: str, request: Request):
    """الملف كامل: الخطوات، الـ ACID، العدّاد، التكلفة، التنبيهات."""
    p = _plan(ref)
    rows = [{"الخطوة": f"{s['sop']}#{s['no']} {s['title']}", "المسؤول": s["owner"],
             "الحالة": s["state"], "السبب": s["why"]} for s in p["steps"]]
    return respond(request, p, title=f"ملف الشحنة {ref}", rows=rows,
                   columns=["الخطوة", "المسؤول", "الحالة", "السبب"])


@router.patch("/{ref}")
async def patch(ref: str, request: Request):
    body = await request.json()
    try:
        return store.update(ref, body, who=_who(request))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"مفيش ملف شحنة بالرقم {ref}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{ref}/sync")
async def sync(ref: str, request: Request, settings: Settings = Depends(get_settings)):
    """اسحب بيانات الشحنة من موديول الشحن البحري في نما."""
    try:
        return await nama_link.sync(ref, settings, who=_who(request))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"مفيش ملف شحنة بالرقم {ref}")


@router.get("/{ref}/nama/expenses")
async def nama_expenses(ref: str, settings: Settings = Depends(get_settings)):
    """أسطر مصاريف الاعتماد المرتبطة بالشحنة في نما (قراءة)."""
    try:
        return await nama_link.pull_expenses(ref, settings)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"مفيش ملف شحنة بالرقم {ref}")


@router.post("/{ref}/steps/{sop_code}/{no}")
async def step(ref: str, sop_code: str, no: int, request: Request):
    """حرّك خطوة: done / pending / na / blocked."""
    if (sop_code, no) not in sop.BY_KEY:
        raise HTTPException(status_code=404, detail=f"مفيش خطوة {sop_code}#{no}")
    body = await request.json()
    try:
        store.set_step(ref, sop_code, no, str(body.get("state") or "done"),
                       who=_who(request), note=str(body.get("note") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _plan(ref)


@router.post("/{ref}/docs/{kind}")
async def document(ref: str, kind: str, request: Request):
    """سجّل مستند: رقمه، رقم الـ ACID المكتوب عليه، واستلمناه ولا لأ."""
    if kind not in sop.DOC_KINDS:
        raise HTTPException(status_code=404, detail=f"نوع مستند مش معروف: {kind}")
    body = await request.json()
    fields = {k: v for k, v in body.items() if k in ("number", "acid_on_doc", "received", "note")}
    store.set_doc(ref, kind, who=_who(request), **fields)
    return _plan(ref)


@router.post("/{ref}/checklist/{key}")
async def check(ref: str, key: str, request: Request):
    """بند من checklist مراجعة مسودة البوليصة: ok / fix / na."""
    if key not in {c.key for c in sop.BL_CHECKLIST}:
        raise HTTPException(status_code=404, detail=f"بند مش معروف: {key}")
    body = await request.json()
    try:
        store.set_check(ref, key, str(body.get("state") or "ok"), who=_who(request),
                        note=str(body.get("note") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _plan(ref)


@router.post("/{ref}/costs")
async def add_cost(ref: str, request: Request):
    """بند تكلفة. بدون رقم فاتورة بيتسجّل بس بيطلع تنبيه — الضابط: لا صرف بدون فاتورة."""
    body = await request.json()
    kind = str(body.get("kind") or "other")
    if kind not in sop.COST_KINDS:
        raise HTTPException(status_code=400, detail=f"بند تكلفة مش معروف: {kind}")
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="المبلغ مطلوب")
    store.add_cost(ref, kind, amount, str(body.get("currency") or "EGP"),
                   str(body.get("invoice_no") or ""), str(body.get("vendor") or ""),
                   str(body.get("note") or ""), who=_who(request))
    return _plan(ref)


@router.delete("/{ref}/costs/{cost_id}")
async def delete_cost(ref: str, cost_id: int, request: Request):
    if not store.delete_cost(ref, cost_id, who=_who(request)):
        raise HTTPException(status_code=404, detail="البند مش موجود")
    return _plan(ref)


@router.post("/{ref}/containers")
async def add_container(ref: str, request: Request):
    body = await request.json()
    no = str(body.get("container_no") or "").strip()
    if not no:
        raise HTTPException(status_code=400, detail="رقم الحاوية مطلوب")
    store.add_container(ref, no, who=_who(request),
                        **{k: v for k, v in body.items() if k != "container_no"})
    return _plan(ref)


@router.patch("/{ref}/containers/{cid}")
async def update_container(ref: str, cid: int, request: Request):
    body = await request.json()
    store.update_container(ref, cid, who=_who(request), **body)
    return _plan(ref)


@router.delete("/{ref}/containers/{cid}")
async def delete_container(ref: str, cid: int, request: Request):
    if not store.delete_container(ref, cid, who=_who(request)):
        raise HTTPException(status_code=404, detail="الحاوية مش موجودة")
    return _plan(ref)


@router.get("/{ref}/log")
async def shipment_log(ref: str, request: Request, limit: int = 100):
    rows = store.log(ref, min(limit, 500))
    return respond(request, {"count": len(rows), "log": rows}, title=f"سجل {ref}",
                   rows=rows, columns=["at", "who", "action", "detail"])


@router.get("/{ref}/file.csv")
async def file_csv(ref: str):
    """ملف الشحنة كـ CSV — الخطوات وحالتها ومسؤولها، للمراجعة أو للأرشيف الورقي."""
    p = _plan(ref)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sop", "no", "phase", "title", "owner", "check", "gate", "state", "source", "why"])
    for s in p["steps"]:
        w.writerow([s["sop"], s["no"], s["phase"], s["title"], s["owner"], s["check"],
                    "gate" if s["gate"] else "", s["state"], s["source"], s["why"]])
    w.writerow([])
    w.writerow(["بند تكلفة", "المبلغ", "العملة", "رقم الفاتورة", "الجهة"])
    for c in p["costs"]:
        w.writerow([sop.COST_KINDS.get(c["kind"], c["kind"]), c["amount"], c["currency"],
                    c.get("invoice_no") or "", c.get("vendor") or ""])
    buf.seek(0)
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{ref}.csv"'})
