# TASKS — قائمة المهام

الحالة: ✅ تم · 🟡 جزئي · ⚪ مخطّط · 🔴 عاجل/بند مفتوح

## ✅ تم (Done)
- ✅ Gateway (Layer 1) + Logs/Monitoring/Security (Layer 6) + Unified Workspace (Layer 3)
- ✅ 5 كنكتورات حيّة (read-only): nama · attendance · crm(Vtiger) · banks · inventory(الجرد)
- ✅ NameBuilder موصّل بالجيتواي (قراءة): قوائم نما حيّة + محلّل محلي + فحص تكرار
- ✅ UX1: تصحيح إملائي (fuzzy) + autocomplete + تطبيع عربي في خانة بحث النوع (name-builder)
- ✅ Finance OS موصّل: KPIs حقيقية + Customers 360 (عملاء AR + موردين AP) من SQL + أدوار الرئيس/المُشغّل
- ✅ **حلّ الأرصدة: SQL connector حيّ** — `/api/v1/finance/{kpis,customers,suppliers}` أرقام حقيقية
- ✅ صفحة التقارير المالية `/tools/finance-reports` (100% حقيقي من SQL)
- ✅ هَب المنصّة الموحّد `/tools/platform`
- ✅ الخزينة أمينة (شيلنا الأرقام الوهمية)
- ✅ **لوحة الأفكار `/tools/ideas`** — الـ181 متطلب كلهم كـ لينكات، بحث + فلاتر + جاهزية الكنكتور
  (`app/ideas/` بيقرا `BACKLOG.md` — أي سطر جديد يظهر فورًا بدون كود)
- ✅ **نقل الكتاب المرجعي (83 فصل)** جوه الريبو → `docs/enterprise-platform/` + `reference/finance-mvp/`
- ✅ 56 اختبار + توثيق نما (OpenAPI CRUD-only, zero-result 400, SQL solution)

## 🟡 جزئي (In progress / partial)
- 🟡 Finance OS: dashboard KPI strip + Customers/Suppliers حقيقي؛ **باقي شاشاته ديمو** (AP invoices · GL ledger · dashboard cash) — يتربطوا أو يتخفوا
- 🟡 UX1: خانة النوع خلصت؛ **UX1b** (إدخال الاسم الكامل → validator → رفض المكرر) لسه
- 🟡 freshness: بيانات as-of 14 يوليو؛ محتاج أتمتة restore لأحدث backup

## ⚪ مخطّط (Planned — من الشات ده والشات اللي قبله)
- ⚪ **أتمتة تحديث البيانات**: سكربت ليلي (download أحدث .bak من Drive → RESTORE) → بيانات بفارق يوم
- ⚪ **Layer 4 — AI Orchestrator**: شات فريق بيتكلم كإنسان · مدير مبيعات ذكي · محصّل ذكي · مؤشر صحة الشركة
- ⚪ **Layer 5 — Write workflows**: إنشاء صنف فعلي (name-builder) · اعتماد فواتير (Finance OS) — audited + HITL
- ⚪ **الصوت العربي (UX3)**: بحث بالصوت + إملاء + transcript في كل مدخلات النص
- ⚪ **UX4 Widgets** على اللوحة الموحّدة
- ⚪ **PA1 Omnichannel**: واتساب · وي شات · إيميل
- ⚪ **PA2 SSO** (Google Workspace/OAuth) · **PA3 RBAC كامل**
- ⚪ **المحرّكات الـ6**: Planned-vs-Actual · Renewals · Reconciliation · Live-vs-Pending · Watchlist · Market-Feeds
- ⚪ **Live-vs-Pending**: بوابة للبيانات غير المُسجّلة/المرحّلة في نما (فكرة المالك)
- ⚪ الدومينات المتبقية (تقارير فوق نما): مبيعات · مشتريات · HR · مخازن · شحن · صيانة · إلخ (BACKLOG.md)
- ⚪ الشكاوي · الاقتراحات · إيصالات الدفع · أوتوكومبليت الأصناف (اتسجّلوا في BACKLOG)
- ⚪ فتح الـ 3 Google Sheets (RESOURCES.md) كمصادر بيانات

## 🔴 بند مفتوح (Open)
- 🔴 **تغيير المفاتيح المكشوفة** (Anthropic أولًا) — مؤجّل بطلب المالك. `secrets/gates-keys.backup.md`
