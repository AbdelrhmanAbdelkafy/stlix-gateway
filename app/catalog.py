"""The gateway's catalogue of itself: every connector and every endpoint it serves.

`registry.py` answers "which company systems exist"; this answers "what has the
gateway actually built on top of them". Together they are the two halves the
ideas board needs in order to say, for any requirement, *where its data already
lives* and *what is still missing*.

Two rules keep this honest:

- **One source of truth for liveness.** `app/ideas/registry.py` used to carry its
  own `True/False` per connector; it now asks `is_live()` here, so a connector
  cannot be live on one screen and planned on another.
- **No drift.** `tests/test_catalog.py` asserts every path below is a real route
  on the app and every real route is listed here — so an endpoint can never be
  added without appearing in the map.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .registry import SYSTEMS, Status


@dataclass(frozen=True)
class Connector:
    """A data source the gateway can read. `system` ties it to registry.SYSTEMS."""

    key: str
    name_ar: str
    name_en: str
    system: str            # registry.SYSTEMS key ("" = gateway-native, no upstream)
    upstream: str          # what it actually talks to
    live: bool
    # Settings attributes to read at request time (empty = always available).
    configured_attr: str = ""
    mode_attr: str = ""
    note: str = ""


# Every connector key the platform knows — live first, then the ones a
# requirement can still be waiting on. The ideas board's readiness is computed
# straight off the `live` flags here.
CONNECTORS: tuple[Connector, ...] = (
    Connector("nama", "نما (ERP)", "Nama ERP", "nama", "Nama REST v1", True,
              "nama_configured", "nama_mode", "Entity CRUD only — no balances (verified)."),
    Connector("sql", "نما SQL", "Nama SQL", "nama", "Nama SQL (read-only login)", True,
              "nama_sql_configured", "", "The only source of real balances/KPIs."),
    Connector("attendance", "الحضور والبصمة", "Attendance", "attendance",
              "Nama REST (TimeAttendance)", True, "nama_configured", "nama_mode",
              "Push punch is a WRITE — blocked while read-only."),
    Connector("crm", "CRM (Vtiger)", "CRM", "crm", "Vtiger REST", True,
              "crm_configured", "crm_mode"),
    Connector("banks", "حسابات البنوك", "Banks", "banks", "Nama REST (Bank/BankAccount)", True,
              "nama_configured", "banks_mode", "Accounts master; balances need SQL."),
    Connector("inventory", "الجرد", "Stocktake", "inventory", "Stlix count app (sync.php)", True,
              "inventory_configured", "inventory_mode"),
    # The cameras: a LAN agent pushes what the DVRs say (ISAPI) — the gateway
    # holds the last report + one frame per channel and says how old it is.
    Connector("eta", "بورتال الضرايب", "ETA e-invoicing", "vat", "ETA SDK v1.0 (documents/search, details)", True,
              "eta_configured", "", "Read-only: sales + purchases with portal status, per entity."),
    Connector("vat", "ض.ق.م — التخطيط", "VAT planner", "vat", "eta cache + data/vat (SQLite)", True,
              "eta_configured", "vat_k_mode", "Gap → invoices needed → slots → package → draft match → paid."),
    Connector("cctv", "الكاميرات", "CCTV (Hikvision)", "cctv", "LAN agent -> ISAPI (push)", True,
              "cctv_configured", "", "Read-only view of DVR state; the agent key only allows uploads."),
    # Live for three of the eleven units: custody, documents, movement. Their
    # data was extracted verbatim from rep-system.html into data/rep/rep.json —
    # files on disk, no credential — and the extracted copy carries the original
    # file's own warnings (placeholder distances, the contested opening balance)
    # on every response. docs/rep-integration.md.
    Connector("rep", "REP التشغيلية", "REP Operations", "rep",
              "data/rep on disk (extracted from rep-system.html)", True,
              note="العهدة والمستندات والحركة مضمومين · باقي ٨ وحدات لسه في الملف الأصلي"),
    Connector("gateway", "الجيتواي نفسه", "Gateway itself", "", "in-process", True,
              note="Workspace, ideas, systems map, metrics."),
    Connector("auth", "المستخدمون والصلاحيات", "Users & permissions", "", "SQLite (data/auth)", True,
              note="أدوار على طريقة نما: مين يشوف إيه ويعدّل إيه — وسجل تدقيق."),
    Connector("hub", "الهَب اللايف", "Live hub", "", "in-process probes (connectors + our sites)", True,
              note="لوحة حالة كل الأنظمة — تتحدّث لوحدها (SSE)."),
    Connector("front-end", "واجهات الموديولات", "Module front-ends", "", "served from /tools", True,
              note="Browser-side helpers: autocomplete, validators, widgets."),
    Connector("all-connectors", "كل الكنكتورات", "All connectors", "", "fan-out", True,
              note="Reads across every live connector at once."),
    # Live since the platform-wide voice layer. The recogniser is the browser's
    # own Web Speech API, so this connector carries no credential and no vendor
    # at all — which is also why it could ship without the external Arabic STT
    # the backlog had assumed it would have to wait for.
    Connector("voice", "الصوت العربي", "Arabic voice", "ai",
              "browser Web Speech API (ar-EG / en-US)", True, "", "",
              note="طبقة واحدة بتتحقن في كل صفحة — مافيش مفتاح ومافيش فاتورة."),
    # Nama Expert. Live with no credential at all: the index is built from the
    # repo and from this catalogue, so retrieval works offline. `configured_attr`
    # points at the Anthropic key because that is what upgrades an answer from
    # "here are the passages" to a composed, cited reply.
    Connector("expert", "Nama Expert", "Nama Expert", "ai",
              "repo docs + gateway map (+ Anthropic when configured)", True,
              "expert_grounded", "",
              note="من غير مفتاح بيرجّع المقاطع ومصادرها — ما بيخترعش إجابة."),
    # The corpus is files on disk, so this is live with no credential at all —
    # `/api/v1/legal/verify` in particular runs with no model and no network.
    # `configured_attr` points at the Anthropic key because that is what turns
    # retrieved provisions into a composed opinion.
    Connector("legal", "المستشار القانوني", "Legal counsel", "legal",
              "corpus/legal on disk (+ Anthropic when configured)", True,
              "expert_grounded", "",
              note="رقم المادة بيتأكَّد من النصّ المحمّل — واللي مش متأكَّد منه بيتشال."),
    # --- not built yet: these are what `blocked`/`partial` readiness points at ---
    # Distinct from `expert`: this is the orchestrator that would *act* — call
    # tools, chain steps, propose writes. The expert only reads and cites.
    Connector("ai-layer", "طبقة الذكاء (Layer 4)", "AI orchestrator", "ai", "LLM / agents", False),
    Connector("new-system", "نظام جديد", "New system", "", "does not exist yet", False,
              note="Needs a system built or bought before a connector is possible."),
    Connector("external", "API خارجي", "External API", "", "third-party API", False),
    Connector("email", "الإيميل", "Email", "email", "IMAP / SMTP", False),
    Connector("omnichannel", "واتساب / وي شات", "Omnichannel", "omnichannel",
              "WhatsApp / WeChat APIs", False),
    Connector("marketdata", "أسعار السوق", "Market data", "marketdata",
              "FX / gold / oil quote feeds", False),
    Connector("sso", "الدخول الموحّد", "SSO", "idp", "Google Workspace / OAuth IdP", False),
    Connector("portal", "بوابات حكومية", "Government portal", "portal",
              "نافذة / الفاتورة الإلكترونية", False),
    Connector("telco", "شركة الاتصالات", "Telco", "telco", "operator API / CDRs", False),
    Connector("custody", "العهدة", "Custody", "custody", "custody records", False),
    Connector("bank-feed", "تغذية بنكية", "Bank feed", "banks", "bank statement feed", False),
)

_BY_KEY = {c.key: c for c in CONNECTORS}


@dataclass(frozen=True)
class Endpoint:
    """One addressable thing the gateway serves today."""

    path: str
    title_ar: str
    connector: str         # CONNECTORS key ("" for a not-built-yet placeholder)
    kind: str = "api"      # api | page | placeholder
    method: str = "GET"
    write: bool = False    # a write op (gated by connector mode)
    system: str = ""       # set only when no connector implies it


# Every live route, in the order a person would explore them. `{param}` matches
# the FastAPI path exactly so the no-drift test can compare them literally.
_ROUTES: tuple[Endpoint, ...] = (
    # gateway-native
    Endpoint("/", "الجذر — روابط البداية", "gateway"),
    Endpoint("/health", "الصحة + وصول نما", "gateway"),
    Endpoint("/systems", "خريطة الأنظمة", "gateway"),
    Endpoint("/connectors", "الكنكتورات وأوضاعها", "gateway"),
    Endpoint("/connectors/{key}", "كنكتور واحد + اللي مستنيه", "gateway"),
    Endpoint("/metrics", "المراقبة (Prometheus/JSON)", "gateway"),
    # The workspace IS the fan-out across every live connector — that is what
    # the `all-connectors` key means, so it belongs to it and not to `gateway`.
    Endpoint("/api/v1/workspace", "اللوحة الموحّدة", "all-connectors"),
    Endpoint("/api/v1/workspace/overview", "اللوحة الموحّدة (نفسها)", "all-connectors"),
    Endpoint("/api/v1/ideas", "كل الأفكار والمتطلبات", "gateway"),
    Endpoint("/api/v1/ideas/domains", "دومينات الأفكار", "gateway"),
    Endpoint("/api/v1/ideas/{idea_id}", "فكرة واحدة", "gateway"),
    Endpoint("/api/v1/map", "الخريطة الموحّدة (أنظمة×كنكتورات×أفكار)", "gateway"),
    Endpoint("/systems/{key}", "نظام واحد + أفكاره", "gateway"),
    # nama
    Endpoint("/api/v1/nama/employees", "الموظفون", "nama"),
    Endpoint("/api/v1/nama/employees/{code}", "موظف بالكود", "nama"),
    Endpoint("/api/v1/nama/lists/{entity}", "أي كيان في نما (قائمة)", "nama"),
    Endpoint("/api/v1/nama/invitem/exists", "فحص تكرار صنف", "nama"),
    Endpoint("/api/v1/nama/{entity}/{code}", "أي كيان في نما بالكود", "nama"),
    # attendance
    Endpoint("/api/v1/attendance/punch", "دفع بصمات (كتابة — مقفولة)", "attendance",
             method="POST", write=True),
    # crm
    Endpoint("/api/v1/crm", "حالة كنكتور الـ CRM", "crm"),
    Endpoint("/api/v1/crm/contacts", "جهات الاتصال", "crm"),
    Endpoint("/api/v1/crm/leads", "العملاء المحتملون", "crm"),
    Endpoint("/api/v1/crm/accounts", "الحسابات/الشركات", "crm"),
    Endpoint("/api/v1/crm/{module}", "أي موديول في Vtiger", "crm"),
    # banks
    Endpoint("/api/v1/banks", "حسابات البنوك", "banks"),
    Endpoint("/api/v1/banks/master", "بيانات البنوك الأساسية", "banks"),
    # inventory
    Endpoint("/api/v1/inventory", "تقدّم الجرد", "inventory"),
    Endpoint("/api/v1/inventory/counts", "أعداد الجرد", "inventory"),
    Endpoint("/api/v1/inventory/manual", "أصناف يدوية", "inventory"),
    # vat / eta
    Endpoint("/api/v1/vat", "ض.ق.م — الكيانات والشهر الحالي", "vat"),
    Endpoint("/api/v1/vat/log", "ض.ق.م — سجل التغييرات", "vat"),
    Endpoint("/api/v1/vat/alerts", "تنبيهات ض.ق.م", "vat"),
    Endpoint("/api/v1/vat/alerts/seen", "تعليم التنبيهات كمقروءة", "vat", method="POST"),
    Endpoint("/api/v1/vat/sweep", "تشغيل الجولة التلقائية دلوقتي", "vat", method="POST"),
    Endpoint("/api/v1/vat/codes", "أكواد التصنيع (AssemblyBOM)", "vat"),
    Endpoint("/api/v1/vat/codes/refresh", "سحب أكواد التصنيع من نما", "vat", method="POST"),
    Endpoint("/api/v1/vat/{entity}/{month}", "خطة الشهر — الفجوة والمواعيد", "vat"),
    Endpoint("/api/v1/vat/{entity}/{month}/sync", "سحب الشهر من البورتال", "eta", method="POST"),
    Endpoint("/api/v1/vat/{entity}/{month}/documents", "مستندات البورتال للشهر", "eta"),
    Endpoint("/api/v1/vat/{entity}/{month}/imports", "تسجيل إفراج استيراد", "vat", method="POST"),
    Endpoint("/api/v1/vat/{entity}/{month}/imports/{import_id}", "حذف إفراج", "vat", method="DELETE"),
    Endpoint("/api/v1/vat/{entity}/{month}/draft", "مطابقة درافت الإقرار", "vat", method="POST"),
    Endpoint("/api/v1/vat/{entity}/{month}/package", "باكدج الإقرار", "vat"),
    Endpoint("/api/v1/vat/{entity}/{month}/package.csv", "باكدج الإقرار CSV", "vat"),
    # eta — the portal's own surface, so nobody opens a browser
    Endpoint("/eta/erp/ping", "المصلحة بتتأكد إن نظامنا شغّال (وقت التسجيل)", "eta", method="PUT"),
    Endpoint("/api/v1/eta/{entity}/ingest", "رفع مستندات مقروءة من المتصفح", "eta", method="POST"),
    Endpoint("/api/v1/eta/browser/read/{action}", "قراءة الصفحة الحالية من البراوزر", "eta"),
    Endpoint("/api/v1/eta/browser/do/{action}", "تحريك البراوزر (goto/click/fill)", "eta",
             method="POST", write=True),
    Endpoint("/vnc/{path}", "شاشة البراوزر (noVNC) — للدخول اليدوي", "eta"),
    Endpoint("/api/v1/eta/{entity}/ping", "اختبار الاتصال بالبورتال", "eta"),
    Endpoint("/api/v1/eta/{entity}/recent", "آخر المستندات على البورتال", "eta"),
    Endpoint("/api/v1/eta/{entity}/notifications", "إشعارات المصلحة", "eta"),
    Endpoint("/api/v1/eta/{entity}/document-types", "أنواع المستندات ومهلة الإلغاء", "eta"),
    Endpoint("/api/v1/eta/{entity}/documents/{uuid}", "المستند الأصلي كما أُرسل", "eta"),
    Endpoint("/api/v1/eta/{entity}/documents/{uuid}/details", "تفاصيل مستند + بنوده", "eta"),
    Endpoint("/api/v1/eta/{entity}/documents/{uuid}/pdf", "PDF المستند من المصلحة", "eta"),
    Endpoint("/api/v1/eta/{entity}/packages", "طلب حزمة شهر كاملة", "eta", method="POST"),
    Endpoint("/api/v1/eta/{entity}/packages/{package_id}", "تنزيل الحزمة", "eta"),
    Endpoint("/api/v1/eta/{entity}/documents/{uuid}/state", "إلغاء/رفض مستند (مقفول افتراضيًا)", "eta",
             method="PUT", write=True),
    # cctv
    Endpoint("/api/v1/cctv", "الكاميرات — الحالة والأجهزة", "cctv"),
    Endpoint("/api/v1/cctv/devices", "أجهزة الـ DVR", "cctv"),
    Endpoint("/api/v1/cctv/devices/{device}/channels", "قنوات جهاز واحد + آخر لقطة", "cctv"),
    Endpoint("/api/v1/cctv/events", "أحداث الكاميرات (حركة/فقد إشارة/هارد)", "cctv"),
    Endpoint("/api/v1/cctv/snapshot/{device}/{channel}.jpg", "آخر لقطة لقناة", "cctv"),
    Endpoint("/api/v1/cctv/push", "تقرير الـ agent (أجهزة/قنوات/أحداث)", "cctv", method="POST"),
    Endpoint("/api/v1/cctv/push/snapshot/{device}/{channel}", "رفع لقطة من الـ agent", "cctv", method="POST"),
    # finance (SQL)
    Endpoint("/api/v1/finance/kpis", "مؤشرات مالية حقيقية", "sql"),
    Endpoint("/api/v1/finance/customers", "أرصدة العملاء (AR)", "sql"),
    Endpoint("/api/v1/finance/suppliers", "أرصدة الموردين (AP)", "sql"),
    # the same three, rebuilt from live Nama documents (?source=live)
    Endpoint("/api/v1/finance/live", "حالة اللقطة اللحظية للأرصدة", "nama"),
    Endpoint("/api/v1/finance/live/guard", "حارس الانحراف — يفحص شهر مقفول", "nama",
             method="POST"),
    Endpoint("/api/v1/finance/live/refresh", "تحديث اللقطة اللحظية (سحب كامل)", "nama",
             method="POST"),
    # expert
    Endpoint("/api/v1/expert", "حالة الخبير وإيه اللي مفهرس", "expert"),
    Endpoint("/api/v1/expert/search", "بحث في المصادر (من غير موديل)", "expert"),
    Endpoint("/api/v1/expert/ask", "اسأل الخبير (نص + سكرين شوت)", "expert",
             method="POST"),
    Endpoint("/api/v1/expert/reindex", "إعادة فهرسة الوثائق", "expert", method="POST"),
    # rep
    Endpoint("/api/v1/rep", "REP — إيه المضموم وإيه الباقي", "rep"),
    Endpoint("/api/v1/rep/custody", "العهدة — الحاملون والعربيات", "rep"),
    Endpoint("/api/v1/rep/movement", "الحركة — الفريق والأسطول والقواعد", "rep"),
    Endpoint("/api/v1/rep/documents", "قوالب المستندات السبعة", "rep"),
    Endpoint("/api/v1/rep/overview", "تقرير الإدارة — محسوب من السجلات", "rep"),
    Endpoint("/api/v1/rep/reload", "إعادة قراءة داتا REP", "rep", method="POST"),
    # legal counsel
    Endpoint("/api/v1/legal", "حالة المستشار والنصوص المحمّلة", "legal"),
    Endpoint("/api/v1/legal/coverage", "تغطية القوانين — المحمّل والناقص", "legal"),
    Endpoint("/api/v1/legal/search", "بحث في النصوص (من غير موديل)", "legal"),
    Endpoint("/api/v1/legal/law/{slug}", "نصّ قانون واحد بمواده", "legal"),
    Endpoint("/api/v1/legal/templates", "صيغ المستندات", "legal"),
    Endpoint("/api/v1/legal/ask", "اسأل المستشار", "legal", method="POST"),
    Endpoint("/api/v1/legal/draft", "اكتب مسودة من صيغة", "legal", method="POST"),
    Endpoint("/api/v1/legal/review", "راجع مستند", "legal", method="POST"),
    Endpoint("/api/v1/legal/verify", "افحص أرقام المواد في أي نص", "legal", method="POST"),
    Endpoint("/api/v1/legal/reindex", "إعادة قراءة مجلد النصوص", "legal", method="POST"),
    # auth (PA2/PA3)
    Endpoint("/login", "صفحة الدخول", "auth", kind="page"),
    Endpoint("/logout", "تسجيل الخروج", "auth"),
    Endpoint("/api/v1/auth/me", "مين داخل وصلاحياته", "auth"),
    Endpoint("/api/v1/auth/login", "دخول (JSON)", "auth", method="POST"),
    Endpoint("/api/v1/auth/logout", "خروج (JSON)", "auth", method="POST"),
    Endpoint("/api/v1/auth/password", "تغيير كلمة مروري", "auth", method="POST"),
    Endpoint("/api/v1/auth/admin/resources", "الموارد والأفعال", "auth"),
    Endpoint("/api/v1/auth/admin/users", "المستخدمون (قائمة/إنشاء)", "auth"),
    Endpoint("/api/v1/auth/admin/users/{username}", "مستخدم واحد (تعديل/حذف)", "auth"),
    Endpoint("/api/v1/auth/admin/users/{username}/password", "تعيين كلمة مرور", "auth", method="POST"),
    Endpoint("/api/v1/auth/admin/users/{username}/overrides", "استثناءات مستخدم", "auth"),
    Endpoint("/api/v1/auth/admin/roles", "الأدوار", "auth"),
    Endpoint("/api/v1/auth/admin/roles/{key}", "دور واحد (حفظ/حذف)", "auth"),
    Endpoint("/api/v1/auth/admin/audit", "سجل التدقيق", "auth"),
    # hub
    Endpoint("/hub/", "STLIX Hub — الباب الواحد", "hub", kind="page"),
    Endpoint("/hub/{name}", "صفحة هَب (platform / admin)", "hub", kind="page"),
    Endpoint("/api/v1/hub/catalog", "الكروت حسب الصلاحيات", "hub"),
    Endpoint("/api/v1/hub/live", "لقطة حالة الأنظمة", "hub"),
    Endpoint("/api/v1/hub/events", "بث لايف (SSE)", "hub"),
    # pages
    Endpoint("/tools/tour", "الجولة — صفحة العرض", "front-end", kind="page"),
    Endpoint("/tools/platform", "الهَب", "front-end", kind="page"),
    Endpoint("/tools/platform/public", "الهَب — العرض العام", "front-end", kind="page"),
    Endpoint("/tools/certificate", "شهادة الجودة (استيراد)", "front-end", kind="page"),
    Endpoint("/tools/expert", "Nama Expert — الشات", "front-end", kind="page"),
    Endpoint("/tools/legal", "المستشار القانوني", "front-end", kind="page"),
    Endpoint("/tools/rep", "REP — العهدة والمستندات والحركة", "front-end", kind="page"),
    Endpoint("/tools/cctv", "الكاميرات — حائط اللقطات والأحداث", "front-end", kind="page"),
    Endpoint("/tools/vat", "ض.ق.م — الفجوة والإقرار", "front-end", kind="page"),
    Endpoint("/tools/portal", "شاشة بورتال الضرايب المباشرة", "front-end", kind="page"),
    Endpoint("/tools/voice.js", "طبقة البحث الصوتي — تتحقن في كل صفحة", "voice",
             kind="page"),
    Endpoint("/tools/ideas", "لوحة الأفكار", "front-end", kind="page"),
    Endpoint("/tools/finance-reports", "التقارير المالية", "front-end", kind="page"),
    Endpoint("/tools/finance-os", "Finance OS", "front-end", kind="page"),
    Endpoint("/tools/name-builder", "إنشاء الأصناف", "front-end", kind="page"),
    Endpoint("/tools/engineer", "مساعد المهندس (حسابات وحصر)", "front-end", kind="page"),
    Endpoint("/tools/library", "مكتبة وثائق المشروع", "front-end", kind="page"),
    Endpoint("/tools/library/{name}", "وثيقة واحدة", "front-end", kind="page"),
)


def _placeholders() -> tuple[Endpoint, ...]:
    """`main.py` mounts `/api/v1/<key>` -> 501 for every PLANNED system.

    Derived rather than listed: adding a System used to mount a public route
    that appeared on no map at all, and the drift only grew.
    """
    return tuple(
        Endpoint(f"/api/v1/{s.key}", f"{s.name_ar} (مخطّط — 501)", "",
                 kind="placeholder", system=s.key)
        for s in SYSTEMS
        if s.status is Status.PLANNED
    )


ENDPOINTS: tuple[Endpoint, ...] = _ROUTES + _placeholders()

_BY_PATH = {e.path: e for e in ENDPOINTS}


def is_live(connector_key: str) -> bool:
    """Whether a connector exists today. The ideas board's readiness rests on this."""
    c = _BY_KEY.get(connector_key)
    return bool(c and c.live)


