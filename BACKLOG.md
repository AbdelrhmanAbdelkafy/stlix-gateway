# Stlix Gateway — Backlog / Roadmap

> 🔗 **This file is live in the app.** Every row below is parsed into the ideas
> board at **`/tools/ideas`** (and `/api/v1/ideas`), where each item becomes a
> card with its own link, its connector readiness, and a deep link `#<id>`.
> **Add a row here → it appears there immediately, no code change.** Keep the
> table shape (`| ID | Item | Source | Status |`) and the id format (`S28`,
> `WH19`, …) so the parser picks it up.

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
| REP operations (custody · documents · movement) | data/rep — extracted verbatim from rep-system.html | 🟢 |

> Bank **balances**: Nama REST exposes no balance/report entity (verified).
> Real numbers require SQL (`chartbalance` / `JournalEntryLine`) or a Nama
> server-side report. Decision pending.

## Sales & Collection (مبيعات وتحصيل)
| # | Item | Source | Status |
|---|------|--------|--------|
| S1 | المبيعات: المخطط / الفعلي / كاش / آجل → Planned-vs-Actual | Nama | ⚪ |
| S2 | التحصيل اليوم: المخطط / الفعلي → Planned-vs-Actual | Nama | ⚪ |
| S3 | أداء مسؤولي المبيعات | Nama / Vtiger | ⚪ |
| S4 | عملاء غير نشطين | Vtiger / Nama | ⚪ |
| S5 | Chinese leads — عملاء محتملين | Vtiger Leads | ⚪ ⚠ needs a China/segment field or tag on leads first (currently 15 leads, `country` empty, no Chinese marker) |
| S6 | حصيلة مطلوبة (required collections / target receivables) → Planned-vs-Actual | Nama | ⚪ |
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
| S17 | العميل-المورد — مين بيشتري أكثر (dual customer/supplier: who buys more) | Nama | ⚪ |
| S18 | صافي وضع العميل مقابل المورد (net customer-vs-supplier position) | Nama | ⚪ |
| S19 | أقل سعر بيع لعميل معيّن — حدّ أدنى مبني على شراءنا منه (per-customer price floor) | Nama | ⚪ |
| S20 | أعلى مبيعات حسب القطاع/الصناعة (top sales by sector) | Nama | ⚪ |
| S21 | تحليلي مبيعات جغرافي (geographic sales analysis) | Nama | ⚪ |
| S22 | توصيات عملاء مقترحين بالـ AI (AI-suggested customers/leads) → AI | Vtiger / AI | ⚪ |
| S23 | مطالبات تمت في موعدها (demands completed on time) | Nama | ⚪ |
| S24 | طلبات تسجيلنا كمورد لدى عملاء (our vendor-registration applications at customers) | Nama / new | ⚪ |
| S25 | قوائم أسماء ومواصفات المنتجات للعملاء (product catalog to send customers) | Nama | ⚪ |
| S26 | تقرير المتاح للمبيعات يوميًا (daily availability report to sales) | Nama | ⚪ |
| S27 | المحصّل الذكي — مين نحصّل منه الأول وكام وترتيب اليوم (AI collection prioritizer) → AI | Nama / AI | ⚪ |

## Purchasing & Materials (مشتريات وخامات)
| # | Item | Source | Status |
|---|------|--------|--------|
| P1 | طلبات شراء عاجلة | Nama | ⚪ |
| P2 | مين طلب خامات ستليكس | Nama | ⚪ |
| P3 | طلبات Site Survey | Nama / Vtiger | ⚪ |
| P4 | أسعار الخامات | Nama | ⚪ |
| P5 | مطابقة موردين (supplier reconciliation) → Reconciliation | Nama | ⚪ |
| P6 | مطابقة موردين تخطّت الأسبوع (overdue >1wk) → Reconciliation/Alerts | Nama | ⚪ |
| P7 | أسعار الشراء المتوقعة — أقصى سعر مقبول (expected purchase price / ceiling) | Nama | ⚪ |
| P8 | توصيات شراء بالـ AI — خامات قرب تخلص (AI reorder recommendations) → AI | Nama / AI | ⚪ |
| P9 | مشتريات إجمالي/تفصيلي حسب المورد والمنطقة الجغرافية (by supplier & region) | Nama | ⚪ |
| P10 | مشتريات ومرتجعات تتطلب مطابقة فورية (immediate reconciliation) → Reconciliation | Nama | ⚪ |
| P11 | طلبات تسجيل موردين (supplier registration / onboarding requests) | Nama / new | ⚪ |
| P12 | طلبات شراء لاستليكس (Stlix purchase requests) | Nama | ⚪ |

