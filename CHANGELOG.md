# CHANGELOG — كل تعديل

> ترتيب زمني تنازلي (الأحدث فوق). تواريخ تقريبية للجلسة (2026-07-24).

## 2026-07-25 — جلسة: لوحة الأفكار + توحيد المستودع
### أُضيف
- **سجل الأفكار** `app/ideas/` — بيقرا `BACKLOG.md` ويحوّله لبيانات: 181 متطلب، 26 دومين، مع **جاهزية الكنكتور** لكل بند (done/ready/partial/blocked) والمحرّك المرتبط.
- Endpoints `/api/v1/ideas` (فلاتر: `q`, `domain`, `status`, `readiness`, `engine`) · `/api/v1/ideas/domains` · `/api/v1/ideas/{id}`.
- **لوحة الأفكار** `modules/platform/ideas.html` + route `/tools/ideas` — كل فكرة كارت بلينك + deep link `#<id>`، بحث عربي/إنجليزي، فلاتر، عدّاد نتائج.
- `IdeasProvider` في اللوحة الموحّدة + كارت في الهَب بيعرض العدد الحيّ.
- 12 اختبار جديد (`tests/test_ideas.py`) → **56 اختبار** (كانوا 44).
### اتغيّر
- **نقل الكتاب المرجعي (83 فصل) جوه الريبو** → `docs/enterprise-platform/` (+ `README.md` يربطه بالتنفيذ) و `reference/finance-mvp/`. كان في `D:\CLAUDE SHARED MEMORY\Enterprise Platform AI based\` — بقى مصدر حقيقة واحد.
- توثيق التسمية: **الهَب = الجيتواي = المنصّة = مشروع واحد** (في الرَنبوك + `SESSION_STATE.json` + `HANDOFF.md`).
### اتصلح
- `_connectors_of` كانت بتقرا `ai` جوه كلمة `Email` (matching بالحروف) → بقت word-boundary.
- زرار "الكل" في لوحة الأفكار كان بيصفّر فلتر الحالة بس والدومين يفضل مقفول من غير ما يبان → بقى يصفّر كل الفلاتر + عدّاد نتائج ظاهر دايمًا.

## 2026-07-24 — جلسة: أرصدة حقيقية + منصّة موحّدة + handover
### أُضيف
- **SQL finance connector** (`app/integrations/finance/`) — يقرأ أرصدة العملاء/الموردين/KPIs من نما SQL مباشرة (pyodbc, read-only, `run_in_threadpool`). Endpoints `/api/v1/finance/{kpis,customers,suppliers}`.
- إعدادات SQL في `config.py` + `.env` (`NAMA_SQL_*`) + login `stlix_gw` (read-only) في SQL Server.
- `pyodbc` في requirements.
- **صفحة التقارير المالية** `modules/finance-os/reports.html` + route `/tools/finance-reports` — تسحب حيّ من `/api/v1/finance/*` (100% حقيقي).
- **هَب المنصّة** `modules/platform/hub.html` + route `/tools/platform` — نقطة دخول موحّدة، live modules + placeholders + SSO placeholder.
- Finance OS: شريط KPIs حقيقي في الداشبورد + أرصدة عملاء/موردين حقيقية في Customers 360 (من `/finance/*`).
- حزمة handover: `SESSION_STATE.json` · `MASTER_EXECUTION_RUNBOOK.md` · `TASKS.md` · `DECISIONS.md` · `CHANGELOG.md` · `NEXT_STEP.md`.
- `docs/nama-balance-report-spec.md` (مواصفة تقرير نماسوفت — اختياري) + `docs/live-balance-queries.sql`.
### اتغيّر
- Finance OS: العملاء من **نما** بدل CRM.
- الخزينة: شيلنا الأرقام الوهمية (الأرصدة الرقمية "قيد الترحيل من GL" — مش مُرحّل بالكامل في الـ backup).
### اتأكد (findings)
- Nama REST = CRUD كيانات فقط (OpenAPI). مفيش SQL/report/balance. أداة SQL في نما = web-login مش API.
- الأرصدة الحقيقية عبر SQL: sales 329.9M · AR 20.0M · purchases 320.0M · AP 186.7M (as-of 14 يوليو).
- data-quality: AR منسوب لعملاء بالاسم ~178K بس؛ الباقي فواتير غير مربوطة.
- نسخ backup يومية على Google Drive (`hardsteel<date>.bak`).

## قبلها (نفس الجلسة والجلسة السابقة)
### أُضيف
- **NameBuilder gateway-wired** (`demo.gateway.html` + `/tools/name-builder`): قوائم نما حيّة (`/nama/lists/{entity}`) + dedup (`/nama/invitem/exists`) + المحلّل المحلي — صفر مفاتيح في المتصفح.
- **UX1** في name-builder: بحث fuzzy (Levenshtein) + autocomplete منسدل بالكيبورد + تطبيع عربي.
- **Finance OS gateway-wired** (`/tools/finance-os`): أدوار PRESIDENT + OPERATOR الجديدة + RBAC + overlay بيانات حيّة.
- `NamaClient.list_query` + `find_first` (يتعامل مع zero-result 400) + endpoints `/nama/lists/{entity}` + `/nama/invitem/exists`.
- `app/routers/tools.py` (تقديم صفحات الموديولات مع حقن مفتاح الجيتواي).
- 5 كنكتورات (nama, attendance, crm, banks, inventory) + workspace + meta + observability + security + rate-limit.
### توثيق
- `BACKLOG.md` (~180 متطلب) + `VISION.md` (6 محرّكات) + `RESOURCES.md` + `templates/` + spec docs.
- بنود جديدة اتسجّلت: شكاوي · اقتراحات · transcript · صوت · autocomplete أصناف · payment slips · widgets · omnichannel · SSO · RBAC.
