# موديول الاستيراد والشحن — التركيب

الموديول ده بيضيف على الهَب كارت جديد **🚢 الاستيراد والشحن** وصفحة `/tools/imports`،
وبياخد إجراءَي **SOP-IMP-001** (خطوات الاستيراد) و **SOP-IMP-002** (بوليصة الشحن)
ويخليهم ملف شحنة شغّال بدل ورقة: 46 خطوة بمسؤوليها ونقط التحقق، 23 منهم **بوابة توقف**،
مطابقة الـ ACID حرف بحرف، عدّاد الـ free time والأرضيات، والـ landed cost للطن —
ومربوط بـ **موديول الشحن البحري في نما (LCShipment)**.

## 1) الملفات

فك الضغط جوه `D:\Nama Code project\stlix-gateway` (كلها ملفات جديدة، مفيش حاجة بتتمسح):

```
app/integrations/imports/__init__.py
app/integrations/imports/sop.py          ← الإجراء نفسه كـ data
app/integrations/imports/engine.py       ← ACID / free time / landed cost / gates / alerts
app/integrations/imports/store.py        ← ملف الشحنة (SQLite: data/imports/imports.db)
app/integrations/imports/nama_link.py    ← الربط بـ LCShipment في نما
app/integrations/imports/router.py       ← /api/v1/imports/*
modules/import/shipments.html            ← الشاشة
tests/test_imports.py                    ← 29 اختبار
scripts/wire_imports.py                  ← بيوصّل الموديول بالجيتواي
docs/sop/SOP-IMP-001-import.md
docs/sop/SOP-IMP-002-bill-of-lading.md
```

## 2) التوصيل

```bat
cd /d "D:\Nama Code project\stlix-gateway"
python scripts\wire_imports.py
pytest tests\test_imports.py -q
```

السكريبت بيعمل 5 تعديلات صغيرة في ملفات موجودة (بيتشغّل مرة واحدة، وآمن لو اتعاد):

| الملف | التعديل |
|---|---|
| `app/config.py` | سطر `imports_db_path` |
| `app/main.py` | `import` + `include_router(imports_router)` |
| `app/routers/tools.py` | route لـ `/tools/imports` |
| `app/auth/resources.py` | Resource `imports` — الكارت في الهَب والصلاحيات |

لو قال **«مالقيتش نقطة الإدراج»** يبقى الملف اتغيّر من ساعة ما اتكتب — التعديل ساعتها بالإيد
(الأسطر مكتوبة في `EDITS` جوه السكريبت).

> الصلاحية: بعد التوصيل هتلاقي مورد جديد اسمه `imports` في شاشة
> https://hub.stlixvalley.com/hub/admin.html — ادّي `يشوف` لمين يتابع الشحنات
> و`يعدّل` للمسؤول الإداري والحسابات. الكارت مبيظهرش لحد من غير `يشوف`.

## 3) الرفع

```bat
github-setup.bat
```

وعلى الـ VPS (Web console من hPanel):

```bash
cd /opt/stlix-gateway && git pull
python3 scripts/wire_imports.py          # لو الويرنج مترفعش من الجهاز
echo "data/imports" >> .git/info/exclude
docker compose -f docker-compose.prod.yml up -d --build
```

`data/imports/imports.db` بيتعمل لوحده أول مرة — نفس مكان `data/vat` و`data/auth`،
فبيعيش بعد أي rebuild.

## 4) الربط بنما

الصفحة بتقرا `LCShipment` (موديول الشحن البحري) عبر الـ REST connector الموجود:

- **استورد من نما** → بيجيب شحنات `LCShipment` وتفتح منها ملف على طول، من غير إعادة إدخال.
- **⟳ اسحب من نما** → بيحدّث البوليصة، الحاويات، البيان الجمركي، الموانئ، الخط الملاحي،
  ETD/ETA/ATA، قيمة الفاتورة، وتواريخ تسليم المستندات والمخزن. الرد بيقول **إيه اللي اتغيّر
  بالظبط** (كان كذا ← بقى كذا)، مش «تم» وخلاص.
- الحقول اللي جاية من نما متعلّمة على الشاشة بـ «من نما».

محتاج `NAMA_CLIENT_ID` و`NAMA_CLIENT_SECRET` في `/opt/stlix-gateway/.env` — من غيرهم
الموديول شغّال عادي بس زراير نما بترد «المفاتيح مش متحطة» بدل ما تفضل بتحاول.

## 5) القواعد اللي الموديول قايم عليها

1. **الإجراء مصدره واحد.** الخطوات والضوابط والـ checklist كلها في `sop.py`، والشاشة
   والـ gates و`/api/v1/imports/sop` بيقروا منه — فمفيش نسختين يختلفوا.
2. **مفيش رقم متخمّن.** من غير تعريفة أرضيات مفيش مبلغ أرضيات، من غير سعر صرف مفيش CIF،
   من غير كمية بالطن مفيش تكلفة للطن — بيقول ناقصه إيه بدل ما يحط رقم معقول.
3. **الدليل قبل الكليك.** الخطوة بتتقفل لوحدها من بيانات الملف (ACID سليم، مستند مستلم،
   وزن متطابق) وبتتعلّم «تلقائي». الكليك اليدوي بيفضل زي ما هو والمحرك مبيلغيهوش.
4. **لا صرف بدون فاتورة.** أي بند تكلفة من غير رقم فاتورة بيطلع تنبيه أحمر وبيمنع
   اكتمال الـ landed cost.
5. **كل تنبيه بيقول اعمل إيه ومين.** مفيش تنبيه من غير إجراء ومسؤول.