## Treasury & Finance (خزينة ومالية)
| # | Item | Source | Status |
|---|------|--------|--------|
| T1 | أرصدة البنوك (أرقام) | SQL / report | 🟡 |
| T2 | شيكات في الخزينة لم تُحصّل + شيكات التزامات | Nama | ⚪ |
| T3 | التأمينات · الضرائب · المدفوعات الحكومية | Nama | ⚪ |
| T4 | التزامات متوقعة (expected obligations) → Renewals | Nama | ⚪ |
| T5 | فواتير ثابتة (recurring / fixed invoices) | Nama | ⚪ |
| T6 | فواتير بورتال (portal / e-invoicing — ETA?) | portal API / Nama | ⚪ |
| T7 | أسعار الصرف اللحظية — يوان / دولار / يورو (real-time FX) → Market-Feeds | external FX API | ⚪ |
| T8 | أقساط واجبة السداد (installments due) → Renewals | Nama | ⚪ |
| T9 | قوائم وتقارير مالية (financial statements & reports) | Nama / SQL | ⚪ |
| T10 | قرارات مالية (financial decisions) | new | ⚪ |
| T11 | مطابقة حركات البنوك مع نما (bank reconciliation) → Reconciliation | bank feed + Nama | ⚪ |
| T12 | فواتير لم تُحصّل — لكل بنك (uncashed invoices per bank) → Reconciliation | Nama | ⚪ |
| T13 | تحليلي مصروف (analytical expense breakdown) | Nama | ⚪ |
| T14 | أعمار الديون (AR / AP aging) | Nama | ⚪ |
| T15 | نقطة التعادل — المجموعة و Stlix (breakeven per entity) | Nama | ⚪ |
| T16 | الزكاة وأعمال الخير (zakat & charity) | Nama | ⚪ |
| T17 | أتعاب مهنية لغير الموظفين — مثال المحاسب القانوني (professional fees) | Nama | ⚪ |
| T18 | تكاليف غير منطقية (cost anomaly detection) → AI | Nama / AI | ⚪ |
| T19 | حسابات وسيطة مفتوحة (open suspense/intermediate accounts) | Nama | ⚪ |
| T20 | أعمار الالتزامات علينا (payables / liabilities aging) | Nama | ⚪ |
| T21 | Cash flow (التدفق النقدي) | Nama / SQL | ⚪ |
| T22 | بنود مسجّلة بشكل خاطئ على السيستم (mis-posted entries) → AI | Nama / AI | ⚪ |
| T23 | عدد الفواتير المراجَعة لكل مراجع (invoices reviewed per reviewer) | Nama | ⚪ |
| T24 | الحسابات المفضلة لاستلام تحويلات العملاء (preferred collection accounts) → enhances Banks connector | Nama | ⚪ |
| T25 | حسابات البنوك لدينا (our bank accounts) — ✅ built (banks connector) | Nama | 🟢 |
| T26 | إيصالات دفع (payment slips / receipts) — سند صرف/قبض قابل للطباعة | Nama | ⚪ |
| T27 | **العهدة** — رصيد افتتاحي يُعدّ باليد لا يُنقل من نما (رقم نما كاذب: 7.9M على E000004 سلّة لناس تانيين) · append-only · القرش وحدة الحساب (من REP) · **الداتا والتقرير الإداري live**: `/api/v1/rep/custody` + `/tools/rep` بتحذيرات المصدر نفسها — دفتر القيد الـappend-only لسه (كتابة) | REP / custody / Nama | 🟡 |
| T28 | **تحقق IBAN بـ MOD-97** — 18 حساب · 11 عدّوا · 3 تعارضات · `BankAccount.iban` في نما مش بيحمل IBAN (من REP) → Data-Quality | REP / banks | ⚪ |

## Maintenance (صيانة)
| # | Item | Source | Status |
|---|------|--------|--------|
| M1 | أعطال آلات ومعدات وأجهزة | Nama / new | ⚪ |
| M2 | الصيانات الدورية — سيارات / آلات / معدات (scheduled maintenance) | Nama / new | ⚪ |
| M3 | صيانة المباني (building maintenance) | Nama / new | ⚪ |

