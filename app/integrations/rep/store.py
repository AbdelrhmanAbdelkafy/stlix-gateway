"""The REP data store — files on disk, provenance attached.

Everything served by the REP connector comes out of `data/rep/rep.json`, which
was extracted **verbatim** from `rep-system.html` (the arrays were evaluated,
not retyped — the same discipline as the legal demo's regexes). The `_source`
block travels with every response, because two of these datasets carry warnings
written by REP's own author: the PLACES distances are declared placeholder in
the original file, and E000155's opening balance equals the Nama figure the
master runbook flags as false. A management report built on this data must show
those warnings, not absorb them.

What is deliberately NOT here: the day-to-day operational records (expense
receipts, planned trips, policy acknowledgements). In the original those lived
in each user's browser localStorage — they were never in the file, so there is
nothing to migrate. The upgraded UI keeps them client-side for now; moving them
server-side is a WRITE path and follows the platform's write rules.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA = _ROOT / "data" / "rep" / "rep.json"

_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(DATA.read_text(encoding="utf-8"))
    return _CACHE


def reset() -> dict:
    global _CACHE
    _CACHE = None
    return load()


def source() -> dict:
    return load()["_source"]


# --- the three adopted units ------------------------------------------------

def custody() -> dict:
    """Cash custody holders and the vehicles held as custody."""
    d = load()
    holders = [p for p in d["people"] if p.get("holder")]
    cars = d["cars"]
    return {
        "holders": [
            {"id": p["id"], "name": p["n"], "job": p["j"], "dept": p["dept"],
             "opening": p.get("open", 0), "flag": p.get("flag")}
            for p in holders
        ],
        "opening_total": sum(p.get("open", 0) for p in holders),
        "vehicle_custody": [
            {"code": c["c"], "name": c["n"], "held_by": c["cust"],
             "holder_left_company": bool(c.get("gone"))}
            for c in cars
        ],
        "orphan_vehicles": [c["n"] + " — عهدتها على " + c["cust"]
                            for c in cars if c.get("gone")],
        "expense_categories": d["expense_categories"],
        "source": d["_source"],
    }


def movement() -> dict:
    """Drivers, fleet, destinations and the dispatch rules."""
    d = load()
    drivers = [p for p in d["people"] if p["dept"] == "الحركة"]
    return {
        "team": [
            {"id": p["id"], "name": p["n"], "role": p["j"], "mobile": p.get("mob"),
             "machine": p.get("mach"), "flag": p.get("flag")}
            for p in drivers
        ],
        "drivers_without_mobile": [p["n"] for p in drivers if not p.get("mob")],
        "fleet": d["cars"],
        "fleet_km_readings": sum(1 for c in d["cars"] if c.get("km") is not None),
        "places": d["places"],
        "places_warning": "المسافات والأزمنة افتراضية — مكتوب كده في الملف الأصلي",
        "load_kinds": d["loads"],
        "rules": [
            "مواعيد الإغلاق تُحسب أولًا: خروج + زمن الطريق لازم يسبق إغلاق الجهة",
            "الدمج: رحلتان لنفس المنطقة في نطاق ٦٠ دقيقة تندمجان لو العربية تسع",
            "لا بضاعة إلا في عربية بضاعة، ولا ركاب فوق سعة المقاعد",
            "التوزيع العادل: السائق صاحب أقل رحلات اليوم يُختار أولًا",
            "قاعدة الـ١٠ دقائق (اللائحة الداخلية): الانتظار التشغيلي فوق ١٠ دقايق هدر",
        ],
        "source": d["_source"],
    }


def documents() -> dict:
    """The seven signed-document templates, verbatim."""
    d = load()
    return {"templates": list(d["doc_templates"].values()),
            "count": len(d["doc_templates"]),
            "source": d["_source"]}


def overview() -> dict:
    """What top management asks about these three units, in one response.

    Every figure here is a sum or count over the store — nothing is typed in.
    The alerts are the ones REP's own engine raised, recomputed from the same
    records rather than copied as text.
    """
    d = load()
    cust = custody()
    mov = movement()
    alerts: list[dict] = []
    for c in d["cars"]:
        if c.get("gone"):
            alerts.append({"level": "bad", "unit": "العهدة",
                           "text": f"عربية يتيمة: {c['n']} عهدتها على {c['cust']} — مشي من الشركة"})
    for p in d["people"]:
        if p.get("flag"):
            alerts.append({"level": "warn", "unit": "الناس", "text": f"{p['n']}: {p['flag']}"})
    for n in mov["drivers_without_mobile"]:
        alerts.append({"level": "bad", "unit": "الحركة",
                       "text": f"سائق بلا موبايل في نما: {n} — النظام مش هيعرف يبلّغه"})
    if mov["fleet_km_readings"] == 0:
        alerts.append({"level": "warn", "unit": "الأسطول",
                       "text": "قراءات العداد فاضية في كل العربيات (B-02) — وحدة الصيانة واقفة عليها"})
    return {
        "custody": {
            "holders": len(cust["holders"]),
            "opening_total": cust["opening_total"],
            "vehicles_held": len(cust["vehicle_custody"]),
            "orphan_vehicles": len(cust["orphan_vehicles"]),
        },
        "movement": {
            "team": len(mov["team"]),
            "drivers_without_mobile": len(mov["drivers_without_mobile"]),
            "fleet": len(mov["fleet"]),
            "destinations": len(mov["places"]),
        },
        "documents": {"templates": documents()["count"]},
        "alerts": alerts,
        "alert_count": len(alerts),
        "source": d["_source"],
    }
