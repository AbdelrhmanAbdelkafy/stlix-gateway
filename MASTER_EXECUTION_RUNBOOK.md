# MASTER EXECUTION RUNBOOK — المرجع الرئيسي

> **ابدأ من هنا في أي شات جديد.** ده المرجع الكامل لتشغيل وإكمال المنصّة بدون فقد سياق.
> اقرأ بعده: `SESSION_STATE.json` (حالة مُهيكلة) · `HANDOFF.md` (آخر جلسة) · `NEXT_STEP.md` (المهمة التالية) · `TASKS.md` · `DECISIONS.md` · `CHANGELOG.md`.

---

## 0) نظرة سريعة
**Stlix Gateway** = نقطة تكامل واحدة (FastAPI) تربط كل أنظمة الشركة من باب واحد.

> ⚠️ **تسمية (مهم):** المالك بيقول **الهَب (hub)** و**الجيتواي (gateway)** و**المنصّة (platform)** — **كلها اسم واحد لنفس المشروع ده**. أي شات جديد: ماتدوّرش على مجلد تاني فيه كلمة platform؛ المشروع هنا فقط.

- المكان: `D:\Nama Code project\stlix-gateway` · **git محلي فقط**.
- كلّم المالك بالعربي المصري.
- المبدأ: قراءة أولًا · مفاتيح server-side · بوابة مزدوجة (كنكتور + مستخدم) · ERP=مصدر الحقيقة · AI مايكتبش مباشرة · كل كتابة عبر workflow مدقّق.

## 1) التشغيل
```bash
# شغّل السيرفر (preview) باسم:
stlix-gateway        # uvicorn app.main:app على 127.0.0.1:8000 (بدون --reload)
```
- **أعِد التشغيل بعد أي تعديل Python / registry / config.** ملفات HTML/JS في `modules/` بتتقري fresh كل طلب (مش محتاجة restart).
- venv: `.venv` (Python 3.14). الاختبارات: `.venv/Scripts/python.exe -m pytest -q` → **136 passing**.
- الأسرار في `.env` (gitignored). نسخة احتياطية للمفاتيح: `secrets/gates-keys.backup.md`.

## 2) الصفحات (افتحها في المتصفح)
| الرابط | إيه هو |
|---|---|
| `/tools/platform` | **الهَب الموحّد** — نقطة الدخول · أرقامه كلها حيّة من `/api/v1/map` · 26 كارت دومين بيوصّلوا للوحة مفلترة |
| `/tools/platform/public` | **الهَب — العرض العام** — نفس الأرقام بالظبط من نفس الوصلة، بتفاصيل داخلية أقل |
| `/api/v1/map` | **الخريطة الموحّدة** — أنظمة × كنكتورات × endpoints × متطلبات × محرّكات في رد واحد |
| `/tools/ideas` | **لوحة الأفكار** — كل متطلب مربوط بنظامه وكنكتوره و**الـ endpoints اللي فيها داتاه الخام** · فلاتر بالـ URL |
| `/tools/finance-reports` | **التقارير المالية الحقيقية** (100% من SQL) — الواجهة المالية الإنتاجية |
| `/tools/finance-os` | **الكوكبيت** — كل قسم من endpoint حيّ: عملاء · موردين · بنوك · فواتير مشتريات · قيود يومية · تحصيلات · مدفوعات · وتاب «مستني إيه» |
| `/tools/name-builder` | إنشاء الأصناف (قراءة) |
| `/tools/engineer` | **مساعد المهندس** — خزانات (سُمك ASME) · مواسير · ليزر · مبادلات · حصر BOM (أوفلاين) |
| `/tools/library` | وثائق المشروع نفسها (الرَنبوك · القرارات · الرؤية) من جوّه المنصّة |
| `/systems` · `/systems/{key}` | خريطة الأنظمة — وكل نظام بيقول كام متطلب مستنيه |
| `/connectors` · `/connectors/{key}` | كل كنكتور + وضعه + **اللي مستنيه** |
| `/api/v1/workspace` · `/metrics` · `/health` | اللوحة/المراقبة/الصحة |

**كله مربوط في الاتجاهين:** من الهَب → الدومين → الفكرة → الـ endpoint → القسم في اللوحة → ورجوع.
أي صفحة API بتقول فوقها: الأفكار اللي بتتغذّى منها · الكنكتور · النظام.

## 3) البنية — 6 طبقات
1. **Gateway** ✅ · 2. **Connectors** (6 حيّة + 3 داخلية) · 3. **Unified Workspace** ✅ (8 أقسام) ·
4. **AI Orchestrator** ⚪ · 5. **Workflows/Write** ⚪ · 6. **Logs/Monitoring/Security** ✅.

