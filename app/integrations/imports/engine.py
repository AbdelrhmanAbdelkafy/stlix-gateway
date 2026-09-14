"""What the shipment file *says* — derived, never typed.

Everything on the screen that is not a fact somebody entered is computed here:
which step the shipment is actually on, whether the ACID survives the walk
across five documents, how many days of free time are left, what the demurrage
would come to, and what the landed cost per ton ended up being against what was
promised at purchase.

Two rules run through all of it:

* **No invented number.** A rate that was never entered — a demurrage tariff, a
  duty percentage, an FX rate for a foreign-currency invoice — produces `None`
  and a sentence naming what is missing. It never produces a plausible default.
  A wrong landed cost is worse than no landed cost: nobody re-checks a figure
  that looks finished.
* **Evidence over clicks.** A step with an `auto` rule ticks itself from the
  file's own data. A person can still tick a step by hand (they may know
  something the record does not), and a manual tick is never undone by the
  engine — but an untouched step that the data already proves is shown as done,
  so the checklist stops being a record of who remembered to click.

Pure functions over dicts: no database, no settings, no network. That is what
lets `tests/test_imports.py` check the free-time arithmetic and the ACID walk
without a server.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import sop

ACID_LEN = 19
#: The SOP's own alert distance: تنبيه قبل نهاية الـ free time بـ 5 أيام.
FREE_TIME_WARN_DAYS = 5
#: خطوة 11: مظروف الـ ACI مرفوع قبل الشحن بـ 48 ساعة على الأقل.
ACI_LEAD_DAYS = 2


# --- dates -------------------------------------------------------------------
def _d(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


# --- ACID --------------------------------------------------------------------
def acid_valid(acid: str | None) -> bool:
    a = (acid or "").strip()
    return len(a) == ACID_LEN and a.isdigit()


def acid_check(shipment: dict, docs: list[dict]) -> dict:
    """Walk the ACID across every document that must carry it.

    Step 12 of SOP-IMP-001 is "المطابقة حرف بحرف", and the reason it is written
    that way is that the failure is one character long: a 19-digit number typed
    into a Chinese supplier's invoice template comes back with one digit
    transposed and the shipment stops in the port. So this does not answer
    "match / no match" — it answers *which position* differs, because that is
    what someone has to put in the email to the supplier.
    """
    acid = (shipment.get("acid") or "").strip()
    rows, mismatches = [], []
    for kind in sop.ACID_DOCS:
        doc = next((d for d in docs if d.get("kind") == kind), None)
        on_doc = (doc or {}).get("acid_on_doc") or ""
        on_doc = on_doc.strip()
        if doc is None:
            state, detail = "missing", "المستند لسه مستلمش"
        elif not on_doc:
            state, detail = "blank", "المستند موجود بس رقم الـ ACID مش متسجّل عليه"
        elif on_doc == acid:
            state, detail = "ok", ""
        else:
            state = "mismatch"
            detail = _diff(acid, on_doc)
            mismatches.append({"kind": kind, "label": sop.DOC_KINDS[kind]["label"],
                               "on_doc": on_doc, "detail": detail})
        rows.append({"kind": kind, "label": sop.DOC_KINDS[kind]["label"], "state": state,
                     "on_doc": on_doc, "detail": detail})
    valid = acid_valid(acid)
    checked = [r for r in rows if r["state"] in ("ok", "mismatch")]
    return {
        "acid": acid or None,
        "valid": valid,
        "format_note": None if valid else (
            "لسه مفيش رقم ACID" if not acid
            else f"الرقم {len(acid)} خانة — المفروض {ACID_LEN} رقم من نافذة"
            if not acid.isdigit() or len(acid) != ACID_LEN else None),
        "docs": rows,
        "mismatches": mismatches,
        "checked": len(checked),
        "expected": len(sop.ACID_DOCS),
        # The gate: valid number, nothing contradicting it, and at least the
        # invoice + packing + BL draft seen. "No mismatches" alone would pass a
        # file where no document has been looked at yet.
        "ok": bool(valid and not mismatches and len(checked) >= 3),
    }


def _diff(expected: str, got: str) -> str:
    if len(expected) != len(got):
        return f"الطول مختلف: عندنا {len(expected)} خانة وعلى المستند {len(got)}"
    bad = [i for i, (a, b) in enumerate(zip(expected, got)) if a != b]
    spots = "، ".join(f"خانة {i + 1}: {expected[i]} ← {got[i]}" for i in bad[:4])
    more = f" (و{len(bad) - 4} اختلاف كمان)" if len(bad) > 4 else ""
    return f"{len(bad)} خانة مختلفة — {spots}{more}"


# --- free time / demurrage ---------------------------------------------------
def clock(shipment: dict, containers: list[dict], today: date | None = None) -> dict:
    """The countdown the SOP asks to be "محدَّث يوميًا في ملف الشحنة"."""
    today = today or date.today()
    etd, eta, ata = _d(shipment.get("etd")), _d(shipment.get("eta")), _d(shipment.get("ata"))
    released = _d(shipment.get("released_at"))
    arrival = ata or eta
    free_days = shipment.get("free_days")
    start = _d(shipment.get("free_time_start")) or arrival
    end = start + timedelta(days=int(free_days)) if (start and free_days) else None

    # Days of demurrage: from the end of free time to the day the goods left the
    # port — or to today while they are still in it.
    stop = released or today
    over = (stop - end).days if end and stop > end else 0
    left = (end - today).days if end and not released else None

    tiers = shipment.get("demurrage_tariff") or []
    n_cont = int(shipment.get("containers") or len(containers) or 0)
    est, est_note = _demurrage(over, n_cont, tiers)

    return {
        "today": _iso(today), "etd": _iso(etd), "eta": _iso(eta), "ata": _iso(ata),
        "arrival": _iso(arrival), "released_at": _iso(released),
        "free_days": free_days, "free_time_start": _iso(start), "free_time_end": _iso(end),
        "days_to_arrival": (arrival - today).days if arrival and not ata else None,
        "days_left": left,
        "overdue_days": over,
        "state": ("released" if released else
                  "overdue" if over > 0 else
                  "warn" if left is not None and left <= FREE_TIME_WARN_DAYS else
                  "ok" if left is not None else "unset"),
        "aci_deadline": _iso(etd - timedelta(days=ACI_LEAD_DAYS)) if etd else None,
        "demurrage_estimate": est,
        "demurrage_note": est_note,
        "containers": n_cont,
        "detention": _detention(containers, today),
        "missing": [k for k, v in (("eta", arrival), ("free_days", free_days)) if not v],
    }


def _demurrage(days: int, containers: int, tiers: list[dict]) -> tuple[float | None, str]:
    """Tiered, per container per day — the way the lines actually bill it."""
    if days <= 0:
        return 0.0, ""
    if not tiers:
        return None, "تعريفة الأرضيات مش متحطة للشحنة دي — حطها من شرائح الخط عشان الرقم يطلع"
    if not containers:
        return None, "عدد الحاويات مش متسجّل"
    total = 0.0
    for day in range(1, days + 1):
        tier = next((t for t in tiers
                     if int(t.get("from", 1)) <= day <= int(t.get("to") or 10 ** 6)), None)
        if tier is None:
            return None, f"مفيش شريحة في التعريفة تغطي اليوم {day}"
        total += float(tier.get("rate") or 0)
    return round(total * containers, 2), ""


def _detention(containers: list[dict], today: date) -> dict:
    """Empties still out, and the deposits still with the line."""
    out = [c for c in containers if not c.get("returned_at")]
    late = [{"no": c.get("container_no"), "days": (today - _d(c.get("out_at"))).days}
            for c in out if _d(c.get("out_at")) and c.get("free_return_days")
            and (today - _d(c.get("out_at"))).days > int(c["free_return_days"])]
    held = [c for c in containers if c.get("deposit") and not c.get("deposit_back")]
    return {"total": len(containers), "returned": len(containers) - len(out),
            "outstanding": len(out), "late": late,
            "deposit_held": round(sum(float(c.get("deposit") or 0) for c in held), 2),
            "deposit_held_count": len(held)}


# --- landed cost -------------------------------------------------------------
def landed(shipment: dict, costs: list[dict]) -> dict:
    """CIF + everything that was actually paid, per ton, against the estimate.

    Nothing here is modelled: there is no duty rate and no VAT rate in the code,
    because both belong to the HS code on the day of the declaration and neither
    can be guessed from an item description. They arrive as cost rows with an
    invoice number behind them, like every other figure.
    """
    fx = shipment.get("fx_rate")
    cur = (shipment.get("currency") or "EGP").upper()
    fob, freight, ins = (_num(shipment.get(k)) for k in ("value_fob", "freight", "insurance"))
    cif_fc = None if fob is None else round(fob + (freight or 0) + (ins or 0), 2)
    cif = _to_egp(cif_fc, cur, fx)

    by_kind: dict[str, float] = {}
    unconverted, undocumented = [], []
    for c in costs:
        amount = _num(c.get("amount"))
        if amount is None:
            continue
        ccur = (c.get("currency") or "EGP").upper()
        egp = _to_egp(amount, ccur, fx)
        if egp is None:
            unconverted.append({"kind": c.get("kind"), "amount": amount, "currency": ccur})
            continue
        by_kind[c.get("kind") or "other"] = round(by_kind.get(c.get("kind") or "other", 0) + egp, 2)
        if not (c.get("invoice_no") or "").strip():
            undocumented.append({"id": c.get("id"), "kind": c.get("kind"), "amount": amount,
                                 "vendor": c.get("vendor")})

    extras = round(sum(by_kind.values()), 2)
    total = None if cif is None else round(cif + extras, 2)
    tons = _num(shipment.get("qty_ton"))
    per_ton = round(total / tons, 2) if (total is not None and tons) else None
    est = _num(shipment.get("est_landed_per_ton"))
    diff_pct = round((per_ton - est) / est * 100, 2) if (per_ton is not None and est) else None

    missing = []
    if cif is None:
        missing.append("قيمة البضاعة (أو سعر الصرف) مش متحطة" if cif_fc is not None
                       else "قيمة البضاعة FOB مش متحطة")
    if not tons:
        missing.append("الكمية بالطن مش متحطة — من غيرها مفيش تكلفة للطن")
    return {
        "currency": cur, "fx_rate": fx,
        "cif_fc": cif_fc, "cif": cif,
        "by_kind": [{"kind": k, "label": sop.COST_KINDS.get(k, k), "amount": v}
                    for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])],
        "extras": extras, "total": total,
        "qty_ton": tons, "per_ton": per_ton,
        "estimate_per_ton": est, "diff_pct": diff_pct,
        # المؤشر في الـ SOP: فرق الـ landed cost المقبول ±5%
        "within_tolerance": None if diff_pct is None else abs(diff_pct) <= 5,
        "undocumented": undocumented,
        "unconverted": unconverted,
        "missing": missing,
        "ready": total is not None and per_ton is not None and not undocumented,
    }


def _num(v):
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _to_egp(amount, currency: str, fx) -> float | None:
    if amount is None:
        return None
    if (currency or "EGP").upper() == "EGP":
        return round(float(amount), 2)
    rate = _num(fx)
    return None if not rate else round(float(amount) * rate, 2)


# --- steps -------------------------------------------------------------------
def resolve_steps(shipment: dict, saved: dict, docs: list[dict], costs: list[dict],
                  checklist: dict, ck: dict, cl: dict, lc: dict) -> list[dict]:
    """Every step with its state — manual first, then evidence, then pending."""
    ev = _evidence(shipment, docs, costs, checklist, ck, cl, lc)
    out = []
    for s in sop.ALL_STEPS:
        row = saved.get((s.sop, s.no), {})
        state = row.get("state") or ""
        auto_done = _auto(s.auto, ev) if s.auto else None
        if state in ("done", "na", "blocked"):
            source = "يدوي"
        elif auto_done is True:
            state, source = "done", "تلقائي"
        elif auto_done is False:
            state, source = "pending", "تلقائي"
        else:
            state, source = state or "pending", ""
        out.append({
            "sop": s.sop, "no": s.no, "phase": s.phase, "title": s.title, "owner": s.owner,
            "check": s.check, "gate": s.gate, "evidence": s.evidence, "auto": s.auto,
            "state": state, "source": source, "who": row.get("who") or "",
            "at": row.get("at"), "note": row.get("note") or "",
            "why": "" if state == "done" else _why(s.auto, ev),
        })
    return out


def _evidence(shipment: dict, docs: list[dict], costs: list[dict], checklist: dict,
              ck: dict, cl: dict, lc: dict) -> dict:
    have = {d.get("kind") for d in docs if d.get("received")}
    term = sop.PAYMENT_TERMS.get(shipment.get("payment_term") or "")
    crit = [c.key for c in sop.BL_CHECKLIST if c.critical]
    return {
        "s": shipment, "docs": have, "ck": ck, "cl": cl, "lc": lc,
        "checklist": checklist, "term": term,
        "checklist_done": all(checklist.get(c.key) == "ok" for c in sop.BL_CHECKLIST),
        "checklist_critical_done": all(checklist.get(k) == "ok" for k in crit),
        "costs": costs,
    }


def _auto(rule: str, ev: dict) -> bool | None:
    """Resolve one `auto` rule to done / not-done / unknown."""
    s, docs = ev["s"], ev["docs"]
    if rule.startswith("doc:"):
        return rule.split(":", 1)[1] in docs
    if "+" in rule:
        return all(_auto(r, ev) for r in rule.split("+"))
    match rule:
        case "acid_valid":
            return acid_valid(s.get("acid"))
        case "acid_match":
            return ev["ck"]["ok"]
        case "acid_on_bl":
            row = next((d for d in ev["ck"]["docs"] if d["kind"] in ("bl_final", "bl_draft")), None)
            return bool(row and row["state"] == "ok")
        case "nafeza_accepted":
            return bool(s.get("nafeza_accepted"))
        case "bl_checklist":
            return ev["checklist_done"]
        case "release_matrix":
            t = ev["term"]
            return bool(t and s.get("bl_type") in t["bl"])
        case "endorsed_if_lc":
            t = ev["term"]
            if not t:
                return None
            return True if not t["needs_endorsement"] else bool(s.get("endorsed"))
        case "telex_verified":
            return True if s.get("bl_type") != "telex" else bool(s.get("telex_verified"))
        case "doc_pack":
            return all(k in docs for k in sop.DOC_PACK)
        case "released_before_freetime":
            c = ev["cl"]
            return None if not c["released_at"] else c["overdue_days"] == 0
        case "containers_returned":
            d = ev["cl"]["detention"]
            return None if not d["total"] else d["outstanding"] == 0
        case "deposits_back":
            d = ev["cl"]["detention"]
            return None if not d["deposit_held_count"] and not d["total"] else d["deposit_held"] == 0
        case "costs_documented" | "line_costs_documented":
            return None if not ev["costs"] else not ev["lc"]["undocumented"]
        case "landed_ready":
            return ev["lc"]["ready"]
        case "weight_checked":
            return bool(s.get("weight_checked"))
        case "customs_declaration":
            return bool((s.get("customs_declaration") or "").strip())
        case _:
            # plain field rules: "hs_code", "eta", "po_code", "grn_code", ...
            parts = [p for p in rule.split("+") if p]
            return all(bool(str(s.get(p) or "").strip()) for p in parts) if parts else None


_WHY = {
    "acid_valid": "رقم ACID (19 رقم) لسه مش متسجّل",
    "acid_match": "الـ ACID لسه مش متطابق على كل المستندات",
    "acid_on_bl": "رقم الـ ACID مش متأكد على البوليصة",
    "nafeza_accepted": "قبول المظروف من نافذة لسه مش مسجّل",
    "bl_checklist": "checklist مسودة البوليصة لسه مش كاملة",
    "release_matrix": "نوع البوليصة مش مطابق لطريقة السداد",
    "endorsed_if_lc": "البوليصة لسه مش مُظهَّرة من البنك",
    "telex_verified": "التلكس لسه مش متأكد من وكيل الخط في مصر",
    "doc_pack": "حزمة المستندات ناقصة",
    "released_before_freetime": "الحاوية لسه ماخرجتش",
    "containers_returned": "فيه حاويات لسه ماترجعتش",
    "deposits_back": "تأمين الحاويات لسه مارجعش",
    "costs_documented": "فيه تكاليف من غير رقم فاتورة",
    "line_costs_documented": "فيه مصاريف خط من غير فاتورة",
    "landed_ready": "الـ landed cost لسه ناقصه بيانات",
    "weight_checked": "الوزن لسه ماتطابقش مع قائمة التعبئة",
    "customs_declaration": "رقم البيان الجمركي مش متسجّل",
    "hs_code": "الـ HS Code مش متحدد",
    "eta+free_days": "الـ ETA أو الـ free time مش متحطين",
    "po_code": "أمر الشراء مش مربوط",
    "incoterm+payment_term": "الـ Incoterm أو شروط السداد لسه مش متسجّلة على الملف",
    "payment_term": "طريقة السداد لسه مش متحددة",
    "broker": "المخلص الجمركي لسه مش متسجّل على الملف",
    "released_at": "الإفراج لسه مش مسجّل",
    "grn_code": "سند الاستلام المخزني مش مسجّل على نما",
}


def _why(rule: str, ev: dict) -> str:
    if rule.startswith("doc:"):
        return f"{sop.DOC_KINDS.get(rule.split(':', 1)[1], {}).get('label', rule)} لسه مستلمش"
    return _WHY.get(rule, "")


# --- phases, gates, progress -------------------------------------------------
def phases(steps: list[dict]) -> list[dict]:
    out = []
    for code, names in (("IMP-001", sop.PHASES_1), ("IMP-002", sop.PHASES_2)):
        for name in names:
            rows = [s for s in steps if s["sop"] == code and s["phase"] == name]
            done = [s for s in rows if s["state"] in ("done", "na")]
            open_gates = [s for s in rows if s["gate"] and s["state"] not in ("done", "na")]
            out.append({"sop": code, "phase": name, "total": len(rows), "done": len(done),
                        "gates_open": [{"no": g["no"], "title": g["title"], "why": g["why"],
                                        "owner": g["owner"]} for g in open_gates],
                        "state": "done" if len(done) == len(rows) else
                                 "blocked" if open_gates and done else
                                 "open" if done else "pending"})
    return out


def progress(steps: list[dict]) -> dict:
    done = sum(1 for s in steps if s["state"] in ("done", "na"))
    gates = [s for s in steps if s["gate"]]
    return {"steps": len(steps), "done": done,
            "pct": round(done / len(steps) * 100) if steps else 0,
            "gates": len(gates),
            "gates_done": sum(1 for s in gates if s["state"] in ("done", "na"))}


def next_action(steps: list[dict], phs: list[dict]) -> dict | None:
    """One thing. An open gate first — that is what the gates are for."""
    for s in steps:
        if s["gate"] and s["state"] not in ("done", "na"):
            return {"sop": s["sop"], "no": s["no"], "title": s["title"], "owner": s["owner"],
                    "why": s["why"] or s["check"], "gate": True}
    for s in steps:
        if s["state"] == "pending":
            return {"sop": s["sop"], "no": s["no"], "title": s["title"], "owner": s["owner"],
                    "why": s["why"] or s["check"], "gate": False}
    return None


# --- alerts ------------------------------------------------------------------
def alerts(shipment: dict, steps: list[dict], ck: dict, cl: dict, lc: dict,
           today: date | None = None) -> list[dict]:
    """Only things somebody has to act on, each with the action and the owner."""
    today = today or date.today()
    out: list[dict] = []

    def add(level, text, do, who, control=""):
        out.append({"level": level, "text": text, "do": do, "who": who, "control": control})

    if ck["mismatches"]:
        m = ck["mismatches"][0]
        add("critical", f"ACID مختلف على {m['label']} — {m['detail']}",
            "وقف الشحن وصحّح المستند مع المورد قبل الإبحار", "المسؤول الإداري", "acid_match")
    elif ck["format_note"]:
        add("warn", ck["format_note"], "سجّل الشحنة على نافذة واستخرج ACID",
            "المسؤول الإداري", "acid_match")

    if cl["state"] == "overdue":
        est = f" — أرضيات تقديرية {cl['demurrage_estimate']:,.0f} ج" if cl["demurrage_estimate"] else ""
        add("critical", f"الـ free time خلص من {cl['overdue_days']} يوم{est}",
            "اسحب الحاوية فورًا، واحصر الأرضيات بفاتورة الخط قبل أي صرف",
            "المسؤول الإداري + الحسابات", "free_time")
    elif cl["state"] == "warn":
        add("warn", f"فاضل {cl['days_left']} يوم على نهاية الـ free time ({cl['free_time_end']})",
            "تأكد إن إذن التسليم والبيان الجمركي جاهزين", "المسؤول الإداري", "free_time")
    elif cl["state"] == "unset" and cl["missing"]:
        add("info", "عدّاد الأرضيات مش شغال — " + " و".join(
            {"eta": "الـ ETA مش متحدد", "free_days": "أيام الـ free time مش متحطة"}[m]
            for m in cl["missing"]),
            "حط الـ ETA وعدد أيام السماح من الخط", "المسؤول الإداري", "free_time")

    if cl["aci_deadline"] and not shipment.get("nafeza_accepted"):
        left = (_d(cl["aci_deadline"]) - today).days
        if left <= 0:
            add("critical", "معاد رفع مظروف الـ ACI (قبل الشحن بـ 48 ساعة) عدّى والمظروف لسه مش مقبول",
                "تابع المورد على CargoX فورًا ووقف الشحن لحد القبول", "AMEXPRO + المسؤول الإداري")
        elif left <= 3:
            add("warn", f"فاضل {left} يوم على آخر معاد لرفع مظروف الـ ACI",
                "أكد إن المورد رفع المظروف وإن نافذة قبلته", "AMEXPRO")

    if lc["undocumented"]:
        total = sum(float(u["amount"]) for u in lc["undocumented"])
        add("critical", f"{len(lc['undocumented'])} بند تكلفة من غير رقم فاتورة (بإجمالي {total:,.0f})",
            "لا صرف إلا مقابل فاتورة أصلية من الجهة المُصدِرة", "الحسابات", "no_invoice_no_pay")
    if lc["unconverted"]:
        add("warn", f"{len(lc['unconverted'])} بند بعملة أجنبية من غير سعر صرف",
            "حط سعر الصرف في بيانات الشحنة عشان التكلفة تكتمل", "الحسابات")
    if lc["within_tolerance"] is False:
        add("warn", f"الـ landed cost للطن بيفرق {lc['diff_pct']:+.1f}% عن التقديري",
            "وثّق سبب الفرق قبل إقفال الملف", "الحسابات")

    d = cl["detention"]
    if d["late"]:
        add("warn", f"{len(d['late'])} حاوية فاتت معاد الإرجاع",
            "رجّع الحاويات واطلب إيصال لكل واحدة", "المخلص / النقل", "detention")
    if d["deposit_held"] and cl["released_at"]:
        add("info", f"تأمين حاويات لسه مع الخط: {d['deposit_held']:,.0f}",
            "تابع الرد وقيّده على الشحنة", "الحسابات")

    term = sop.PAYMENT_TERMS.get(shipment.get("payment_term") or "")
    if term and shipment.get("bl_type") and shipment["bl_type"] not in term["bl"]:
        add("critical", f"{term['label']} مع {sop.BL_TYPES.get(shipment['bl_type'], '؟')} — "
                        f"المفروض {term['bl_label']}",
            term["control"], "الحسابات + المسؤول الإداري", "final_vs_draft")
    if term and term["needs_endorsement"] and not shipment.get("endorsed") and cl["released_at"]:
        add("critical", "اتفرج على الشحنة والبوليصة مش مسجّل إنها مُظهَّرة من البنك",
            "راجع ملف البوليصة — الإفراج بدون تظهير مخالفة للإجراء", "الحسابات", "final_vs_draft")
    if shipment.get("bl_type") == "telex" and not shipment.get("telex_verified"):
        add("warn", "التلكس لسه مش متأكد من وكيل الخط في مصر",
            "التأكيد يبقى كتابي من الوكيل، مش لقطة شاشة من المورد", "المسؤول الإداري", "fake_telex")

    for s in steps:
        if s["gate"] and s["state"] == "blocked":
            add("critical", f"خطوة موقوفة: {s['title']}", s["note"] or s["check"], s["owner"])

    rank = {"critical": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda a: rank[a["level"]])


# --- the whole file ----------------------------------------------------------
def plan(shipment: dict, docs: list[dict], costs: list[dict], containers: list[dict],
         checklist: dict, saved_steps: dict, today: date | None = None) -> dict:
    ck = acid_check(shipment, docs)
    cl = clock(shipment, containers, today)
    lc = landed(shipment, costs)
    steps = resolve_steps(shipment, saved_steps, docs, costs, checklist, ck, cl, lc)
    phs = phases(steps)
    return {
        "shipment": shipment, "acid_check": ck, "clock": cl, "landed": lc,
        "steps": steps, "phases": phs, "progress": progress(steps),
        "next": next_action(steps, phs),
        "alerts": alerts(shipment, steps, ck, cl, lc, today),
        "documents": _doc_rows(docs), "costs": costs, "containers": containers,
        "checklist": [{"key": c.key, "label": c.label, "what": c.what, "critical": c.critical,
                       "state": checklist.get(c.key, "")} for c in sop.BL_CHECKLIST],
        "payment_term": sop.PAYMENT_TERMS.get(shipment.get("payment_term") or ""),
    }


def _doc_rows(docs: list[dict]) -> list[dict]:
    have = {d.get("kind"): d for d in docs}
    return [{"kind": k, "label": v["label"], "needs_acid": v["acid"], "in_pack": v["pack"],
             **{f: (have.get(k) or {}).get(f) for f in ("number", "acid_on_doc", "received", "note", "at")}}
            for k, v in sop.DOC_KINDS.items()]


# --- fleet KPIs (SOP-IMP-001 §11) -------------------------------------------
def kpis(plans: list[dict]) -> dict:
    """The four indicators the SOP names. Each says how many shipments it could
    measure, because an average over two closed files is not a KPI yet."""
    rel, dem, acc, land = [], [], [], []
    for p in plans:
        c, l = p["clock"], p["landed"]
        if c["arrival"] and c["released_at"]:
            rel.append((_d(c["released_at"]) - _d(c["arrival"])).days)
        if c["released_at"]:
            dem.append(c["overdue_days"])
            acc.append(1 if p["acid_check"]["ok"] and not p["acid_check"]["mismatches"] else 0)
        if l["diff_pct"] is not None:
            land.append(l["diff_pct"])
    return {
        "release_days": {"value": round(sum(rel) / len(rel), 1) if rel else None, "n": len(rel),
                         "label": "متوسط زمن الإفراج (يوم)", "target": "يُحدد بعد 3 شهور قياس"},
        "demurrage_days": {"value": round(sum(dem) / len(dem), 1) if dem else None, "n": len(dem),
                           "label": "متوسط أيام الأرضيات للشحنة", "target": "صفر"},
        "doc_accuracy": {"value": round(sum(acc) / len(acc) * 100) if acc else None, "n": len(acc),
                         "label": "دقة المستندات من أول مرة %", "target": "100%"},
        "landed_diff": {"value": round(sum(land) / len(land), 1) if land else None, "n": len(land),
                        "label": "متوسط فرق الـ landed cost %", "target": "±5%"},
    }
