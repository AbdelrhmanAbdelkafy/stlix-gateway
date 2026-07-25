# Ideas wiring — where every backlog row lands

Generated reference for `app/ideas/wiring.py`. `BACKLOG.md` stays the source
of truth for *what* the owner asked for; this records *where* each item lands
and *why*, including the English reasoning that does not fit on a card.

`data endpoints` = live routes whose **raw data** feeds the idea. They are never
the deliverable — a planned report stays planned no matter how much of its data
is already queryable.

## Sales & Collection · مبيعات وتحصيل (`S`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `S1` | nama | `/api/v1/finance/kpis`<br>`/api/v1/finance/customers` | خطة مبيعات وحقل نقدي/آجل على الفاتورة | Sales documents are Nama, but the actual money (salesTotal, and collected vs remaining = cash vs credit) is computed only by the SQL-backed finance endpoints, never by Nama REST. |
| `S2` | nama | `/api/v1/finance/customers` | تقرير تحصيل بالتاريخ وهدف تحصيل يومي | Collection is a money figure, so only /api/v1/finance/customers (collected vs outstanding per customer) exposes it; it is cumulative, so the per-day and planned sides are still missing. |
| `S3` | nama · crm | `/api/v1/nama/lists/{entity}`<br>`/api/v1/crm/accounts` | تقرير SQL للمبيعات لكل مندوب | The salesman master reads as a Nama list entity and rep-owned accounts read from Vtiger, but no live endpoint attributes sales money to a rep. |
| `S4` | crm · nama | `/api/v1/crm/accounts`<br>`/api/v1/finance/customers` | تقرير عملاء واقفين بربط Vtiger بآخر تاريخ فاتورة | Accounts come from Vtiger and /api/v1/finance/customers already returns lastInvoiceDate, which is exactly the inactivity signal — only the rule on top is missing. |
| `S5` | crm | `/api/v1/crm/leads` | حقل الدولة/الشريحة على leads في Vtiger | Purely a Vtiger Leads filter: the leads are already readable, but they carry no Chinese/segment marker to filter on. |
| `S6` | nama | `/api/v1/finance/customers`<br>`/api/v1/finance/kpis` | تواريخ استحقاق وأعمار ديون على المديونيات | Target receivables are money, so outstanding per customer and company AR come only from the SQL-backed finance endpoints; Nama REST computes no balance. |
| `S7` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL للمبيعات لكل فرع | Branch master and the sales documents are readable as generic Nama entities, but /api/v1/finance/* only totals company-wide and never splits by branch. |
| `S8` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL للمبيعات لكل مندوب | The salesman master and sales documents are readable Nama entities, but no live endpoint returns sales money per rep. |
| `S9` | crm · nama | `/api/v1/crm/accounts`<br>`/api/v1/crm/leads` | تقرير عملاء جدد بتاريخ الإنشاء والمصدر في Vtiger | New-customer count and origin are Vtiger fields (account creation, lead source) that are readable today; nothing aggregates them into a period count. |
| `S10` | crm · nama | `/api/v1/crm/accounts`<br>`/api/v1/finance/customers` | قاعدة تسرّب عملاء على lastInvoiceDate | The account list is Vtiger and the last-purchase date comes from the SQL-backed /api/v1/finance/customers; only the churn definition is missing. |
| `S11` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL بتكلفة بند الفاتورة COGS | Sales and purchase documents are readable Nama entities, but no live endpoint returns cost per line, so no margin percentage can honestly be claimed as reachable. |
| `S12` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL على بنود SalesInvoice | Item master and sales documents are Nama entities readable through the generic list read; ranking by quantity sold needs line-level aggregation no endpoint exposes. |
| `S13` | nama | `/api/v1/nama/lists/{entity}` | تكلفة البند ومبيعاته مجمّعة في تقرير SQL | The item master reads from Nama, but margin per item needs both selling price and cost per invoice line, which only a SQL report can produce. |
| `S14` | crm · nama | `/api/v1/crm/leads`<br>`/api/v1/crm/accounts` | حقل تحويل leads لحسابات في Vtiger | Both sides of the ratio are live Vtiger modules; what is missing is the field that says which lead became which account. |
| `S15` | crm · nama | `/api/v1/crm/{module}` | زيارات المندوبين متسجلة فعلاً في Vtiger | The generic CRM module read can already return any Vtiger module (Events/Calendar), so the blocker is data capture, not an integration. |
| `S16` | nama | `/api/v1/nama/lists/{entity}` | تقرير يربط SalesOrder بالتسليمات والفواتير | Orders and their fulfilment documents are Nama entities readable one list at a time; the remaining-quantity calculation across them does not exist yet. |
| `S17` | nama | `/api/v1/finance/customers`<br>`/api/v1/finance/suppliers` | مفتاح يربط سجل العميل بسجل المورد | Both money sides (what they buy from us, what we buy from them) are already returned by the SQL-backed finance endpoints; only the identity match is missing. |
| `S18` | nama | `/api/v1/finance/customers`<br>`/api/v1/finance/suppliers` | قاعدة مقاصة بين رصيد العميل والمورد | Outstanding on both sides is real SQL data already exposed; the net position is a computation nothing performs yet. |
| `S19` | nama | `/api/v1/finance/suppliers`<br>`/api/v1/nama/lists/{entity}` | تاريخ أسعار الشراء لكل صنف وكل طرف | What we pay a party in total is live SQL data and the purchase documents are readable Nama entities, but a per-item floor needs line-level prices. |
| `S20` | nama · crm | `/api/v1/finance/customers`<br>`/api/v1/crm/accounts` | مفتاح يربط العميل بحساب Vtiger عشان النشاط | Sales money per customer is live SQL data and the industry field is already a returned Vtiger Accounts column; the join between them does not exist. |
| `S21` | nama | `/api/v1/finance/customers`<br>`/api/v1/nama/lists/{entity}` | حقل المنطقة الجغرافية على ملف العميل | Sales per customer is real SQL money and the customer master reads as a Nama entity, but nothing carries a usable geography to aggregate on. |
| `S22` | crm · ai | `/api/v1/crm/leads`<br>`/api/v1/crm/accounts` | طبقة الذكاء AI | The candidate pool is live Vtiger data already readable, but nothing scores or recommends over it until the AI layer exists. |
| `S23` | nama | `/api/v1/nama/lists/{entity}` | حقل تاريخ الاستحقاق على مستند الطلب وقاعدة الالتزام | Demand/claim documents are Nama entities the generic list read can return; on-time judgement needs a promised date to compare against. |
| `S24` | nama *(+registrations?)* | — | سجل طلبات اعتمادنا عند العملاء — مش موجود | The backlog itself marks this as Nama/new: our vendor-registration applications at customers exist in no connected system, so no endpoint may be attached. |
| `S25` | nama | `/api/v1/nama/lists/{entity}` | كتالوج مطبوع من InvItem وخصائصه | The item master and its ItemClass attribute lists are exactly what the generic Nama list read already serves to the name-builder; only the customer-facing rendering is missing. |
| `S26` | nama · inventory | `/api/v1/nama/lists/{entity}`<br>`/api/v1/inventory/counts` | مصدر رصيد مخزون لحظي — Nama REST مبيطلعش أرصدة | The item master reads from Nama and the stocktake app returns real counted quantities, but those are a point-in-time count, not a daily available-to-sell balance. |
| `S27` | nama · ai | `/api/v1/finance/customers` | طبقة الذكاء AI لترتيب أولويات التحصيل | Outstanding and lastInvoiceDate per customer — the whole ranking input — are already live SQL data; the prioritiser itself needs the AI layer. |

## Purchasing & Materials · مشتريات وخامات (`P`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `P1` | nama | `/api/v1/nama/lists/{entity}` | حقل الأولوية على طلبات الشراء وتقرير عليها | Purchase requests are Nama documents the generic list read can return; nothing marks or sorts them by urgency yet. |
| `P2` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/nama/employees` | تقرير على طلبات الخامات لكل طالب | Both halves are live Nama reads — the material-request documents as a list entity and the requesting employee via the employees endpoint. |
| `P3` | nama · crm *(+surveys?)* | — | سجل طلبات معاينة — مش موجود في أي نظام | Both connectors can already read any entity/module, so the blocker is that no Nama entity or Vtiger module holds site-survey requests. |
| `P4` | nama | `/api/v1/nama/lists/{entity}` | تقرير تاريخ أسعار من مستندات الشراء في Nama | Price lists and purchase documents are Nama entities readable through the generic list read; no endpoint returns a price trend per material. |
| `P5` | nama | `/api/v1/finance/suppliers`<br>`/api/v1/nama/lists/{entity}` | محرك المطابقة Reconciliation وكشف حساب من المورد | Our side of the statement (purchaseTotal, paid, outstanding) is live SQL money and the underlying documents are readable Nama entities; the supplier's own statement is not in any system. |
| `P6` | nama | `/api/v1/finance/suppliers` | تاريخ آخر مطابقة لكل مورد | Supplier balances and lastInvoiceDate are real SQL data, but the overdue rule needs reconciliation state, which nothing stores. |
| `P7` | nama | `/api/v1/nama/lists/{entity}` | سعر أقصى مستهدف لكل صنف | Purchase documents and price lists read as Nama entities; the accepted maximum is a judgement value that exists nowhere yet. |
| `P8` | nama · inventory · ai | `/api/v1/nama/lists/{entity}`<br>`/api/v1/inventory/counts` | طبقة الذكاء AI وتغذية استهلاك ورصيد مستمرة | The item master reads from Nama, but reorder recommendations need both an on-hand/consumption signal (not exposed) and the AI layer to rank them. |
| `P9` | nama | `/api/v1/finance/suppliers`<br>`/api/v1/nama/lists/{entity}` | حقل المنطقة الجغرافية على ملف المورد | Purchase money per supplier is already returned by the SQL-backed finance endpoint and the supplier master reads from Nama; only the geography dimension is missing. |
| `P10` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/finance/suppliers` | محرك المطابقة Reconciliation بقاعدة مرتجعات الشراء | Purchase and return documents are readable Nama entities and supplier money comes from SQL; nothing flags which pairs need immediate matching. |
| `P11` | nama *(+registrations?)* | — | سجل طلبات اعتماد الموردين — مش موجود في أي نظام | Marked Nama/new in the backlog: supplier registration requests live in no connected system today, so attaching any endpoint would be false. |
| `P12` | nama | `/api/v1/nama/lists/{entity}` | تقرير طلبات الشراء على كيان Stlix بس | Purchase requests are Nama documents the generic list read already returns; the Stlix-only cut and its rollup do not exist. |

## Treasury & Finance · خزينة ومالية (`T`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `T1` | banks · nama | `/api/v1/banks` | استعلام SQL لأرصدة الحسابات من JournalEntryLine | The bank accounts themselves are already live from Nama via /api/v1/banks, but Nama REST exposes no balance entity (verified), so the actual numbers must come from the finance SQL connector. |
| `T2` | nama | `/api/v1/nama/lists/{entity}` | تقرير على شيكات Nama — وارد وصادر | Treasury cheques are ordinary Nama documents, readable today only through the generic entity list; no cheque-specific endpoint exists. |
| `T3` | nama | `/api/v1/nama/lists/{entity}` | تقرير على سندات الضرايب والتأمينات في Nama | Insurance, tax and government payments are posted as Nama vouchers whose raw records are reachable via the generic list read; the totals are not computed anywhere yet. |
| `T4` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/finance/suppliers` | تقرير بالالتزامات الجاية — شيكات وأقساط ومستحقات موردين | The obligation documents live in Nama (generic list read) and the only real payable money figure available today is supplier outstanding from the finance SQL connector. |
| `T5` | nama | `/api/v1/nama/lists/{entity}` | حقل متكرر/مرة واحدة على فاتورة Nama وتقرير بمواعيدها | Invoices are Nama documents readable through the generic entity list, but nothing today distinguishes a recurring invoice from a one-off. |
| `T6` | portal · nama | `/api/v1/nama/lists/{entity}` | كونكتور بوابة الفاتورة الإلكترونية ETA — بره Nama | The invoice records are Nama data reachable via the generic list read, but the portal submission/acceptance state lives in an external e-invoicing portal that has no system key in the map. |
| `T7` | marketdata · banks | — | API أسعار صرف خارجي | Real-time CNY/USD/EUR rates exist in no internal system; banks is the closest key because currency hangs off bank accounts, and a market-data system would be the honest new entry. |
| `T8` | nama | `/api/v1/nama/lists/{entity}` | تقرير على أقساط Nama ومواعيد سدادها | Installment schedules are Nama records reachable only through the generic entity list; no due-date roll-up endpoint exists. |
| `T9` | nama | `/api/v1/finance/kpis` | استعلامات SQL لميزان المراجعة والأرباح والمركز المالي | Nama REST exposes no computed reports, so the only real figures today are the company totals in /api/v1/finance/kpis; full statements need new SQL over the GL. |
| `T10` | nama *(+decisions?)* | — | سجل قرارات واعتمادات مالية — مش موجود في أي نظام | Financial decisions are not recorded in any live system; nama is the closest owner of the figures they would reference, but the decision records themselves need a new store. |
| `T11` | banks · nama | `/api/v1/banks`<br>`/api/v1/nama/lists/{entity}` | كونكتور كشف حساب البنك — الطرف التاني للمطابقة | Our side of the reconciliation (accounts and Nama journal documents) is already queryable, but the bank statement feed to match against does not exist yet. |
| `T12` | nama · banks | `/api/v1/finance/customers`<br>`/api/v1/banks` | ربط الفاتورة ببنك التحصيل في تقرير SQL | Uncollected invoice money is real AR and therefore only honest from /api/v1/finance/customers; /api/v1/banks supplies the bank dimension, but nothing joins the two today. |
| `T13` | nama | `/api/v1/finance/suppliers`<br>`/api/v1/nama/lists/{entity}` | استعلام SQL على JournalEntryLine بحسب مركز التكلفة | The generic list read exposes the expense accounts and cost centres themselves; the spend totals are computed figures and must come from the finance SQL connector, not Nama REST. |
| `T14` | nama | `/api/v1/finance/customers`<br>`/api/v1/finance/suppliers` | تواريخ استحقاق الفواتير في استعلامات SQL لأعمار الديون | AR/AP outstanding is real money and is already queryable per customer and per supplier from the SQL connector, which only lacks the date bucketing. |
| `T15` | nama | `/api/v1/finance/kpis` | تقسيم التكاليف ثابت/متغير لكل كيان في SQL | Company-wide sales and purchase totals are already real in /api/v1/finance/kpis, but breakeven needs cost behaviour and an entity dimension that the query does not carry. |
| `T16` | nama | `/api/v1/nama/lists/{entity}` | تقرير على حسابات الزكاة والتبرعات وسنداتها | Zakat and charity postings are Nama documents whose raw records are reachable via the generic entity list; the totals are not computed anywhere. |
| `T17` | nama | `/api/v1/nama/lists/{entity}` | تصنيف أتعاب مهنية على المستفيدين غير الموظفين | Payees and their vouchers are Nama records readable through the generic list, but nothing marks a payment as a professional fee today. |
| `T18` | nama · ai | `/api/v1/finance/suppliers` | طبقة الذكاء AI وتكاليف على مستوى بنود الفاتورة | Purchase totals per supplier are the only real cost figures live today (SQL connector); flagging unreasonable costs additionally requires the planned ai system. |
| `T19` | nama | `/api/v1/nama/lists/{entity}` | استعلام SQL لأرصدة الحسابات الوسيطة المفتوحة | The generic list read exposes the chart of accounts entries themselves; whether a suspense account still carries a balance is a computed figure Nama REST does not expose. |
| `T20` | nama | `/api/v1/finance/suppliers` | تواريخ استحقاق فواتير الموردين في استعلام SQL | Supplier outstanding is real money already queryable from the SQL connector; only the aging buckets are missing. |
| `T21` | nama · banks | `/api/v1/finance/customers`<br>`/api/v1/finance/suppliers` | استعلامات SQL على حركة الخزينة والبنك بالتاريخ | Collected and paid amounts from the SQL connector are the closest real cash-in/cash-out data today, and cash flow also spans the bank accounts, but true movements need new GL queries. |
| `T22` | nama · ai | `/api/v1/nama/lists/{entity}` | طبقة الذكاء AI وتغذية بقيود JournalEntryLine للتصنيف | The posted documents are Nama records readable through the generic list, but deciding a posting is wrong requires the planned ai system. |
| `T23` | nama | `/api/v1/nama/lists/{entity}` | حقل المراجع/المعتمد على الفاتورة في Nama | Invoices are Nama documents reachable via the generic list read; who reviewed each one is an audit-trail attribute not surfaced today. |
| `T24` | banks · nama | `/api/v1/banks` | ربط كل عميل بحساب التحصيل المفضل في Nama | The candidate accounts are already live via /api/v1/banks; what is missing is the preference link that would enhance the banks connector. |
| `T25` | banks · nama | `/api/v1/banks`<br>`/api/v1/banks/master` | مفيش ناقص — شغال من كونكتور banks | This is the one 🟢 treasury item: bank accounts and the bank master list are served from Nama through the banks connector. |
| `T26` | nama | `/api/v1/nama/lists/{entity}` | طبقة طباعة PDF لسندات القبض والصرف | Receipt and payment vouchers are Nama records reachable via the generic entity list; the gateway has no document-rendering output today. |

## Maintenance · صيانة (`M`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `M1` | nama *(+maintenance?)* | `/api/v1/nama/lists/{entity}` | سجل أعطال المعدات — مش موجود في أي نظام | Nama holds the asset register but no breakdown/fault record exists in any connected system, so nothing behind this idea is queryable today and attaching a Nama list endpoint would overstate readiness. |
| `M2` | nama · movement *(+maintenance?)* | `/api/v1/nama/lists/{entity}` | نظام صيانة بجدول وقائي لكل أصل — مش موجود | Scheduled maintenance needs both a PM schedule store (nowhere today) and the vehicle dimension from the planned movement system, so no live endpoint returns the underlying due-date data. |
| `M3` | nama *(+maintenance?)* | — | أوامر شغل صيانة المباني — مش موجودة في أي نظام | Building work orders are recorded in no system; the spend behind them would only become a real figure through an SQL expense report, so there is nothing honest to link to now. |

## Fleet · أسطول / سيارات (`FL`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `FL1` | nama · movement | `/api/v1/nama/lists/{entity}` | تقرير SQL بتكلفة كل عربية من مستندات Nama | Vehicles and the documents charged to them are readable as generic Nama entities, but the daily/monthly TCO is a computed money total, which per the verified Nama REST limits can only be produced by the SQL/finance layer. |
| `FL2` | nama · movement | `/api/v1/nama/lists/{entity}` | تقرير SQL بتكلفة الوقود لكل عربية من Nama | The raw fuel purchase documents are Nama entities reachable through the generic list endpoint; only the per-vehicle summation is missing, and the money total itself has to come from the SQL report layer. |
| `FL3` | nama · movement *(+maintenance?)* | `/api/v1/nama/lists/{entity}` | تقرير تكلفة صيانة لكل عربية من مستندات Nama | Repair spend is booked as ordinary Nama documents that the generic list endpoint can read, but classifying which spend is maintenance (and totalling it) needs a maintenance connector plus the SQL cost report. |

## IT & Electronic Assets · أصول تقنية (`IT`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `IT1` | custody · nama | `/api/v1/nama/lists/{entity}` | كونكتور العهد يربط كل جهاز بموظفه | Device items/assets are readable as Nama entities via the generic list endpoint, but who currently holds which laptop/phone/screen (العهدة) has no live source, so only the register side is queryable. |

## HR · موارد بشرية (`H`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `H1` | nama | `/api/v1/nama/employees`<br>`/api/v1/nama/lists/{entity}` | تقرير على مستندات إنهاء الخدمة في Nama | Resignations are a change of employeeState on the Nama employee master (already returned by /api/v1/nama/employees, which surfaces employeeState and hiring) plus a termination document readable through the generic entity reader; only the period report is missing. |
| `H2` | nama | `/api/v1/nama/employees` | مخزن خطوات التعيين والإنهاء — Nama مفيهوش الكيان ده | Who is joining or leaving is already queryable from the Nama employee master (hiring date, employeeState), but the onboarding/offboarding steps themselves are the "new" half of the backlog source and exist nowhere yet. |
| `H3` | nama · academy | `/api/v1/nama/lists/{entity}` | كونكتور LMS للتدريب — نظام academy | Training and development is exactly what the planned academy system is for; the Nama half (course and training records attached to employees) is readable today only through the generic entity reader, so academy leads and nama supplies the employee link. |
| `H4` | archive *(+forms?)* | — | نماذج وتفويضات إلكترونية — مش موجودة في أي نظام | Forms and delegations (تفويضات) are documents, so archive is the closest of the 17, but issuing, approving and expiring a delegation is a workflow archive does not model — hence a proposed forms system; no live endpoint returns any of this, so no endpoints are attached. |
| `H5` | nama · crm | `/api/v1/nama/lists/{entity}`<br>`/api/v1/crm/{module}` | طلب توظيف في Nama وخط مرشحين على Vtiger | The backlog row names both sources: the requisition (open headcount) is an HR/Nama record reachable via the generic entity reader, while the applicant pipeline would be Vtiger records reachable via the generic module reader — both are raw doors, neither is a report. |
| `H6` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL لرصيد العهدة النقدية المفتوحة | The row explicitly separates this from asset custody (العهدة), so it is cash held by an employee — Nama custody and settlement documents are readable as raw entities, but the outstanding money figure is a computed balance and Nama REST exposes none, so it needs SQL like /api/v1/finance/* does for AR/AP. |
| `H7` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL للمرتبات برصيد السلف المتبقي | Employee advance and loan documents are Nama HR entities readable through the generic entity reader, but "how much is still owed" is a computed balance — the finance SQL connector today covers only SalesInvoice/PurchaseInvoice, so payroll SQL has to be added. |
| `H8` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/nama/employees` | تقرير على عقود الموظفين في Nama | Contracts are their own Nama HR entity (readable via the generic entity reader) and the employee master already gives the hiring date and state that anchor them; nothing but the report layer is missing. |
| `H9` | nama · attendance | `/api/v1/nama/employees`<br>`/api/v1/nama/lists/{entity}` | تقرير داخل وخارج بتواريخ التعيين وإنهاء الخدمة | Headcount in/out is the hiring date and employeeState already returned by /api/v1/nama/employees; attendance is the second system because physical entry/exit is TimeAttendance, and the live attendance route is POST /punch only, so TimeAttendance is readable today solely through the generic Nama entity reader. |
| `H10` | nama | `/api/v1/nama/lists/{entity}` | محرك التجديدات Renewals على تاريخ نهاية العقد | Same raw data as H8 — the Nama contract entity carries the end date — and the backlog itself tags this to the Renewals engine, so the only gap is the shared expiry-window engine, not a connector. |
| `H11` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL لإجمالي المرتبات — Nama REST مبيجمّعش | Per-employee salary elements are Nama entities readable as raw records via the generic entity reader, but the expected monthly payroll is a money total, and money totals are only trustworthy from the SQL connector, which today queries invoices and would have to be extended to payroll tables. |
| `H12` | nama · attendance | `/api/v1/nama/lists/{entity}` | تقرير يربط TimeAttendance بعناصر الأساسي والإضافي | The ratio needs two Nama-held raw sets — punched overtime and night-shift hours (TimeAttendance, only readable via the generic entity reader since /api/v1/attendance/punch is write-side) and the basic/overtime pay elements — so attendance joins nama as a second system. |
| `H13` | nama | `/api/v1/nama/employees`<br>`/api/v1/nama/lists/{entity}` | حقل تصنيف إداري/عمالي وتقرير SQL للمرتبات | The count half is already queryable — /api/v1/nama/employees returns jobTitle and employeeState — but the split needs an agreed category flag, and the cost half is a money total that must come from payroll SQL, not from Nama REST. |
| `H14` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL للمرتبات بمركز التكلفة | Direct vs indirect labour is a cost-centre allocation over payroll lines; the underlying salary/allocation records are Nama entities readable raw via the generic entity reader, but the classification and the totals are a SQL report that does not exist. |
| `H15` | nama · meals · housing | `/api/v1/nama/lists/{entity}` | تقرير SQL للمرتبات وكونكتور الوجبات والسكن | Total loaded cost is payroll plus food and accommodation, so meals and housing join nama; only the payroll component has raw data queryable today (Nama salary entities via the generic reader) and the meals/housing systems are still planned. |
| `H16` | nama · movement | `/api/v1/nama/lists/{entity}` | تقرير SQL لبدل الانتقالات في المرتبات | Transport paid to staff is a payroll allowance element in Nama (raw records readable via the generic entity reader) while bus and vehicle-side transport cost belongs to the planned movement system; the per-employee and total money figures still require SQL. |
| `H17` | nama *(+events?)* | — | سجل فعاليات الموظفين — مش موجود في أي نظام | Nama is the closest of the 17 because attendees are employees, but outings and staff events have no record type in any live system, so a small events system is proposed and — per the planned-status rule — no endpoint is attached. |
| `H18` | nama | `/api/v1/nama/employees` | تقرير شرايح أعمار للموظفين — والمهام مش متسجلة | Headcount and demographics are pure employee-master fields already returned in full by /api/v1/nama/employees, making this the most immediately buildable HR item; only the tasks-per-employee dimension lacks a record type. |
| `H19` | nama | `/api/v1/nama/employees`<br>`/api/v1/nama/lists/{entity}` | تقرير معدل الدوران بتواريخ التعيين والإنهاء | Turnover is leavers over average headcount, and both inputs are Nama employee-master fields (hiring, employeeState) plus the termination entity — no new connector, just the calculation and a period window. |
| `H20` | nama | `/api/v1/nama/lists/{entity}` | تقرير شهري على الجزاءات والخصومات في Nama | The backlog sources this to Nama, so penalty documents and their payroll deduction lines are readable raw through the generic entity reader; the monthly aggregation (and any money total, which belongs in SQL) is what is missing. |
| `H21` | nama | `/api/v1/nama/lists/{entity}` | بيانات تقييم أداء متسجلة فعلاً في Nama | The row sources performance to Nama, so the generic entity reader is the honest door to any evaluation records held there; the blocker is that appraisal data has to exist and be maintained before any report can rank workers. |
| `H22` | nama | `/api/v1/nama/lists/{entity}` | تقرير على مشاكل وشكاوى الموظفين في Nama | The idea is explicitly about issues already logged on Nama, so the raw records are reachable through the generic entity reader; only the listing and trend view on top of that entity has to be built. |

## Marketing · تسويق (`MK`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `MK1` | website *(+social?)* | — | كونكتور السوشيال — Meta وLinkedIn وX | Follower/engagement/reach figures live only in the external social platforms, and of the 17 the closest owner is the public-channel system (website); nothing in the gateway reads them today so no endpoint is honest here. |
| `MK2` | crm *(+marketing?)* | — | سجل معارض — مش موجود في أي نظام | Expected exhibitions per country is lead-generation planning data that would sit beside CRM accounts/leads, but no exhibition record exists in any live connector so there is nothing queryable yet. |
| `MK3` | crm | — | مخزن استبيانات — Vtiger مفيهوش موديول استبيان | Feedback responses would be attached to Vtiger contacts/accounts, but the raw data behind the idea is the responses themselves — the contact list is the audience, not the data — so no endpoint qualifies. |
| `MK4` | crm *(+market-intel?)* | — | سجل منافسين — مش موجود في Vtiger ولا Nama | Competitor profiles are market intelligence with no home among the 17; the CRM is the closest place such records would live, and nothing is queryable until the register is created. |
| `MK5` | crm *(+market-intel?)* | — | مصدر خارجي لأسعار المنافسين | The subject of the idea is competitor pricing, which no live connector holds; our own price list in Nama is only the comparison baseline, so attaching a Nama endpoint would misrepresent what is available. |
| `MK6` | crm · ai *(+market-intel?)* | — | طبقة الذكاء AI ومصدر أخبار عن المنافسين | Competitor news is external content that only exists once the AI layer gathers and summarises it, with the resulting notes filed against the competitor/CRM record; nothing is readable today. |
| `MK7` | website | — | كونكتور تحليلات الموقع — GA4 أو Matomo | Daily traffic, sessions and conversions belong to the registered website system and come from an analytics API the gateway does not yet call, so there is no live endpoint behind this. |

## Investments / Equity · استثمارات ومساهمات (`I`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `I1` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL لأرصدة حقوق الملكية والمساهمين | The contribution and shareholding records are Nama entities and are already readable through the generic list endpoint, but the invested value or equity balance is a computed money figure that only the SQL-backed finance path can produce. |

## Warehouse & Inventory · مخازن ومخزون (`WH`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `WH1` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/nama/{entity}/{code}` | تقرير على أذون الصرف والاستلام في Nama | Delivery and receipt notes are ordinary Nama documents: the generic list read exposes the raw document set and the by-code read opens a single note, but nothing aggregates them yet. |
| `WH2` | nama | `/api/v1/nama/lists/{entity}` | تقرير على مرتجعات البيع والشراء في Nama | Return documents are Nama entities readable through the generic list endpoint; no return-specific endpoint exists, so the honest fallback is the only source. |
| `WH3` | nama · inventory | `/api/v1/nama/lists/{entity}`<br>`/api/v1/inventory` | محرك رصيد مخزون يضم مستندات Nama غير المرحّلة | Book stock and the not-yet-posted documents are raw Nama entities via the generic list read, while the live stocktake app already exposes the physically-counted-but-unposted side; the merged real-time figure itself is not computed anywhere. |
| `WH4` | nama | `/api/v1/nama/lists/{entity}` | تقرير آخر حركة وأعمار المخزون من مستندات Nama | Slow-moving detection needs per-item last-movement dates derived from movement documents, which are only readable as raw Nama entities today. |
| `WH5` | nama | `/api/v1/nama/lists/{entity}` | تقرير يربط المرتجعات بأمر البيع الأصلي | Order-remnant returns are Nama return documents joined to their order; both sides are raw entities reachable only through the generic list read. |
| `WH6` | nama | `/api/v1/nama/lists/{entity}` | تقرير حركة مخزن الخردة في Nama | Scrap increases/decreases/damage are movement documents against one Nama warehouse; the raw documents are queryable generically but the netted change is not. |
| `WH7` | nama | `/api/v1/nama/lists/{entity}` | محرك رصيد مخزون محسوب — Nama REST مبيطلعش أرصدة | Detecting negative/oversold stock requires a per-item balance that Nama REST does not publish, so only the underlying movement documents are queryable today. |
| `WH8` | nama | `/api/v1/nama/invitem/exists`<br>`/api/v1/nama/lists/{entity}` | مسح تكرار شامل على InvItem كله | The item master is Nama data; /api/v1/nama/invitem/exists genuinely answers duplicate-by-identity-code for one code and the list read exposes the item and class entities, but no batch dedupe pass exists. |
| `WH9` | inventory · nama | `/api/v1/inventory`<br>`/api/v1/inventory/counts`<br>`/api/v1/inventory/manual`<br>`/api/v1/nama/lists/{entity}` | تقرير تفصيلي للجرد بالصنف والعدّاد والمنطقة | The live stocktake connector already returns counted quantities with counter and zone plus manually added items, and the Nama list read supplies item descriptions; only the detailed report itself is missing. |
| `WH10` | inventory · nama · ai | `/api/v1/inventory`<br>`/api/v1/nama/lists/{entity}` | طبقة الذكاء AI لاختيار عينة جرد عشوائية | The sampling frame is live (tracked/counted items from the stocktake app, item master from Nama), but choosing and pushing a random spot-count needs the not-yet-built AI layer. |
| `WH11` | inventory · nama | `/api/v1/inventory` | سجل مواعيد الجرد ومحرك التجديدات Renewals | The stocktake app exposes the current session state (rev, tracked, counted, counters) which a reminder keys off, but there is no stored cadence or due-date history to alert against. |
| `WH12` | nama | `/api/v1/nama/lists/{entity}` | تجميع أذون الصرف بالمخزن والصنف في Nama | Issued quantities come from Nama goods-issue documents, readable only as raw entities via the generic list endpoint; no per-warehouse total is computed. |
| `WH13` | inventory · nama | `/api/v1/inventory/counts`<br>`/api/v1/inventory`<br>`/api/v1/nama/lists/{entity}` | رصيد دفتري من Nama نقارن بيه جرد اليوم | The actual side is already live in the stocktake counts endpoint and the book side's source documents are readable via the Nama list endpoint, but the actual-vs-book diff that seeds the next day's count does not exist. |
| `WH14` | nama · custody | `/api/v1/nama/lists/{entity}` | كونكتور العهد وحالة الترحيل/الاعتماد على مستندات Nama | Unposted and unapproved documents are Nama entities reachable through the generic list read, but the custody side has no connector at all, so the Live-vs-Pending view cannot be assembled yet. |
| `WH15` | nama · inventory | `/api/v1/nama/lists/{entity}`<br>`/api/v1/inventory/counts` | تقرير رصيد مخزون — Nama REST مبيطلعش كميات | Book quantity must be derived from raw Nama movement documents since REST exposes no balance, while the stocktake counts endpoint already returns real counted quantities per item as the physical counterpart. |
| `WH16` | nama | `/api/v1/nama/lists/{entity}` | تقرير رصيد مخزون وقواعد تحويل الوحدات للوحدة الأكبر | The unit definitions and item master carrying conversion factors are readable as Nama list entities, but the quantities to convert are not exposed by Nama REST. |
| `WH17` | nama | `/api/v1/nama/lists/{entity}` | مطابقة أسماء تقريبية على InvItem كله | Item names live in the Nama item master, fully readable via the list endpoint, and the existing exists-check proves exact duplicates only; near-duplicate names need a matching pass. |
| `WH18` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/nama/{entity}/{code}` | قواعد تحقق على حقول الوحدات في InvItem | Unit-of-measure values sit on Nama item records: the list read exposes the item and unit entities and the by-code read opens one item's fields, but nothing flags wrong units. |

## Logistics, Shipping & Customs · شحن وجمارك (`LG`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `LG1` | nama · movement | `/api/v1/nama/lists/{entity}` | موديول تتبع شحنات فوق أوامر شراء Nama | The purchase orders and incoming-goods documents behind an in-transit shipment are Nama entities readable through the generic list endpoint; only the transit status itself is missing, which is why the logistics (movement) system is the second key. |
| `LG2` | nama · movement | `/api/v1/nama/lists/{entity}` | موديول طلبات شحن فوق طلبات الشراء في Nama | "Required shipments" is derived from open purchase demand/orders already held in Nama and readable via the generic list endpoint; no more specific endpoint covers purchasing documents. |
| `LG3` | nama · movement | `/api/v1/nama/lists/{entity}` | موديول عروض أسعار شحن جنب عروض Nama | Purchase quotations and shipments-under-preparation are Nama documents reachable via the generic list endpoint, but the shipping-quote and shipping-RFQ half has no store yet and belongs to the logistics system. |
| `LG4` | movement · archive *(+customs?)* | — | موديول جمارك لنموذج 4 وكونكتور الأرشيف للمسح | Form 4 is a customs/insurance import document whose source is entirely new — nothing about it is queryable in Nama today, so no endpoint may be attached; `movement` is the closest registered system but a real customs module is what this wants. |
| `LG5` | movement · nama | `/api/v1/nama/lists/{entity}` | كونكتور شحن داخلي فوق أذون التسليم في Nama | Domestic shipping is exactly what the registered `movement` (vehicle/gate & logistics) system covers, while the delivery/dispatch documents behind it are Nama entities readable via the generic list endpoint. |
| `LG6` | movement *(+customs?)* | — | موديول تخليص جمركي بالمخلصين وشغل كل شحنة | The backlog source is `new`: clearance-agent jobs, fees per shipment and agent performance exist nowhere queryable, so attaching any Nama endpoint would be dishonest. |
| `LG7` | movement | — | كونكتور حجز شحن تحت نظام movement | Cargo bookings are a pure `new` source with no Nama footprint; the registered `movement` system already describes itself as logistics, so no new system key is needed — only the connector. |
| `LG8` | portal | — | كونكتور بوابة نافذة Nafeza الجمركية | Nafeza is an external government portal with no local data at all, so no endpoint applies; it is a customs-domain integration that `movement` only approximates. |

## Safety / HSE · السلامة (`SF`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `SF1` | nama *(+hse?)* | `/api/v1/nama/employees` | سجل إصابات عمل — مش موجود في أي نظام | The employee master this report must join to is genuinely live at /api/v1/nama/employees, but the injury events themselves are recorded nowhere, so the endpoint is only the employee dimension, not the report. |
| `SF2` | nama · custody *(+hse?)* | `/api/v1/nama/lists/{entity}` | سجل صرف مهمات الأمان للعمال فوق مستندات Nama | PPE, laundry and cleaning supplies are ordinary Nama items and store documents readable through the generic list endpoint; what is missing is the issuance record tying each item to a worker, which is custody data. |

## Governance & Watchlist · حوكمة وقوائم حظر (`GV`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `GV1` | nama · crm | `/api/v1/nama/employees`<br>`/api/v1/nama/lists/{entity}`<br>`/api/v1/crm/accounts` | محرك Watchlist يخزّن علامات القايمة السودا ويربطها | The three party sets this blacklist targets are already queryable — employees via the employee endpoint, suppliers via the generic Nama list endpoint (finance/suppliers returns balances, not a master, so it must not be used here), and customers via CRM accounts; only the flag store is missing. |
| `GV2` | nama | — | استعلام SQL على جداول نشاط مستخدمي Nama | Nama REST exposes no user-activity/audit entity and the live SQL surface is limited to /api/v1/finance/* (KPIs, customer and supplier balances), so nothing queryable covers this yet; it surfaces under monitoring because it is an activity feed, not a report. |

## Communications · تواصل (`CM`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `CM1` | email | — | كونكتور IMAP للبريد — لسه مش متوصّل | Answered-vs-unanswered is computed from mailbox threads, which only an IMAP connector can read; no live endpoint touches mail today. |
| `CM2` | crm | `/api/v1/crm/{module}` | تقرير SLA على موديول HelpDesk في Vtiger | Tickets are standard Vtiger HelpDesk records and the generic module reader can already query them read-only, so the raw data is reachable — only the ticket KPI report on top is missing. |
| `CM3` | telco · custody | — | تغذية CDR من شركة المحمول لخطوط الشركة | Call and SMS detail records live with the operator, not in any of our systems; callcenter is the closest voice-owning system of the 17 and custody covers the line/SIM assigned to each employee. |
| `CM4` | callcenter | — | كونكتور نظام callcenter — CDR وIVR وإحصائيات | This idea is the callcenter system itself, which is registered as planned with no router behind it, so nothing is queryable yet. |
| `CM5` | crm | — | نوع حالة شكوى في Vtiger — مش موجود دلوقتي | Complaints would be filed as Vtiger cases beside tickets, but no complaint record type is set up yet, so unlike CM2 there is no existing module whose data the generic reader would return. |
| `CM6` | crm | — | نموذج ومخزن اقتراحات — مش موجود في أي نظام | A suggestion box has no module in Vtiger or entity in Nama, so the raw data does not exist anywhere yet; the CRM is simply where the tracked records would naturally live. |

## Attendance · حضور وبصمة (`AT`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `AT1` | attendance · nama | `/api/v1/nama/employees`<br>`/api/v1/nama/lists/{entity}` | تقرير حضور على TimeAttendance للكيانين | The employee endpoint returns the attendanceMachineCode that links a person to a fingerprint device, and the punch documents themselves are a Nama entity readable through the generic list endpoint; the punch route is write-only so it is not a data source. |
| `AT2` | attendance · nama | `/api/v1/nama/employees` | تطبيق بصمة موبايل بالموقع يغذّي TimeAttendance | Only the employee master behind who may punch is queryable; mobile punches do not exist yet, so no attendance document endpoint may be claimed for this idea. |

## Market Data & Rates · بيانات السوق والأسعار (`MD`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `MD1` | marketdata | — | API خارجي لأسعار الذهب | Gold quotes are a pure external market feed with no internal source; banks is the closest of the 17 because these rates are treasury reference data consumed next to currency and accounts. |
| `MD2` | marketdata | — | API خارجي لأسعار البترول | Barrel prices come only from an external market feed; nothing in Nama, CRM or inventory carries them, so no live endpoint can be attached. |
| `MD3` | nama · marketdata | `/api/v1/nama/lists/{entity}` | API أسعار وقود خارجي وتقرير استهلاك من Nama | This idea has two halves: our own fuel purchase/issue documents are Nama entities already readable via the generic list endpoint (and tie to vehicle movement), while the market fuel price is external; any fuel cost total would still have to come from the SQL/finance path. |
| `MD4` | marketdata · ai | — | طبقة الذكاء AI وتاريخ أسعار صرف للتنبؤ | An EGP forecast is a model output, not stored data — it needs Layer 4 (AI) on top of external rate history, so nothing is queryable and the banks system is only where the result would be consumed. |
| `MD5` | marketdata | — | API أسعار صرف خارجي — زي T7 | Live CNY/USD/EUR rates exist only outside the company; the banks connector reads account currency codes from Nama but no rate, so attaching /api/v1/banks would falsely imply rates are available. |

## Quality · جودة / QC (`Q`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `Q1` | nama · archive *(+quality?)* | — | سجل نتايج فحص وشهادات جودة — مش موجود | Test results and certificates are captured in no connected system; Nama items and job orders are only the keys they would attach to, so no live endpoint returns the actual QC data. |

## Admin & Compliance · شؤون إدارية وامتثال (`AC`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `AC1` | archive · nama | — | سجل تأشيرات بتواريخ انتهاء ومحرك التجديدات Renewals | The backlog source is `new` — the employee endpoint returns staff records but no visa or residency expiry field, so the raw data behind a renewal alert is not queryable anywhere today. |
| `AC2` | archive · nama | `/api/v1/nama/lists/{entity}` | سجل رخص العربيات بتواريخها ومحرك التجديدات Renewals | The source is `new / Nama`: the vehicles and assets whose traffic licences are tracked are Nama entities readable via the generic list endpoint, while the licence documents themselves need the archive. |
| `AC3` | archive | — | سجل مستندات بتواريخ انتهاء لمحرك التجديدات Renewals | A purely `new` source — this is the generic renewals umbrella over AC1/AC2/AC4/AC5, and until a document register with dates exists there is nothing to query; it drops Nama because no commercial document is implied. |
| `AC4` | nama · archive | `/api/v1/nama/lists/{entity}` | سجل عقود إيجار بتواريخ انتهاء ومحرك التجديدات Renewals | Lease contracts and their rent postings are Nama documents reachable through the generic list endpoint; the lease agreement itself is an archive document, and only the expiry-window report is missing. |
| `AC5` | nama · archive | `/api/v1/nama/lists/{entity}` | سجل اشتراكات بتواريخ تجديد ومحرك التجديدات Renewals | Subscriptions bill as recurring Nama invoices readable via the generic list endpoint, so the spend side is queryable; the renewal-date field and the alert are what must be built. |
| `AC6` | nama · surveillance | `/api/v1/nama/employees` | جدول ورديات الأمن وكونكتور surveillance | The backlog row itself ties this to the surveillance system; the guards are on payroll so the employee endpoint genuinely returns the roster's base records, but no shift schedule or post assignment is queryable. |

## Operations & Production · عمليات وإنتاج (`OP`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `OP1` | nama | `/api/v1/nama/lists/{entity}` | تقرير على أوامر التشغيل لدى الغير في Nama | Prep orders sent out to third parties are Nama documents that the generic entity list can already read; only the open-WIP aggregation on top of them is missing. |
| `OP2` | nama *(+production?)* | `/api/v1/nama/lists/{entity}` | مخزن خطوات ومهام لكل أمر تشغيل — مش موجود | Job orders and batches are readable as Nama entities through the generic list endpoint, but the plan steps and their statuses have no store anywhere, so only the anchor records are queryable. |
| `OP3` | nama *(+production?)* | — | تغذية إنتاج يومي وهالك من الصالة — مش موجودة | Daily floor productivity and scrap are not logged in Nama or any live connector, so no endpoint returns the underlying counts; a production/MES source has to exist first. |
| `OP4` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL يقارن سعر أمر التشغيل بالتكلفة الفعلية | Job orders and the sales documents priced from them are readable as Nama entities, but the accuracy percentage is a computed money comparison that only the SQL/finance layer can produce. |
| `OP5` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL مخطط مقابل فعلي لأوامر التشغيل | The planned and actual cost lines sit on Nama job-order documents the generic list endpoint can read, yet Nama REST exposes no computed cost, so the Planned/Actual engine must run over SQL. |
| `OP6` | nama *(+production?)* | — | تغذية ساعات تشغيل الماكينات — مش موجودة في أي نظام | Per-machine running hours come from the machines themselves and are not recorded in Nama or any live connector, so there is no endpoint that returns them. |
| `OP7` | nama | `/api/v1/nama/lists/{entity}` | تقرير SQL لتكلفة الطن محمّلة بالمصاريف غير المباشرة | Items and their production documents are readable as Nama entities, but an overhead-loaded cost per ton is a computed money figure and Nama REST exposes no costing report, so the number itself requires SQL. |
| `OP8` | nama | `/api/v1/nama/lists/{entity}` | تقرير يومي على ساعات التشغيل المسجلة في Nama | This is explicitly the hours already logged inside Nama, so the raw entries are reachable through the generic entity list endpoint; only the daily productivity roll-up is missing. |
| `OP9` | nama *(+production?)* | — | خطة تشغيل يومية — مش موجودة في أي نظام | No plan document exists in Nama or any live connector, so nothing behind the daily production plan is queryable; the plan side must be created before a plan-vs-actual view is possible. |

## Travel & Personal · سفر — خاص بالمالك (`TR`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `TR1` | movement *(+travel?)* | — | سجل رحلات الرئيس بالوقت والتكلفة والهدف | Owner-personal travel data exists in no system; `movement` is the nearest of the 17 but a travel system is the honest addition, and nothing about trips is queryable today. |
| `TR2` | movement · nama *(+travel?)* | `/api/v1/nama/lists/{entity}` | قايمة مشتريات السفر مربوطة بطلبات الشراء في Nama | The source is `new / Nama`: anything actually bought posts as a Nama purchase document readable via the generic list endpoint, which is why this breaks the travel-only default. |
| `TR3` | movement *(+travel?)* | — | موديول checklist عام على المنصة | A `new` source with no data anywhere; it belongs to the same travel/ops tracker as TR1, so it inherits the domain default rather than claiming a system of its own. |

## Legal · قانوني (`L`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `L1` | archive *(+legal?)* | — | موديول قضايا بالجلسات والأطراف — مش موجود | A pure `new` source with no queryable footprint; none of the 17 systems is legal, so archive is the closest home for case files while a dedicated legal system is what the map actually lacks. |

## Product / R&D · منتجات وتطوير (`PD`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `PD1` | nama *(+rnd?)* | `/api/v1/nama/invitem/exists` | خط مقترحات منتجات ينتهي بإضافة صنف في Nama | The proposal records are a `new` source, but the existing product catalog a proposal must be screened against is genuinely queryable through the item-existence check; the R&D pipeline itself has no registered system. |

## Management & Planning · إدارة وتخطيط (`G`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `G1` | archive · regulations *(+planning?)* | — | لوحة توجيهات نكتب فيها مش قراءة بس | The gateway already stores and serves idea records parsed from BACKLOG.md, so the raw data genuinely is queryable at /api/v1/ideas; what is missing is an owner-authored, writable directions register, which no registered system covers. |
| `G2` | regulations · archive | — | سجل قرارات إدارية بالمصدر والتاريخ والحالة | Administrative decisions are issued directives, which is exactly what the registered `regulations` (policies & bylaws) system holds; the source is `new`, so nothing is queryable yet. |
| `G3` | ai · nama | `/api/v1/finance/kpis`<br>`/api/v1/workspace` | طبقة الذكاء AI لتقييم مؤشرات الأنظمة المجمّعة | Its backlog source is `all`: the SQL-backed finance KPIs and the workspace aggregation already expose the cross-connector figures a health score consumes, so the only blocker is the Layer-4 AI scoring — which is why it breaks the archive/regulations default. |

## Platform & AI · Platform & AI (`A`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `A1` | ai · nama · crm · banks · inventory · attendance | `/api/v1/workspace`<br>`/systems` | طبقة الذكاء AI فوق الكونكتورات الشغالة | A1 is the natural-language orchestrator over every connector, so its home is the `ai` system reading the live Nama and CRM connectors; the raw substrate it would query is already aggregated at /api/v1/workspace, and /systems is the connector map it would route over — neither is a report, and A1 carries no status marker so it parses as planned. |
| `A2` | nama | `/api/v1/nama/lists/{entity}`<br>`/api/v1/nama/{entity}/{code}` | كيانات متعرّفة فعلاً في Nama NameBuilder | NameBuilder is a Nama-native capability: entities/screens defined there are read back over the same Nama REST, and the generic list/get readers are already the honest way to reach any such entity once it exists — no NameBuilder-specific endpoint is claimed. |
| `A3` | ai · crm · nama | `/api/v1/crm/leads`<br>`/api/v1/crm/accounts`<br>`/api/v1/crm/contacts`<br>`/api/v1/finance/customers` | طبقة الذكاء AI فوق قراءات Vtiger وتقارير SQL | The note scopes it as an AI agent over CRM+Nama, so the pipeline data (leads, accounts, contacts) is already queryable on the CRM connector, and the only honest money signal for follow-up priority and forecast is the SQL-backed /api/v1/finance/customers — Nama REST exposes no computed balances. |

## Platform UX & Input · تجربة الاستخدام والإدخال — عابر لكل الموديولات (`UX`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `UX1` | nama | `/api/v1/nama/lists/{entity}` | نفس ودجت الاقتراح والتصحيح على باقي حقول الإدخال | The autocomplete/autocorrect corpus is the Nama item-class lists, which /api/v1/nama/lists/{entity} already serves server-side (its docstring says it powers the item-builder's live attribute lists); the type-search box is already shipped (status next, link /tools/name-builder), so only the remaining inputs are outstanding. |
| `UX1b` | nama | `/api/v1/nama/invitem/exists`<br>`/api/v1/nama/lists/{entity}` | محلّل يحوّل الاسم المكتوب لأجزاء الكود | Both halves of the raw data are live: the attribute lists to validate each part against, and the read-only duplicate check by description1 that decides accept/reject — the idea is still planned because the free-text-to-parts parser between them does not exist, so these are data sources only, not the deliverable. |
| `UX2` | website *(+frontend?)* | — | مكوّن إدخال نص طويل لصق وتعديل في الواجهة | A paste-and-edit long-text option in every writing input is pure browser-side plumbing with no upstream system and nothing queryable today; `website` (the only forms/web key in the map) is the closest of the 17, and the honest home is a new `frontend` system matching the gateway's existing `front-end` connector. |
| `UX3` | ai | — | API خارجي لتحويل الكلام العربي لنص STT | Speech-to-text and Arabic voice search are an AI service that must be proxied server-side, so `ai` (LLM/agent endpoints) is the closest live key; the catalog already models the Arabic STT connector under a distinct `voice` system that is not among the 17, and no audio/transcription endpoint exists yet. |
| `UX4` | website *(+frontend?)* | `/api/v1/workspace` | مخزن إعدادات الودجتات فوق workspace API | Launchable dashboard widgets render the unified workspace's per-section summaries, which /api/v1/workspace already returns as raw data; the widget definitions themselves are front-end state with no system in the map, so `website` is the closest stand-in and `frontend` the proposed home. |

## Platform & Access · منصّة وصلاحيات — عابر للمنصّة كلها (`PA`)

| id | systems | data endpoints | ناقص | why |
|---|---|---|---|---|
| `PA1` | omnichannel | — | كونكتور WhatsApp وWeChat Business API | Customer messaging channels are closest to the existing callcenter and email keys, but the gateway's own catalog already names the real home `omnichannel`; nothing is queryable today because no messaging connector exists, and the conversations would surface against CRM contacts/leads. |
| `PA2` | idp | — | كونكتور دخول موحد SSO مع Google Workspace | Single Sign-On is platform-wide auth with no upstream business system, so `website` (the platform front door) is the closest of the 17 while the catalog's `sso` connector already points at an `idp` system; no identity data is queryable anywhere today, so no endpoint is attached. |
| `PA3` | idp | — | طبقة صلاحيات وأدوار على مستوى المنصة | RBAC is the double gate over every feature — gateway role check plus each connector's own permissions — so it belongs to the same proposed identity/access system as SSO; no user, role or permission data exists behind any live endpoint, and the systems list the overview section already shows is what an RBAC view would filter. |
| `PA4` | ai | — | API خارجي لتحويل الكلام العربي لنص STT | PA4 explicitly points at UX3 — platform-wide Arabic voice search and dictation — so it maps identically: closest live key `ai` for a server-side STT proxy, proposed `voice` system per the catalog, and nothing queryable until that connector is built. |

