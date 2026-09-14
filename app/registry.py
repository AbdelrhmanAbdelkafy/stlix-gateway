"""The map of every system the gateway integrates.

This is the single source of truth for `نقطة التكامل` - one entry per company
system. Wiring a system for real means adding its router under
`app/integrations/<key>/` and flipping `status` to LIVE; until then it is
advertised as PLANNED so the gateway already exposes the full landscape.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    LIVE = "live"
    PLANNED = "planned"


@dataclass(frozen=True)
class System:
    key: str          # url/module slug
    name_en: str
    name_ar: str
    status: Status
    description: str = ""
    #: Where a human opens this system. Empty when there is nothing to open yet —
    #: an address that 404s is worse than none, same rule as everywhere else here.
    url: str = ""


# Order roughly reflects rollout priority.
SYSTEMS: list[System] = [
    System("nama", "Nama ERP", "نما", Status.LIVE, "ERP: employees, attendance, documents.",
           url="https://stlixvalley.namasoft.net/erp"),
    System("attendance", "Attendance & Fingerprint", "البصمة والحضور", Status.LIVE,
           "Punch push/read (routes to Nama TimeAttendance)."),
    System("vat", "VAT planner (ETA portal)", "ض.ق.م والبورتال", Status.LIVE,
           "Sales/purchases pulled from the ETA e-invoicing portal per entity; the month's purchase "
           "gap, invoice slots, cancellations, the return package and its procedure states.", url="/tools/vat"),
    System("cctv", "CCTV (Hikvision)", "الكاميرات", Status.LIVE,
           "DVR state, channels, storage, snapshots and events — pushed by the LAN agent "
           "(agents/cctv-agent); the VPS never dials a DVR.", url="/tools/cctv"),
    System("crm", "CRM", "سي آر إم", Status.LIVE, "Vtiger: contacts, leads, accounts (read-only).",
           url="https://crm.stlixvalley.com"),
    System("callcenter", "Call Center", "الكول سنتر", Status.PLANNED, "Calls, tickets, IVR."),
    System("email", "Email", "الإيميل", Status.PLANNED, "Send/receive, templates."),
    System("website", "Website", "الويب سايت", Status.PLANNED,
           "Public site / forms + traffic analytics (MK7)."),
    # LIVE since Nama Expert: `/api/v1/expert/*` is a real AI endpoint reading a
    # real index. Live means the code exists — grounding still depends on
    # ANTHROPIC_API_KEY being set, exactly as `nama` is live-but-unconfigured
    # without its credentials. Speech-to-text is browser-native (Web Speech API)
    # on the chat page, so it costs no vendor; the *orchestrator* (`ai-layer`)
    # is still unbuilt, and stays a separate, not-live connector.
    System("ai", "AI Services", "الذكاء الاصطناعي", Status.LIVE,
           "Nama Expert: grounded Q&A over the repo documents and the gateway's own map, "
           "with screenshots and Arabic voice. Sources cited; no model = passages only.",
           url="/tools/expert"),
    System("archive", "Archive", "الأرشيف", Status.PLANNED,
           "Document & record store: contracts, licenses, certificates, Form 4."),
    System("inventory", "Inventory / Stocktaking", "الجرد", Status.LIVE,
           "Stlix stocktake counting app (count/sync.php): counts, manual items, progress (read-only).",
           url="https://crm.stlixvalley.com/count/count.html"),
    System("academy", "Academy", "الأكاديمية", Status.PLANNED, "Training / LMS.",
           url="https://www.notion.so/39ffe2ccb2ed81a98be7d522a0779b49"),
    # REP is the operational front-end layer for everything Nama and the CRM do
    # not own — 11 built modules (custody, movement, meals, people, policies,
    # academy, banks, stocktake, alerts, documents, home). PLANNED here because
    # none of it is bridged yet: it reads Nama directly with its own admin
    # credential, which is the thing this gateway exists to end. See
    # docs/rep-integration.md.
    # LIVE since custody + documents + movement were adopted: their data was
    # extracted verbatim from rep-system.html into data/rep/ and is served at
    # /api/v1/rep/* — the single-file PWA's records became a connector that
    # management reports read, which was the point of merging REP at all. The
    # other eight units (meals, people/dictionary, policies, academy, banks,
    # stocktake, alerts, home) still live only in the original file.
    System("rep", "REP Operations", "REP التشغيلية", Status.LIVE,
           "Custody, signed-document templates and movement — adopted from the REP "
           "single-file PWA, served as data with provenance and management rollups. "
           "Remaining units (meals, dictionary, policies, academy…) not yet adopted.",
           url="/tools/rep"),
    # LIVE since the counsel: /api/v1/legal/* reads real files and, more to the
    # point, /api/v1/legal/verify checks article citations against them with no
    # model in the path. Live means the code exists; the corpus starts empty and
    # says so, the way `nama` is live-but-unconfigured without credentials.
    System("legal", "Legal Counsel", "المستشار القانوني", Status.LIVE,
           "Grounded legal Q&A, contract drafting and document review over loaded "
           "statutes, company contracts and internal bylaws. Every article number is "
           "verified against the loaded text; unverified ones are struck out.",
           url="/tools/legal"),
    System("regulations", "Regulations", "اللوائح", Status.PLANNED,
           "Internal policies & bylaws (the document store itself is `archive`)."),
    System("surveillance", "Surveillance & Alarm", "المراقبة والإنذار", Status.PLANNED,
           "CCTV cameras, alarms, access control, events."),
    System("movement", "Movement & Gate", "الحركة", Status.PLANNED,
           "Vehicle / gate movement & logistics."),
    System("housing", "Housing & Accommodation", "التسكين", Status.PLANNED,
           "Worker housing / accommodation assignments."),
    System("custody", "Custody & Assets", "العهدة", Status.PLANNED,
           "Assets & tools held by employees (عُهد)."),
    System("meals", "Meals & Catering", "التغذية", Status.PLANNED,
           "Meal eligibility & catering reports."),
    System("banks", "Bank Accounts", "حسابات البنوك", Status.LIVE,
           "Bank accounts (Nama): bank, GL account, currency. Balances = separate pending report."),
    # LIVE since the shipment file: `/api/v1/imports/*` runs the two approved
    # procedures (SOP-IMP-001/002) as one record per shipment — steps, ACID
    # match across the documents, free-time counter, landed cost per ton. Nama's
    # LCShipment stays the record of the shipment; this is the layer Nama has no
    # field for. Live with no credential, like `legal`: the procedure and the
    # file are on disk, and Nama credentials upgrade it from typed to synced.
    System("imports", "Imports & Shipping", "الاستيراد والشحن", Status.LIVE,
           "SOP-IMP-001/002 as a live shipment file over Nama's sea-shipping module "
           "(LCShipment): 46 steps with 23 stop gates, letter-by-letter ACID match across "
           "8 documents, free-time/demurrage counter, landed cost per ton vs the estimate.",
           url="/tools/imports"),
    # Upstream parties the backlog already depends on. Each is a distinct
    # counterparty with its own credentials and lifecycle — the test that
    # separates a system from a mere capability. Added because connectors in
    # catalog.py already pointed at four of these keys with nothing behind them.
    System("marketdata", "Market Data Feeds", "أسعار السوق والصرف", Status.PLANNED,
           "External price feeds: FX, gold, oil (T7, MD1-MD5). Quotes only, not a Nama source."),
    System("portal", "Government Portals", "البوابات الحكومية", Status.PLANNED,
           "ETA e-invoicing + Nafeza single window (T6, LG8). Statutory submit/read."),
    System("idp", "Identity Provider (SSO)", "الدخول الموحّد", Status.PLANNED,
           "Google Workspace / OAuth IdP behind SSO + RBAC (PA2, PA3). Auth, not a data source."),
    System("omnichannel", "Omnichannel Messaging", "قنوات التواصل", Status.PLANNED,
           "WhatsApp / WeChat and further channels behind one API (PA1). Sending is a WRITE."),
    System("telco", "Telco / Company Lines", "خطوط الشركة", Status.PLANNED,
           "Mobile operator CDRs & billing for company staff lines (CM3)."),
]


def as_dicts() -> list[dict]:
    return [
        {
            "key": s.key,
            "name_en": s.name_en,
            "name_ar": s.name_ar,
            "status": s.status.value,
            "description": s.description,
        }
        for s in SYSTEMS
    ]
