# NEXT_STEP — المهمة التالية فقط

> ملف واحد، مهمة واحدة. لما تخلص، حدّثه بالمهمة اللي بعدها من `TASKS.md`.

## المهمة الحالية
**اختَر واحدة مع المالك (كلها جاهزة نبدأ فيها):**

### الأعلى قيمة → أتمتة تحديث البيانات (freshness)
اكتب سكربت على السيرفر (اللي عليه SQL Server) يشتغل كل ليلة:
1. ينزّل أحدث `hardsteel<YYYYMMDD>.bak` من Google Drive folder `1yvCI6unRWALtzf1yiU9kiHAPaBB56Xtt/full`.
2. `RESTORE DATABASE NAMA_TEST FROM DISK=...` (WITH REPLACE).
3. الجيتواي بيقرأ الجديد تلقائيًا (مفيش تغيير كود — `finance` connector بيقرأ `NAMA_TEST`).

النتيجة: Finance OS + التقارير بفارق **يوم واحد** بدل 10 أيام. (حاليًا البيانات as-of 2026-07-14.)

### بدائل جاهزة (لو المالك عايز حاجة تانية الأول)
- **الصوت العربي + شات الفريق اللي بيتكلم كإنسان** (Layer 4 + Web Speech) — مش متوقف على أي حاجة.
- **Finance OS كله حقيقي** — نشيل باقي الديمو (AP invoices, GL ledger) ونربطهم بـ SQL أو نخفيهم.
- **أول محرّك: التنبيهات (Renewals)** — يغطّي 7-8 بنود.

## المطلوب قبل ما تبدأ
- شغّل السيرفر: preview name `stlix-gateway` → افتح `http://localhost:8000/tools/platform`.
- اقرأ `MASTER_EXECUTION_RUNBOOK.md` (المرجع) + `HANDOFF.md` (الحالة).

## بند مؤجّل (مش عاجل بس مهم)
🔴 **تغيير المفاتيح المكشوفة** (Anthropic أولًا) — المالك أجّله. `secrets/gates-keys.backup.md`.
