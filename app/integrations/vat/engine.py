"""The arithmetic of the routine, with every input named.

    payable            = VAT_sales − VAT_purchases − VAT_imports − credit_in
    target_payable     = k‰ × net_sales                       (k per entity)
    VAT_purchases_need = VAT_sales − VAT_imports − credit_in − target_payable
    gap (VAT)          = VAT_purchases_need − VAT_purchases_have
    gap (base)         = gap / 14%     ← "هات فواتير مشتريات بقيمة …"

Negative gap = surplus (رصيد فايض) → tell the admin group, buy nothing.
Manufacturing / trading split: a line is manufacturing when its item code is
one of the AssemblyBOM item codes (data/vat/manufacturing-codes.json, refreshed
from Nama when configured); everything else is trading.
"""
from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path

from ...config import Settings, get_settings
from ..eta import store as eta
from ..eta.client import Entity
from . import store

VAT_RATE = 0.14
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CODES_FILE = _ROOT / "data" / "vat" / "manufacturing-codes.json"
SIGN = {"I": 1, "D": 1, "C": -1, "II": 1, "EI": 1, "ED": 1, "EC": -1}
WEEKLY_DAYS = (7, 14, 21, 28)
NO_INVOICE_FROM_DAY = 30


def manufacturing_codes() -> set[str]:
    if not CODES_FILE.exists():
        return set()
    try:
        j = json.loads(CODES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {str(c).strip().upper() for c in (j.get("codes") or []) if str(c).strip()}


def save_manufacturing_codes(codes: list[str], source: str = "manual") -> int:
    CODES_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean = sorted({str(c).strip().upper() for c in codes if str(c).strip()})
    CODES_FILE.write_text(json.dumps({"source": source, "count": len(clean), "codes": clean},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    return len(clean)


def _split(doc: dict, codes: set[str]) -> tuple[float, float, float, float]:
    """(net_manufacturing, vat_manufacturing, net_trading, vat_trading) for one document."""
    lines = doc.get("lines")
    if not lines:
        net, vat = _net_or_estimate(doc), _vat_or_estimate(doc)
        return (net, vat, 0.0, 0.0) if not codes else (0.0, 0.0, net, vat)
    nm = vm = nt = vt = 0.0
    for ln in lines:
        code = str(ln.get("internal_code") or "").upper()
        code2 = str(ln.get("item_code") or "").upper()
        if code in codes or code2 in codes:
            nm += float(ln.get("net") or 0)
            vm += float(ln.get("vat") or 0)
        else:
            nt += float(ln.get("net") or 0)
            vt += float(ln.get("vat") or 0)
    return nm, vm, nt, vt


def _net_or_estimate(doc: dict) -> float:
    """The portal's document list shows one money column: the total, tax included.
    Reading a missing net as zero would silently drop the whole month, so back
    the net out of the total instead — and `vat_known` stays false, which is how
    the screen knows to call the figure an estimate."""
    net = doc.get("net")
    if net is not None:
        return float(net)
    total = float(doc.get("total") or 0)
    return round(total / (1 + VAT_RATE), 2) if total else 0.0


def _vat_or_estimate(doc: dict) -> float:
    if doc.get("vat") is not None and doc.get("vat_known"):
        return float(doc["vat"])
    net = float(doc.get("net") or 0)
    total = float(doc.get("total") or 0)
    if net:
        diff = total - net
        return diff if 0 <= diff <= net * 0.2 else round(net * VAT_RATE, 2)
    return round(total - total / (1 + VAT_RATE), 2) if total else 0.0


def schedule(month: str, today: date, has_imports: bool, credit_in: float,
             purchase_days: list[int]) -> list[dict]:
    """The invoice slots of the month and whether each got covered."""
    y, m = int(month[:4]), int(month[5:7])
    last = calendar.monthrange(y, m)[1]
    slots: list[dict] = []
    if not has_imports and credit_in <= 0:
        slots.append({"day": 1, "rule": "يوم 1 — مفيش استيراد ولا رصيد مرحّل"})
    for d in WEEKLY_DAYS:
        if d <= last:
            slots.append({"day": d, "rule": "أسبوعي"})
    for s in slots:
        lo = s["day"] - 3 if s["day"] > 1 else 1
        hi = min(s["day"] + 3, NO_INVOICE_FROM_DAY - 1)
        s["covered"] = any(lo <= pd <= hi for pd in purchase_days)
        s["date"] = date(y, m, s["day"]).isoformat()
        s["past"] = date(y, m, s["day"]) < today
    return slots


def plan(entity: Entity, month: str, settings: Settings | None = None, today: date | None = None) -> dict:
    settings = settings or get_settings()
    today = today or date.today()
    codes = manufacturing_codes()
    row = store.month_row(entity.key, month, settings)
    docs = eta.documents(entity.key, month, settings=settings)
    sync = eta.last_sync(entity.key, month, settings)

    sales = {"net": 0.0, "vat": 0.0, "net_m": 0.0, "vat_m": 0.0, "net_t": 0.0, "vat_t": 0.0, "count": 0}
    purch = {"net": 0.0, "vat": 0.0, "count": 0, "days": []}
    imp_docs = {"net": 0.0, "vat": 0.0, "count": 0}
    problems: list[dict] = []
    estimated = 0
    customs = set(entity.customs_issuer_ids)
    for d in docs:
        st = d.get("status") or ""
        sign = SIGN.get((d.get("doc_type") or "I").upper(), 1)
        if st in ("cancelled", "rejected", "invalid"):
            problems.append({"uuid": d["uuid"], "internal_id": d.get("internal_id"), "direction": d["direction"],
                             "status": st, "net": d.get("net"), "counterparty": d.get("receiver_name") if d["direction"] == "Sent" else d.get("issuer_name"),
                             "reason": d.get("reason")})
            continue
        if st not in ("valid",):
            continue  # submitted-but-not-yet-valid is not money yet
        vat = _vat_or_estimate(d) * sign
        net = _net_or_estimate(d) * sign
        if not d.get("vat_known"):
            estimated += 1
        if d["direction"] == "Sent":
            nm, vm, nt, vt = _split(d, codes)
            sales["net"] += net
            sales["vat"] += vat
            sales["net_m"] += nm * sign
            sales["vat_m"] += (vm if d.get("vat_known") else nm * VAT_RATE) * sign
            sales["net_t"] += nt * sign
            sales["vat_t"] += (vt if d.get("vat_known") else nt * VAT_RATE) * sign
            sales["count"] += 1
        else:
            if str(d.get("issuer_id") or "") in customs:
                imp_docs["net"] += net
                imp_docs["vat"] += vat
                imp_docs["count"] += 1
            else:
                purch["net"] += net
                purch["vat"] += vat
                purch["count"] += 1
                if d.get("issued_at"):
                    try:
                        purch["days"].append(int(d["issued_at"][8:10]))
                    except ValueError:
                        pass

    manual = store.imports(entity.key, month, settings)
    imports_vat = imp_docs["vat"] + sum(float(i["vat"]) for i in manual)
    imports_base = imp_docs["net"] + sum(float(i["base"] or 0) for i in manual)
    credit_in = float(row.get("credit_in") or 0)

    if settings.vat_k_mode == "per_activity":
        target = (entity.k_manufacturing * sales["net_m"] + entity.k_trading * sales["net_t"]) / 1000
    else:
        target = entity.k_total * sales["net"] / 1000
    need_vat = sales["vat"] - imports_vat - credit_in - target
    gap_vat = need_vat - purch["vat"]
    payable_now = sales["vat"] - purch["vat"] - imports_vat - credit_in

    y, m = int(month[:4]), int(month[5:7])
    last_day = calendar.monthrange(y, m)[1]
    ny, nm_ = (y + 1, 1) if m == 12 else (y, m + 1)
    filing_deadline = date(ny, nm_, calendar.monthrange(ny, nm_)[1])
    recheck_day = date(ny, nm_, 7)
    month_over = today > date(y, m, last_day)

    slots = schedule(month, today, imports_vat > 0, credit_in, purch["days"])
    remaining_slots = [s for s in slots if not s["past"] and not s["covered"]]
    per_slot = (gap_vat / VAT_RATE / len(remaining_slots)) if gap_vat > 0 and remaining_slots else 0.0

    if gap_vat > 0:
        headline = f"محتاج فواتير مشتريات بقيمة {gap_vat / VAT_RATE:,.0f} ج (ض.ق.م {gap_vat:,.0f} ج)"
        action = "buy"
    elif gap_vat < 0:
        headline = f"رصيد فايض {-gap_vat:,.0f} ج ض.ق.م — يتبعت لجروب الأدمن، مفيش شراء"
        action = "surplus"
    else:
        headline = "مظبوط بالظبط"
        action = "ok"
    if sales["count"] == 0:
        headline = "مفيش مبيعات على البورتال للشهر ده لسه"
        action = "none"

    return {
        "entity": entity.public(), "month": month, "today": today.isoformat(),
        "status": row["status"], "status_ar": row["status_ar"],
        "k_mode": settings.vat_k_mode, "vat_rate": VAT_RATE,
        "sync": sync, "synced": bool(sync and sync.get("ok")),
        # How many of the month's documents had no VAT figure on the portal and
        # were backed out of the total instead. The screen says so out loud:
        # a plan built on estimates is not the same promise as one built on
        # figures the portal printed.
        "estimated_docs": estimated,
        "sales": {k: round(v, 2) if isinstance(v, float) else v for k, v in sales.items()},
        "purchases": {"net": round(purch["net"], 2), "vat": round(purch["vat"], 2), "count": purch["count"]},
        "imports": {"vat": round(imports_vat, 2), "base": round(imports_base, 2),
                    "portal_docs": imp_docs["count"], "manual": manual},
        "credit_in": credit_in,
        "target_payable": round(target, 2),
        "purchases_vat_needed": round(need_vat, 2),
        "purchases_base_needed": round(need_vat / VAT_RATE, 2),
        "gap_vat": round(gap_vat, 2), "gap_base": round(gap_vat / VAT_RATE, 2),
        "payable_now": round(payable_now, 2),
        "credit_out_if_filed_now": round(-payable_now, 2) if payable_now < 0 else 0.0,
        "headline": headline, "action": action,
        "slots": slots, "per_slot_base": round(per_slot, 2),
        "problems": problems,
        "manufacturing_codes": len(codes),
        "calendar": {"month_over": month_over, "recheck_day": recheck_day.isoformat(),
                     "filing_deadline": filing_deadline.isoformat(),
                     "days_to_deadline": (filing_deadline - today).days},
        "documents": len(docs),
    }


def compare_draft(plan_: dict, draft: dict) -> dict:
    """Rami's draft return vs our numbers, line by line (all in VAT terms)."""
    ours = {"sales_vat": plan_["sales"]["vat"], "purchases_vat": plan_["purchases"]["vat"],
            "imports_vat": plan_["imports"]["vat"], "credit_in": plan_["credit_in"],
            "payable": plan_["payable_now"]}
    rows, ok = [], True
    for k, v in ours.items():
        theirs = draft.get(k)
        diff = None if theirs is None else round(float(theirs) - v, 2)
        match = theirs is not None and abs(diff) < 1.0
        ok = ok and match
        rows.append({"field": k, "ours": round(v, 2), "draft": theirs, "diff": diff, "match": match})
    return {"match": ok, "rows": rows}


def package(plan_: dict) -> dict:
    """What goes to the return: the figures + the document lists behind them."""
    return {
        "entity": plan_["entity"], "month": plan_["month"],
        "figures": {"sales_net": plan_["sales"]["net"], "sales_vat": plan_["sales"]["vat"],
                    "sales_manufacturing_net": plan_["sales"]["net_m"], "sales_trading_net": plan_["sales"]["net_t"],
                    "purchases_net": plan_["purchases"]["net"], "purchases_vat": plan_["purchases"]["vat"],
                    "imports_base": plan_["imports"]["base"], "imports_vat": plan_["imports"]["vat"],
                    "credit_in": plan_["credit_in"], "payable": plan_["payable_now"],
                    "credit_out": plan_["credit_out_if_filed_now"]},
        "problems": plan_["problems"],
        "calendar": plan_["calendar"],
    }
