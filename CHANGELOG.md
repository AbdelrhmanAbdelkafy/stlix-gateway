# CHANGELOG — كل تعديل

> ترتيب زمني تنازلي (الأحدث فوق). تواريخ تقريبية للجلسة (2026-07-24).

## 2026-07-25 (2) — جلسة: ربط الأفكار بالـ workspace وبالجيتواي (الهَب بقى مربوط فعلًا)
> طلب المالك: «اربط الأفكار بالـ workspace وبالـ gateway علشان يبقى hub — populate كامل متكامل».
> اللوحة كانت جزيرة: 181 متطلب معروضين ومش مربوطين بحاجة، و20 بند بس فيهم أي لينك.

### أُضيف
- **`app/ideas/wiring.py`** — مكان كل واحد من الـ181 في المنصّة: الأنظمة المسؤولة · **الـ endpoints اللي فيها داتاه الخام** · القسم في اللوحة · و"ناقص إيه" بجملة عربية. **135 من 181 داتاهم موجودة دلوقتي.** جدول صريح لكل id + `DOMAIN_DEFAULTS` عشان أي سطر جديد في الباكلوج مايقعش برّه الخريطة.
- **`app/catalog.py`** — الجيتواي بيوصف نفسه: 20 كنكتور + 54 endpoint (بما فيهم الـ501 placeholders، مشتقّة من `SYSTEMS` مش مكتوبة). الجاهزية بقت بتتحسب من `is_live()` هنا بدل نسخة تانية في `ideas/registry.py`.
- **`app/graph.py` + `GET /api/v1/map`** — الوصلة الواحدة (أنظمة × كنكتورات × endpoints × متطلبات × محرّكات). فلاتر `?system=` `?connector=` `?engine=` و`?view=`.
- **الاتجاه العكسي:** `/systems/{key}` · `/connectors/{key}` (اللي مستنيه بالظبط) · `/api/v1/ideas?system=|connector=|endpoint=|section=|has_data=`.
- **5 أنظمة** كان الباكلوج معتمد عليها ومش على الخريطة: `marketdata` · `portal` · `idp` · `omnichannel` · `telco`.
- **قسم `finance` في اللوحة الموحّدة** — مصدر الأرقام الحقيقية الوحيد كان ناقص من "اللوحة اللي بتجمّع كل حاجة".
- **`/tools/library`** — وثائق الريبو مقروءة من جوّه المنصّة (كان `BACKLOG.md` هو الملف الوحيد اللي المنصّة شايفاه).
- **كوكي `sg_key`** (HttpOnly · SameSite=lax · **GET/HEAD بس**) عشان لينك `<a>` عادي على `/api/v1/*` يشتغل.
- 27 اختبار جديد (`test_catalog.py` · `test_graph.py`) → **83 اختبار** (كانوا 56).

### اتغيّر
- **الهَب** — مافيش رقم مكتوب بالإيد: كل الأرقام من `/api/v1/map` + 26 كارت دومين بيوصّلوا للوحة مفلترة.
- **لوحة الأفكار** — الكارت بقى `<article>` مش لينك واحد: شارة النظام (فلتر) · الـ endpoints · "ناقص كنكتور" بيوصّل لصفحة الكنكتور · حالة الفلاتر كلها ظاهرة في الـ URL وقابلة للمسح فردي.
- **الـ501 placeholders** بقت بترد HTML/JSON وبتقول كام متطلب مستني النظام ده بدل رسالة خطأ جافة.
- **`/health`** بيقول حالة كل الكنكتورات الحيّة (كان بيفحص نما بس).
- **`/metrics`** فيه تجميع لكل كنكتور (كان paths خام مالهاش معنى).
- الباكلوج: 18 سطر اتوسموا بمحرّكهم — **Watchlist وMarket-Feeds كانوا صفر** رغم إن GV1 حرفيًا blacklist وMD1-MD5 حرفيًا market feeds.

### اتصلح
- **`/connectors` كان بيعرض `nama` بس** وستة كنكتورات حيّة — سطر مكتوب بالإيد من قبل الكنكتورات ما تتبنى.
- **5 كنكتورات بتشاور على أنظمة مش موجودة** على الخريطة (`idp`, `omnichannel`, `portal`, `telco`, `voice`) — وكانت بتتعرض في `/connectors` على طول.
- **17 route شغّالة ومش على أي خريطة** (الـ501 placeholders) + خريطة بتوعد بـ endpoints مش موجودة.
- أرقام بايظة: الهَب "5 كنكتورات"/"44 اختبار" (الحقيقة 9 و83) · الجذر "11 نظام" (22) · README بيقول `crm` و`inventory` مخطّطين وهما حيّين · VISION "4 live".
- `inventory` و`banks` كانوا بيقولوا **صفر فكرة** رغم إن 18 متطلب مخازن قاعدين فوقهم — الكنكتور دلوقتي بيتاخد من الـ endpoint اللي فعلًا فيه الداتا مش من نص عمود Source بس.

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
