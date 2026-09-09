"""Everything a permission can be granted on — and, for the hub, how to show it.

One list drives three things so they can never disagree: the permission
matrix in the admin screen, the path→resource check in the middleware, and the
cards on the hub. A resource is either a page/API the gateway serves (`paths`
name the URL prefixes it guards) or a link to another system of ours (no
paths — the hub just hides the card from people without `view`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

ACTIONS: tuple[str, ...] = ("view", "edit", "admin")
ACTION_LABELS = {"view": "يشوف", "edit": "يعدّل", "admin": "يدير"}

#: Role slugs used for the hub's audience chips; a card lists the roles it is
#: *meant* for — permissions decide who actually sees it.
AUDIENCES = ("sales", "proc", "mgmt", "factory", "it")


@dataclass(frozen=True)
class Resource:
    key: str
    name: str                 # Arabic display name
    group: str                # hub section
    icon: str
    desc: str
    url: str                  # where the card opens (GW-relative or absolute)
    paths: tuple[str, ...] = ()   # URL prefixes on the gateway this resource guards
    external: bool = False        # another system of ours (no gateway path)
    host: str = ""                # shown on the card
    audiences: tuple[str, ...] = AUDIENCES
    kw: str = ""                  # extra search words
    status: str = "live"          # live | preview | internal
    live_key: str = ""            # key in /api/v1/hub/live to show a status dot
    editable: bool = True         # False = "edit" makes no sense (link / read-only page)
    order: int = 100


G_DAILY = "العمليات اليومية"
G_MONEY = "المال والخبرة"
G_SALES = "العملاء والمبيعات"
G_HR = "شؤون العاملين"
G_CORE = "الأنظمة الأساسية"
G_INFRA = "الإدارة والبنية التحتية"

RESOURCES: tuple[Resource, ...] = (
    # ---- gateway pages / APIs -------------------------------------------------
    Resource("hub", "STLIX Hub", G_CORE, "🚪", "الباب الواحد — الصفحة الرئيسية",
             "/hub/", paths=("/hub", "/api/v1/hub"), host="hub.stlixvalley.com",
             editable=False, order=0, status="internal"),
    Resource("platform", "Enterprise Platform", G_DAILY, "🏗️",
             "رصيد صنف بالعربي · NAME BUILDER بالـ AI · طلبات مبيعات↔مشتريات · التقرير اليومي",
             "/hub/platform.html", paths=("/hub/platform.html",), host="hub.stlixvalley.com",
             audiences=("sales", "proc", "mgmt"), kw="رصيد صنف اسم كود طلب تقرير platform builder",
             status="preview", order=1),
    Resource("gateway", "لوحة الـ gateway", G_DAILY, "🧭",
             "الباب الفني للمنصة: كل الأدوات والـ APIs والأنظمة المربوطة",
             "/tools/platform", paths=("/tools/platform", "/tools/tour", "/tools/library",
                                       "/api/v1/map", "/api/v1/workspace", "/systems",
                                       "/connectors", "/metrics", "/docs", "/openapi.json",
                                       "/redoc", "/"),
             host="gw.stlixvalley.com", audiences=("it", "mgmt"),
             kw="gateway hub platform لوحة أدوات api جولة tour مكتبة library", live_key="gateway",
             editable=False, order=2),
    Resource("name-builder", "NAME BUILDER", G_DAILY, "🧱",
             "إنشاء صنف جديد بكود واسم مضبوطين — بدون تكرار",
             "/tools/name-builder", paths=("/tools/name-builder", "/api/v1/nama"),
             host="gw.stlixvalley.com", audiences=("proc", "it"),
             kw="صنف جديد اسم كود name builder نما", live_key="nama", order=3),
    Resource("engineer", "Engineer", G_DAILY, "📐",
             "حسابات المهندس: عرض الاستربس، أوزان، تقطيع اللفات",
             "/tools/engineer", paths=("/tools/engineer",), host="gw.stlixvalley.com",
             audiences=("factory", "sales"), kw="مهندس وزن استربس تقطيع لفة حساب engineer",
             editable=False, order=4),
    Resource("rep", "REP — العهدة والحركة", G_DAILY, "🚚",
             "عهدة المندوبين، المستندات المطبوعة، حركة التوصيل، وتقرير الإدارة",
             "/tools/rep", paths=("/tools/rep", "/api/v1/rep"), host="gw.stlixvalley.com",
             audiences=("sales", "mgmt", "factory"),
             kw="مندوب عهدة حركة توصيل مستندات rep custody", live_key="rep", order=5),
    Resource("certificate", "شهادة الاستيراد", G_DAILY, "📜",
             "إصدار شهادة/مستند استيراد للشحنة بالبيانات المضبوطة",
             "/tools/certificate", paths=("/tools/certificate",), host="gw.stlixvalley.com",
             audiences=("proc", "mgmt"), kw="شهادة استيراد شحنة certificate import", order=6),
    Resource("count-app", "تطبيق الجرد", G_DAILY, "📋",
             "عدّ المخزون من الموبايل ومزامنة مع النظام",
             "https://crm.stlixvalley.com/count/count.html", paths=("/api/v1/inventory",),
             external=True, host="crm.stlixvalley.com", audiences=("proc", "factory"),
             kw="جرد عد مخزون count stocktake", live_key="inventory", order=7),
    Resource("finance", "Finance OS", G_MONEY, "💰",
             "لوحة الخزينة والعملاء والتقارير المالية (قراءة)",
             "/tools/finance-os", paths=("/tools/finance-os", "/tools/finance-reports",
                                        "/api/v1/finance", "/api/v1/banks"),
             host="gw.stlixvalley.com", audiences=("mgmt",),
             kw="مالية خزينة بنوك عملاء finance تقارير أرصدة", live_key="finance", order=10),
    Resource("expert", "Nama Expert", G_MONEY, "🎓",
             "اسأل عن نما بالعربي — يجاوب من التوثيق والقرارات بتاعتنا",
             "/tools/expert", paths=("/tools/expert", "/api/v1/expert"), host="gw.stlixvalley.com",
             audiences=("proc", "mgmt", "it"), kw="نما خبير سؤال expert مساعد namasoft",
             live_key="expert", order=11),
    Resource("legal", "المستشار القانوني", G_MONEY, "⚖️",
             "عقود ونماذج قانونية جاهزة + إجابات مستندة لنصوص القانون المصري",
             "/tools/legal", paths=("/tools/legal", "/api/v1/legal"), host="gw.stlixvalley.com",
             audiences=("mgmt",), kw="قانوني عقد نموذج legal counsel محامي", order=12),
    Resource("ideas", "لوحة الأفكار", G_MONEY, "💡",
             "الـ backlog: كل فكرة وحالتها ومين عليها",
             "/tools/ideas", paths=("/tools/ideas", "/api/v1/ideas"), host="gw.stlixvalley.com",
             audiences=("mgmt", "it"), kw="افكار backlog مهام ideas", status="internal", order=13),
    Resource("users", "المستخدمون والصلاحيات", G_INFRA, "🛡️",
             "إنشاء مستخدمين، الأدوار، ومين يشوف/يعدّل إيه",
             "/hub/admin.html", paths=("/hub/admin.html", "/api/v1/auth/admin"),
             host="hub.stlixvalley.com", audiences=("it",),
             kw="مستخدمين صلاحيات أدوار users roles permissions admin", order=40),
    # ---- other systems of ours (links) ----------------------------------------
    Resource("crm-site", "vTiger CRM", G_SALES, "🤝",
             "العملاء، الفرص، المتابعات — نظام العملاء الرئيسي",
             "https://crm.stlixvalley.com/", paths=("/api/v1/crm",), external=True,
             host="crm.stlixvalley.com", audiences=("sales", "mgmt"),
             kw="عملاء crm فرص متابعة vtiger api", live_key="site:crm", editable=False, order=30),
    Resource("erp-site", "نما ERP", G_CORE, "🗄️",
             "نظام السجل الوحيد: الأصناف، المخازن، الفواتير، الحسابات",
             "https://stlixvalley.namasoft.net/erp", external=True, host="namasoft.net",
             audiences=("proc", "mgmt", "it"), kw="نما erp أصناف مخازن فواتير حسابات namasoft",
             live_key="site:erp", editable=False, order=50),
    Resource("website", "stlixvalley.com", G_SALES, "🌐",
             "الموقع الرسمي — كتالوج المنتجات وطلبات التواصل",
             "https://stlixvalley.com/", external=True, host="stlixvalley.com",
             audiences=("sales", "mgmt"), kw="موقع كتالوج منتجات website wordpress",
             live_key="site:website", editable=False, order=32),
    Resource("egygrouphs", "egygrouphs.com", G_SALES, "🏢",
             "موقع المجموعة المصرية لتجارة المعادن + بانل الصور",
             "https://egygrouphs.com/", external=True, host="egygrouphs.com",
             audiences=("sales", "mgmt"), kw="المجموعة المصرية موقع صور egygroup",
             live_key="site:egygrouphs", editable=False, order=33),
    Resource("attendance-site", "الحضور والانصراف", G_HR, "🕒",
             "البصمات والحضور اليومي — على سيرفرنا",
             "https://attendance.stlixvalley.com/", paths=("/api/v1/attendance",), external=True,
             host="attendance.stlixvalley.com", audiences=("mgmt", "it"),
             kw="حضور انصراف بصمة attendance api", live_key="site:attendance", editable=False, order=21),
    Resource("payroll-site", "الرواتب", G_HR, "💵", "نظام الرواتب — على سيرفرنا",
             "https://payroll.stlixvalley.com/", external=True, host="payroll.stlixvalley.com",
             audiences=("mgmt",), kw="رواتب مرتبات payroll", live_key="site:payroll",
             editable=False, order=22),
    Resource("wp-admin", "لوحة تحكم stlixvalley.com", G_SALES, "🛠️",
             "WordPress admin — الصفحات، الصور، النماذج، الإضافات",
             "https://stlixvalley.com/wp-admin/", external=True, host="stlixvalley.com",
             audiences=("mgmt", "it"), kw="ووردبريس wordpress admin لوحة تحكم الموقع wp-admin",
             live_key="site:website", editable=False, order=34),
    Resource("egy-admin", "بانل egygrouphs.com", G_SALES, "🖼️",
             "إدارة صور وخدمات المجموعة المصرية — رفع، ترتيب، علامة مائية",
             "https://egygrouphs.com/ar/admin", external=True, host="egygrouphs.com",
             audiences=("mgmt", "it"), kw="بانل صور خدمات egygroup admin لوحة تحكم",
             live_key="site:egygrouphs", editable=False, order=35),
    Resource("hpanel-sites", "Hostinger — المواقع", G_INFRA, "🌐",
             "استضافة ووردبريس stlixvalley.com: الملفات، الـ SSL، الإيميل، الـ backups",
             "https://hpanel.hostinger.com/websites", external=True, host="hostinger.com",
             audiences=("it",), kw="hostinger websites استضافة ووردبريس ملفات ssl", editable=False, order=60),
    Resource("strapi", "Strapi CMS (الموقع القديم)", G_INFRA, "🗂️",
             "لوحة الـ CMS القديمة على السيرفر (container strapiback)",
             "http://153.92.209.190:1337/admin", external=True, host="153.92.209.190:1337",
             audiences=("it",), kw="strapi cms قديم", status="internal", editable=False, order=66),
    Resource("notion", "الذاكرة المشتركة (Notion)", G_CORE, "🧠",
             "توثيق المشاريع والقرارات — NAME BUILDER، الـ SOPs، الـ runbooks",
             "https://www.notion.so/", external=True, host="notion.so",
             audiences=("mgmt", "it"), kw="توثيق notion ذاكرة قرارات sop", editable=False, order=52),
    Resource("hpanel", "Hostinger VPS", G_INFRA, "🖥️",
             "لوحة السيرفر — الاستضافة، الـ SSL، الـ backups، الـ DNS بتاع stlixvalley.com",
             "https://hpanel.hostinger.com/vps", external=True, host="hostinger.com",
             audiences=("it",), kw="سيرفر vps hostinger استضافة dns دومين", editable=False, order=61),
    Resource("portainer", "Portainer", G_INFRA, "🐳",
             "إدارة الـ Docker containers على السيرفر (gateway / strapi / postgres)",
             "https://153.92.209.190:9443/", external=True, host="153.92.209.190:9443",
             audiences=("it",), kw="docker containers portainer", status="internal",
             editable=False, order=61),
    Resource("phpmyadmin", "phpMyAdmin", G_INFRA, "🐬", "قاعدة بيانات الـ CRM",
             "https://crm.stlixvalley.com/phpmyadmin/", external=True, host="crm.stlixvalley.com",
             audiences=("it",), kw="mysql database phpmyadmin قاعدة بيانات", status="internal",
             editable=False, order=62),
    Resource("google", "Google Workspace", G_INFRA, "📧", "الإيميلات والحسابات والـ Drive",
             "https://admin.google.com/", external=True, host="google.com",
             audiences=("it", "mgmt"), kw="ايميل حسابات google workspace drive", editable=False, order=63),
    Resource("godaddy", "GoDaddy", G_INFRA, "🌍", "النطاقات المسجّلة",
             "https://account.godaddy.com/products", external=True, host="godaddy.com",
             audiences=("it",), kw="دومين godaddy نطاق", editable=False, order=64),
    Resource("cameras", "الكاميرات (Hik-Connect)", G_INFRA, "📹", "كاميرات المصنع والمخازن",
             "https://www.hik-connect.com/", external=True, host="hik-connect.com",
             audiences=("mgmt", "factory"), kw="كاميرات مراقبة hikvision cctv", editable=False, order=65),
)

BY_KEY: dict[str, Resource] = {r.key: r for r in RESOURCES}

#: Paths that need no permission at all (login, probes, the voice asset).
PUBLIC_PREFIXES: tuple[str, ...] = (
    "/login", "/logout", "/health", "/favicon.ico", "/tools/voice.js",
    "/api/v1/auth/me", "/api/v1/auth/login", "/api/v1/auth/logout", "/hub/login.html",
)

# Longest prefix wins, so "/tools/platform" beats "/".
_PATH_INDEX: list[tuple[str, str]] = sorted(
    ((p, r.key) for r in RESOURCES for p in r.paths), key=lambda t: -len(t[0])
)


def resource_for_path(path: str) -> str:
    """Which resource a URL belongs to. Unknown paths fall under `gateway`."""
    for prefix, key in _PATH_INDEX:
        if prefix == "/":
            if path == "/":
                return key
            continue
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            return key
        # "/tools/finance-os" also covers "/tools/finance-os.html"-style siblings
        if path.startswith(prefix) and len(prefix) > 8:
            return key
    return "gateway"


def is_public(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?")
               for p in PUBLIC_PREFIXES)


def as_dicts() -> list[dict]:
    return [
        {"key": r.key, "name": r.name, "group": r.group, "icon": r.icon, "desc": r.desc,
         "url": r.url, "external": r.external, "host": r.host, "audiences": list(r.audiences),
         "kw": r.kw, "status": r.status, "live_key": r.live_key, "editable": r.editable,
         "order": r.order}
        for r in sorted(RESOURCES, key=lambda r: r.order)
    ]
