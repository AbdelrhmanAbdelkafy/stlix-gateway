# البورتال من المتصفح — من غير تسجيل نظام ولا مفاتيح API

بيشغّل Chromium حقيقي على جهازك بـ **بروفايل ثابت**: بتسجّل دخول بإيدك مرة واحدة
(بالـ OTP لو فيه)، والجلسة بتفضل محفوظة، وبعد كده الـ MCP بيشتغل جوّه نفس الجلسة.

**الباسورد مش بيتخزّن ولا بيتكتب من البرنامج.** مفيش إعداد اسمه password ومفيش أداة
بتاخده. ده مقصود: باسورد بورتال الضرايب لو تسرّب من ملف، حد يقدر يقدّم إقرار باسمك.
الكوكي المحلي بيديك نفس الراحة بخطر أقل بكتير.

## التركيب (مرة واحدة، على الجهاز اللي هيشتغل عليه)
```bat
pip install mcp playwright httpx
playwright install chromium
```

في `claude_desktop_config.json`:
```json
"stlix-portal": {
  "command": "python",
  "args": ["D:/Nama Code project/stlix-gateway/mcp/eta-portal-browser/server.py"],
  "env": {
    "STLIX_GATEWAY_URL": "https://gw.stlixvalley.com",
    "STLIX_ETA_BROWSER_KEY": "<ETA_BROWSER_KEY من .env على الـ VPS>",
    "ETA_PROFILE_DIR": "D:/stlix-portal-profile",
    "ETA_HEADLESS": "1"
  }
}
```

## أول تشغيل
1. `portal_status` → `signed_in: false`
2. `portal_open_login` → بتتفتح نافذة → **سجّل دخولك بنفسك**
3. `portal_status` → `signed_in: true`. خلاص.

## الأدوات
`portal_status · portal_open_login · portal_goto · portal_page_text · portal_screenshot ·
portal_tables · portal_find · portal_click · portal_fill · portal_download ·
portal_scrape_month · portal_close`

- **القراءة**: `portal_tables` بيطلّع جداول المستندات صف صف، و`portal_page_text` بيقرا أي صفحة.
- **الربط بالمنصة**: `portal_scrape_month` بيبعت الصفوف لـ
  `POST /api/v1/eta/{entity}/ingest` على الـ gateway، فحاسبة ض.ق.م والشاشة والتنبيهات
  بتشتغل زي ما هي بالظبط — من غير أي مفاتيح من المصلحة.
- **الكتابة**: `portal_click` بيرفض أي كلمة فيها إرسال/تأكيد/إلغاء/رفض/دفع/توقيع إلا
  بـ `confirm=True`، وبياخد لقطة قبل وبعد. `portal_fill` بيرفض خانات الباسورد والـ OTP.

## حدود لازم تعرفها
- لو البورتال غيّر شكل الصفحات، القراءة ممكن تحتاج تظبيط — ده ثمن إننا بنقرا واجهة
  بدل API رسمي.
- الجلسة بتنتهي بعد فترة (البورتال بيقرر) → `portal_status` هيقول `signed_in: false`
  وتعمل `portal_open_login` تاني.
- الـ VAT مش دايمًا ظاهر في جدول القائمة؛ اللي مش ظاهر بيتسجّل كـ **تقديري** في الـ
  gateway (`vat_known = 0`) مش كصفر.
- شغّل ده على جهاز واحد بس؛ جلستين متوازيتين على نفس الحساب البورتال ممكن يقطعهم.
