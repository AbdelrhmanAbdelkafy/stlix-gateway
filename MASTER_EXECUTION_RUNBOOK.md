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
- venv: `.venv` (Python 3.14). الاختبارات: `.venv/Scripts/python.exe -m pytest -q` → **44 passing**.
- الأسرار في `.env` (gitignored). نسخة احتياطية للمفاتيح: `secrets/gates-keys.backup.md`.

## 2) الصفحات (افتحها في المتصفح)
| الرابط | إيه هو |
|---|---|
| `/tools/platform` | **الهَب الموحّد** — نقطة الدخول · live modules + placeholders + SSO |
| `/tools/finance-reports` | **التقارير المالية الحقيقية** (100% من SQL) — الواجهة المالية الإنتاجية |
| `/tools/finance-os` | الكوكبيت بالأدوار (Demo prototype) — KPIs + عملاء/موردين حقيقي، الباقي ديمو |
| `/tools/ideas` | **لوحة الأفكار** — كل متطلب قاله المالك كـ لينك · بحث + فلتر بجاهزية الكنكتور · مصدرها `BACKLOG.md` |
| `/tools/name-builder` | إنشاء الأصناف (قراءة) |
| `/api/v1/workspace` · `/systems` · `/connectors` · `/metrics` · `/health` | اللوحة/الخريطة/المراقبة |

## 3) البنية — 6 طبقات
1. **Gateway** ✅ · 2. **Connectors** (5 live + SQL finance) · 3. **Unified Workspace** ✅ ·
4. **AI Orchestrator** ⚪ · 5. **Workflows/Write** ⚪ · 6. **Logs/Monitoring/Security** ✅.

## 4) الكنكتورات (كلها read-only)
`nama` (ERP) · `attendance` (بصمة) · `crm` (Vtiger) · `banks` · `inventory` (الجرد).
**النمط:** `app/integrations/<key>/{client,connector,router}.py` + سجّل في `main.py` + `registry.py` + `workspace/providers.py` + test. سكافولد في `templates/`.

## 5) 🎯 الأرصدة الحقيقية (المحور المهم)
- **نما REST مابيدّيش أرصدة** (CRUD كيانات فقط — اتأكد من OpenAPI). الحل: **SQL مباشر**.
- **الجيتواي بيقرأ من نما SQL**: connector `app/integrations/finance/` (pyodbc, read-only).
  - الاتصال في `.env`: `NAMA_SQL_SERVER=localhost` · `NAMA_SQL_DATABASE=NAMA_TEST` · `NAMA_SQL_USER=stlix_gw` · `NAMA_SQL_PASSWORD=***` · driver `ODBC Driver 17 for SQL Server` (Encrypt=yes;TrustServerCertificate=yes).
  - login `stlix_gw` = read-only (db_datareader). أُنشئ عبر SSMS: `CREATE LOGIN stlix_gw ... ; CREATE USER ... ; ALTER ROLE db_datareader ADD MEMBER stlix_gw`.
  - Endpoints: `/api/v1/finance/kpis` · `/customers` · `/suppliers` → أرقام حقيقية.
- **الأرقام (as-of 2026-07-14):** 549 عميل · 586 مورد · مبيعات 329.9M · AR 20.0M · مشتريات 320.0M · AP 186.7M.
- **أرصدة البنوك مؤجّلة** (محتاجة GL — مش مُرحّل بالكامل في الـ backup الحالي).
- **التحديث (freshness):** البيانات = آخر `.bak` مُرستَر. نسخ يومية على Google Drive folder `1yvCI6unRWALtzf1yiU9kiHAPaBB56Xtt/full` (`hardsteel<date>.bak`). **مفيش قراءة للـ .bak وهو على الدرايف** — لازم download + `RESTORE DATABASE`. الأتمتة = سكربت ليلي (شوف NEXT_STEP).
- بديل رسمي (اختياري): تقرير من نماسوفت — `docs/nama-balance-report-spec.md`.

## 6) استكشاف نما مباشر (للـ debugging)
- عبر MCP **`LOCALERP`**: `mcp__LOCALERP__nama_local_sql_query` (SELECT قراءة فقط على `NAMA_TEST`، user `claude_ro`). استخدمه لاستكشاف الـ schema/الأرقام بدون ما تلمس الجيتواي.
- استعلامات جاهزة: `docs/live-balance-queries.sql`.

## 7) حقائق نما (gotchas)
- API = CRUD فقط (`/{Entity}/{list,findByIdOrCode,save,delete}`). عقد كل كيان: `/erp/browseapi/openapi/{Entity}.json` (فيه trailing commas — parse بتساهل).
- **zero-result filtered list = HTTP 400 body فاضي** → `NamaClient.find_first`.
- `textCriteria`: `field,Equal,value,AND;` — operator case-sensitive (`Equal` بس). التواريخ `DD-MM-YYYY`.
- أرصدة العملاء/الموردين من `SalesInvoice`/`PurchaseInvoice` (`total`/`totalPaid`/`remaining`) JOIN `Customer`/`Supplier` على `customer_id`/`supplier_id`.

## 8) إزاي تكمّل (نمط الشغل)
- **موديول front-end:** `modules/<name>/*.html` + route في `app/routers/tools.py` عبر `_serve()` (بيحقن `__GATEWAY_API_KEY__`). يستدعي endpoints الجيتواي بـ `X-API-Key`.
- **تقرير/endpoint:** أضف method في الـ connector + endpoint في الـ router بـ `respond()` (HTML+JSON).
- **كتابة (write):** اقلب الكنكتور `read_write` **عمدًا**، خلف workflow مدقّق + HITL.
- **بعد أي تعديل:** `pytest -q` → restart preview → verify live.

## 8b) الأفكار والمتطلبات (181 بند)
- **مصدر الحقيقة `BACKLOG.md`** — سطر markdown لكل فكرة. `app/ideas/registry.py` بيقراه ويطلّع:
  الدومين · المصدر · الحالة · المحرّك · **جاهزية الكنكتور**. **ضيف سطر → يظهر في اللوحة فورًا** (مفيش كود).
- **الجاهزية:** `done` اتعمل · `ready` كل كنكتوراته موجودة (محتاج تقرير بس) · `partial` ناقص جزء · `blocked` محتاج تكامل جديد.
- **الأرقام دلوقتي:** 1 اتعمل · **107 كنكتورها جاهز** · 43 ناقص جزء · 30 محتاج تكامل جديد.
- أكتر الكنكتورات الناقصة طلبًا: نظام جديد (47) · API خارجي (15) · **طبقة الذكاء Layer 4 (9)**.
- `/api/v1/ideas?readiness=ready` = اللي نقدر نبنيه النهاردة.

## 9) المتبقّي (الأولويات)
شوف `NEXT_STEP.md` (المهمة الواحدة) و`TASKS.md` (الكل). أهمها: أتمتة تحديث البيانات · Layer 4 (AI/صوت) · Layer 5 (write) · أول محرّك (Renewals) · SSO/RBAC · Omnichannel.

## 10) بند مفتوح
🔴 **تغيير المفاتيح المكشوفة** (Anthropic أولًا) — مؤجّل بطلب المالك. `secrets/gates-keys.backup.md`.
