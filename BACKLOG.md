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
| S5 | Chinese leads — عملاء محتملين | Vtiger Leads | ⚪ ⚠ needs a China/segment field or tag on leads first (currently 15 leads, `country` empty, no Chinese marker) |

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
| T4 | التزامات متوقعة (expected obligations) | Nama | ⚪ |
| T5 | فواتير ثابتة (recurring / fixed invoices) | Nama | ⚪ |
| T6 | فواتير بورتال (portal / e-invoicing — ETA?) | portal API / Nama | ⚪ |
| T7 | أسعار الصرف اللحظية — يوان / دولار / يورو (real-time FX) | external FX API | ⚪ |
| T8 | أقساط واجبة السداد (installments due) | Nama | ⚪ |

## Maintenance (صيانة)
| # | Item | Source | Status |
|---|------|--------|--------|
| M1 | أعطال آلات ومعدات وأجهزة | Nama / new | ⚪ |
| M2 | الصيانات الدورية — سيارات / آلات / معدات (scheduled maintenance) | Nama / new | ⚪ |
| M3 | صيانة المباني (building maintenance) | Nama / new | ⚪ |

## HR (موارد بشرية)
| # | Item | Source | Status |
|---|------|--------|--------|
| H1 | الاستقالات | Nama | ⚪ |
| H2 | Onboarding / Offboarding | Nama / new | ⚪ |
| H3 | تدريبات وتطوير | Nama / new | ⚪ |
| H4 | نماذج وتفويضات | new | ⚪ |
| H5 | تعيينات مفتوحة (open positions / requisitions) | Nama / Vtiger | ⚪ |
| H6 | عهدة الموظف (employee cash custody — distinct from asset custody العهدة) | Nama | ⚪ |
| H7 | سلف العاملين (employee advances / loans) | Nama | ⚪ |

## Marketing (تسويق)
| # | Item | Source | Status |
|---|------|--------|--------|
| MK1 | Social platforms (منصات التواصل) | external APIs | ⚪ |
| MK2 | المعارض المتوقعة — حسب الدولة (expected exhibitions by country) | new / research | ⚪ |

## Investments / Equity (استثمارات ومساهمات)
| # | Item | Source | Status |
|---|------|--------|--------|
| I1 | إسهامات / مساهمات (contributions / shareholdings) | Nama | ⚪ |

## Warehouse & Inventory (مخازن ومخزون)
| # | Item | Source | Status |
|---|------|--------|--------|
| WH1 | تسليم واستلام بضائع (goods delivery & receipt) | Nama | ⚪ |
| WH2 | مرتجعات مبيعات ومشتريات (sales & purchase returns) | Nama | ⚪ |

## Market Data & Rates (بيانات السوق والأسعار)
| # | Item | Source | Status |
|---|------|--------|--------|
| MD1 | أسعار الذهب (gold prices) | external API | ⚪ |
| MD2 | البترول بالبرميل (oil per barrel) | external API | ⚪ |
| MD3 | المحروقات (fuel prices / consumption) | external / Nama | ⚪ |
| MD4 | توقعات أسعار الجنيه (EGP forecast) | external / AI | ⚪ |
| MD5 | أسعار الصرف اللحظية (FX) → see T7 | external FX API | ⚪ |

## Quality (جودة / QC)
| # | Item | Source | Status |
|---|------|--------|--------|
| Q1 | الاختبارات / QC / الشهادات (tests, QC, certificates) | Nama / new | ⚪ |

## Admin & Compliance (شؤون إدارية وامتثال)
| # | Item | Source | Status |
|---|------|--------|--------|
| AC1 | التأشيرات — تنبيه تجديد (visas, renewal alerts) | new | ⚪ |
| AC2 | التراخيص والسجلات والمرور (licenses, registers, traffic) | new / Nama | ⚪ |

## Operations & Production (عمليات وإنتاج)
| # | Item | Source | Status |
|---|------|--------|--------|
| OP1 | طلبات تجهيز — عند الغير (prep orders at third parties / subcontract WIP) | Nama | ⚪ |
| OP2 | Action plan — per job order / per batch (patch) | Nama / new | ⚪ |

## Management & Planning (إدارة وتخطيط)
| # | Item | Source | Status |
|---|------|--------|--------|
| G1 | توجهات / أفكار (directions / ideas board) | new | ⚪ |
| G2 | قرارات إدارية (administrative decisions) | new | ⚪ |

## Platform & AI (north star)
| # | Item | Notes |
|---|------|-------|
| A1 | Enterprise platform, AI-based | Layer 4 AI Orchestrator over the gateway: query/act across all connectors via natural language; the unifying vision. |
| A2 | Nama NameBuilder | Use Nama's NameBuilder to define custom entities/screens → new connectors read them via the same REST (enabler for custom modules: maintenance, custody, forms…). |

## Registered systems (map placeholders, not yet built)
call-center · email · website · AI · archive · inventory (الجرد) · academy ·
regulations (اللوائح) · surveillance & alarm · movement (الحركة) ·
housing (التسكين) · custody (العهدة) · meals (التغذية)
