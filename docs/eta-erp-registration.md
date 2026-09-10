# تسجيل نظامنا على بوابة الممول (مرة واحدة)

من غير الخطوة دي مفيش `client_id`/`client_secret` أصلًا، وأي محاولة اتصال بترجع
`{"error":"invalid_client"}` — وده بالظبط اللي حصل لما جرّبنا: البورتال رد، بس رفض
المفاتيح لأن مفيش نظام مربوط.

**اللي بنسجّله ده نظام يقرأ بس.** الإصدار مش هيمر من هنا (محتاج eSeal على توكن)،
والإلغاء/الرفض مقفولين في `.env`.

## المطلوب قبل ما تبدأ

- حساب **مدير** على بروفايل الممول (`profile.eta.gov.eg`) لكل كيان. لو الحساب مع
  المحاسب، هو اللي يعمل الخطوات دي أو يديك صلاحية مدير.
- **الرقم الضريبي** لكل كيان (موجود عندنا في `.env`).
- من عندنا (جاهزين):
  - **Callback base URL**: `https://gw.stlixvalley.com/eta/erp`
  - **API key** للـ callback: القيمة اللي في `ETA_ERP_CALLBACK_KEY` في
    `/opt/stlix-gateway/.env` — تتولّد بـ `openssl rand -hex 24`.

## الخطوات

1. ادخل `https://profile.eta.gov.eg` بحساب المدير بتاع الكيان.
2. من القائمة: **الأنظمة / ERP Systems** ← **تسجيل نظام جديد**.
3. النوع: **ERP** (مش POS). البيئة: **Production**.
   - لو عايز تجرب الأول من غير أي مساس بالإنتاج، اعمل تسجيل على **Pre-production**
     وهنحط `ETA_ENV=preprod` — نفس الكود بالظبط.
4. اسم النظام: `STLIX Gateway` (أو أي اسم واضح).
5. لو طلب **عنوان النظام / Callback URL**: `https://gw.stlixvalley.com/eta/erp`
   وطلب **API key**: حط قيمة `ETA_ERP_CALLBACK_KEY`.
   ETA هتعمل `PUT https://gw.stlixvalley.com/eta/erp/ping` وتستنى نفس الرقم الضريبي
   يرجع لها — ده اللي الـ endpoint بتاعنا بيعمله، فالتأكيد المفروض ينجح فورًا.
6. بعد الحفظ هتظهر **Client ID** و **Client Secret 1** و **Client Secret 2**.
   - الـ secret بيتعرض **مرة واحدة** — انسخه في نفس اللحظة.
   - Secret 2 موجود عشان تغيّر المفتاح من غير ما توقف النظام؛ سيبه لوقت التغيير.
7. كرّر من 1 لـ 6 للكيان التاني.

## بعدها

حط القيم في `/opt/stlix-gateway/.env` جوّه `ETA_ENTITIES_JSON` (سطر واحد)، وبعدين:

```bash
cd /opt/stlix-gateway && docker compose -f docker-compose.prod.yml up -d --build
curl -s -H "X-API-Key: $GW" https://gw.stlixvalley.com/api/v1/eta/group/ping
curl -s -H "X-API-Key: $GW" https://gw.stlixvalley.com/api/v1/eta/stlix/ping
```

`{"ok": true}` معناها خلصنا، والسحب الشهري هيمشي لوحده.

## لو اتقفل الطريق

- **مفيش خيار «تسجيل نظام»** في البروفايل → الحساب مش مدير، أو الكيان مسجّل تحت
  ممثل (مفوّض) — الممثل هو اللي يسجّل وياخد الـ credentials.
- **الـ ping بيفشل** → اتأكد إن `ETA_ERP_CALLBACK_KEY` متحط وإن الـ container متعمله
  rebuild بعد ما اتحط؛ جرّب من برّه:
  ```bash
  curl -i -X PUT https://gw.stlixvalley.com/eta/erp/ping \
       -H "Authorization: ApiKey <KEY>" -H "Content-Type: application/json" \
       -d '{"rin":"<الرقم الضريبي>"}'
  ```
  المفروض `200 {"rin":"…"}`.
- **`invalid_client` بعد التسجيل** → غالبًا اتسجّل على بيئة تانية (preprod) أو الـ
  secret اتنسخ ناقص.
