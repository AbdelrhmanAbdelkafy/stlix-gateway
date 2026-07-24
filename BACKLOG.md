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
| S6 | حصيلة مطلوبة (required collections / target receivables) | Nama | ⚪ |
| S7 | مبيعات فرع (sales by branch) | Nama | ⚪ |
| S8 | مبيعات مسؤول مبيعات (sales by rep) | Nama | ⚪ |
| S9 | عملاء جدد — عدد ومصدر (new customers count & source) | Vtiger / Nama | ⚪ |
| S10 | عملاء توقفوا معنا (churned customers count) | Vtiger / Nama | ⚪ |
| S11 | نسبة الربحية — للتكلفة / لسعر البيع (margin to cost / to sale price) | Nama | ⚪ |
| S12 | الأصناف الأفضل مبيعًا (best-selling items) | Nama | ⚪ |
| S13 | الأصناف الأعلى ربحية (highest-margin items) | Nama | ⚪ |
| S14 | نسبة التحويل (lead→customer conversion rate) | Vtiger / Nama | ⚪ |
| S15 | عدد الزيارات (sales visits count) | Vtiger / Nama | ⚪ |
| S16 | حالة إتمام الأوردر — المتبقي منه (order completion / remaining) | Nama | ⚪ |

## Purchasing & Materials (مشتريات وخامات)
| # | Item | Source | Status |
|---|------|--------|--------|
| P1 | طلبات شراء عاجلة | Nama | ⚪ |
| P2 | مين طلب خامات ستليكس | Nama | ⚪ |
| P3 | طلبات Site Survey | Nama / Vtiger | ⚪ |
| P4 | أسعار الخامات | Nama | ⚪ |
| P5 | مطابقة موردين (supplier reconciliation) → Reconciliation | Nama | ⚪ |
| P6 | مطابقة موردين تخطّت الأسبوع (overdue >1wk) → Reconciliation/Alerts | Nama | ⚪ |

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
| T9 | قوائم وتقارير مالية (financial statements & reports) | Nama / SQL | ⚪ |
| T10 | قرارات مالية (financial decisions) | new | ⚪ |
| T11 | مطابقة حركات البنوك مع نما (bank reconciliation) | bank feed + Nama | ⚪ |
| T12 | فواتير لم تُحصّل — لكل بنك (uncashed invoices per bank) | Nama | ⚪ |
| T13 | تحليلي مصروف (analytical expense breakdown) | Nama | ⚪ |

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
| H8 | عقود موظفين (employee contracts) | Nama | ⚪ |
| H9 | موظفين — خروج ودخول (employee entry / exit) | Nama | ⚪ |
| H10 | عقود عمل مطلوب تجديدها (contracts due for renewal) → Renewals | Nama | ⚪ |
| H11 | قيمة الرواتب المتوقعة للشهر (expected monthly payroll) | Nama | ⚪ |
| H12 | نسبة الإضافي للأساسي + السهر (overtime/basic ratio, night shift) | Nama | ⚪ |
| H13 | بلو-كولر / وايت-كولر — عدد وقيمة (blue vs white collar count & cost) | Nama | ⚪ |
| H14 | القيم المباشرة وغير المباشرة للموظفين (direct/indirect labor cost) | Nama | ⚪ |
| H15 | تكلفة الموظف الكلية (total loaded employee cost) | Nama | ⚪ |
| H16 | قيمة الانتقالات — الكلية + لكل موظف (transport cost total & per employee) | Nama | ⚪ |

## Marketing (تسويق)
| # | Item | Source | Status |
|---|------|--------|--------|
| MK1 | Social platforms (منصات التواصل) | external APIs | ⚪ |
| MK2 | المعارض المتوقعة — حسب الدولة (expected exhibitions by country) | new / research | ⚪ |
| MK3 | استبيانات آراء العملاء (customer feedback surveys) | Vtiger / new | ⚪ |
| MK4 | المنافسون (competitors) | new / research | ⚪ |
| MK5 | أسعار المنافسين (competitor prices) | new / research | ⚪ |

