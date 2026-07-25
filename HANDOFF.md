# HANDOFF — حالة آخر جلسة

> ابدأ بالترتيب: `MASTER_EXECUTION_RUNBOOK.md` → `SESSION_STATE.json` →
> `HANDOFF.md` → `NEXT_STEP.md`.
>
> `D:\Nama Code project\stlix-gateway` · git محلي بس · كلّم المالك بالعربي المصري.
> **الهَب = الجيتواي = المنصّة = المشروع ده. مافيش مجلد تاني.**

## آخر جلسة — 2026-07-25: الأرقام اللحظية

### النتيجة

أيوه، ينفع نحسب AR/AP لحظي من مستندات الفواتير نفسها وسطور تسويتها:

```text
gross = Σ details[].price.price
net   = Σ details[].price.netValue
paid  = Σ externalPaymentLines[].paymentValue
open  = net - paid
```

السندات `ReceiptVoucher` و`PaymentVoucher` مفيدة للتحقيق في حركة السداد، لكن ماينفعش
نجمعها كلها كرصيد عملاء/موردين لأن فيها أطراف وحركات تانية. مصدر الرصيد الحيّ هو
الفاتورة + `externalPaymentLines`.

### الإثبات على المجتمع الكامل

نسخة SQL المرجعية as-of **2026-07-14**:

- AR = **20,021,265.86 ج**.
- AP = **186,710,932.48 ج**.

لقطة REST السحابية النهائية على preview الجديد
(`2026-07-25T03:19:16+00:00`، و`complete=true`):

- **6,881** فاتورة مبيعات مُرحّلة؛ AR = **19,914,391.24 ج**.
- **6,864** فاتورة مشتريات مُرحّلة؛ AP = **187,491,246.17 ج**.
- بعد شرح الفواتير الجديدة والتسويات والتعديلات بعد النسخة، الباقي غير المفسّر:
  **0.17 ج AR** و**0.16 ج AP**.
- مطابقة يونيو 2026 عدّت على **138** فاتورة مبيعات و**164** فاتورة مشتريات، مع
  allow-list صريح لإلغاء السند المعروف `FP22026060000105`.

الوضع المحلي الصارم وقف على **401** لأن REST المحلي `:8080` لا يقبل credential السحابة.
مافيش ادعاء إنه عدّى.

### اللي اتنفّذ

- `app/integrations/finance/live.py`: لقطة خلفية كاملة للعملاء والموردين وفواتير البيع
  والشراء، وتجميع KPI وأرصدة الأطراف من REST.
- `?source=live` على `/api/v1/finance/{kpis,customers,suppliers}`، مع
  `/api/v1/finance/live` وrefresh يدوي.
- build تلقائي عند الإقلاع، وتحديث دوري اختياري بـ`LIVE_FINANCE_REFRESH_SECONDS`.
- `scripts/reconcile_live_vs_sql.py`: مقارنة read-only مستند بمستند، exit 1 عند أي فرق
  غير مفسّر، و`--allow-reversal` للإلغاءات المراجَعة فقط.
- SQL اتصلّح: الربط بـ`subsidiaryId` + `subsidiaryEntityType`، وحالة
  `documentFileStatus='Stable'`، وFLOAT بدل BIGINT للحفاظ على القروش.
- NamaClient اتقفل على قواعد الـpaging والـ400 الجزئي، مع retry لأخطاء النقل فقط،
  ووسم أي sweep ناقص.
- المسودات: كود منتهي بـ`@draft` **أو كود فاضي** = غير مُرحّل.
- الأكواد المكررة بين legal entities ما بتتدمجش؛ الكود لوحده مش primary key.
- التقارير بتعرض SQL/live بوضوح، والهَب الداخلي ما يفضّلش live إلا لو اللقطة كاملة.
- **115 اختبار يعدّوا**.

### التشغيل

- :8000 اتساب زي ما هو لأنه كان من شات تاني.
- آخر نسخة اتشغّلت باسم `stlix-gateway-alt` على
  `http://127.0.0.1:8010`.
- بعد أي تعديل Python: restart ثم استنى `GET /api/v1/finance/live` لحد
  `available=true` و`building=false`.

## قواعد ما تتكسرش

- كل الكنكتورات read-only؛ أي كتابة workflow مدقّق + HITL.
- المفاتيح server-side؛ المتصفح ماياخدش سر.
- ماينزلش رقم فلوس قبل مطابقة SQL لنفس الفترة.
- `records_count` للصفحة فقط؛ paging يبدأ من 1 و`pageSize` لحد 1000.
- HTTP 400 ممكن يكون نجاح جزئي؛ اقرأ الـbody قبل الحكم.
- الفكرة المخططة ما تاخدش لينك لحاجة مبنية.
- سطر جديد في `BACKLOG.md` يظهر في `/tools/ideas` فورًا.

## مفتوح بقرار المالك

- `modules/platform/hub.public.html`: يتشال ولا يعتمد `/api/v1/map`؟
  شات تاني عدّله ووصّله؛ **ما نعتبرش ده قرار من المالك**.
- 🔴 تغيير المفاتيح المكشوفة (Anthropic أولًا): مؤجّل بطلب المالك.
  `secrets/gates-keys.backup.md`.

## التالي

`NEXT_STEP.md`: تحويل المطابقة لحارس أوتوماتيك `pass|drift|blocked`. المصدر الافتراضي
يفضل `sql` لحد قرار صريح وبعد وجود الحارس.