## 4) الكنكتورات (كلها read-only)
`nama` (ERP) · `sql` (الأرصدة الحقيقية) · `attendance` (بصمة) · `crm` (Vtiger) · `banks` · `inventory` (الجرد).
**النمط:** `app/integrations/<key>/{client,connector,router}.py` → سجّل في `main.py` + `registry.py`
+ **`catalog.py` (الكنكتور والـ endpoints بتاعته)** + `workspace/providers.py` + test. سكافولد في `templates/`.
> الخطوة الجديدة هي `catalog.py`، ومن غيرها `tests/test_catalog.py` بيقع — وده مقصود:
> مايبقاش فيه endpoint شغّال ومش على الخريطة، ولا خريطة بتوعد بحاجة مش موجودة.

## 5) 🎯 الأرصدة الحقيقية (المحور المهم)
> **إيه اللي لحظي فعلًا؟** نما REST **حيّة**: الموظفين · العملاء · الفواتير كمستندات · البنوك ·
> الـ CRM · الجرد · و**التحصيلات والمدفوعات** (`ReceiptVoucher`/`PaymentVoucher`).
> اللي **مش لحظي** = أي **رصيد محسوب** (AR/AP/KPIs) — دي من نسخة مُرستَرة.
> **ليه:** REST مابتدّيش أرصدة، و**SQL السحابي مقفول** (tcp/1433 و1434 timeout — مقيس).
> **عمر البيانات ظاهر دلوقتي** في كل رد مالي (`freshness.as_of` / `age_days` / `stale`).

- **نما REST مابيدّيش أرصدة** (CRUD كيانات فقط — اتأكد من OpenAPI). الحل: **SQL مباشر**.
- **الجيتواي بيقرأ من نما SQL**: connector `app/integrations/finance/` (pyodbc, read-only).
  - الاتصال في `.env`: `NAMA_SQL_SERVER=localhost` · `NAMA_SQL_DATABASE=NAMA_TEST` · `NAMA_SQL_USER=stlix_gw` · `NAMA_SQL_PASSWORD=***` · driver `ODBC Driver 17 for SQL Server` (Encrypt=yes;TrustServerCertificate=yes).
  - login `stlix_gw` = read-only (db_datareader). أُنشئ عبر SSMS: `CREATE LOGIN stlix_gw ... ; CREATE USER ... ; ALTER ROLE db_datareader ADD MEMBER stlix_gw`.
  - Endpoints: `/api/v1/finance/kpis` · `/customers` · `/suppliers` → أرقام حقيقية.
- **الأرقام (as-of 2026-07-14):** 549 عميل · 586 مورد · مبيعات 329.9M · AR 20.0M · مشتريات 320.0M · AP 186.7M.
- **الأرقام اللحظية (`?source=live`):** بتتبني من مستندات نما REST — الصافي من `details[].price.netValue`
  والمحصّل من `externalPaymentLines[].paymentValue`. اللقطة بتتبني في الخلفية (~8 دقايق / ~14,000 مستند):
  `POST /api/v1/finance/live/refresh` ثم `GET /api/v1/finance/live`.
- **`FINANCE_DEFAULT_SOURCE`** (في `.env`) بيحدّد مصدر `/api/v1/finance/*` لما مافيش `?source=`.
  بينزل `sql`. **ماتقلبهاش `live` قبل ما `scripts/reconcile_live_vs_sql.py` يعدّي على الجهاز ده.**
- **`scripts/reconcile_live_vs_sql.py`** — المطابقة مستند بمستند، وبترجّع exit 1 لو فيه فرق مش مفسَّر:
  `--rest local` (نفس الداتا → صفر فرق مسموح) · `--rest cloud` (السداد بعد النسخة مفسَّر، غيره لأ).
- **حارس الانحراف** — بعد كل مسح، شهر **مقفول** بيتطابق تاني مع SQL. الثابت في الشهر المقفول
  = **مجموعة المستندات + إجمالي وصافي كل مستند**؛ المحصّل بيكبر طبيعي (فاتورة مايو بتتسدّد
  في يوليو) فمابيتعدّش انحراف. يعني الحارس بيمسك: حقل نما اتغيّر · صلاحية ضاقت · مسودّة
  دخلت المُرحَّل — وماينرّش على الفاضي.
  - `freshness.guard{status, reason, period, checked_at}` في كل رد مالي · التفاصيل الكاملة
    في `GET /api/v1/finance/live` · فحص فوري `POST /api/v1/finance/live/guard`.
  - **`drift`** بيرجّع الافتراضي لـ`sql` **وبيقول إنه عمل كده وليه**. `?source=live` الصريح
    بيفضل شغّال — دي الطريقة اللي بيها تبصّ على اللي باظ.
  - **`unknown` مابيحوّلش** (مافيش SQL / أول إقلاع / انقطاع). إنك مش قادر تفحص ≠ الرقم غلط.
  - الإعدادات: `FINANCE_GUARD_ENABLED` · `FINANCE_GUARD_PERIOD` · `FINANCE_ALLOWED_REVERSALS`.
