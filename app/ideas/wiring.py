"""Where each requirement in BACKLOG.md actually lands in the platform.

`BACKLOG.md` says WHAT the owner asked for. This says, for each of those
rows, WHERE it belongs: which company system owns it, which live endpoints
already hold its raw data, which workspace section would surface it, and —
in one Arabic clause — what is still missing before it can be built.

Two layers, on purpose:

- `WIRING` is explicit, one row per backlog id. The mapping is a judgement
  call per idea (does a cheque report read Nama REST or the SQL balances?),
  so it is written down rather than guessed at runtime.
- `DOMAIN_DEFAULTS` catches anything `WIRING` has not seen. Add a row to
  BACKLOG.md and it still lands somewhere sensible with no code change —
  it just inherits its domain's systems instead of a bespoke answer.

Invariants (locked by `tests/test_wiring.py`, which will fail rather than
let this rot):

- every system named here is a key in `registry.SYSTEMS`;
- every endpoint named here is a real route, via `catalog.paths()`;
- **no endpoint here is ever a deliverable.** These are data sources: the
  raw rows a report would be built from. A planned idea linking to a built
  page would claim work nobody has done, so pages are excluded outright.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import catalog
from ..registry import SYSTEMS


# Short aliases so a wiring row fits on one line and stays scannable.
_EP = {
    "nama": "/api/v1/nama/lists/{entity}",
    "emp": "/api/v1/nama/employees",
    "emp1": "/api/v1/nama/employees/{code}",
    "ent1": "/api/v1/nama/{entity}/{code}",
    "dup": "/api/v1/nama/invitem/exists",
    "crm": "/api/v1/crm/{module}",
    "acc": "/api/v1/crm/accounts",
    "lead": "/api/v1/crm/leads",
    "cont": "/api/v1/crm/contacts",
    "bank": "/api/v1/banks",
    "bankm": "/api/v1/banks/master",
    "inv": "/api/v1/inventory",
    "invc": "/api/v1/inventory/counts",
    "invm": "/api/v1/inventory/manual",
    "kpi": "/api/v1/finance/kpis",
    "ar": "/api/v1/finance/customers",
    "ap": "/api/v1/finance/suppliers",
    "ws": "/api/v1/workspace",
    "sys": "/systems",
    "map": "/api/v1/map",
    "repc": "/api/v1/rep/custody",
    "repm": "/api/v1/rep/movement",
    "repd": "/api/v1/rep/documents",
    "repo": "/api/v1/rep/overview",
}


@dataclass(frozen=True)
class Wire:
    """One idea's place in the platform."""

    systems: tuple[str, ...]      # registry.SYSTEMS keys, most responsible first
    section: str                  # workspace section that would surface it
    endpoints: tuple[str, ...]    # live routes holding its raw data (never a report)
    needs: str                    # the one missing thing, in Arabic, for the card
    proposed_system: str = ""     # a system worth adding that is not on the map yet

    @property
    def primary(self) -> str:
        return self.systems[0]


def _w(systems: str, section: str, endpoints: str, needs: str, proposed: str = '') -> Wire:
    """Space-separated shorthand: `_w("nama crm", "nama", "kpi ar", "…")`."""
    return Wire(
        tuple(systems.split()),
        section,
        tuple(_EP[a] for a in endpoints.split()),
        needs,
        proposed,
    )


# What a new BACKLOG.md row inherits when it has no explicit wiring below.
DOMAIN_DEFAULTS: dict[str, Wire] = {
    "A": _w("ai nama crm banks inventory attendance", "overview", "", ""),  # Platform & AI
    "AC": _w("archive nama", "nama", "", ""),  # شؤون إدارية وامتثال
    "AT": _w("attendance nama", "nama", "", ""),  # حضور وبصمة
    "CM": _w("crm", "overview", "", ""),  # تواصل
    "FL": _w("nama movement", "nama", "", ""),  # أسطول / سيارات
    "G": _w("archive regulations", "ideas", "", ""),  # إدارة وتخطيط
    "GV": _w("nama crm", "overview", "", ""),  # حوكمة وقوائم حظر
    "H": _w("nama", "nama", "", ""),  # موارد بشرية
    "I": _w("nama", "nama", "", ""),  # استثمارات ومساهمات
    "IT": _w("custody nama", "nama", "", ""),  # أصول تقنية
    "L": _w("archive", "ideas", "", ""),  # قانوني
    "LG": _w("nama movement", "nama", "", ""),  # شحن وجمارك
    "M": _w("nama", "nama", "", ""),  # صيانة
    "MD": _w("marketdata", "overview", "", ""),  # بيانات السوق والأسعار
    "MK": _w("crm", "crm", "", ""),  # تسويق
    "OP": _w("nama", "nama", "", ""),  # عمليات وإنتاج
    "P": _w("nama", "nama", "", ""),  # مشتريات وخامات
    "PA": _w("idp", "overview", "", ""),  # منصّة وصلاحيات — عابر للمنصّة كلها
    "PD": _w("nama", "nama", "", ""),  # منتجات وتطوير
    "Q": _w("nama archive", "ideas", "", ""),  # جودة / QC
    "S": _w("nama", "nama", "", ""),  # مبيعات وتحصيل
    "SF": _w("nama", "nama", "", ""),  # السلامة
    "T": _w("nama", "nama", "", ""),  # خزينة ومالية
    "TR": _w("movement", "ideas", "", ""),  # سفر — خاص بالمالك
    "UX": _w("nama", "overview", "", ""),  # تجربة الاستخدام والإدخال — عابر لكل الموديولات
    "WH": _w("nama", "inventory", "", ""),  # مخازن ومخزون
}


