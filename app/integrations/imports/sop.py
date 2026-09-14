"""SOP-IMP-001 / SOP-IMP-002 as data — the procedure the screen is built from.

The two SOPs are approved documents. Retyping their steps into a page means the
page and the document drift the moment one of them is edited, and nobody finds
out until a shipment is stuck in the port. So the steps live here once: the
screen renders them, the engine gates on them, `/api/v1/imports/sop` serves them,
and `tests/test_imports.py` fails if a step loses its owner or its checkpoint.

A step carries more than a title:

* `owner`   — who does it (the SOP's مسؤول column).
* `check`   — the checkpoint that proves it was done (نقطة تحقق).
* `gate`    — True when the next phase must not start before it closes. These
              are the steps whose failure costs money: the ACID match, نافذة's
              acceptance, the BL draft review, the telex verified with the line
              and not with the supplier.
* `auto`    — the evidence the engine can read for itself. A step with `auto`
              ticks from data (a valid ACID, a received document, a recorded
              weight), so the checklist reflects the file rather than who
              remembered to click. `auto` never *un*-ticks a manual "done":
              a person may know something the record does not.
* `sla`     — days from the anchor event by which the step should be closed,
              used for "متأخرة" rather than to invent a deadline.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    sop: str            # "IMP-001" | "IMP-002"
    no: int
    phase: str
    title: str
    owner: str
    check: str
    gate: bool = False
    auto: str = ""
    evidence: str = ""   # doc kind that proves it, when one exists
    sla: tuple[str, int] | None = None   # (anchor, days)


# --- SOP-IMP-001 — خطوات الاستيراد ------------------------------------------
P1_A = "أ — قبل الشراء"
P1_B = "ب — أمر الشراء والتمويل"
P1_C = "ج — ACI قبل الشحن"
P1_D = "د — الشحن والمستندات"
P1_E = "هـ — الإفراج والاستلام"
P1_F = "و — الإقفال المالي"

IMPORT_STEPS: tuple[Step, ...] = (
    Step("IMP-001", 1, P1_A, "تحديد الاحتياج والمواصفات (المقاس، السماكة، الدرجة، الكمية)",
         "المشتريات / المصنع", "مطابقة المواصفة مع حساب عرض الاستربس للمكنة"),
    Step("IMP-001", 2, P1_A, "تحديد الـ HS Code المتوقع للصنف", "المسؤول الإداري",
         "مراجعة الرسوم والقيود والاشتراطات على البند", auto="hs_code"),
    Step("IMP-001", 3, P1_A, "فحص اشتراطات GOEIC وأي جهة رقابية على الصنف", "المسؤول الإداري",
         "تأكيد إن الصنف مش محتاج موافقة مسبقة، أو استخراجها"),
    Step("IMP-001", 4, P1_A, "التأكد إن المورد مسجّل وموثق على CargoX", "AMEXPRO",
         "تأكيد كتابي من المورد بحالة التوثيق", gate=True),
    Step("IMP-001", 5, P1_A, "اعتماد العرض النهائي (سعر، Incoterm، مدة التوريد، شروط السداد)",
         "المدير", "العرض معتمد بإيميل — مش شفهي", gate=True, auto="incoterm+payment_term"),

    Step("IMP-001", 6, P1_B, "إصدار أمر الشراء على نما بالمواصفات والكميات المعتمدة",
         "المشتريات", "مطابقة الـ PO مع العرض المعتمد سطر بسطر", auto="po_code"),
    Step("IMP-001", 7, P1_B, "تحديد طريقة السداد وفتحها مع البنك", "الحسابات",
         "شروط الاعتماد مطابقة للـ PO ولشروط البوليصة المطلوبة", auto="payment_term"),
    Step("IMP-001", 8, P1_B, "استخراج نموذج التمويل من البنك وحفظ صورته في ملف الشحنة",
         "الحسابات", "رقم النموذج وتاريخه مسجلين", evidence="finance_form"),

    Step("IMP-001", 9, P1_C, "تسجيل الشحنة على نافذة واستخراج رقم ACID (19 رقم)",
         "المسؤول الإداري", "الرقم صادر ومحفوظ في ملف الشحنة", gate=True, auto="acid_valid"),
    Step("IMP-001", 10, P1_C, "إرسال ACID + بيانات الشركة للمورد كتابيًا", "المسؤول الإداري",
         "تأكيد استلام من المورد"),
    Step("IMP-001", 11, P1_C, "المورد يرفع مظروف ACI على CargoX ويكتب ACID على كل المستندات",
         "AMEXPRO تتابع", "مرفوع قبل الشحن بـ 48 ساعة على الأقل", gate=True,
         sla=("etd", -2)),
    Step("IMP-001", 12, P1_C, "مطابقة ACID على الفاتورة وقائمة التعبئة ومسودة البوليصة وشهادة المنشأ",
         "المسؤول الإداري + المدير", "أي اختلاف في رقم واحد = توقيف الشحنة. المطابقة حرف بحرف",
         gate=True, auto="acid_match"),
    Step("IMP-001", 13, P1_C, "تأكيد قبول المظروف من نافذة قبل إبحار الباخرة", "المسؤول الإداري",
         "حالة القبول مسجلة، ولو رُفض يتعمل تصحيح أو تظلم فورًا", gate=True,
         auto="nafeza_accepted", sla=("etd", 0)),

    Step("IMP-001", 14, P1_D, "مراجعة مسودة البوليصة قبل إصدارها", "المسؤول الإداري",
         "طبقًا لـ SOP-IMP-002 — المراجعة دي مش اختيارية", gate=True, auto="bl_checklist"),
    Step("IMP-001", 15, P1_D, "استلام حزمة المستندات (BL، فاتورة، تعبئة، منشأ، تحليل)",
         "المسؤول الإداري", "checklist مكتملة، والفاتورة قيمتها CIF واضحة", auto="doc_pack"),
    Step("IMP-001", 16, P1_D, "تتبع الباخرة وتحديد ETA وتسجيل بداية الـ free time",
         "المسؤول الإداري", "تاريخ نهاية الـ free time محسوب ومكتوب في ملف الشحنة",
         gate=True, auto="eta+free_days"),
    Step("IMP-001", 17, P1_D, "إخطار المخلص بالمستندات و ETA بتكليف مكتوب", "المسؤول الإداري",
         "التكليف محدد النطاق والرسوم المتوقعة", auto="broker"),

    Step("IMP-001", 18, P1_E, "إصدار إذن التسليم من الخط الملاحي", "المسؤول الإداري",
         "طبقًا لـ SOP-IMP-002", gate=True, evidence="delivery_order", auto="doc:delivery_order"),
    Step("IMP-001", 19, P1_E, "إعداد البيان الجمركي وسداد الضرائب والرسوم", "المخلص / الحسابات",
         "مطابقة القيمة والـ HS Code في البيان مع الفاتورة", gate=True, auto="customs_declaration"),
    Step("IMP-001", 20, P1_E, "الفحص والمعاينة (لو مطلوبة) والإفراج", "المخلص",
         "نتيجة الفحص مسجلة", auto="released_at"),
    Step("IMP-001", 21, P1_E, "النقل للمخزن والاستلام والوزن", "مسؤول المخزن",
         "مطابقة الوزن والعدد مع قائمة التعبئة، وتوثيق أي فرق بالصور في نفس اليوم",
         gate=True, auto="weight_checked"),
    Step("IMP-001", 22, P1_E, "فحص الجودة (الدرجة، السماكة، العيوب السطحية)", "المصنع",
         "شهادة التحليل مطابقة للمستلم فعليًا", evidence="coa"),
    Step("IMP-001", 23, P1_E, "إدخال سند الاستلام المخزني على نما", "مسؤول المخزن",
         "إعادة قراءة الرصيد بعد الإدخال للتأكد", gate=True, auto="grn_code"),

    Step("IMP-001", 24, P1_F, "تجميع كل فواتير الشحنة (نولون، تخليص، أرضيات، نقل، رسوم بنكية)",
         "الحسابات", "كل مبلغ له فاتورة أصلية باسم الشركة", auto="costs_documented"),
    Step("IMP-001", 25, P1_F, "تحميل تكاليف الاستلام الإضافية على الشحنة في نما", "الحسابات",
         "مطابقة إجمالي التكاليف المحمّلة مع الفواتير المجمعة", gate=True),
    Step("IMP-001", 26, P1_F, "مطابقة حساب المخلص وتسويته", "الحسابات",
         "كشف المخلص = مجموع الفواتير + أتعابه، بدون بنود بدون مستند"),
    Step("IMP-001", 27, P1_F, "حساب الـ landed cost النهائي للطن وتسجيله", "الحسابات",
         "مقارنته بالتقديري وقت الشراء وتوثيق سبب الفرق", gate=True, auto="landed_ready"),
    Step("IMP-001", 28, P1_F, "إقفال ملف الشحنة وأرشفته", "المسؤول الإداري",
         "الملف كامل بكل المستندات والمراسلات"),
)

# --- SOP-IMP-002 — بوليصة الشحن ---------------------------------------------
P2_A = "أ — مراجعة المسودة"
P2_B = "ب — الإصدار وطريقة الإفراج"
P2_C = "ج — استلام الحق في البوليصة"
P2_D = "د — إذن التسليم والإفراج"
P2_E = "هـ — بعد الإفراج"

BL_STEPS: tuple[Step, ...] = (
    Step("IMP-002", 1, P2_A, "استلام مسودة البوليصة من المورد أو وكيل الشحن",
         "AMEXPRO / المسؤول الإداري", "المسودة مستلمة قبل الإبحار", evidence="bl_draft",
         auto="doc:bl_draft", sla=("etd", 0)),
    Step("IMP-002", 2, P2_A, "مراجعة المسودة بندًا بندًا بالـ checklist", "المسؤول الإداري",
         "كل بند متأشر عليه مكتوبًا", gate=True, auto="bl_checklist"),
    Step("IMP-002", 3, P2_A, "إرسال التعديلات كتابيًا واستلام مسودة معدّلة", "المسؤول الإداري",
         "مراجعة النسخة المعدلة من الأول، مش الفرق بس"),
    Step("IMP-002", 4, P2_A, "الموافقة على الإصدار كتابيًا", "المدير / المسؤول الإداري",
         "الموافقة بإيميل محفوظ في ملف الشحنة", gate=True),

    Step("IMP-002", 5, P2_B, "تحديد نوع البوليصة والإفراج حسب طريقة السداد",
         "الحسابات + المسؤول الإداري", "مصفوفة طريقة السداد → نوع البوليصة", gate=True,
         auto="release_matrix"),
    Step("IMP-002", 6, P2_B, "استلام البوليصة النهائية (Final) وحفظها", "المسؤول الإداري",
         "مطابقة النهائية مع المسودة المعتمدة — بيحصل إن التعديل مش بيتنفذ",
         evidence="bl_final", auto="doc:bl_final"),
    Step("IMP-002", 7, P2_B, "تأكيد ظهور رقم ACID على البوليصة", "المسؤول الإداري",
         "الرقم مطابق حرف بحرف لرقم نافذة", gate=True, auto="acid_on_bl"),

    Step("IMP-002", 8, P2_C, "اعتماد/CAD: استلام المستندات من البنك بعد السداد أو القبول",
         "الحسابات", "البوليصة مُظهَّرة من البنك — بوليصة بدون تظهير مش صالحة للإفراج",
         gate=True, auto="endorsed_if_lc"),
    Step("IMP-002", 9, P2_C, "تحويل مباشر: استلام الأصول بالكوريير أو طلب Telex Release",
         "المسؤول الإداري", "رقم الكوريير متتبع، أو التلكس مؤكد"),
    Step("IMP-002", 10, P2_C, "التحقق من التلكس من الخط الملاحي مباشرة — مش من لقطة شاشة من المورد",
         "المسؤول الإداري", "تأكيد كتابي من وكيل الخط في مصر", gate=True, auto="telex_verified"),
    Step("IMP-002", 11, P2_C, "تظهير البوليصة من الشركة (لو مطلوب) بتوقيع المفوض والختم",
         "المسؤول الإداري", "المفوض بالتوقيع هو اللي وقّع فعلًا"),

    Step("IMP-002", 12, P2_D, "تقديم الأصول (أو التلكس) لوكيل الخط الملاحي في مصر",
         "المسؤول الإداري", "إيصال استلام الأصول من الوكيل", gate=True),
    Step("IMP-002", 13, P2_D, "سداد مصاريف الخط (خدمات، تأمين حاويات، أي مستحقات)", "الحسابات",
         "كل مبلغ بفاتورة من الخط باسم الشركة", auto="line_costs_documented"),
    Step("IMP-002", 14, P2_D, "استخراج إذن التسليم وتسليمه للمخلص", "المسؤول الإداري",
         "تاريخ الإذن ومدة صلاحيته مسجلين", gate=True, evidence="delivery_order",
         auto="doc:delivery_order"),
    Step("IMP-002", 15, P2_D, "متابعة سحب الحاوية قبل نهاية الـ free time", "المسؤول الإداري",
         "عدّاد الأيام محدَّث يوميًا في ملف الشحنة", gate=True, auto="released_before_freetime"),

    Step("IMP-002", 16, P2_E, "إرجاع الحاويات الفاضية في الموعد", "المخلص / النقل",
         "إيصال الإرجاع لكل حاوية", auto="containers_returned"),
    Step("IMP-002", 17, P2_E, "متابعة رد تأمين الحاويات من الخط", "الحسابات",
         "المبلغ مرتجع فعلًا ومقيد على الشحنة", auto="deposits_back"),
    Step("IMP-002", 18, P2_E, "أرشفة البوليصة وكل مرفقاتها في ملف الشحنة", "المسؤول الإداري",
         "الملف كامل: المسودة، النهائية، التظهير، الإذن، إيصالات الإرجاع"),
)

ALL_STEPS: tuple[Step, ...] = IMPORT_STEPS + BL_STEPS
BY_KEY: dict[tuple[str, int], Step] = {(s.sop, s.no): s for s in ALL_STEPS}

PHASES_1: tuple[str, ...] = (P1_A, P1_B, P1_C, P1_D, P1_E, P1_F)
PHASES_2: tuple[str, ...] = (P2_A, P2_B, P2_C, P2_D, P2_E)


# --- checklist مراجعة مسودة البوليصة (SOP-IMP-002 §8) ------------------------
@dataclass(frozen=True)
class Check:
    key: str
    label: str
    what: str
    critical: bool = False


BL_CHECKLIST: tuple[Check, ...] = (
    Check("shipper", "Shipper", "اسم وعنوان المورد مطابق للفاتورة"),
    Check("consignee", "Consignee", "الكيان القانوني الصح باسمه الرسمي بالكامل — أخطر خانة عندنا بسبب وجود أكتر من كيان", True),
    Check("notify", "Notify Party", "بيانات الشركة أو المخلص بإيميل وتليفون شغالين"),
    Check("acid", "ACID", "ظاهر وصحيح، 19 رقم، مطابق لنافذة", True),
    Check("goods", "وصف البضاعة", "مطابق للفاتورة وللـ HS Code — مش وصف عام", True),
    Check("weight", "الوزن والعدد", "مطابق لقائمة التعبئة (Gross / Net / عدد الطرود)"),
    Check("containers", "أرقام الحاويات والسيل", "مطابقة لقائمة التعبئة"),
    Check("ports", "ميناء الشحن والتفريغ", "صحيحين، والتفريغ هو الميناء المخطط له فعلًا", True),
    Check("freight", "Freight Prepaid / Collect", "مطابق للـ Incoterm المتفق عليه"),
    Check("originals", "عدد الأصول الصادرة", "معروف ومسجل (عادة 3)"),
    Check("onboard", "تاريخ الشحن (On Board)", "مطابق لشروط الاعتماد المستندي لو فيه اعتماد"),
    Check("bl_kind", "نوع البوليصة", "Master ولا House — وواضح مين المُصدِر"),
)

# --- مصفوفة طريقة السداد → نوع البوليصة (SOP-IMP-002 §9) ---------------------
PAYMENT_TERMS: dict[str, dict] = {
    "LC": {"label": "اعتماد مستندي (LC)", "bl": ("original",),
           "bl_label": "Original BL to order، مُظهَّرة من البنك",
           "control": "مايتمش أي إفراج قبل استلام المستندات من البنك", "needs_endorsement": True},
    "CAD": {"label": "مستندات مقابل الدفع (CAD)", "bl": ("original",),
            "bl_label": "Original BL",
            "control": "البنك مبيسلّمش المستندات إلا بعد السداد", "needs_endorsement": True},
    "TT100": {"label": "تحويل مقدم كامل (TT 100%)", "bl": ("seawaybill", "telex"),
              "bl_label": "Sea Waybill أو Telex Release",
              "control": "الأسرع والأقل أرضيات، وبيُستخدم مع مورد موثوق بس", "needs_endorsement": False},
    "TT_PARTIAL": {"label": "تحويل جزئي / رصيد مفتوح", "bl": ("original",),
                   "bl_label": "Original BL",
                   "control": "البوليصة هي ضمانك، مايتمش تلكس قبل استكمال السداد",
                   "needs_endorsement": False},
}

BL_TYPES = {"original": "Original BL", "seawaybill": "Sea Waybill", "telex": "Telex Release"}

# --- الضوابط الرقابية (SOP-IMP-001 §8 + SOP-IMP-002 §10) ---------------------
CONTROLS: tuple[dict, ...] = (
    {"key": "acid_match", "risk": "رفض الشحنة أو توقيفها بسبب اختلاف ACID",
     "control": "مطابقة الرقم على كل مستند قبل الإبحار (خطوة 12)", "who": "المسؤول الإداري + المدير"},
    {"key": "free_time", "risk": "أرضيات بسبب تأخر المستندات",
     "control": "تاريخ نهاية الـ free time مكتوب في الملف، وتنبيه قبلها بـ 5 أيام", "who": "المسؤول الإداري"},
    {"key": "no_invoice_no_pay", "risk": "صرف مبالغ للمخلص أو الخط بدون مستند",
     "control": "لا صرف إلا مقابل فاتورة أصلية من الجهة المُصدِرة", "who": "الحسابات"},
    {"key": "declaration_match", "risk": "تلاعب في قيمة أو وصف البضاعة في البيان",
     "control": "مطابقة البيان الجمركي مع الفاتورة والـ HS Code قبل التقديم", "who": "المسؤول الإداري"},
    {"key": "wrong_entity", "risk": "تحميل تكاليف على الكيان القانوني الغلط",
     "control": "الكيان المستورد محدد قبل إصدار أي مستند، والاسم مطابق على البوليصة والفاتورة",
     "who": "الحسابات"},
    {"key": "weight_late", "risk": "فرق وزن أو مواصفة تُكتشف متأخر",
     "control": "الوزن والفحص في نفس يوم الاستلام مع صور", "who": "مسؤول المخزن"},
    {"key": "fake_telex", "risk": "تلكس مزيف أو غير مؤكد",
     "control": "التأكيد من وكيل الخط في مصر كتابيًا، مش من المورد", "who": "المسؤول الإداري"},
    {"key": "final_vs_draft", "risk": "البوليصة النهائية مختلفة عن المعتمدة",
     "control": "مطابقة النهائية بالكامل قبل السداد", "who": "المسؤول الإداري"},
    {"key": "detention", "risk": "detention بسبب تأخر إرجاع الحاويات",
     "control": "إيصال إرجاع لكل حاوية + متابعة بعد الإفراج", "who": "الحسابات"},
)

# --- الحالات الاستثنائية ------------------------------------------------------
EXCEPTIONS: tuple[dict, ...] = (
    {"case": "رفض مظروف ACI من نافذة",
     "do": "تصحيح البيانات وإعادة الرفع فورًا، أو تقديم تظلم — وإبلاغ المورد بوقف الشحن لحد الحل"},
    {"case": "المورد مش موثق على CargoX",
     "do": "وقف الشحن. التوثيق شرط، والبديل الوحيد هو تفويض وكيل الشحن لو النوع بيسمح"},
    {"case": "تأخير في وصول أصل البوليصة",
     "do": "طلب Telex Release قبل بداية الأرضيات مش بعدها"},
    {"case": "أرضيات مستحقة",
     "do": "حصر المبلغ بفاتورة الخط، حسابه مستقل، اعتماد مكتوب قبل الصرف، وتحليل السبب بعد الإفراج"},
    {"case": "فرق في الوزن أو المواصفة",
     "do": "إخطار المورد كتابيًا خلال المدة المسموحة في العقد مع الصور وشهادة الوزن"},
    {"case": "فقدان أصل البوليصة",
     "do": "إخطار الخط فورًا — الإفراج بيحتاج ضمان بنكي أو تعويض حسب سياسة الخط، والحالة تُعرض على المدير مباشرة"},
    {"case": "البوليصة وصلت بدون تظهير البنك",
     "do": "ترجع للبنك للتظهير، وممنوع أي محاولة إفراج بدونه"},
    {"case": "تعديل مطلوب بعد الإصدار (Switch/Amendment)",
     "do": "يطلب من المُصدِر عبر الخط، بمصاريف تعديل معتمدة مسبقًا"},
    {"case": "تغيير ميناء التفريغ",
     "do": "إخطار الخط والمخلص كتابيًا وإعادة مراجعة ACI"},
)

# --- المستندات اللي بتتطلب في الملف -----------------------------------------
DOC_KINDS: dict[str, dict] = {
    "invoice": {"label": "الفاتورة التجارية", "acid": True, "pack": True},
    "packing": {"label": "قائمة التعبئة", "acid": True, "pack": True},
    "bl_draft": {"label": "مسودة البوليصة", "acid": True, "pack": False},
    "bl_final": {"label": "البوليصة النهائية", "acid": True, "pack": True},
    "coo": {"label": "شهادة المنشأ", "acid": True, "pack": True},
    "coa": {"label": "شهادة التحليل", "acid": False, "pack": True},
    "nafeza": {"label": "إقرار نافذة (ACID)", "acid": True, "pack": False},
    "finance_form": {"label": "نموذج التمويل البنكي", "acid": False, "pack": False},
    "delivery_order": {"label": "إذن التسليم", "acid": False, "pack": False},
    "customs": {"label": "البيان الجمركي", "acid": True, "pack": False},
    "weight_note": {"label": "شهادة/تذكرة وزن", "acid": False, "pack": False},
    "endorsement": {"label": "تظهير البنك", "acid": False, "pack": False},
}

#: المستندات اللي لازم تكون في الحزمة قبل ما نخطر المخلص (خطوة 15).
DOC_PACK = tuple(k for k, v in DOC_KINDS.items() if v["pack"])
#: المستندات اللي المفروض رقم الـ ACID يبان عليها ويتطابق (خطوة 12).
ACID_DOCS = tuple(k for k, v in DOC_KINDS.items() if v["acid"])

# --- بنود التكلفة اللي بتكوّن الـ landed cost --------------------------------
COST_KINDS: dict[str, str] = {
    "freight": "نولون",
    "insurance": "تأمين",
    "duty": "ضريبة جمركية",
    "vat": "ض.ق.م على الاستيراد",
    "clearance": "أتعاب تخليص",
    "port": "مصاريف ميناء وخط ملاحي",
    "demurrage": "أرضيات",
    "detention": "غرامة تأخير حاويات",
    "inland": "نقل داخلي",
    "bank": "رسوم بنكية",
    "other": "أخرى",
}

#: بنود لازم يكون وراها فاتورة أصلية باسم الشركة — الضابط `no_invoice_no_pay`.
COSTS_NEED_INVOICE = tuple(COST_KINDS)

GLOSSARY: tuple[dict, ...] = (
    {"term": "ACI", "means": "Advance Cargo Information — الإفصاح المسبق عن البضائع، إلزامي للشحن البحري لمصر"},
    {"term": "نافذة", "means": "منصة المستورد المصري لتسجيل الشحنة واستخراج رقم ACID"},
    {"term": "CargoX", "means": "المنصة اللي المُصدِّر الأجنبي بيسجل عليها ويرفع منها مظروف مستندات الـ ACI"},
    {"term": "ACID", "means": "رقم إقرار الشحنة المسبق — 19 رقم، بيتولد من نافذة"},
    {"term": "CIF", "means": "قيمة البضاعة + الشحن + التأمين — أساس حساب الضريبة الجمركية في مصر"},
    {"term": "Free time", "means": "فترة السماح المجانية لبقاء الحاوية قبل بداية الأرضيات"},
    {"term": "Demurrage", "means": "أرضيات — الحاوية لسه جوه الميناء بعد انتهاء الـ free time"},
    {"term": "Detention", "means": "غرامة تأخير — الحاوية خرجت ومترجعتش فاضية في الموعد"},
    {"term": "Telex Release", "means": "إخطار من وكيل ميناء الشحن بأن الأصول اتسلمت منه، فيُفرج بدون تقديم أصل"},
    {"term": "Landed cost", "means": "التكلفة الفعلية للخامة بعد تحميل الشحن والتخليص والنقل"},
)


def as_dict() -> dict:
    """The whole procedure, for `/api/v1/imports/sop` and for the page."""
    return {
        "sops": [
            {"code": "SOP-IMP-001", "title": "خطوات الاستيراد", "phases": list(PHASES_1),
             "steps": [_step(s) for s in IMPORT_STEPS]},
            {"code": "SOP-IMP-002", "title": "خطوات بوليصة الشحن (BL)", "phases": list(PHASES_2),
             "steps": [_step(s) for s in BL_STEPS]},
        ],
        "bl_checklist": [{"key": c.key, "label": c.label, "what": c.what, "critical": c.critical}
                         for c in BL_CHECKLIST],
        "payment_terms": PAYMENT_TERMS,
        "bl_types": BL_TYPES,
        "controls": list(CONTROLS),
        "exceptions": list(EXCEPTIONS),
        "doc_kinds": DOC_KINDS,
        "cost_kinds": COST_KINDS,
        "glossary": list(GLOSSARY),
        "counts": {"steps": len(ALL_STEPS), "gates": sum(1 for s in ALL_STEPS if s.gate),
                   "checklist": len(BL_CHECKLIST), "controls": len(CONTROLS)},
    }


def _step(s: Step) -> dict:
    return {"sop": s.sop, "no": s.no, "phase": s.phase, "title": s.title, "owner": s.owner,
            "check": s.check, "gate": s.gate, "auto": s.auto, "evidence": s.evidence,
            "sla": list(s.sla) if s.sla else None}
