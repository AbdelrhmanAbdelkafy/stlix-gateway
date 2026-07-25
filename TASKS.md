# TASKS — قائمة المهام

الحالة: ✅ تم · 🟡 جزئي · ⚪ مخطّط · 🔴 عاجل/بند مفتوح

> الأرقام الحيّة مش مكتوبة هنا عشان ماتبوظش — `/api/v1/map` و`/systems` و`/connectors`
> بيقولوا الحالة الحقيقية في أي لحظة.

## ✅ تم (Done)
- ✅ Gateway (Layer 1) + Logs/Monitoring/Security (Layer 6) + Unified Workspace (Layer 3)
- ✅ كنكتورات حيّة (كلها read-only): nama · sql · attendance · crm(Vtiger) · banks · inventory(الجرد)
- ✅ NameBuilder موصّل بالجيتواي (قراءة): قوائم نما حيّة + محلّل محلي + فحص تكرار
- ✅ UX1: تصحيح إملائي (fuzzy) + autocomplete + تطبيع عربي في خانة بحث النوع (name-builder)
- ✅ Finance OS موصّل: KPIs حقيقية + Customers 360 (عملاء AR + موردين AP) من SQL + أدوار الرئيس/المُشغّل
- ✅ **حلّ الأرصدة: SQL connector حيّ** — `/api/v1/finance/{kpis,customers,suppliers}` أرقام حقيقية
- ✅ صفحة التقارير المالية `/tools/finance-reports` (100% حقيقي من SQL)
- ✅ هَب المنصّة الموحّد `/tools/platform` — **كل أرقامه محسوبة، مفيش رقم مكتوب بالإيد**
- ✅ الخزينة أمينة (شيلنا الأرقام الوهمية)
- ✅ **لوحة الأفكار `/tools/ideas`** — كل المتطلبات كـ لينكات، بحث + فلاتر + جاهزية الكنكتور
  (`app/ideas/` بيقرا `BACKLOG.md` — أي سطر جديد يظهر فورًا بدون كود)
- ✅ **الخريطة الموحّدة** — `app/graph.py` + `/api/v1/map`: أنظمة × كنكتورات × endpoints × متطلبات × محرّكات،
  وكل الصفحات بتقطع من نفس الـ join فمستحيل رقم يختلف من صفحة لصفحة
- ✅ **`app/ideas/wiring.py`** — كل متطلب مربوط بنظامه + الـ endpoints اللي فيها داتاه الخام +
  قسمه في اللوحة + "ناقص إيه" بالعربي (135 متطلب داتاهم موجودة دلوقتي)
- ✅ **`app/catalog.py`** — الجيتواي بيوصف نفسه (كنكتورات + كل الـ routes)، والجاهزية بتتحسب منه
- ✅ الاتجاه العكسي: `/systems/{key}` · `/connectors/{key}` (اللي مستنيه) · `?ep=` · روابط في أقسام اللوحة
- ✅ 5 أنظمة كان الباكلوج معتمد عليها ومش على الخريطة: marketdata · portal · idp · omnichannel · telco
- ✅ **`/tools/library`** — وثائق الريبو مقروءة من جوّه المنصّة
- ✅ **مساعد المهندس `/tools/engineer`** (PD2) — خزانات/مواسير/ليزر/مبادلات + حصر BOM
- ✅ **إصلاح ابتلاع الداتا الحيّة** — نما بترجّع 400 على النجاح الجزئي؛ الكلاينت كان برميه.
  `ReceiptVoucher`/`PaymentVoucher` (التحصيلات والمدفوعات اللحظية) بقوا مقروئين
- ✅ **إظهار عمر البيانات** — كل رد مالي بيقول `as_of`/`age_days`/`stale`
  (صفحة التقارير كانت حاطة شارة «حيّ» على أرقام عمرها 11 يوم)
- ✅ **AR/AP/KPIs لحظية من Nama REST** — الفاتورة `net − paid` اتطابقت مع SQL:
  فرق غير مفسَّر 0.17 ج في AR و0.16 ج في AP على كل المجتمع. `?source=live` + لقطة خلفية
  كل ساعة + source/age/exclusions ظاهرين + SQL المُرستَر يفضل المرجع الكامل.