- **قلب المقارنة في `app/integrations/finance/reconcile.py`** — السكربت والحارس بيستدعوا
  نفس الكود. نسختين من «إيه اللي يعتبر فرق» كانوا هيختلفوا، واللي يهم منهم هو اللي محدش بيقراه.
- **أرصدة البنوك مؤجّلة** (محتاجة GL — مش مُرحّل بالكامل في الـ backup الحالي).
- **التحديث (freshness):** البيانات = آخر `.bak` مُرستَر. نسخ يومية على Google Drive folder `1yvCI6unRWALtzf1yiU9kiHAPaBB56Xtt/full` (`hardsteel<date>.bak`). **مفيش قراءة للـ .bak وهو على الدرايف** — لازم download + `RESTORE DATABASE`. الأتمتة = سكربت ليلي (شوف NEXT_STEP).
- بديل رسمي (اختياري): تقرير من نماسوفت — `docs/nama-balance-report-spec.md`.

## 6) استكشاف نما مباشر (للـ debugging)
- عبر MCP **`LOCALERP`**: `mcp__LOCALERP__nama_local_sql_query` (SELECT قراءة فقط على `NAMA_TEST`، user `claude_ro`). استخدمه لاستكشاف الـ schema/الأرقام بدون ما تلمس الجيتواي.
- استعلامات جاهزة: `docs/live-balance-queries.sql`.

## 7) حقائق نما (gotchas)
- API = CRUD فقط (`/{Entity}/{list,findByIdOrCode,save,delete}`). عقد كل كيان: `/erp/browseapi/openapi/{Entity}.json` (فيه trailing commas — parse بتساهل).
- **الـ400 معناها حاجتين مختلفتين** — والخلط بينهم كان بيضيّع داتا حيّة:
  - **بودي فاضي** = فلتر صحيح مالوش نتيجة → `find_first` بترجّع None.
  - **بودي فيه records** = **نجاح جزئي**: بعض السجلات فشلت والباقي راجع فعلًا.
    `_handle()` بتحتفظ بيه وبتوسمه `_partial{returned, failed}`.
    ده اللي كان مخفي `ReceiptVoucher` و`PaymentVoucher` (التحصيلات والمدفوعات اللحظية).
- **`records_count` بتاع الصفحة مش الإجمالي.** paging: `startPage` (يبدأ من 1) + `pageSize` (لحد 1000).
- **`@draft`** في آخر كود المستند = **غير مُرحَّل**. لازم يتفلتر قبل أي مجموع فلوس.
- `textCriteria`: `field,Equal,value,AND;` — operator case-sensitive (`Equal` بس). التواريخ `DD-MM-YYYY`.
- أرصدة العملاء/الموردين من `SalesInvoice`/`PurchaseInvoice` (`total`/`totalPaid`/`remaining`) JOIN `Customer`/`Supplier` على `customer_id`/`supplier_id`.

## 8) إزاي تكمّل (نمط الشغل)
- **موديول front-end:** `modules/<name>/*.html` + route في `app/routers/tools.py` عبر `_serve()` (بيحقن `__GATEWAY_API_KEY__`). يستدعي endpoints الجيتواي بـ `X-API-Key`.
- **تقرير/endpoint:** أضف method في الـ connector + endpoint في الـ router بـ `respond()` (HTML+JSON).
- **كتابة (write):** اقلب الكنكتور `read_write` **عمدًا**، خلف workflow مدقّق + HITL.
- **بعد أي تعديل:** `pytest -q` → restart preview → verify live.

## 8b) الأفكار والمتطلبات (181 بند) — والخريطة اللي بتربطهم
- **مصدر الحقيقة `BACKLOG.md`** — سطر markdown لكل فكرة. `app/ideas/registry.py` بيقراه ويطلّع:
  الدومين · المصدر · الحالة · المحرّك · **جاهزية الكنكتور**. **ضيف سطر → يظهر في اللوحة فورًا** (مفيش كود).
  > ⚠️ **بس الاختبارات بتطلب سطر في `app/ideas/wiring.py` كمان.** اللوحة بتشتغل من غيره (بيرث
  > `DOMAIN_DEFAULTS`)، لكن `test_graph.py` بيقع لحد ما الفكرة تقول *بالظبط* إيه اللي ناقصها.
  > ده مقصود: فكرة على اللوحة من غير "ناقص إيه" واضحة بتفضل قاعدة من غير ما حد يعرف يبدأ منين.