## Fleet (أسطول / سيارات)
| # | Item | Source | Status |
|---|------|--------|--------|
| FL1 | تكلفة السيارة — يوميًا / شهريًا (vehicle cost daily/monthly, TCO) | Nama | ⚪ |
| FL2 | تكلفة البنزين (fuel cost) | Nama | ⚪ |
| FL3 | تكلفة الصيانات (vehicle maintenance cost) | Nama | ⚪ |
| FL4 | **محرك الحركة** — 57% قرار تلقائي · دمج رحلات · تصعيد · يقول «ليه» (من REP) · 9 عربيات والعداد فاضي في الكل · **المحرك اتنقل** يشتغل فوق `/api/v1/rep/movement` في `/tools/rep` (الرحلات اليومية لكل متصفح لحد ما الكتابة تتفتح) | REP / movement | 🟢 |

## IT & Electronic Assets (أصول تقنية)
| # | Item | Source | Status |
|---|------|--------|--------|
| IT1 | تقارير الأجهزة الإلكترونية — موبايل / شاشة / كمبيوتر (device inventory & reports) | Nama / custody | ⚪ |

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
| H17 | الـ Outing / فعاليات الموظفين (staff outings & events) | new | ⚪ |
| H18 | متوسط العمر + العدد + المهام لكل موظف (workforce demographics & tasks/employee) | Nama | ⚪ |
| H19 | معدل دوران الموظفين (employee turnover rate) | Nama | ⚪ |
| H20 | الجزاءات لكل شهر (monthly penalties / deductions) | Nama | ⚪ |
| H21 | أداء العاملين (workers performance) | Nama | ⚪ |
| H22 | مشاكل الموظفين على نما (employee issues logged on Nama) | Nama | ⚪ |
| H23 | **قاموس المسميات الوظيفية** — 73 مسمّى في نما → 13 مسمّى معياري (من REP) | REP / Nama | ⚪ |
| H24 | **تنظيف أرقام موبايل الموظفين** — نما فيها 46 من 206 · 8 أرقام مكررة على 17 موظف · REP هو المصدر النظيف (D-10) → Data-Quality | REP / Nama | ⚪ |
| H25 | **محرك الجزاءات** — قانون 14/2025: م.139 ثمانية جزاءات فقط · م.138 مهلة 30 يوم · م.148 الفصل للمحكمة العمالية (من REP، اختُبر 7 سيناريو) | REP / regulations | ⚪ |
| H26 | **اللوائح الـ18** — صفر مصدّقة من المديرية (المادة 137) · النسخة لسه بتتعدل فماينفعش منطق يعتمد عليها | REP / regulations | ⚪ |
| H27 | **الأكاديمية** — 9 مسارات · 47 درس · القفل حسب مسار نما (من REP / نوشن) | REP / academy | ⚪ |
| H28 | **الوجبات** — معادلة 9ص · 37 وجبة · الفلتر الصحيح `employeeState=Working` (44 موظف) لا Other3 (من REP) | REP / attendance / meals | ⚪ |

## Marketing (تسويق)
| # | Item | Source | Status |
|---|------|--------|--------|
| MK1 | Social platforms (منصات التواصل) | external APIs | ⚪ |
| MK2 | المعارض المتوقعة — حسب الدولة (expected exhibitions by country) | new / research | ⚪ |
| MK3 | استبيانات آراء العملاء (customer feedback surveys) | Vtiger / new | ⚪ |
| MK4 | المنافسون (competitors) | new / research | ⚪ |
| MK5 | أسعار المنافسين (competitor prices) | new / research | ⚪ |
| MK6 | أخبار المنافسين (competitor news) | new / research | ⚪ |
| MK7 | أداء الويب سايت يوميًا (daily website performance) | analytics API | ⚪ |

## Investments / Equity (استثمارات ومساهمات)
| # | Item | Source | Status |
|---|------|--------|--------|
| I1 | إسهامات / مساهمات (contributions / shareholdings) | Nama | ⚪ |

