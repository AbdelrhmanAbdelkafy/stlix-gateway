"""ربط ملف الشحنة بموديول الشحن البحري في نما (LCShipment).

نما هي سجل الشحنة: الاعتماد المستندي، البوليصة، الحاويات، الموانئ، الخط الملاحي،
ومواعيد الإبحار والوصول كلها موجودة على `LCShipment` وبتتقفل بالمستندات. الهَب
مش بيكرّر الكلام ده — بيقرأه، وبيضيف فوقه الطبقة اللي نما مفيهاش: خطوات الـ SOP،
مطابقة الـ ACID، عدّاد الـ free time، والتنبيهات.

القاعدة: الحقول اللي في `store.NAMA_FIELDS` بتتكتب من هنا بس. حد يعدّلها من
الشاشة يبقى عندنا نسختين من الحقيقة، وده بالظبط اللي الربط ده بيمنعه. أي فرق بين
اللي عندنا واللي في نما بيتسجّل في الـ log وبيترد في نتيجة الـ sync، فالمستخدم
بيشوف إيه اللي اتغيّر مش بس إن فيه sync حصل.

نما بتقرا وتكتب التواريخ بصيغة DD-MM-YYYY؛ التحويل بيتعمل هنا مرة واحدة عشان باقي
الموديول يشوف ISO زي أي تاريخ تاني.
"""
from __future__ import annotations

from datetime import datetime

from ...config import Settings
from . import store

#: The Nama entity behind "الشحن البحري". Its lines (LCShipmentInvoiceLine) carry
#: the items, and LcExpenseShipmentLine links the LC expense documents to it.
ENTITY = "LCShipment"
LINE_ENTITY = "LCShipmentInvoiceLine"


def _date(value) -> str | None:
    """Nama's DD-MM-YYYY (or an ISO string) → ISO. Anything else → None."""
    if not value:
        return None
    text = str(value).strip()[:10]
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _ref(value, field: str = "name1") -> str | None:
    """A Nama reference comes back either nested or as a bare code."""
    if isinstance(value, dict):
        return value.get(field) or value.get("name2") or value.get("code")
    return str(value) if value else None