- **الجاهزية:** `done` اتعمل · `ready` كل كنكتوراته موجودة (محتاج تقرير بس) · `partial` ناقص جزء · `blocked` محتاج تكامل جديد.
- **الأرقام دلوقتي (183 متطلب):** 2 اتعملوا · **107 كنكتورها جاهز** · 45 ناقص جزء · 29 محتاج تكامل جديد.
- أكتر الكنكتورات الناقصة طلبًا: نظام جديد (47) · API خارجي (15) · **طبقة الذكاء Layer 4 (10)**.
- `/api/v1/ideas?readiness=ready` = اللي نقدر نبنيه النهاردة.

### `app/ideas/wiring.py` — مكان كل متطلب في المنصّة
لكل واحد من الـ181: **الأنظمة** اللي بيقع تحتها · **الـ endpoints** اللي فيها داتاه الخام ·
**القسم** في اللوحة الموحّدة · و**"ناقص إيه"** بجملة عربية واحدة.
- الجدول صريح (181 سطر) عشان الربط ده حُكم لكل فكرة مش قاعدة — لكن أي سطر جديد في
  `BACKLOG.md` بيرث دومينه من `DOMAIN_DEFAULTS` فمابيقعش برّه الخريطة.
- **قاعدة مقفولة باختبار:** الـ endpoint = *داتا خام*، **مش تقرير جاهز**. فكرة مخطّطة عمرها
  ما تاخد لينك لصفحة مبنية (`tests/test_graph.py`).
- التفاصيل الكاملة + سبب كل ربط: `docs/ideas-wiring.md`.

### `app/catalog.py` — الجيتواي بيوصف نفسه
كل كنكتور (20) وكل endpoint (54 بما فيهم الـ501 placeholders). منه بتتحسب الجاهزية
(`is_live`)، ومنه `/connectors`. **`tests/test_catalog.py` بيقع لو الكود والخريطة اختلفوا في أي اتجاه.**

### `app/graph.py` — الوصلة الواحدة
`/systems` و`/connectors` و`/api/v1/map` واللوحة كلهم بيقطعوا من نفس الـ join، فمستحيل
رقم يختلف من صفحة لصفحة.

## 9) المتبقّي (الأولويات)
شوف `NEXT_STEP.md` (المهمة الواحدة) و`TASKS.md` (الكل). أهمها: أتمتة تحديث البيانات · Layer 4 (AI/صوت) · Layer 5 (write) · أول محرّك (Renewals) · SSO/RBAC · Omnichannel.

## 9b) ضمّ REP (2026-07-25)
REP = 11 وحدة واجهات تشغيلية (عهدة · حركة · وجبات · ناس · لوائح · أكاديمية · بنوك · جرد ·
تنبيهات · مستندات · رئيسية). دخل الخريطة كنظام `rep` + كنكتور `rep` (**مش live** — لسه
بيقرا نما مباشرة باعتماده الخاص). **التفاصيل الكاملة الوحدة بالوحدة: `docs/rep-integration.md`.**
- **مكرر يتحذف:** قراءة البنوك · الجرد · الموظفين · الحضور — الجيتواي عنده الأربعة حيّين.
- **مصدر معلومات:** الكيانات القانونية الثلاثة · كتالوج 599 كيان · القاموس الوظيفي ·
  اللوائح ومحرك الجزاءات · الأكاديمية · جودة الموبايلات.
- **merge:** التنبيهات ← محرك Renewals · التوقيع ← آلية HITL لـ Layer 5 · العهدة · الحركة ·
  الوجبات · MOD-97 · الأدوار المحسوبة · الأسطح الثلاثة.
- **15 سطر جديد في `BACKLOG.md`** → 198 متطلب.
- 🔴 **قواعد كتابة نما من REP — لازم تُقرأ قبل Layer 5:** `addRecord:true` على كود موجود
  **بيستبدل السجل صامتًا** · أي تحديث لمصفوفة **بيستبدلها كلها** · **إعادة حفظ مسودة بـAPI
  = commit دائم** · الأكواد العربية بتفشل مع `findByIdOrCode`.
- 🔴 **مفتاح نما الأدمن بتاع REP مكشوف** واعتماد **منفصل** عن مفاتيح الجيتواي (بصمة مختلفة)،
  ومفتاح مزامنة الجرد **مشترك** بين الاتنين. تغيير مفاتيح الجيتواي مايغطّيهوش.

## 10) بند مفتوح
🔴 **تغيير المفاتيح المكشوفة** (Anthropic أولًا) — مؤجّل بطلب المالك. `secrets/gates-keys.backup.md`.
