# CCTV agent — الكاميرات على الـ Hub

الـ DVRs في شبكة المصنع ورا الراوتر؛ الـ VPS مش بيوصلهم (وما ينفعش يوصلهم — فتح ISAPI
على الإنترنت = DVR مسروق). فالاتجاه معكوس: **جهاز في الشبكة** بيسأل الـ DVRs بـ ISAPI
ويبعت النتيجة للـ gateway. باسوردات الـ DVRs ما بتخرجش من `config.json` على الجهاز ده.

## تشغيل (Windows)
1. انسخ الفولدر ده على أي PC شغّال 24/7 في شبكة المصنع (نفس الـ PC بتاع wechat-mcp ينفع).
2. `copy config.example.json config.json` وعدّل:
   - `gateway.agent_key` = نفس `CCTV_AGENT_KEY` اللي في `/opt/stlix-gateway/.env` على الـ VPS
     (ولّد واحد: `openssl rand -base64 24`).
   - لكل DVR: `host` (IP المحلي)، `user`، `password`. الـ `id` لازم يفضل ثابت (حروف/أرقام/شرطة).
3. Double-click على `run-cctv-agent.bat` (بيثبّت `requests` لو ناقصة، وبيعيد التشغيل لو وقع).
4. بعد دقيقة: https://hub.stlixvalley.com/tools/cctv

## بيبعت إيه
كل `interval_s` ثانية: معلومات الجهاز (موديل/سيريال/فيرموير)، CPU/RAM/uptime، الهاردات
(سعة/فاضي/حالة)، القنوات وحالتها، لقطة JPEG 640×360 لكل قناة، وأحداث الـ DVR
(حركة VMD، عبور خط، فقد إشارة، هارد ممتلئ) من `alertStream`.

## المطلوب على الـ DVR
- ISAPI شغّال (افتراضي) ومستخدم عنده صلاحية Remote: Live View + Parameters.
- لو Hik-Connect بس بدون IP محلي معروف: من قائمة الـ DVR → Configuration → Network → TCP/IP.
- Port 80 (HTTP) داخل الشبكة بس. مفيش حاجة بتتفتح على الإنترنت.

## استكشاف أخطاء
- `deviceInfo unreachable` → IP/port غلط أو الـ PC مش على نفس الشبكة (`ping 192.168.1.64`).
- `401` من الـ DVR → user/password، أو المستخدم ماعندوش صلاحية ISAPI.
- `push failed: 401` → `agent_key` مش مطابق لـ `CCTV_AGENT_KEY` على الـ VPS.
- لقطات فاضية لقناة analog = مفيش إشارة على القناة دي.