def _num(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def map_record(rec: dict) -> dict:
    """LCShipment → the shipment-file fields Nama owns. Pure, so it is testable."""
    return {
        "bl_no": rec.get("billOfLading") or None,
        "containers_no": rec.get("containerNumber") or None,
        "customs_declaration": rec.get("customDeclaration") or None,
        "etd": _date(rec.get("actualSailingDate") or rec.get("estimatedDateDeparture")),
        "eta": _date(rec.get("estimatedArrivalDate")),
        "ata": _date(rec.get("actualArrivalDate")),
        "docs_delivery_date": _date(rec.get("documentsDeliveryDate")),
        "store_delivery_date": _date(rec.get("storeDeliveryDate")),
        "transit_days": _num(rec.get("transitDays")),
        "value_fob": _num(rec.get("commercialInvoiceValue")),
        "currency": _ref(rec.get("currency"), "code") or None,
        "port_loading": _ref(rec.get("portOfLoading")),
        "port_discharge": _ref(rec.get("portOfDischarge")),
        "shipping_line": _ref(rec.get("shippingLine")) or rec.get("shippingLineCode") or None,
        "nama_state": rec.get("state") or None,
    }


def summary(rec: dict) -> dict:
    """One row for the "اربط بشحنة من نما" picker."""
    m = map_record(rec)
    return {"code": rec.get("code"), "name": rec.get("name1") or rec.get("description1") or "",
            "bl_no": m["bl_no"], "eta": m["eta"], "ata": m["ata"], "state": m["nama_state"],
            "port_discharge": m["port_discharge"], "shipping_line": m["shipping_line"],
            "lc": _ref(rec.get("letterOfCredit"), "code")}


async def candidates(settings: Settings, limit: int = 100) -> dict:
    """Sea shipments in Nama, newest first — what a file can be linked to."""
    if not settings.nama_configured:
        return {"ok": False, "error": "مفاتيح نما مش متحطة في .env", "rows": []}
    from ..nama.client import NamaClient
    data = await NamaClient(settings).list_query(ENTITY, page_size=min(limit, 1000),
                                                 order_by="code desc")
    rows = (data.get("records") or {}).get(ENTITY) or []
    return {"ok": True, "count": len(rows), "rows": [summary(r) for r in rows]}


async def fetch(settings: Settings, code: str) -> dict:
    from ..nama.client import NamaClient
    data = await NamaClient(settings).find(ENTITY, code)
    rows = (data.get("records") or {}).get(ENTITY) or []
    if not rows:
        raise KeyError(code)
    return rows[0]


async def sync(ref: str, settings: Settings, who: str = "", code: str | None = None) -> dict:
    """Pull the linked LCShipment and write the fields Nama owns.

    Returns what changed rather than just "ok": a sync that silently rewrites the
    ETA under a countdown somebody is watching is worse than no sync.
    """
    shipment = store.get(ref)
    if shipment is None:
        raise KeyError(ref)
    code = code or shipment.get("nama_code")
    if not code:
        return {"ok": False, "error": "ملف الشحنة مش مربوط بشحنة في نما"}
    if not settings.nama_configured:
        return {"ok": False, "error": "مفاتيح نما مش متحطة في .env"}
    try:
        rec = await fetch(settings, code)
    except KeyError:
        return {"ok": False, "error": f"مفيش شحنة بالكود {code} في نما"}

    mapped = {k: v for k, v in map_record(rec).items() if v is not None}
    changed = [{"field": k, "was": shipment.get(k), "now": v}
               for k, v in mapped.items() if str(shipment.get(k) or "") != str(v)]
    if changed:
        store.update(ref, mapped, who=who or "nama-sync", source="nama")
    store.mark_synced(ref)
    return {"ok": True, "code": code, "changed": changed, "fields": len(mapped),
            "note": "" if changed else "مفيش فرق — الملف متطابق مع نما"}


async def create_from_nama(code: str, settings: Settings, who: str = "", **extra) -> dict:
    """Open a shipment file straight from a Nama LCShipment — no double entry."""
    rec = await fetch(settings, code)
    fields = {k: v for k, v in map_record(rec).items() if v is not None}
    fields.update({k: v for k, v in extra.items() if v not in (None, "")})
    fields["nama_code"] = code
    fields.setdefault("goods", rec.get("name1") or rec.get("description1") or "")
    # containerNumber is one text field in Nama; the count is what the countdown
    # needs, and a text field cannot be counted reliably — so it stays unset
    # until somebody enters the containers, rather than being guessed.
    return store.create(fields, who=who)


async def pull_expenses(ref: str, settings: Settings, who: str = "") -> dict:
    """Best-effort: the LC expense lines Nama already holds for this shipment.

    Nama's expense documents differ between installations, so this never claims
    a total. It either finds lines and reports what it added, or says the entity
    is not readable with this credential and leaves the costs as they are —
    it does not fall back to an estimate.
    """
    shipment = store.get(ref)
    if shipment is None:
        raise KeyError(ref)
    code = shipment.get("nama_code")
    if not code:
        return {"ok": False, "error": "الملف مش مربوط بشحنة في نما"}
    if not settings.nama_configured:
        return {"ok": False, "error": "مفاتيح نما مش متحطة في .env"}
    from ...core.errors import UpstreamError
    from ..nama.client import NamaClient
    client = NamaClient(settings)
    try:
        data = await client.list_query("LcExpenseShipmentLine", page_size=200,
                                       text_criteria=f"lcShipment.code,Equal,{code},And;")
    except UpstreamError as exc:
        return {"ok": False, "error": f"مصاريف الاعتماد مش مقروءة من نما: {exc}", "added": 0}
    rows = (data.get("records") or {}).get("LcExpenseShipmentLine") or []
    return {"ok": True, "found": len(rows), "added": 0,
            "note": "الأسطر دي بتربط مستندات مصاريف الاعتماد بالشحنة — التحميل على الملف "
                    "بيتعمل من شاشة التكاليف بعد مراجعة الفواتير (ضابط: لا صرف بدون فاتورة أصلية)",
            "rows": [{"expense_doc": (r.get("lcExpenseDocument") or {}).get("code")
                      if isinstance(r.get("lcExpenseDocument"), dict) else r.get("lcExpenseDocument"),
                      "line": r.get("lineNumber")} for r in rows[:50]]}