## Warehouse & Inventory (مخازن ومخزون)
| # | Item | Source | Status |
|---|------|--------|--------|
| WH1 | تسليم واستلام بضائع (goods delivery & receipt) | Nama | ⚪ |
| WH2 | مرتجعات مبيعات ومشتريات (sales & purchase returns) | Nama | ⚪ |
| WH3 | تقارير مخزون لحظية + غير المسجّل بعد (real-time stock incl. unposted) → Live-vs-Pending | Nama | ⚪ |
| WH4 | رواكد — مخزون راكد (slow-moving / dead stock) | Nama | ⚪ |
| WH5 | مرتجع بواقي أوردر (order-remnant returns) | Nama | ⚪ |
| WH6 | مخزن الاسكراب — زاد/نقص/تالف (scrap warehouse changes) | Nama | ⚪ |
| WH7 | أصناف مسحوبة على المكشوف (negative / oversold stock) | Nama | ⚪ |
| WH8 | أصناف مكررة (duplicate item master) → data quality | Nama | ⚪ |
| WH9 | تقارير جرد تفصيلي (detailed stocktake reports) | Nama | ⚪ |
| WH10 | تنبيه جرد عشوائي يختاره الـ AI (AI-chosen random spot-count) → AI | Nama / AI | ⚪ |
| WH11 | تنبيه الجرد الدوري (periodic stocktake reminder) → Renewals/Alerts | Nama | ⚪ |
| WH12 | كميات الأصناف المنصرفة من كل مخزن (issued qty per warehouse) | Nama | ⚪ |
| WH13 | تأكيد آخر اليوم — فعلي مقابل دفتري ثم يغذّي الجرد الدوري تاني يوم (EOD actual-vs-book → next-day stocktake) | Nama | ⚪ |
| WH14 | متابعة لايف لمعاملات لم تُسجّل/لم تُعتمد + عدّ العهد (live unposted/unapproved incl. custody) → Live-vs-Pending | Nama | ⚪ |
| WH15 | كمية الأصناف في المخزن (stock quantities on hand) | Nama | ⚪ |
| WH16 | قائمة الكميات بأكبر وحدة (quantities in largest unit) | Nama | ⚪ |
| WH17 | أسماء الأصناف المكررة (duplicate item names) → data quality | Nama | ⚪ |
| WH18 | الوحدات الخطأ (wrong units of measure) → data quality | Nama | ⚪ |

## Logistics, Shipping & Customs (شحن وجمارك)
| # | Item | Source | Status |
|---|------|--------|--------|
| LG1 | شحنات على وصول (incoming / in-transit shipments) → Live-vs-Pending | Nama / new | ⚪ |
| LG2 | شحنات مطلوبة (required shipments) | Nama / new | ⚪ |
| LG3 | شحنات تحت التجهيز + عروض أسعار مشتريات + عروض شحن + طلب عرض سعر شحن → Live-vs-Pending | Nama / new | ⚪ |
| LG4 | نموذج 4 (Form 4 — customs / insurance) | new | ⚪ |
| LG5 | شحن داخلي (domestic shipping) | Nama / new | ⚪ |
| LG6 | مخلّصين (customs clearance agents) | new | ⚪ |
| LG7 | Cargo | new | ⚪ |
| LG8 | نافذة / Nafeza (national single window) | external portal | ⚪ |
| LG9 | **CargoX Document Creator & Validator** — إنشاء مستندات الشحن (فاتورة · قائمة تعبئة · شهادة منشأ · B/L) والتحقق منها **قبل** الرفع على CargoX/ACID، + شات بوت بيسأل عن الناقص ويكمّله. الرفض بعد الرفع بيكلّف وقت ورسوم — الفحص محلّه قبل الإرسال | Nama / external portal / ai | ⚪ |
| LG10 | **شهادة الجودة للاستيراد** — مولّد شهادة جودة للصلب (Foshan Amax Pro): رقم الشهادة والعقد · المشتري · شروط التسليم · المواصفة ونوع الصلب · جداول المواصفات والخواص الميكانيكية · لوجو وختم وQR | front-end | 🟢 شغّال أوفلاين على `/tools/certificate` — البيانات بتتكتب بالإيد، مش متربطة بنما لسه |

## Safety / HSE (السلامة)
| # | Item | Source | Status |
|---|------|--------|--------|
| SF1 | إصابات عمل (work injuries) | Nama / new | ⚪ |
| SF2 | مهمات سيفتي — غسيل / نظافة (PPE / safety supplies) | Nama / new | ⚪ |