def get_connector(key: str) -> Connector | None:
    return _BY_KEY.get(key)


def get_endpoint(path: str) -> Endpoint | None:
    return _BY_PATH.get(path)


def paths() -> set[str]:
    return set(_BY_PATH)


def endpoints_of(connector_key: str) -> list[str]:
    return [e.path for e in ENDPOINTS if e.connector == connector_key]


def live_keys() -> list[str]:
    return [c.key for c in CONNECTORS if c.live]


def connector_state(c: Connector, settings: Settings) -> dict:
    """A connector row with its runtime state — what `/connectors` should say.

    `configured` is about credentials being present, `live` about the code
    existing. A connector can be live and unconfigured (nothing in `.env` yet).
    """
    configured = bool(getattr(settings, c.configured_attr)) if c.configured_attr else c.live
    mode = getattr(settings, c.mode_attr) if c.mode_attr else ("read_only" if c.live else "—")
    return {
        "key": c.key,
        "name_ar": c.name_ar,
        "name_en": c.name_en,
        "system": c.system,
        "upstream": c.upstream,
        "live": c.live,
        "configured": configured,
        "mode": mode,
        "read_only": mode != "read_write",
        "endpoints": endpoints_of(c.key),
        "note": c.note,
    }


def as_dicts(settings: Settings) -> list[dict]:
    return [connector_state(c, settings) for c in CONNECTORS]


def endpoints_as_dicts() -> list[dict]:
    return [
        {"path": e.path, "title_ar": e.title_ar, "connector": e.connector,
         "kind": e.kind, "method": e.method, "write": e.write}
        for e in ENDPOINTS
    ]
