"""REP endpoints — العهدة · المستندات · الحركة، وفوقهم تقرير الإدارة.

`/overview` is the reason this connector exists in the owner's words: the data
inside the three units becomes the thing management reports are drawn from.
Every figure in it is computed over `data/rep/rep.json`; the provenance block
and its warnings ride along on every response, because two of these datasets
carry caveats written by REP's own author and a report that hides its caveats
is a report that gets believed wrongly.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...core.render import respond
from ...core.security import require_api_key
from . import store

router = APIRouter(prefix="/rep", tags=["rep"],
                   dependencies=[Depends(require_api_key)])


@router.get("")
async def status(request: Request):
    """What of REP is adopted here, and where the rest still lives."""
    src = store.source()
    d = store.load()
    adopted = ["العهدة (cust)", "المستندات (docs)", "الحركة (disp)"]
    rows = [{"metric": "وحدات مضمومة", "value": " · ".join(adopted)},
            {"metric": "أشخاص", "value": len(d["people"])},
            {"metric": "عربيات", "value": len(d["cars"])},
            {"metric": "أماكن", "value": len(d["places"])},
            {"metric": "قوالب مستندات", "value": len(d["doc_templates"])},
            {"metric": "المصدر", "value": src["file"]},
            {"metric": "الصفحة", "value": "/tools/rep"}]
    return respond(request, {
        "system": "REP التشغيلية",
        "adopted_units": adopted,
        "remaining_units": ["الوجبات", "الناس/القاموس", "اللوائح", "الأكاديمية",
                            "البنوك", "الجرد", "التنبيهات", "الرئيسية"],
        "counts": {"people": len(d["people"]), "cars": len(d["cars"]),
                   "places": len(d["places"]), "templates": len(d["doc_templates"])},
        "source": src,
    }, title="REP التشغيلية", rows=rows, columns=["metric", "value"])


@router.get("/custody")
async def custody(request: Request):
    """حاملو العهدة النقدية وعُهد العربيات — بالأعلام اللي عليها."""
    c = store.custody()
    rows = [{"الحامل": h["name"], "الكود": h["id"], "القسم": h["dept"],
             "الرصيد الافتتاحي": h["opening"], "ملاحظة": h.get("flag") or ""}
            for h in c["holders"]]
    rows += [{"الحامل": v["held_by"], "الكود": v["code"], "القسم": "عهدة عربية",
              "الرصيد الافتتاحي": "", "ملاحظة": ("🔴 مشي من الشركة" if v["holder_left_company"] else v["name"])}
             for v in c["vehicle_custody"]]
    return respond(request, c, title="العهدة", rows=rows,
                   columns=["الحامل", "الكود", "القسم", "الرصيد الافتتاحي", "ملاحظة"])


@router.get("/movement")
async def movement(request: Request):
    """فريق الحركة والأسطول والأماكن وقواعد المحرّك."""
    m = store.movement()
    rows = [{"الاسم": t["name"], "الدور": t["role"], "موبايل": t["mobile"] or "🔴 مفيش",
             "ماكينة": t["machine"] or "", "ملاحظة": t["flag"] or ""} for t in m["team"]]
    return respond(request, m, title="الحركة", rows=rows,
                   columns=["الاسم", "الدور", "موبايل", "ماكينة", "ملاحظة"])


@router.get("/documents")
async def documents(request: Request):
    """قوالب المستندات السبعة — كما هي من REP."""
    d = store.documents()
    rows = [{"القالب": t["emoji"] + " " + t["title"], "البادئة": t["prefix"],
             "جسر نما": t["bridge"] or "—", "حقول": len(t["fields"])}
            for t in d["templates"]]
    return respond(request, d, title="قوالب المستندات", rows=rows,
                   columns=["القالب", "البادئة", "جسر نما", "حقول"])


@router.get("/overview")
async def overview(request: Request):
    """تقرير الإدارة العليا — كل رقم محسوب من السجلات، مش مكتوب."""
    o = store.overview()
    rows = [
        {"البند": "حاملو عهدة نقدية", "القيمة": o["custody"]["holders"]},
        {"البند": "إجمالي الأرصدة الافتتاحية (ج)", "القيمة": o["custody"]["opening_total"]},
        {"البند": "عربيات في عهدة", "القيمة": o["custody"]["vehicles_held"]},
        {"البند": "🔴 عربيات يتيمة (حاملها مشي)", "القيمة": o["custody"]["orphan_vehicles"]},
        {"البند": "فريق الحركة", "القيمة": o["movement"]["team"]},
        {"البند": "🔴 سائقون بلا موبايل", "القيمة": o["movement"]["drivers_without_mobile"]},
        {"البند": "الأسطول", "القيمة": o["movement"]["fleet"]},
        {"البند": "قوالب مستندات موقَّعة", "القيمة": o["documents"]["templates"]},
        {"البند": "تنبيهات مفتوحة", "القيمة": o["alert_count"]},
    ]
    return respond(request, o, title="REP — تقرير الإدارة", rows=rows,
                   columns=["البند", "القيمة"])


@router.post("/reload")
async def reload():
    """أعد قراءة data/rep/rep.json بعد تحديثه."""
    d = store.reset()
    return {"reloaded": True, "people": len(d["people"]),
            "templates": len(d["doc_templates"])}