## Governance & Watchlist (حوكمة وقوائم حظر)
| # | Item | Source | Status |
|---|------|--------|--------|
| GV1 | Blacklist — موظف / مورد / عميل (cross-domain) → Watchlist | Nama / Vtiger | ⚪ |
| GV2 | عمل إيه على نما يوميًا — سجل نشاط المستخدمين (daily user activity/audit) | Nama / SQL | ⚪ |

## Communications (تواصل)
| # | Item | Source | Status |
|---|------|--------|--------|
| CM1 | إيميلات تم / لم يتم الرد عليها (emails answered vs unanswered) | Email / IMAP | ⚪ |
| CM2 | Tickets — التذاكر (support / helpdesk) | Vtiger | ⚪ |
| CM3 | مكالمات ورسائل الموظفين — خطوط الشركة (staff calls/messages, company lines) | telco / new | ⚪ |
| CM4 | الكول سنتر (call center) → registered system `callcenter` | new | ⚪ |
| CM5 | الشكاوي (complaints) — تسجيل/تتبع/تصعيد شكاوى العملاء والموظفين | Vtiger / new | ⚪ |
| CM6 | الاقتراحات (suggestions) — صندوق اقتراحات + تتبع الحالة | Vtiger / new | ⚪ |

## Attendance (حضور وبصمة) — connector live
| # | Item | Source | Status |
|---|------|--------|--------|
| AT1 | البصمة الإلكترونية للشركتين (electronic fingerprint, both legal entities) | Nama | ⚪ |
| AT2 | البصمة الشخصية / الموبايل (personal / mobile fingerprint) | Nama / app | ⚪ |

## Market Data & Rates (بيانات السوق والأسعار)
| # | Item | Source | Status |
|---|------|--------|--------|
| MD1 | أسعار الذهب (gold prices) → Market-Feeds | external API | ⚪ |
| MD2 | البترول بالبرميل (oil per barrel) → Market-Feeds | external API | ⚪ |
| MD3 | المحروقات (fuel prices / consumption) → Market-Feeds | external / Nama | ⚪ |
| MD4 | توقعات أسعار الجنيه (EGP forecast) | external / AI | ⚪ |
| MD5 | أسعار الصرف اللحظية (FX) — نفس T7 → Market-Feeds | external FX API | ⚪ |

## Quality (جودة / QC)
| # | Item | Source | Status |
|---|------|--------|--------|
| Q1 | الاختبارات / QC / الشهادات (tests, QC, certificates) | Nama / new | ⚪ |

## Admin & Compliance (شؤون إدارية وامتثال)
| # | Item | Source | Status |
|---|------|--------|--------|
| AC1 | التأشيرات — تنبيه تجديد (visas, renewal alerts) → Renewals | new | ⚪ |
| AC2 | التراخيص والسجلات والمرور (licenses, registers, traffic) → Renewals | new / Nama | ⚪ |
| AC3 | أوراق مطلوب تجديدها (documents due for renewal) → Renewals | new | ⚪ |
| AC4 | إيجارات شارفت على الانتهاء (leases nearing expiry) → Renewals | Nama / new | ⚪ |
| AC5 | اشتراكات شارفت على الانتهاء (subscriptions nearing expiry) → Renewals | Nama / new | ⚪ |
| AC6 | الحراسة (security guarding / shifts) — ties to surveillance system | Nama / new | ⚪ |
| AC7 | **الكيانات القانونية الثلاثة** — 01 المجموعة المصرية · 02 ستليكس فالي · 005 STLIX GLOBAL HOLDING (من REP) — الفواتير فيها `legalEntity` فالتقارير محتاجة تعرفهم | REP / Nama | ⚪ |
| AC8 | **كتالوج كيانات نما — 599 كيان** (من REP) — عندنا قراءة عامة لأي كيان بس مافيش كتالوج يقول فيه إيه | REP / Nama | ⚪ |
| AC9 | **قوالب المستندات الموقَّعة السبعة** (من REP) — استلام/تسليم عهدة وعربية وغيرها، قابلة للطباعة بكود `PFX-YYYYMMDD-NNN` · **مبنية**: `/api/v1/rep/documents` + توليد وطباعة في `/tools/rep` — التوقيع يدوي على الورق لحد ما PA5 (ECDSA) تتبني | REP / gateway | 🟢 |

