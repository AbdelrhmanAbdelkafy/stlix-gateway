"""Wire «نسيت كلمة السر» into the gateway. Run once; safe to re-run.

New files stand alone (`app/auth/reset.py`, `app/auth/reset_router.py`,
`app/core/mailer.py`, three pages under `modules/hub/`). These are the edits
they need in files that already exist — settings, two router mounts, the public
path list, the hub's page allow-list, the admin resource's paths, and a link on
the login screen.

    python scripts/wire_password_reset.py          # apply
    python scripts/wire_password_reset.py --check  # report only

Every edit is anchored on text that must be present, and marked by text that
means "already done", so a second run changes nothing. If an anchor is gone the
script names the file instead of writing something wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SETTINGS = '''
    # --- نسيت كلمة السر + الإيميل ------------------------------------------
    # The address every reset request is copied to. Blank = nobody is told.
    auth_owner_email: str = Field(default="")
    # Used to build the reset link (e.g. https://hub.stlixvalley.com). Blank =
    # the host the request came in on, which is right for one machine and wrong
    # the moment somebody opens the hub by IP.
    public_base_url: str = Field(default="")
    reset_ttl_minutes: int = Field(default=30)
    # Plain SMTP. Blank host = mail is off, and the reset flow says so out loud
    # instead of pretending a message was sent.
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    smtp_tls: bool = Field(default=True)
'''

# (file, anchor, payload, marker, mode)  mode: after | before | replace
EDITS: list[tuple[str, str, str, str, str]] = [
    (
        "app/config.py",
        "    hub_live_interval: float = Field(default=20.0)\n",
        SETTINGS,
        "auth_owner_email",
        "after",
    ),
    (
        "app/main.py",
        "from .auth.router import admin as auth_admin_router, api as auth_api_router, router as auth_router\n",
        "from .auth.reset_router import admin as reset_admin_router, api as reset_api_router, "
        "pages as reset_pages_router\n",
        "reset_router import",
        "after",
    ),
    (
        "app/main.py",
        "    app.include_router(auth_router)\n",
        "    app.include_router(reset_pages_router)\n",
        "include_router(reset_pages_router",
        "after",
    ),
    (
        "app/main.py",
        "    app.include_router(auth_admin_router, prefix=API_PREFIX)\n",
        "    app.include_router(reset_api_router, prefix=API_PREFIX)\n"
        "    app.include_router(reset_admin_router, prefix=API_PREFIX)\n",
        "include_router(reset_api_router",
        "after",
    ),
    (
        "app/auth/resources.py",
        '    "/login", "/logout", "/health", "/favicon.ico", "/tools/voice.js",\n',
        '    # نسيت كلمة السر: حد مش قادر يدخل مايتطلبش منه يدخل الأول. كل واحد\n'
        '    # منهم بيرد نفس الجملة سواء الحساب موجود أو لأ، وعليه rate limit.\n'
        '    "/forgot", "/reset", "/api/v1/auth/forgot", "/api/v1/auth/reset",\n'
        '    "/api/v1/auth/systems",\n',
        '"/api/v1/auth/forgot"',
        "after",
    ),
    (
        "app/auth/resources.py",
        '             "/hub/admin.html", paths=("/hub/admin.html", "/api/v1/auth/admin"),',
        '             "/hub/admin.html", paths=("/hub/admin.html", "/hub/resets.html",\n'
        '                                       "/api/v1/auth/admin"),',
        '"/hub/resets.html"',
        "replace",
    ),
    (
        "app/hub/router.py",
        '_PAGES = {"index.html", "platform.html", "admin.html"}',
        '_PAGES = {"index.html", "platform.html", "admin.html", "resets.html"}',
        '"resets.html"',
        "replace",
    ),
    (
        "modules/hub/login.html",
        '  <div class="foot">الدخول للأدوات الداخلية',
        '  <div class="foot" style="margin-top:12px">'
        '<a href="/forgot" style="color:#E0A53A;text-decoration:none">نسيت كلمة السر؟</a></div>\n',
        'href="/forgot"',
        "before",
    ),
]


def main(check_only: bool = False) -> int:
    todo, done, missing = [], [], []
    for rel, anchor, payload, marker, mode in EDITS:
        path = ROOT / rel
        if not path.exists():
            missing.append(f"{rel}: مش موجود")
            continue
        text = path.read_text(encoding="utf-8")
        if marker in text:
            done.append(f"{rel}: متوصّل بالفعل ({marker})")
            continue
        if anchor not in text:
            missing.append(f"{rel}: مالقيتش نقطة الإدراج — الملف اتغيّر، وصّلها بإيدك")
            continue
        todo.append((path, anchor, payload, mode, rel))

    for line in done:
        print("=", line)
    for line in missing:
        print("!", line)
    if check_only:
        for _p, _a, _i, _m, rel in todo:
            print("+", f"{rel}: محتاج توصيل")
        return 1 if (todo or missing) else 0

    for path, anchor, payload, mode, rel in todo:
        # Re-read per edit: three of these land in app/main.py, and applying them
        # all to one stale snapshot would make each write drop the one before it.
        text = path.read_text(encoding="utf-8")
        if anchor not in text:
            missing.append(f"{rel}: نقطة الإدراج اختفت أثناء التطبيق")
            continue
        new = {"after": anchor + payload, "before": payload + anchor, "replace": payload}[mode]
        path.write_text(text.replace(anchor, new, 1), encoding="utf-8")
        print("+", f"{rel}: اتوصّل")

    if missing:
        print("\nفيه ملفات محتاجة توصيل يدوي — شوف السطور اللي فوق.")
        return 1
    print("""
تمام. ناقص إعدادات الإيميل في .env:

  # المستقبِل — أكتر من عنوان مفصولين بفاصلة
  AUTH_OWNER_EMAIL=abdelrhman.abdelkafy@gmail.com,abdelrhman.abdelkafy@hotmail.com
  PUBLIC_BASE_URL=https://hub.stlixvalley.com
  # المرسِل — mailbox على دومين الشركة
  SMTP_HOST=smtp.hostinger.com
  SMTP_PORT=465
  SMTP_USER=noreply@stlixvalley.com
  SMTP_PASSWORD=<باسورد الـ mailbox — مش باسورد hPanel>
  SMTP_FROM=noreply@stlixvalley.com

بديل: جيميل (smtp.gmail.com:587) بـ App Password. وHotmail/Outlook.com مش
بينفع كمرسِل — مايكروسوفت وقّفت الـ basic auth للحسابات الشخصية؛ ينفع مستقبِل بس.

من غيرهم الموديول شغّال، بس الطلبات بتستنى في /hub/resets.html وإنت بتولّد
اللينك بإيدك بدل ما يتبعت. شغّل: pytest tests/test_password_reset.py -q
""")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
