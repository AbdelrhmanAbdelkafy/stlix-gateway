# Stlix Gateway — Backlog / Roadmap

Requirements captured from the owner, grouped by domain. Most are **reports /
KPIs** derived from existing connectors (Nama, Vtiger) rather than new external
systems — they become endpoints under a domain connector, and workspace
sections. Source column: where the data lives.

Status: 🟢 live · 🟡 next · ⚪ planned

## Connectors (live)
| Connector | Source | Status |
|-----------|--------|--------|
| Nama ERP (employees, entities) | Nama REST | 🟢 |
| Attendance / fingerprint | Nama REST | 🟢 |
| CRM (contacts, leads, accounts) | Vtiger | 🟢 |
| Banks (accounts, master) | Nama REST | 🟢 |

> Bank **balances**: Nama REST exposes no balance/report entity (verified).
> Real numbers require SQL (`chartbalance` / `JournalEntryLine`) or a Nama
> server-side report. Decision pending.

## Sales & Collection (مبيعات وتحصيل)
| # | Item | Source | Status |
|---|------|--------|--------|
| S1 | المبيعات: المخطط / الفعلي / كاش / آجل | Nama | ⚪ |
| S2 | التحصيل اليوم: المخطط / الفعلي | Nama | ⚪ |
| S3 | أداء مسؤولي المبيعات | Nama / Vtiger | ⚪ |
| S4 | عملاء غير نشطين | Vtiger / Nama | ⚪ |
| S5 | Chinese leads — عملاء محتملين | Vtiger Leads | ⚪ |

## Purchasing & Materials (مشتريات وخامات)
| # | Item | Source | Status |
|---|------|--------|--------|
| P1 | طلبات شراء عاجلة | Nama | ⚪ |
| P2 | مين طلب خامات ستليكس | Nama | ⚪ |
| P3 | طلبات Site Survey | Nama / Vtiger | ⚪ |
| P4 | أسعار الخامات | Nama | ⚪ |

## Treasury & Finance (خزينة ومالية)
| # | Item | Source | Status |
|---|------|--------|--------|
| T1 | أرصدة البنوك (أرقام) | SQL / report | 🟡 |
| T2 | شيكات في الخزينة لم تُحصّل + شيكات التزامات | Nama | ⚪ |
| T3 | التأمينات · الضرائب · المدفوعات الحكومية | Nama | ⚪ |

## Maintenance (صيانة)
| # | Item | Source | Status |
|---|------|--------|--------|
| M1 | أعطال آلات ومعدات وأجهزة | Nama / new | ⚪ |

## HR (موارد بشرية)
| # | Item | Source | Status |
|---|------|--------|--------|
| H1 | الاستقالات | Nama | ⚪ |
| H2 | Onboarding / Offboarding | Nama / new | ⚪ |
| H3 | تدريبات وتطوير | Nama / new | ⚪ |
| H4 | نماذج وتفويضات | new | ⚪ |
| H5 | تعيينات مفتوحة (open positions / requisitions) | Nama / Vtiger | ⚪ |

## Marketing (تسويق)
| # | Item | Source | Status |
|---|------|--------|--------|
| MK1 | Social platforms (منصات التواصل) | external APIs | ⚪ |

## Investments / Equity (استثمارات ومساهمات)
| # | Item | Source | Status |
|---|------|--------|--------|
| I1 | إسهامات / مساهمات (contributions / shareholdings) | Nama | ⚪ |

## Platform & AI (north star)
| # | Item | Notes |
|---|------|-------|
| A1 | Enterprise platform, AI-based | Layer 4 AI Orchestrator over the gateway: query/act across all connectors via natural language; the unifying vision. |
| A2 | Nama NameBuilder | Use Nama's NameBuilder to define custom entities/screens → new connectors read them via the same REST (enabler for custom modules: maintenance, custody, forms…). |

## Registered systems (map placeholders, not yet built)
call-center · email · website · AI · archive · inventory (الجرد) · academy ·
regulations (اللوائح) · surveillance & alarm · movement (الحركة) ·
housing (التسكين) · custody (العهدة) · meals (التغذية)