## Operations & Production (عمليات وإنتاج)
| # | Item | Source | Status |
|---|------|--------|--------|
| OP1 | طلبات تجهيز — عند الغير (prep orders at third parties / subcontract WIP) | Nama | ⚪ |
| OP2 | Action plan — per job order / per batch (patch) | Nama / new | ⚪ |
| OP3 | إنتاجية صالة الإنتاج — يومي + نسبة الهالك (floor productivity/day + scrap rate) | Nama / new | ⚪ |
| OP4 | نسبة دقة تسعير أوامر الشغل (job-order pricing accuracy) | Nama | ⚪ |
| OP5 | التكلفة المتوقعة ↔ الفعلية لأوامر الشغل (expected vs actual cost) → Planned/Actual | Nama | ⚪ |
| OP6 | إجمالي ساعات تشغيل لكل آلة (machine running hours) | Nama / new | ⚪ |
| OP7 | تكلفة الطن للصنف — شاملة الـ overhead (cost/ton incl. overhead) | Nama | ⚪ |
| OP8 | إنتاجية نما — ساعات التشغيل خلال اليوم (production hours logged/day) | Nama | ⚪ |
| OP9 | خطة تشغيل استليكس اليومية (daily production/operating plan) | Nama / new | ⚪ |

## Travel & Personal (سفر — خاص بالمالك)
| # | Item | Source | Status |
|---|------|--------|--------|
| TR1 | Tracker سفريات — وقت / تكلفة / أهداف (owner-personal) | new | ⚪ |
| TR2 | قائمة مشتريات السفر (travel purchases list) | new / Nama | ⚪ |
| TR3 | Checklist (travel / ops checklist) | new | ⚪ |

## Legal (قانوني)
| # | Item | Source | Status |
|---|------|--------|--------|
| L1 | قضايا ونزاعات (legal cases & disputes) | new | ⚪ |
| L2 | **المستشار القانوني** — شات بيجاوب من الدساتير والقوانين المصرية والدولية، بيكتب عقود، بيراجع لوائح وصيغ · **مبني**: `/tools/legal` + `/api/v1/legal/*` | legal / gateway | 🟢 |
| L3 | **حارس أرقام المواد** — كل «مادة N» في أي ردّ بتتفحص ضد النصّ المحمّل: موجودة تعدّي، مش موجودة تتشال، قانونها مش محمّل يتعلّم عليها. رقم مادة مخترع أخطر من أي رقم فلوس غلط | legal / gateway | 🟢 |
| L4 | **`/verify` — افحص أي نص** حتى لو مش إحنا اللي كتبناه (مسودة الطرف التاني · عقد قديم · بند جاي على واتساب). من غير موديل خالص | legal / gateway | 🟢 |
| L5 | **صيغ المستندات** — عقد عمل · NDA · شراء دولي · توريد محلي · إنذار · محضر مجلس. الفراغ اللي ماتملاش بيفضل ظاهر ⟨كده⟩، وكل صيغة بتقفل بقايمة «لازم يتراجع بشريًا» | legal / gateway | 🟢 |
| L6 | **تحميل نصوص القوانين** — المحرّك مبني والمجلد فاضي. المطلوب: المدني · التجاري · العمل · الشركات · العقوبات · الجمارك · الضرايب · الخدمة المدنية · الدستور · المدني الصيني · CISG · إنكوترمز · نيويورك | legal | 🟡 |
| L7 | **رفع عقودنا الموقّعة كسوابق** (tier: precedent) — الإيجارات والتأسيس وعقد فوشان موجودين في الدرايف · «إحنا كتبنا البند ده إزاي قبل كده» | legal / archive | ⚪ |
| L8 | **اللوائح الـ18 كـ tier: internal** — وصفر منها مصدّق من المديرية (من REP)، فلائحة الجزاءات مش نافذة | legal / REP | ⚪ |
| L9 | مراجعة العقود مقابل قانون العمل الجديد — بند بند، والباطل يتقال إنه باطل ولو موقّع عليه | legal / ai | ⚪ |
| L10 | تنبيه انتهاء العقود والتراخيص → see Renewals engine | legal / Nama | ⚪ |

