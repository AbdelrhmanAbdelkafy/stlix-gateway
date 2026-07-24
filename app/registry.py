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


# Order roughly reflects rollout priority.
SYSTEMS: list[System] = [
    System("nama", "Nama ERP", "نما", Status.LIVE, "ERP: employees, attendance, documents."),
    System("attendance", "Attendance & Fingerprint", "البصمة والحضور", Status.LIVE,
           "Punch push/read (routes to Nama TimeAttendance)."),
    System("crm", "CRM", "سي آر إم", Status.LIVE, "Vtiger: contacts, leads, accounts (read-only)."),
    System("callcenter", "Call Center", "الكول سنتر", Status.PLANNED, "Calls, tickets, IVR."),
    System("email", "Email", "الإيميل", Status.PLANNED, "Send/receive, templates."),
    System("website", "Website", "الويب سايت", Status.PLANNED, "Public site / forms."),
    System("ai", "AI Services", "الذكاء الاصطناعي", Status.PLANNED, "LLM/agent endpoints."),
    System("archive", "Archive", "الأرشيف", Status.PLANNED, "Document archive."),
    System("inventory", "Inventory / Stocktaking", "الجرد", Status.PLANNED, "Stock counts."),
    System("academy", "Academy", "الأكاديمية", Status.PLANNED, "Training / LMS."),
    System("regulations", "Regulations", "اللوائح", Status.PLANNED, "Policies & bylaws."),
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