- ✅ **حارس الانحراف** — بعد كل مسح، شهر مقفول بيتطابق مع SQL. شارة `pass|drift|unknown`
  بتسافر مع كل رقم؛ `drift` بيرجّع الافتراضي لـ`sql` وبيقول السبب. بيمسك تغيير حقل في نما،
  صلاحية ضاقت، ومسودّة دخلت المُرحَّل — ومابينرّش على السداد بعد النسخة لأنه طبيعي.
- ✅ **`live` بقى الافتراضي** (قرار المالك 2026-07-25) — `FINANCE_DEFAULT_SOURCE=live`،
  فالصفحات المالية بترد من **إنتاج نما** (`stlixvalley.namasoft.net`) من غير `?source=`.
  الرجوع نفس السطر. المسح الخلفي كل ساعة (`LIVE_FINANCE_REFRESH_SECONDS=3600`).
- ✅ **`hub.public.html` اتوصّل** (قرار المالك) — بقى يقرا من `/api/v1/map` على
  `/tools/platform/public`؛ كان يتيم وفيه AR/AP وتاريخ مكتوبين بالإيد
- ✅ **كوكي المتصفح** (GET/HEAD بس) — لينك `<a>` على `/api/v1/*` كان هيموت 401 أول ما نحطّ مفتاح
- ✅ 115 اختبار + توثيق نما (OpenAPI CRUD-only، دلالات الـ400، paging/drafts، SQL/live)
- ✅ **نقل الكتاب المرجعي (83 فصل)** جوه الريبو → `docs/enterprise-platform/` + `reference/finance-mvp/`

## 🟡 جزئي (In progress / partial)
- 🟡 Finance OS: dashboard KPI strip + Customers/Suppliers حقيقي؛ **باقي شاشاته ديمو**
  (AP invoices · GL ledger · dashboard cash) — يتربطوا أو يتخفوا
- 🟡 UX1: خانة النوع خلصت؛ **UX1b** (إدخال الاسم الكامل → validator → رفض المكرر) لسه
- 🟡 **PD2 مساعد المهندس** — شغّال بس **أوفلاين**: الحصر بيتنسخ بالإيد، مش متراجع على أصناف نما
- 🟡 `housing` و`meals` على الخريطة بمتطلب واحد مشترك بس (H15) — والتغذية دي هدف مشروع البصمة،
  يعني الأغلب الباكلوج ناقصه سطور

## ⚪ مخطّط (Planned)
- ⚪ **تحديث SQL المرجعي** — AR/AP بقت لحظية من REST؛ يفضل سكربت backup ليلي اختياري
  لتحديث المرجع الكامل: download أحدث `.bak` من Drive → RESTORE → بيانات بفارق يوم
- ⚪ **Layer 4 — AI Orchestrator**: شات فريق بيتكلم كإنسان · مدير مبيعات ذكي · محصّل ذكي · مؤشر صحة الشركة
- ⚪ **Layer 5 — Write workflows**: إنشاء صنف فعلي (name-builder) · اعتماد فواتير — audited + HITL
- ⚪ **ربط حصر المهندس بنما** (PD2) — فحص التكرار موجود أصلًا في `/api/v1/nama/invitem/exists`
- ⚪ **الصوت العربي (UX3)**: بحث بالصوت + إملاء + transcript في كل مدخلات النص
- ⚪ **UX4 Widgets** على اللوحة الموحّدة
- ⚪ **PA1 Omnichannel**: واتساب · وي شات · إيميل · **PA2 SSO** · **PA3 RBAC كامل**
- ⚪ **المحرّكات الـ6**: Planned-vs-Actual · Renewals · Reconciliation · Live-vs-Pending · Watchlist · Market-Feeds
  (كلهم بقى ليهم عدّاد حقيقي: `/api/v1/map?view=engines`)
- ⚪ الدومينات المتبقية — **107 متطلب كنكتورهم جاهز**: `/api/v1/ideas?readiness=ready`
- ⚪ فتح الـ 3 Google Sheets (RESOURCES.md) كمصادر بيانات

## 🔴 بند مفتوح (Open)
- 🔴 **تغيير المفاتيح المكشوفة** (Anthropic أولًا) — مؤجّل بطلب المالك. `secrets/gates-keys.backup.md`