## Product / R&D (منتجات وتطوير)
| # | Item | Source | Status |
|---|------|--------|--------|
| PD1 | مقترح منتجات جديدة (new product proposals) | new | ⚪ |
| PD2 | **مساعد المهندس** — خزانات وأوعية (سُمك ASME) · مواسير صحية · ليزر وتشكيل · مبادلات · حصر BOM | front-end | 🟢 شغّال أوفلاين على `/tools/engineer` — الحصر لسه بيتنسخ بالإيد، مش متربط بأصناف نما |

## Management & Planning (إدارة وتخطيط)
| # | Item | Source | Status |
|---|------|--------|--------|
| G1 | توجهات / أفكار (directions / ideas board) | new | ⚪ |
| G2 | قرارات إدارية (administrative decisions) | new | ⚪ |
| G3 | How healthy are we? — مؤشر صحة الشركة (executive health score) → AI | all | ⚪ |

## Platform & AI (north star)
| # | Item | Notes |
|---|------|-------|
| A1 | Enterprise platform, AI-based | Layer 4 AI Orchestrator over the gateway: query/act across all connectors via natural language; the unifying vision. |
| A2 | Nama NameBuilder | Use Nama's NameBuilder to define custom entities/screens → new connectors read them via the same REST (enabler for custom modules: maintenance, custody, forms…). |
| A3 | مدير مبيعات ذكي (AI sales manager) | AI agent over CRM+Nama: prioritize leads, nudge follow-ups, forecast — part of the enterprise platform. |
| A4 | **Nama Expert** — شات خبير بيحلّ المشاكل: تسأله عن نما أو عن المنصّة، يجاوب من الخريطة والوثائق والعقود، مش من حفظه · **مبني**: `/tools/expert` + `/api/v1/expert/*` | ai / gateway / nama | 🟢 |
| A5 | **مصادر معرفة الخبير** — `/api/v1/map` (المنصّة بتوصف نفسها) · `/tools/library` (وثائق الريبو) · قواعد الكتابة المقيسة من REP · مشاريعنا هنا — **كلها مفهرسة**؛ الناقص كتالوج الـ599 كيان (OpenAPI) | ai / gateway / nama / REP | 🟡 |
| A6 | **صوّر واسأل** — ترفع سكرين شوت من نما فيه الإرور، الخبير يقراه ويقول السبب والحل · **مبني** (لصق/سحب/اختيار ملف → الجيتواي → الموديل) | ai / gateway | 🟢 |
| A7 | **كلّمه بالصوت** — سؤال وجواب بالعربي المصري صوتيًا (نفس قدرة UX3) · **مبني** بـ Web Speech API (`ar-EG`) — مورّد صفر ومفتاح صفر | ai / voice / gateway | 🟢 |
| A8 | **كل إجابة بمصدرها** — الخبير يقول جوابه جه منين (endpoint · وثيقة · كيان)، و«مش عارف» إجابة مقبولة. إجابة من غير مصدر = نفس فخّ الرقم المكتوب بالإيد · **مفروضة في التصميم**: من غير موديل بيرجّع المقاطع بس، ومع موديل بيتعلّم عليه `[S#]` ولو جاوب من غير استشهاد الردّ نفسه بيقول كده | ai / gateway | 🟢 |
| A9 | **الخبير يقترح ولا ينفّذ** — أي كتابة يقترحها تعدّي على workflow مدقّق + توقيع بشري (Layer 5 + توقيع REP) · القاعدة مكتوبة في تعليمات الخبير، وآلية التوقيع نفسها لسه (PA5) | ai / gateway / REP | 🟡 |