## Investments / Equity (استثمارات ومساهمات)
| # | Item | Source | Status |
|---|------|--------|--------|
| I1 | إسهامات / مساهمات (contributions / shareholdings) | Nama | ⚪ |

## Warehouse & Inventory (مخازن ومخزون)
| # | Item | Source | Status |
|---|------|--------|--------|
| WH1 | تسليم واستلام بضائع (goods delivery & receipt) | Nama | ⚪ |
| WH2 | مرتجعات مبيعات ومشتريات (sales & purchase returns) | Nama | ⚪ |
| WH3 | تقارير مخزون لحظية + غير المسجّل بعد (real-time stock incl. unposted) | Nama | ⚪ |
| WH4 | رواكد — مخزون راكد (slow-moving / dead stock) | Nama | ⚪ |
| WH5 | مرتجع بواقي أوردر (order-remnant returns) | Nama | ⚪ |
| WH6 | مخزن الاسكراب — زاد/نقص/تالف (scrap warehouse changes) | Nama | ⚪ |

## Logistics, Shipping & Customs (شحن وجمارك)
| # | Item | Source | Status |
|---|------|--------|--------|
| LG1 | شحنات على وصول (incoming / in-transit shipments) | Nama / new | ⚪ |
| LG2 | شحنات مطلوبة (required shipments) | Nama / new | ⚪ |
| LG3 | شحنات تحت التجهيز + عروض أسعار مشتريات + عروض شحن + طلب عرض سعر شحن | Nama / new | ⚪ |
| LG4 | نموذج 4 (Form 4 — customs / insurance) | new | ⚪ |
| LG5 | شحن داخلي (domestic shipping) | Nama / new | ⚪ |
| LG6 | مخلّصين (customs clearance agents) | new | ⚪ |
| LG7 | Cargo | new | ⚪ |
| LG8 | نافذة / Nafeza (national single window) | external portal | ⚪ |

## Safety / HSE (السلامة)
| # | Item | Source | Status |
|---|------|--------|--------|
| SF1 | إصابات عمل (work injuries) | Nama / new | ⚪ |
| SF2 | مهمات سيفتي — غسيل / نظافة (PPE / safety supplies) | Nama / new | ⚪ |

## Governance & Watchlist (حوكمة وقوائم حظر)
| # | Item | Source | Status |
|---|------|--------|--------|
| GV1 | Blacklist — موظف / مورد / عميل (cross-domain) | Nama / Vtiger | ⚪ |

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
| AC3 | أوراق مطلوب تجديدها (documents due for renewal) → Renewals | new | ⚪ |
| AC4 | إيجارات شارفت على الانتهاء (leases nearing expiry) → Renewals | Nama / new | ⚪ |
| AC5 | اشتراكات شارفت على الانتهاء (subscriptions nearing expiry) → Renewals | Nama / new | ⚪ |
| AC6 | الحراسة (security guarding / shifts) — ties to surveillance system | Nama / new | ⚪ |

## Operations & Production (عمليات وإنتاج)
| # | Item | Source | Status |
|---|------|--------|--------|
| OP1 | طلبات تجهيز — عند الغير (prep orders at third parties / subcontract WIP) | Nama | ⚪ |
| OP2 | Action plan — per job order / per batch (patch) | Nama / new | ⚪ |
| OP3 | إنتاجية صالة الإنتاج — يومي + نسبة الهالك (floor productivity/day + scrap rate) | Nama / new | ⚪ |
| OP4 | نسبة دقة تسعير أوامر الشغل (job-order pricing accuracy) | Nama | ⚪ |
| OP5 | التكلفة المتوقعة ↔ الفعلية لأوامر الشغل (expected vs actual cost) → Planned/Actual | Nama | ⚪ |
| OP6 | إجمالي ساعات تشغيل لكل آلة (machine running hours) | Nama / new | ⚪ |

## Legal (قانوني)
| # | Item | Source | Status |
|---|------|--------|--------|
| L1 | قضايا ونزاعات (legal cases & disputes) | new | ⚪ |

## Product / R&D (منتجات وتطوير)
| # | Item | Source | Status |
|---|------|--------|--------|
| PD1 | مقترح منتجات جديدة (new product proposals) | new | ⚪ |

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
