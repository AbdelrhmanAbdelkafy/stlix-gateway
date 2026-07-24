# مواصفة تقرير الأرصدة من نماسوفت (Nama Balance Report — spec for Namasoft)

> **الهدف:** الجيتواي (Stlix Gateway) محتاج يقرأ **أرصدة العملاء والموردين الحيّة** من نما.
> الـ REST الحالي بيدّي الفواتير والكيانات، لكن **مش بيدّي الأرصدة المحسوبة** (`remaining`/`totalPaid`).
> الطلب: تعملوا **query / report entity** بترجّع الأرصدة، **يُقرأ بنفس الـ REST credentials الحالية** (`clientId` + `clientSecret`) عبر `POST {Entity}/list`.
> كده الجيتواي يقراها زي أي كيان — من غير أي بروتوكول أو صلاحيات جديدة.

> **⭐ أبسط حل (مفضّل):** عندكم بالفعل أداة SQL شغّالة في `/erp/vue.html#/utils/sql`.
> المطلوب ببساطة: **افتحوا نفس تنفيذ الـ SQL للـ REST API credentials** (`clientId`+`clientSecret`)
> — endpoint بيستقبل SQL (SELECT قراءة فقط) ويرجّع JSON. ساعتها الجيتواي يشغّل الاستعلامات
> الجاهزة مباشرة (في `docs/live-balance-queries.sql`) ونجيب كل الأرصدة الحيّة فورًا.
> لو ده مش ممكن أمنيًا، البديل هو الـ report entities الموصوفة تحت.

الحساب مثبّت من الـ schema (اختُبر على نسخة قاعدة نما): الحقول اللي محتاجينها موجودة في
`SalesInvoice` / `PurchaseInvoice` (الأعمدة: `total`, `totalPaid`, `remaining`, `customer_id`,
`issueDate`). المطلوب تجميعها لكل عميل/مورد.

---

## 1) تقرير أرصدة العملاء — `StlixCustomerBalance`
كيان/استعلام يُقرأ عبر `POST StlixCustomerBalance/list` ويرجّع صف لكل عميل بالحقول:

| الحقل | المصدر / الحساب | النوع |
|---|---|---|
| `code` | كود العميل (`Customer.code`) | نص |
| `name1` | اسم العميل | نص |
| `salesTotal` | `SUM(SalesInvoice.total)` للعميل | رقم |
| `collected` | `SUM(SalesInvoice.totalPaid)` | رقم |
| `outstanding` | `SUM(SalesInvoice.remaining)` — **الرصيد المستحق** | رقم |
| `invoicesCount` | عدد الفواتير | رقم |
| `lastInvoiceDate` | `MAX(SalesInvoice.issueDate)` — بصيغة `DD-MM-YYYY` | تاريخ |
| `salesMan` | المندوب (اختياري) | نص |

## 2) تقرير أرصدة الموردين — `StlixSupplierBalance`
نفس الشكل من `PurchaseInvoice`:

| الحقل | الحساب | النوع |
|---|---|---|
| `code` | `Supplier.code` | نص |
| `name1` | اسم المورد | نص |
| `purchaseTotal` | `SUM(PurchaseInvoice.total)` | رقم |
| `paid` | `SUM(PurchaseInvoice.totalPaid)` | رقم |
| `outstanding` | `SUM(PurchaseInvoice.remaining)` — **المستحق علينا** | رقم |
| `invoicesCount` | عدد الفواتير | رقم |
| `lastInvoiceDate` | `MAX(PurchaseInvoice.issueDate)` `DD-MM-YYYY` | تاريخ |

## 3) كشف حساب عميل (اختياري — لشاشة العملاء 360) — `StlixCustomerStatement`
صف لكل حركة، يُفلتَر بكود العميل (`textCriteria "customerCode,Equal,<code>,AND;"`):

| الحقل | المصدر |
|---|---|
| `customerCode` | كود العميل (للفلترة) |
| `docCode` | رقم المستند (فاتورة/سند قبض) |
| `docType` | النوع (فاتورة / سند قبض) |
| `date` | التاريخ `DD-MM-YYYY` |
| `debit` | مدين |
| `credit` | دائن |

## 4) أعمار الديون (اختياري) — buckets في تقرير العملاء
لو أمكن، أضيفوا للأعمدة أعلاه: `dueCurrent` · `due30` · `due60` · `due90plus`
(تقسيم `outstanding` حسب تأخّر `payDate`/تاريخ الاستحقاق مقابل تاريخ اليوم).

---

## الشكل المتوقّع للرد (JSON عبر REST)
نفس شكل أي `list` في نما:
```json
{ "records": { "StlixCustomerBalance": [
    {"code":"C1000001","name1":"MARS Egypt - مارس مصر","salesTotal":5048334,"collected":5270625,"outstanding":120996,"invoicesCount":22,"lastInvoiceDate":"22-11-2025"},
    ...
] }, "records_count": 549 }
```

## ملاحظات للتنفيذ (Namasoft)
- الوصول بنفس اعتماد الـ REST الحالي: هيدرز `clientId` + `clientSecret` (اللي بنستخدمه دلوقتي).
- التواريخ بصيغة `DD-MM-YYYY` (زي باقي نما).
- الأرقام صافية بدون فواصل.
- لو الأسهل عندكم عمل **screen/query** بدل entity: المهم إنه **يُستدعى عبر REST ويرجّع JSON** بالحقول أعلاه.
- ترقيم النتائج: ندعم `pageSize` (نفس آلية `list`).

## الجانب اللي جاهز عندنا (Stlix Gateway)
بمجرد ما الكيانات دي تتفعّل، الجيتواي هيقراها فورًا عبر connector مالي
(`app/integrations/finance/`) بيستخدم نفس `NamaClient.list_query`، وبيغذّي **Finance OS**
(الخزينة · العملاء 360 · الموردين · KPIs). مفيش أي تغيير مطلوب في الأمان — قراءة فقط.