## Platform UX & Input (تجربة الاستخدام والإدخال — عابر لكل الموديولات)
Cross-cutting front-end helpers — apply to every module's text inputs, not one screen.
| # | Item | Source | Status |
|---|------|--------|--------|
| UX1 | Autocomplete + تصحيح تلقائي في textboxes — أول تطبيق: بحث النوع/الوصف في **name-builder** (اقتراح أثناء الكتابة + تصحيح أخطاء إملائية) | front-end / KB | 🟡 خانة بحث النوع: ✅ (fuzzy/Levenshtein + تطبيع عربي + منسدل بالكيبورد). باقي: خانة الوصف الحر + مدخلات باقي الموديولات |
| UX1b | **name-builder — إدخال الاسم الكامل**: المستخدم يكتب الاسم كله → validator يعمل autocorrect + autocomplete على كل جزء → بناء الكود → فحص التكرار في نما → **رفض لو مكرر** (end-to-end من نص حر لصنف مقبول أو مرفوض) | front-end + `/nama/invitem/exists` | ⚪ (الأساس جاهز: المحلّل المحلي + dedup endpoint) |
| UX2 | Transcript — خيار تفريغ نصّي في أي مدخل كتابة (لصق/تحرير نص طويل) | front-end | ⚪ |
| UX3 | صوت → كتابة + **بحث صوتي بالعربي** في كل مدخلات النص والبحث · **مبني**: `/tools/voice.js` بيتحقن في كل صفحة من الاتنين رِندرر — مايك واحد بيكتب في الحقل اللي معاه الفوكس، أو في مربع البحث بتاع الصفحة | front-end / voice | 🟢 |
| UX4 | Widgets — عناصر لوحة قابلة للتخصيص والإطلاق على الـ Unified Workspace ("طلعلي") | gateway workspace | ⚪ |

## Platform & Access (منصّة وصلاحيات — عابر للمنصّة كلها)
Cross-cutting platform capabilities — apply everywhere, not one screen. **Every feature/report/action is gated twice: by the API connector's own permissions AND by the logged-in user's role/permissions (RBAC).**
| # | Item | Source | Status |
|---|------|--------|--------|
| PA1 | **Omnichannel comms** — المنصّة بتتواصل بكل القنوات: واتساب · وي شات · وغيرها (send/receive عبر الجيتواي) | WhatsApp/WeChat APIs + gateway | ⚪ |
| PA2 | **SSO** — دخول موحّد (Single Sign-On) | IdP (Google Workspace / OAuth) | ⚪ |
| PA3 | **RBAC** — صلاحيات المستخدم الداخل + احترام صلاحيات كل connector (بوابة مزدوجة) | gateway auth + connectors | ⚪ |
| PA4 | بحث/كتابة بالصوت بالعربي عبر كل المنصّة · **مبني** — نفس الطبقة، Web Speech API بتاعة المتصفح: مافيش مفتاح ومافيش مورّد ومافيش فاتورة. Ctrl+M · ar-EG/en-US | front-end / voice | 🟢 |
| PA5 | **التوقيع الرقمي كآلية HITL** — ECDSA P-256 · `extractable:false` · المفتاح الخاص مايسيبش الجهاز · اختُبر بـ4 هجمات كلها مرفوضة (من REP) — دي آلية الموافقة البشرية اللي Layer 5 محتاجها | REP / gateway | ⚪ |
| PA6 | **الدور يُحسَب لا يُعطَى** — «مين انت» × «حالة الحاجة» = دورك، بدون شاشة إدارة أدوار (من REP D-07) | REP / idp | ⚪ |
| PA7 | **ثلاثة أسطح — السطح يتبع البيئة مش الهوية** — داكن للمكتب · فاتح للمخزن (الداكن مش مقروء في الشمس) · ورقي للطباعة (من REP D-06) | REP / front-end | ⚪ |
| PA8 | 🔴 **تغيير مفتاح نما الأدمن بتاع REP** — اعتماد منفصل عن مفاتيح الجيتواي (بصمة مختلفة) ومكشوف plaintext في حزمة REP · ومفتاح مزامنة الجرد مشترك بين الاتنين | REP / gateway | ⚪ |

## Registered systems
> ⚠️ **مش هنا.** الخريطة الحيّة للأنظمة بقت في الكود: [`/systems`](/systems) —
> وكل نظام بيقول كام متطلب مستنيه وأي كنكتور بيغذّيه. القائمة اللي كانت هنا
> كانت نص حر مالوش أي ربط بالمتطلبات، وكانت لسه بتقول إن الجرد "مش مبني"
> بعد ما بقى كنكتور حيّ.

**كل نظام على الخريطة بقى وراه متطلب واحد على الأقل** — أضعفهم: التسكين (`housing`)
والتغذية (`meals`) شايلين متطلب واحد بس بينهم (H15 تكلفة الموظف الكلية). التغذية
تحديدًا هي **هدف مشروع البصمة** — يعني غالبًا ناقصها سطور خاصة بيها هنا، مش نظام زيادة.