# The populated map: every id in BACKLOG.md, grouped as the backlog groups them.
WIRING: dict[str, Wire] = {
    # --- Sales & Collection · مبيعات وتحصيل ---------------
    "S1": _w("nama", "nama", "kpi ar", "خطة مبيعات وحقل نقدي/آجل على الفاتورة"),
    "S2": _w("nama", "nama", "ar", "تقرير تحصيل بالتاريخ وهدف تحصيل يومي"),
    "S3": _w("nama crm", "nama", "nama acc", "تقرير SQL للمبيعات لكل مندوب"),
    "S4": _w("crm nama", "crm", "acc ar", "تقرير عملاء واقفين بربط Vtiger بآخر تاريخ فاتورة"),
    "S5": _w("crm", "crm", "lead", "حقل الدولة/الشريحة على leads في Vtiger"),
    "S6": _w("nama", "nama", "ar kpi", "تواريخ استحقاق وأعمار ديون على المديونيات"),
    "S7": _w("nama", "nama", "nama", "تقرير SQL للمبيعات لكل فرع"),
    "S8": _w("nama", "nama", "nama", "تقرير SQL للمبيعات لكل مندوب"),
    "S9": _w("crm nama", "crm", "acc lead", "تقرير عملاء جدد بتاريخ الإنشاء والمصدر في Vtiger"),
    "S10": _w("crm nama", "crm", "acc ar", "قاعدة تسرّب عملاء على lastInvoiceDate"),
    "S11": _w("nama", "nama", "nama", "تقرير SQL بتكلفة بند الفاتورة COGS"),
    "S12": _w("nama", "nama", "nama", "تقرير SQL على بنود SalesInvoice"),
    "S13": _w("nama", "nama", "nama", "تكلفة البند ومبيعاته مجمّعة في تقرير SQL"),
    "S14": _w("crm nama", "crm", "lead acc", "حقل تحويل leads لحسابات في Vtiger"),
    "S15": _w("crm nama", "crm", "crm", "زيارات المندوبين متسجلة فعلاً في Vtiger"),
    "S16": _w("nama", "nama", "nama", "تقرير يربط SalesOrder بالتسليمات والفواتير"),
    "S17": _w("nama", "nama", "ar ap", "مفتاح يربط سجل العميل بسجل المورد"),
    "S18": _w("nama", "nama", "ar ap", "قاعدة مقاصة بين رصيد العميل والمورد"),
    "S19": _w("nama", "nama", "ap nama", "تاريخ أسعار الشراء لكل صنف وكل طرف"),
    "S20": _w("nama crm", "nama", "ar acc", "مفتاح يربط العميل بحساب Vtiger عشان النشاط"),
    "S21": _w("nama", "nama", "ar nama", "حقل المنطقة الجغرافية على ملف العميل"),
    "S22": _w("crm ai", "crm", "lead acc", "طبقة الذكاء AI"),
    "S23": _w("nama", "nama", "nama", "حقل تاريخ الاستحقاق على مستند الطلب وقاعدة الالتزام"),
    "S24": _w("nama", "nama", "", "سجل طلبات اعتمادنا عند العملاء — مش موجود", "registrations"),
    "S25": _w("nama", "nama", "nama", "كتالوج مطبوع من InvItem وخصائصه"),
    "S26": _w("nama inventory", "inventory", "nama invc", "مصدر رصيد مخزون لحظي — Nama REST مبيطلعش أرصدة"),
    "S27": _w("nama ai", "nama", "ar", "طبقة الذكاء AI لترتيب أولويات التحصيل"),
    # --- Purchasing & Materials · مشتريات وخامات ----------
    "P1": _w("nama", "nama", "nama", "حقل الأولوية على طلبات الشراء وتقرير عليها"),
    "P2": _w("nama", "nama", "nama emp", "تقرير على طلبات الخامات لكل طالب"),
    "P3": _w("nama crm", "nama", "", "سجل طلبات معاينة — مش موجود في أي نظام", "surveys"),
    "P4": _w("nama", "nama", "nama", "تقرير تاريخ أسعار من مستندات الشراء في Nama"),
    "P5": _w("nama", "nama", "ap nama", "محرك المطابقة Reconciliation وكشف حساب من المورد"),
    "P6": _w("nama", "nama", "ap", "تاريخ آخر مطابقة لكل مورد"),
    "P7": _w("nama", "nama", "nama", "سعر أقصى مستهدف لكل صنف"),
    "P8": _w("nama inventory ai", "nama", "nama invc", "طبقة الذكاء AI وتغذية استهلاك ورصيد مستمرة"),
    "P9": _w("nama", "nama", "ap nama", "حقل المنطقة الجغرافية على ملف المورد"),
    "P10": _w("nama", "nama", "nama ap", "محرك المطابقة Reconciliation بقاعدة مرتجعات الشراء"),
    "P11": _w("nama", "nama", "", "سجل طلبات اعتماد الموردين — مش موجود في أي نظام", "registrations"),
    "P12": _w("nama", "nama", "nama", "تقرير طلبات الشراء على كيان Stlix بس"),
    # --- Treasury & Finance · خزينة ومالية ----------------
    "T1": _w("banks nama", "banks", "bank", "استعلام SQL لأرصدة الحسابات من JournalEntryLine"),
    "T2": _w("nama", "banks", "nama", "تقرير على شيكات Nama — وارد وصادر"),
    "T3": _w("nama", "nama", "nama", "تقرير على سندات الضرايب والتأمينات في Nama"),
    "T4": _w("nama", "nama", "nama ap", "تقرير بالالتزامات الجاية — شيكات وأقساط ومستحقات موردين"),
    "T5": _w("nama", "nama", "nama", "حقل متكرر/مرة واحدة على فاتورة Nama وتقرير بمواعيدها"),
    "T6": _w("portal nama", "nama", "nama", "كونكتور بوابة الفاتورة الإلكترونية ETA — بره Nama"),
    "T7": _w("marketdata banks", "overview", "", "API أسعار صرف خارجي"),
    "T8": _w("nama", "nama", "nama", "تقرير على أقساط Nama ومواعيد سدادها"),
    "T9": _w("nama", "overview", "kpi", "استعلامات SQL لميزان المراجعة والأرباح والمركز المالي"),
    "T10": _w("nama", "overview", "", "سجل قرارات واعتمادات مالية — مش موجود في أي نظام", "decisions"),
    "T11": _w("banks nama", "banks", "bank nama", "كونكتور كشف حساب البنك — الطرف التاني للمطابقة"),
    "T12": _w("nama banks", "banks", "ar bank", "ربط الفاتورة ببنك التحصيل في تقرير SQL"),
    "T13": _w("nama", "nama", "ap nama", "استعلام SQL على JournalEntryLine بحسب مركز التكلفة"),
    "T14": _w("nama", "overview", "ar ap", "تواريخ استحقاق الفواتير في استعلامات SQL لأعمار الديون"),
    "T15": _w("nama", "overview", "kpi", "تقسيم التكاليف ثابت/متغير لكل كيان في SQL"),
    "T16": _w("nama", "nama", "nama", "تقرير على حسابات الزكاة والتبرعات وسنداتها"),
    "T17": _w("nama", "nama", "nama", "تصنيف أتعاب مهنية على المستفيدين غير الموظفين"),
    "T18": _w("nama ai", "nama", "ap", "طبقة الذكاء AI وتكاليف على مستوى بنود الفاتورة"),
    "T19": _w("nama", "nama", "nama", "استعلام SQL لأرصدة الحسابات الوسيطة المفتوحة"),
    "T20": _w("nama", "overview", "ap", "تواريخ استحقاق فواتير الموردين في استعلام SQL"),
    "T21": _w("nama banks", "overview", "ar ap", "استعلامات SQL على حركة الخزينة والبنك بالتاريخ"),
    "T22": _w("nama ai", "nama", "nama", "طبقة الذكاء AI وتغذية بقيود JournalEntryLine للتصنيف"),
    "T23": _w("nama", "nama", "nama", "حقل المراجع/المعتمد على الفاتورة في Nama"),
    "T24": _w("banks nama", "banks", "bank", "ربط كل عميل بحساب التحصيل المفضل في Nama"),
    "T25": _w("banks nama", "banks", "bank bankm", "مفيش ناقص — شغال من كونكتور banks"),
    "T26": _w("nama", "nama", "nama", "طبقة طباعة PDF لسندات القبض والصرف"),
    # --- Maintenance · صيانة ------------------------------
    "M1": _w("nama", "nama", "nama", "سجل أعطال المعدات — مش موجود في أي نظام", "maintenance"),
    "M2": _w("nama movement", "nama", "nama", "نظام صيانة بجدول وقائي لكل أصل — مش موجود", "maintenance"),
    "M3": _w("nama", "ideas", "", "أوامر شغل صيانة المباني — مش موجودة في أي نظام", "maintenance"),
    # --- Fleet · أسطول / سيارات ---------------------------
    "FL1": _w("nama movement", "nama", "nama", "تقرير SQL بتكلفة كل عربية من مستندات Nama"),
    "FL2": _w("nama movement", "nama", "nama", "تقرير SQL بتكلفة الوقود لكل عربية من Nama"),
    "FL3": _w("nama movement", "nama", "nama", "تقرير تكلفة صيانة لكل عربية من مستندات Nama", "maintenance"),
    # --- IT & Electronic Assets · أصول تقنية --------------
    "IT1": _w("custody nama", "nama", "nama", "كونكتور العهد يربط كل جهاز بموظفه"),
    # --- HR · موارد بشرية ---------------------------------
    "H1": _w("nama", "nama", "emp nama", "تقرير على مستندات إنهاء الخدمة في Nama"),
    "H2": _w("nama", "nama", "emp", "مخزن خطوات التعيين والإنهاء — Nama مفيهوش الكيان ده"),
    "H3": _w("nama academy", "nama", "nama", "كونكتور LMS للتدريب — نظام academy"),
    "H4": _w("archive", "ideas", "", "نماذج وتفويضات إلكترونية — مش موجودة في أي نظام", "forms"),
    "H5": _w("nama crm", "nama", "nama crm", "طلب توظيف في Nama وخط مرشحين على Vtiger"),
    "H6": _w("nama", "nama", "nama", "تقرير SQL لرصيد العهدة النقدية المفتوحة"),
    "H7": _w("nama", "nama", "nama", "تقرير SQL للمرتبات برصيد السلف المتبقي"),
    "H8": _w("nama", "nama", "nama emp", "تقرير على عقود الموظفين في Nama"),
    "H9": _w("nama attendance", "nama", "emp nama", "تقرير داخل وخارج بتواريخ التعيين وإنهاء الخدمة"),
    "H10": _w("nama", "nama", "nama", "محرك التجديدات Renewals على تاريخ نهاية العقد"),
    "H11": _w("nama", "nama", "nama", "تقرير SQL لإجمالي المرتبات — Nama REST مبيجمّعش"),
    "H12": _w("nama attendance", "nama", "nama", "تقرير يربط TimeAttendance بعناصر الأساسي والإضافي"),
    "H13": _w("nama", "nama", "emp nama", "حقل تصنيف إداري/عمالي وتقرير SQL للمرتبات"),
    "H14": _w("nama", "nama", "nama", "تقرير SQL للمرتبات بمركز التكلفة"),
    "H15": _w("nama meals housing", "nama", "nama", "تقرير SQL للمرتبات وكونكتور الوجبات والسكن"),
    "H16": _w("nama movement", "nama", "nama", "تقرير SQL لبدل الانتقالات في المرتبات"),
    "H17": _w("nama", "ideas", "", "سجل فعاليات الموظفين — مش موجود في أي نظام", "events"),
    "H18": _w("nama", "nama", "emp", "تقرير شرايح أعمار للموظفين — والمهام مش متسجلة"),
    "H19": _w("nama", "nama", "emp nama", "تقرير معدل الدوران بتواريخ التعيين والإنهاء"),
    "H20": _w("nama", "nama", "nama", "تقرير شهري على الجزاءات والخصومات في Nama"),
    "H21": _w("nama", "nama", "nama", "بيانات تقييم أداء متسجلة فعلاً في Nama"),
    "H22": _w("nama", "nama", "nama", "تقرير على مشاكل وشكاوى الموظفين في Nama"),
    # --- Marketing · تسويق --------------------------------
    "MK1": _w("website", "overview", "", "كونكتور السوشيال — Meta وLinkedIn وX", "social"),
    "MK2": _w("crm", "crm", "", "سجل معارض — مش موجود في أي نظام", "marketing"),
    "MK3": _w("crm", "crm", "", "مخزن استبيانات — Vtiger مفيهوش موديول استبيان"),
    "MK4": _w("crm", "crm", "", "سجل منافسين — مش موجود في Vtiger ولا Nama", "market-intel"),
    "MK5": _w("crm", "crm", "", "مصدر خارجي لأسعار المنافسين", "market-intel"),
    "MK6": _w("crm ai", "crm", "", "طبقة الذكاء AI ومصدر أخبار عن المنافسين", "market-intel"),
    "MK7": _w("website", "overview", "", "كونكتور تحليلات الموقع — GA4 أو Matomo"),
    # --- Investments / Equity · استثمارات ومساهمات --------
    "I1": _w("nama", "nama", "nama", "تقرير SQL لأرصدة حقوق الملكية والمساهمين"),
    # --- Warehouse & Inventory · مخازن ومخزون -------------
    "WH1": _w("nama", "inventory", "nama ent1", "تقرير على أذون الصرف والاستلام في Nama"),
    "WH2": _w("nama", "inventory", "nama", "تقرير على مرتجعات البيع والشراء في Nama"),
    "WH3": _w("nama inventory", "inventory", "nama inv", "محرك رصيد مخزون يضم مستندات Nama غير المرحّلة"),
    "WH4": _w("nama", "inventory", "nama", "تقرير آخر حركة وأعمار المخزون من مستندات Nama"),
    "WH5": _w("nama", "inventory", "nama", "تقرير يربط المرتجعات بأمر البيع الأصلي"),
    "WH6": _w("nama", "inventory", "nama", "تقرير حركة مخزن الخردة في Nama"),
    "WH7": _w("nama", "inventory", "nama", "محرك رصيد مخزون محسوب — Nama REST مبيطلعش أرصدة"),
    "WH8": _w("nama", "inventory", "dup nama", "مسح تكرار شامل على InvItem كله"),
    "WH9": _w("inventory nama", "inventory", "inv invc invm nama", "تقرير تفصيلي للجرد بالصنف والعدّاد والمنطقة"),
    "WH10": _w("inventory nama ai", "inventory", "inv nama", "طبقة الذكاء AI لاختيار عينة جرد عشوائية"),
    "WH11": _w("inventory nama", "inventory", "inv", "سجل مواعيد الجرد ومحرك التجديدات Renewals"),
    "WH12": _w("nama", "inventory", "nama", "تجميع أذون الصرف بالمخزن والصنف في Nama"),
    "WH13": _w("inventory nama", "inventory", "invc inv nama", "رصيد دفتري من Nama نقارن بيه جرد اليوم"),
    "WH14": _w("nama custody", "inventory", "nama", "كونكتور العهد وحالة الترحيل/الاعتماد على مستندات Nama"),
    "WH15": _w("nama inventory", "inventory", "nama invc", "تقرير رصيد مخزون — Nama REST مبيطلعش كميات"),
    "WH16": _w("nama", "inventory", "nama", "تقرير رصيد مخزون وقواعد تحويل الوحدات للوحدة الأكبر"),
    "WH17": _w("nama", "inventory", "nama", "مطابقة أسماء تقريبية على InvItem كله"),
    "WH18": _w("nama", "inventory", "nama ent1", "قواعد تحقق على حقول الوحدات في InvItem"),
    # --- Logistics, Shipping & Customs · شحن وجمارك -------
    "LG1": _w("nama movement", "nama", "nama", "موديول تتبع شحنات فوق أوامر شراء Nama"),
    "LG2": _w("nama movement", "nama", "nama", "موديول طلبات شحن فوق طلبات الشراء في Nama"),
    "LG3": _w("nama movement", "nama", "nama", "موديول عروض أسعار شحن جنب عروض Nama"),
    "LG4": _w("movement archive", "ideas", "", "موديول جمارك لنموذج 4 وكونكتور الأرشيف للمسح", "customs"),
    "LG5": _w("movement nama", "nama", "nama", "كونكتور شحن داخلي فوق أذون التسليم في Nama"),
    "LG6": _w("movement", "ideas", "", "موديول تخليص جمركي بالمخلصين وشغل كل شحنة", "customs"),
    "LG7": _w("movement", "ideas", "", "كونكتور حجز شحن تحت نظام movement"),
    "LG8": _w("portal", "overview", "", "كونكتور بوابة نافذة Nafeza الجمركية"),
    # المستند نفسه مبني من داتا موجودة في نما (الفاتورة وسطورها والطرف)، فالناقص
    # مش الداتا — الناقص الطرف اللي بيستقبلها والتحقق قبل الرفع.
    # The certificate is built and served; what it still lacks is the ERP behind
    # its fields. Purchaser, contract and product are all in Nama already.
    "LG10": _w("nama portal", "nama", "nama ent1",
               "الشهادة شغّالة بس بتتكتب بالإيد — الناقص تعبئة المشتري والعقد والصنف من نما"),
    # --- Nama Expert (Layer 4) — طلب المالك 2026-07-25 ------------------------
    # الخبير بيقرا من الخريطة والوثائق، فمصادره endpoints موجودة فعلًا؛ الناقص
    # طبقة الذكاء نفسها.
    "A4": _w("ai nama", "overview", "sys ws map",
             "مبني — الفهرس بيقرا الوثائق والخريطة. الناقص: ANTHROPIC_API_KEY "
             "علشان يصيغ الإجابة بدل ما يعرض المقاطع"),
    "A5": _w("ai nama rep archive", "overview", "sys ws map",
             "الوثائق والخريطة مفهرسة كلها · الناقص كتالوج الـ599 كيان (OpenAPI) "
             "يتسحب ويتفهرس معاهم"),
    "A6": _w("ai", "overview", "",
             "خط الصورة مبني من المتصفح للجيتواي — القراءة نفسها محتاجة الموديل موصول"),
    "A7": _w("ai", "overview", "",
             "مبني بـ Web Speech API في المتصفح — مافيش ناقص، بس بيشتغل على "
             "المتصفحات اللي مدعّماه"),
    "A8": _w("ai", "overview", "sys map",
             "مفروضة في التصميم مش feature: من غير موديل مافيش صياغة أصلًا، "
             "ومع موديل الردّ بيقول لو جه من غير استشهاد"),
    "A9": _w("ai rep", "overview", "",
             "القاعدة مكتوبة في تعليمات الخبير — الناقص آلية التوقيع نفسها (PA5) و Layer 5"),
    # --- المستشار القانوني (2026-07-25) — docs/legal-counsel.md --------------
    # المحرّك مبني، والمصدر ملفات على القرص مش endpoint — فمافيش endpoints هنا:
    # القوانين مش في نما ولا في الـ CRM، وربطها بأي منهم هيبقى ادّعاء.
    "L2": _w("legal ai", "ideas", "",
             "مبني — الناقص نصوص القوانين نفسها في corpus/legal (L6)"),
    "L3": _w("legal", "ideas", "",
             "الحارس شغّال — بس ما ينفعش يأكّد مادة من قانون مش محمّل، فقيمته "
             "بتكبر مع كل نصّ بيتحمّل"),
    "L4": _w("legal", "ideas", "",
             "شغّال دلوقتي من غير موديل ومن غير شبكة — مافيش ناقص"),
    "L5": _w("legal", "ideas", "",
             "٦ صيغ جاهزة — الناقص إن بنودها تتربط بمواد من نصّ محمّل بدل اسم "
             "القانون بس"),
    "L6": _w("legal", "ideas", "",
             "نصوص القوانين نفسها — ملفات نصّ في corpus/legal. ده الناقص الوحيد "
             "اللي بيفتح باقي الدومين"),
    "L7": _w("legal archive", "ideas", "",
             "عقودنا الموقّعة موجودة في الدرايف — محتاجة تتحوّل نصّ وتترفع tier: precedent"),
    "L8": _w("legal rep regulations", "ideas", "",
             "الـ18 لائحة عند REP — ترفع tier: internal، ويتقال إنها مش مصدّقة "
             "من المديرية فمش نافذة"),
    "L9": _w("legal ai", "ideas", "",
             "محتاج نصّ قانون العمل محمّل (L6) قبل أي مراجعة بند-ببند"),
    "L10": _w("legal nama", "nama", "ent1",
              "تواريخ انتهاء العقود والتراخيص في نما — نفس محرّك Renewals"),
    # --- من حزمة REP (اندمجت 2026-07-25) — docs/rep-integration.md -----------
    # كلها بتشاور على نظام `rep` كطرف مسؤول: الوحدة مبنية عند REP، والناقص إنها
    # تقرا من الجيتواي بدل ما تمسك اعتماد نما بنفسها.
    "H23": _w("rep nama", "nama", "emp",
              "REP عنده القاموس (73 مسمّى → 13) — الناقص إنه يقرا الموظفين من الجيتواي"),
    "H24": _w("rep nama attendance", "nama", "emp emp1",
              "REP هو المصدر النظيف للموبايلات (نما فيها 46/206 و8 مكرر على 17) — الناقص جسر Employee.mobile"),
    "H25": _w("rep regulations", "ideas", "",
              "محرك الجزاءات مبني ومختبر عند REP — الناقص كنكتور اللوائح"),
    "H26": _w("rep regulations archive", "ideas", "",
              "18 لائحة صفر مصدّقة والنسخة لسه بتتعدل — مافيش منطق يُبنى قبل ما تستقر"),
    "H27": _w("rep academy nama", "ideas", "emp",
              "المسارات والدروس عند REP من نوشن — الناقص كنكتور الأكاديمية"),
    "H28": _w("rep attendance meals nama", "nama", "emp",
              "معادلة الوجبات عند REP — الناقص كنكتور الوجبات فوق الحضور"),
    "T27": _w("rep custody nama", "nama", "repc repo",
              "الداتا والتقرير الإداري live من كنكتور REP — الناقص دفتر القيد "
              "الـappend-only (كتابة بموافقة، زي كل كتابة)"),
    "T28": _w("rep banks", "nama", "bank bankm",
              "مدقّق MOD-97 عند REP والحسابات حيّة عندنا — الناقص ضمّ المدقّق فوق الـ endpoint"),
    "FL4": _w("rep movement nama", "nama", "repm repo",
              "المحرك شغّال فوق كنكتور الحركة في /tools/rep — الناقص قراءات "
              "العداد (فاضية في كل العربيات) وترحيل الرحلات server-side (كتابة)"),
    "PA5": _w("rep archive", "overview", "",
              "توقيع REP (ECDSA · مفتاح في الجهاز) هو آلية HITL لـ Layer 5 — الناقص طبقة الكتابة"),
    "PA6": _w("rep idp", "overview", "",
              "قاعدة «الدور يُحسَب» عند REP — الناقص هوية موحّدة تنفّذها"),
    "PA7": _w("rep", "overview", "",
              "الأسطح الثلاثة عند REP — الناقص ضمّها في نظام تصميم الجيتواي"),
    "PA8": _w("rep nama", "monitoring", "",
              "مفتاح نما الأدمن بتاع REP مكشوف واعتماد منفصل — الناقص قرار المالك بالتغيير"),
    "AC7": _w("rep nama", "nama", "nama",
              "الكيانات القانونية الثلاثة موثّقة عند REP ومش عندنا — الناقص إضافتها للخريطة"),
    "AC8": _w("rep nama", "nama", "nama",
              "كتالوج 599 كيان عند REP — الناقص فهرس للكيانات جوّه الجيتواي"),
    "AC9": _w("rep archive", "overview", "repd",
              "القوالب السبعة بتتولّد وتتطبع من /tools/rep — الناقص توقيع PA5 "
              "الرقمي بدل الإمضا على الورق"),
    "LG9": _w("portal nama ai", "nama", "nama ent1",
              "كونكتور CargoX/ACID للتحقق والرفع + Layer 4 للشات بوت — داتا المستندات نفسها موجودة في نما"),
    # --- Safety / HSE · السلامة ---------------------------
    "SF1": _w("nama", "nama", "emp", "سجل إصابات عمل — مش موجود في أي نظام", "hse"),
    "SF2": _w("nama custody", "nama", "nama", "سجل صرف مهمات الأمان للعمال فوق مستندات Nama", "hse"),
    # --- Governance & Watchlist · حوكمة وقوائم حظر --------
    "GV1": _w("nama crm", "overview", "emp nama acc", "محرك Watchlist يخزّن علامات القايمة السودا ويربطها"),
    "GV2": _w("nama", "monitoring", "", "استعلام SQL على جداول نشاط مستخدمي Nama"),
    # --- Communications · تواصل ---------------------------
    "CM1": _w("email", "overview", "", "كونكتور IMAP للبريد — لسه مش متوصّل"),
    "CM2": _w("crm", "crm", "crm", "تقرير SLA على موديول HelpDesk في Vtiger"),
    "CM3": _w("telco custody", "overview", "", "تغذية CDR من شركة المحمول لخطوط الشركة"),
    "CM4": _w("callcenter", "overview", "", "كونكتور نظام callcenter — CDR وIVR وإحصائيات"),
    "CM5": _w("crm", "crm", "", "نوع حالة شكوى في Vtiger — مش موجود دلوقتي"),
    "CM6": _w("crm", "crm", "", "نموذج ومخزن اقتراحات — مش موجود في أي نظام"),
    # --- Attendance · حضور وبصمة --------------------------
    "AT1": _w("attendance nama", "nama", "emp nama", "تقرير حضور على TimeAttendance للكيانين"),
    "AT2": _w("attendance nama", "nama", "emp", "تطبيق بصمة موبايل بالموقع يغذّي TimeAttendance"),
    # --- Market Data & Rates · بيانات السوق والأسعار ------
    "MD1": _w("marketdata", "overview", "", "API خارجي لأسعار الذهب"),
    "MD2": _w("marketdata", "overview", "", "API خارجي لأسعار البترول"),
    "MD3": _w("nama marketdata", "nama", "nama", "API أسعار وقود خارجي وتقرير استهلاك من Nama"),
    "MD4": _w("marketdata ai", "overview", "", "طبقة الذكاء AI وتاريخ أسعار صرف للتنبؤ"),
    "MD5": _w("marketdata", "overview", "", "API أسعار صرف خارجي — زي T7"),
    # --- Quality · جودة / QC ------------------------------
    "Q1": _w("nama archive", "ideas", "", "سجل نتايج فحص وشهادات جودة — مش موجود", "quality"),
    # --- Admin & Compliance · شؤون إدارية وامتثال ---------
    "AC1": _w("archive nama", "ideas", "", "سجل تأشيرات بتواريخ انتهاء ومحرك التجديدات Renewals"),
    "AC2": _w("archive nama", "nama", "nama", "سجل رخص العربيات بتواريخها ومحرك التجديدات Renewals"),
    "AC3": _w("archive", "ideas", "", "سجل مستندات بتواريخ انتهاء لمحرك التجديدات Renewals"),
    "AC4": _w("nama archive", "nama", "nama", "سجل عقود إيجار بتواريخ انتهاء ومحرك التجديدات Renewals"),
    "AC5": _w("nama archive", "nama", "nama", "سجل اشتراكات بتواريخ تجديد ومحرك التجديدات Renewals"),
    "AC6": _w("nama surveillance", "nama", "emp", "جدول ورديات الأمن وكونكتور surveillance"),
    # --- Operations & Production · عمليات وإنتاج ----------
    "OP1": _w("nama", "nama", "nama", "تقرير على أوامر التشغيل لدى الغير في Nama"),
    "OP2": _w("nama", "nama", "nama", "مخزن خطوات ومهام لكل أمر تشغيل — مش موجود", "production"),
    "OP3": _w("nama", "ideas", "", "تغذية إنتاج يومي وهالك من الصالة — مش موجودة", "production"),
    "OP4": _w("nama", "nama", "nama", "تقرير SQL يقارن سعر أمر التشغيل بالتكلفة الفعلية"),
    "OP5": _w("nama", "nama", "nama", "تقرير SQL مخطط مقابل فعلي لأوامر التشغيل"),
    "OP6": _w("nama", "ideas", "", "تغذية ساعات تشغيل الماكينات — مش موجودة في أي نظام", "production"),
    "OP7": _w("nama", "nama", "nama", "تقرير SQL لتكلفة الطن محمّلة بالمصاريف غير المباشرة"),
    "OP8": _w("nama", "nama", "nama", "تقرير يومي على ساعات التشغيل المسجلة في Nama"),
    "OP9": _w("nama", "ideas", "", "خطة تشغيل يومية — مش موجودة في أي نظام", "production"),
    # --- Travel & Personal · سفر — خاص بالمالك ------------
    "TR1": _w("movement", "ideas", "", "سجل رحلات الرئيس بالوقت والتكلفة والهدف", "travel"),
    "TR2": _w("movement nama", "nama", "nama", "قايمة مشتريات السفر مربوطة بطلبات الشراء في Nama", "travel"),
    "TR3": _w("movement", "ideas", "", "موديول checklist عام على المنصة", "travel"),
    # --- Legal · قانوني -----------------------------------
    "L1": _w("archive", "ideas", "", "موديول قضايا بالجلسات والأطراف — مش موجود", "legal"),
    # --- Product / R&D · منتجات وتطوير --------------------
    "PD1": _w("nama", "nama", "dup", "خط مقترحات منتجات ينتهي بإضافة صنف في Nama", "rnd"),
    "PD2": _w("nama", "overview", "", "ربط حصر BOM بأصناف Nama — فحص تكرار وإنشاء عبر workflow"),
    # --- Management & Planning · إدارة وتخطيط -------------
    "G1": _w("archive regulations", "ideas", "", "لوحة توجيهات نكتب فيها مش قراءة بس", "planning"),
    "G2": _w("regulations archive", "ideas", "", "سجل قرارات إدارية بالمصدر والتاريخ والحالة"),
    "G3": _w("ai nama", "overview", "kpi ws", "طبقة الذكاء AI لتقييم مؤشرات الأنظمة المجمّعة"),
    # --- Platform & AI · Platform & AI --------------------
    "A1": _w("ai nama crm banks inventory attendance", "overview", "ws sys", "طبقة الذكاء AI فوق الكونكتورات الشغالة"),
    "A2": _w("nama", "nama", "nama ent1", "كيانات متعرّفة فعلاً في Nama NameBuilder"),
    "A3": _w("ai crm nama", "crm", "lead acc cont ar", "طبقة الذكاء AI فوق قراءات Vtiger وتقارير SQL"),
    # --- Platform UX & Input · تجربة الاستخدام والإدخال — عابر لكل الموديولات --
    "UX1": _w("nama", "nama", "nama", "نفس ودجت الاقتراح والتصحيح على باقي حقول الإدخال"),
    "UX1b": _w("nama", "nama", "dup nama", "محلّل يحوّل الاسم المكتوب لأجزاء الكود"),
    "UX2": _w("website", "overview", "", "مكوّن إدخال نص طويل لصق وتعديل في الواجهة", "frontend"),
    # Shipped without the external STT this row assumed it needed: the browser
    # has a recogniser, and it costs nothing.
    "UX3": _w("ai", "overview", "",
              "مبني — الناقص بس إن التعرّف بيعتمد على المتصفح، فالمتصفح اللي "
              "مش مدعّم Web Speech ما بيشوفش المايك أصلًا"),
    "UX4": _w("website", "overview", "ws", "مخزن إعدادات الودجتات فوق workspace API", "frontend"),
    # --- Platform & Access · منصّة وصلاحيات — عابر للمنصّة كلها --
    "PA1": _w("omnichannel", "overview", "", "كونكتور WhatsApp وWeChat Business API"),
    "PA2": _w("idp", "overview", "", "كونكتور دخول موحد SSO مع Google Workspace"),
    "PA3": _w("idp", "overview", "", "طبقة صلاحيات وأدوار على مستوى المنصة"),
    "PA4": _w("ai", "overview", "", "مبني — نفس طبقة UX3، بتتحقن في كل صفحة"),
}


_SYSTEM_KEYS = {s.key for s in SYSTEMS}


def wire_for(idea_id: str, prefix: str) -> Wire:
    """The explicit wiring, else the domain default so nothing is ever unplaced."""
    w = WIRING.get(idea_id)
    if w is not None:
        return w
    return DOMAIN_DEFAULTS.get(prefix, _w("nama", "overview", "", ""))


def systems_of(idea_id: str, prefix: str) -> tuple[str, ...]:
    return wire_for(idea_id, prefix).systems


def unknown_systems() -> set[str]:
    """Any system key used here that registry.SYSTEMS does not define."""
    used = {s for w in list(WIRING.values()) + list(DOMAIN_DEFAULTS.values())
            for s in w.systems}
    return used - _SYSTEM_KEYS


def unknown_endpoints() -> set[str]:
    """Any endpoint used here that is not a real route."""
    used = {e for w in WIRING.values() for e in w.endpoints}
    return used - catalog.paths()
