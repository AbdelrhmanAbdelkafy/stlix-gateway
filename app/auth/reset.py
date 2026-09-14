"""نسيت كلمة السر — one-time reset links for the hub, and a tracked request for
every other system on the server.

Two different problems, on purpose:

**The hub** (hub.stlixvalley.com / gw.stlixvalley.com) is ours, so a person can
reset it themselves: they ask, a one-time link goes to the address on their
account, the link sets a new password and dies. Thirty minutes, single use, and
using it logs every existing session of theirs out — a reset is also what you do
when you think somebody else has your password.

**Everything else** — نما، الـ CRM، الحضور، الرواتب، ووردبريس، Portainer،
phpMyAdmin — has its own login that this platform does not own, so pretending to
reset it would be a lie. What the platform can do is the part that actually
takes the time: route the person to that system's own recovery where one exists,
and otherwise record the request and put it in the owner's inbox with everything
needed to act on it. The request is a row, not a WhatsApp message that scrolls
away.

Security decisions worth stating, because each one was a choice:

* **No user enumeration.** "مش لاقي الحساب" tells an attacker which usernames
  exist. Every request returns the same answer whether or not the account is
  there.
* **The token is never stored.** Only its SHA-256. A stolen database gives
  nobody a working link.
* **The token never reaches an anonymous response.** It goes to the address on
  the account, or — when mail is not configured — it waits on the admin screen
  for a person to hand over. What the browser gets back is the same sentence
  either way.
* **Rate limits on both sides:** per account and per IP, so the endpoint is not
  a way to flood somebody's inbox or to farm timing differences.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()

TTL_MINUTES_DEFAULT = 30
#: Open requests allowed per account, and per IP, in a rolling hour.
MAX_PER_ACCOUNT_HOUR = 3
MAX_PER_IP_HOUR = 10
#: One sentence, returned whether the account exists or not.
SAME_ANSWER = ("لو الحساب موجود، هتوصلك رسالة على الإيميل المسجّل عليه خلال دقايق. "
               "لو مفيش إيميل مسجّل، الطلب راح لمسؤول النظام.")
#: With SMTP off nothing can be sent to anybody, which is a fact about the
#: server and not about the account — so saying it leaks nothing and stops a
#: person waiting for a mail that was never going to arrive.
NO_MAIL_ANSWER = ("الطلب اتسجّل. إرسال الإيميلات مقفول على السيرفر دلوقتي، "
                  "فمسؤول النظام هو اللي هيبعتلك لينك الاسترجاع.")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS resets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL DEFAULT '',
  system TEXT NOT NULL DEFAULT 'hub',
  identifier TEXT NOT NULL DEFAULT '',
  token_hash TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL,
  used_at REAL,
  cancelled_at REAL,
  ip TEXT NOT NULL DEFAULT '',
  delivery TEXT NOT NULL DEFAULT 'pending',
  delivery_note TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_resets_hash ON resets(token_hash);
CREATE INDEX IF NOT EXISTS idx_resets_user ON resets(username, created_at);
"""


# --- الأنظمة التانية على السيرفر ---------------------------------------------
#: resource key → how a password is recovered there. `url` is that system's OWN
#: recovery page; `None` means it has none and only an admin can reset it.
#: Nothing here is a deep link that was guessed: where the exact path is not
#: certain, it points at the login page and says what to press.
SYSTEMS: dict[str, dict] = {
    "hub": {"label": "STLIX Hub والأدوات (gw)", "url": None, "self": True,
            "how": "استرجاع ذاتي من هنا — هيوصلك لينك على إيميلك."},
    "erp-site": {"label": "نما ERP", "url": None, "self": False,
                 "how": "مفيش استرجاع ذاتي — مدير نما هو اللي بيعيد تعيين كلمة المرور من شاشة المستخدمين."},
    "crm-site": {"label": "vTiger CRM", "url": "https://crm.stlixvalley.com/", "self": False,
                 "how": "من صفحة الدخول اضغط Forgot Password — بيبعت على الإيميل المسجّل في بروفايل المستخدم. "
                        "لو الإيميل مش مظبوط، الأدمن بيغيّرها من Settings → Users."},
    "attendance-site": {"label": "لوحة الحضور (البصمة)", "url": None, "self": False,
                        "how": "اللوحة بتدخل بكلمة مرور واحدة متخزّنة في إعدادات السيرفر — التغيير من الـ IT."},
    "payroll-site": {"label": "الرواتب", "url": None, "self": False,
                     "how": "مفيش استرجاع ذاتي — الـ IT بيعيد التعيين من لوحة النظام."},
    "website": {"label": "ووردبريس stlixvalley.com",
                "url": "https://stlixvalley.com/wp-login.php?action=lostpassword", "self": False,
                "how": "ووردبريس بيبعت لينك على إيميل المستخدم. لو الإيميل مش شغال، الأدمن بيغيّرها من Users."},
    "egygrouphs": {"label": "بانل egygrouphs.com", "url": None, "self": False,
                   "how": "بانل بتاعنا — الـ IT بيغيّر كلمة المرور من إعدادات الموقع."},
    "portainer": {"label": "Portainer", "url": None, "self": False,
                  "how": "مفيش استرجاع بالإيميل — الاسترجاع بيتعمل من الـ console على السيرفر (container reset)."},
    "phpmyadmin": {"label": "phpMyAdmin", "url": None, "self": False,
                   "how": "الدخول بحساب MySQL — التغيير من السيرفر مباشرة."},
    "hpanel": {"label": "Hostinger (hPanel / VPS)",
               "url": "https://auth.hostinger.com/forgot-password", "self": False,
               "how": "استرجاع من حساب Hostinger نفسه."},
    "google": {"label": "Google Workspace",
               "url": "https://accounts.google.com/signin/recovery", "self": False,
               "how": "استرجاع من جوجل، أو من admin.google.com لو إنت الأدمن."},
    "notion": {"label": "Notion", "url": "https://www.notion.so/login", "self": False,
               "how": "من صفحة الدخول → Forgot password (بيبعت كود على الإيميل)."},
}


def systems() -> list[dict]:
    return [{"key": k, **v} for k, v in SYSTEMS.items()]


# --- db ----------------------------------------------------------------------
def _conn(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(path), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def ensure(path: Path) -> None:
    """Create the resets table and add `users.email` if it is not there yet.

    The column is added here rather than in `store.py`'s schema so an existing
    auth.db — the one already running on the VPS with its users in it — upgrades
    itself on first open instead of needing a migration somebody has to remember
    to run.
    """
    with _LOCK, _conn(path) as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        if "email" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- emails on accounts ------------------------------------------------------
def get_email(path: Path, username: str) -> str:
    ensure(path)
    with _conn(path) as c:
        row = c.execute("SELECT email FROM users WHERE username=?", (username,)).fetchone()
    return (row["email"] if row else "") or ""


def emails(path: Path) -> dict[str, str]:
    ensure(path)
    with _conn(path) as c:
        return {r["username"]: r["email"] or "" for r in c.execute("SELECT username, email FROM users")}


def set_email(path: Path, username: str, email: str) -> bool:
    ensure(path)
    email = (email or "").strip()
    if email and not _looks_like_email(email):
        raise ValueError("الإيميل شكله مش مظبوط")
    with _LOCK, _conn(path) as c:
        n = c.execute("UPDATE users SET email=? WHERE username=?", (email, username)).rowcount
    return bool(n)


def _looks_like_email(value: str) -> bool:
    if value.count("@") != 1 or " " in value:
        return False
    local, _, domain = value.partition("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def find_user(path: Path, identifier: str) -> str | None:
    """Username or email → username. Case-insensitive on both."""
    ensure(path)
    ident = (identifier or "").strip().lower()
    if not ident:
        return None
    with _conn(path) as c:
        row = c.execute("SELECT username FROM users WHERE username=? AND active=1", (ident,)).fetchone()
        if row:
            return row["username"]
        row = c.execute("SELECT username FROM users WHERE lower(email)=? AND active=1",
                        (ident,)).fetchone()
    return row["username"] if row else None


# --- requests ----------------------------------------------------------------
def throttled(path: Path, username: str, ip: str) -> str:
    """'' when the request may proceed, else why not. Checked before any work."""
    ensure(path)
    since = time.time() - 3600
    with _conn(path) as c:
        if username:
            n = c.execute("SELECT COUNT(*) n FROM resets WHERE username=? AND created_at>?",
                          (username, since)).fetchone()["n"]
            if n >= MAX_PER_ACCOUNT_HOUR:
                return "طلبات كتير على الحساب ده في ساعة — استنى شوية أو كلّم الـ IT"
        if ip:
            n = c.execute("SELECT COUNT(*) n FROM resets WHERE ip=? AND created_at>?",
                          (ip, since)).fetchone()["n"]
            if n >= MAX_PER_IP_HOUR:
                return "طلبات كتير من نفس الجهاز — استنى شوية"
    return ""


def record(path: Path, *, username: str, system: str, identifier: str, ip: str,
           ttl_minutes: int = TTL_MINUTES_DEFAULT, with_token: bool) -> tuple[int, str]:
    """Write the request. Returns (id, token) — token is '' when none was issued.

    A request for another system carries no token: there is nothing here that
    could set a password on نما or on ووردبريس, so issuing one would only create
    a secret that unlocks nothing.
    """
    ensure(path)
    now = time.time()
    token = secrets.token_urlsafe(32) if with_token else ""
    with _LOCK, _conn(path) as c:
        # A new link retires the ones before it — two live links for one account
        # means an old mail still works after the person got a newer one.
        if with_token and username:
            c.execute("UPDATE resets SET cancelled_at=? WHERE username=? AND system='hub' "
                      "AND used_at IS NULL AND cancelled_at IS NULL", (now, username))
        cur = c.execute(
            "INSERT INTO resets (username, system, identifier, token_hash, created_at, expires_at, ip, delivery)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (username, system, identifier, _sha(token) if token else "", now,
             now + ttl_minutes * 60, ip, "pending"))
    return cur.lastrowid, token


def mark_delivery(path: Path, req_id: int, state: str, note: str = "") -> None:
    """state: sent | failed | manual — what actually happened to the mail."""
    with _LOCK, _conn(path) as c:
        c.execute("UPDATE resets SET delivery=?, delivery_note=? WHERE id=?", (state, note[:400], req_id))


def check(path: Path, token: str) -> dict | None:
    """The live request behind a token, or None (unknown / used / expired)."""
    ensure(path)
    if not token:
        return None
    with _conn(path) as c:
        row = c.execute(
            "SELECT * FROM resets WHERE token_hash=? AND used_at IS NULL AND cancelled_at IS NULL",
            (_sha(token),)).fetchone()
    if not row or row["expires_at"] < time.time() or row["system"] != "hub":
        return None
    return dict(row)


def consume(path: Path, token: str, new_password: str, store) -> tuple[bool, str]:
    """Set the password and burn the link. `store` is the AuthStore.

    The order matters: the password is written first, and only a successful
    write burns the token. Burning first would turn a rejected password (too
    short, say) into a dead link and a person locked out by a typo.
    """
    row = check(path, token)
    if not row:
        return False, "اللينك مش صالح أو انتهت مدته — اطلب واحد جديد"
    try:
        store.set_password(row["username"], new_password, actor=f"reset:{row['id']}")
    except ValueError as exc:
        return False, str(exc)
    except KeyError:
        return False, "الحساب مش موجود"
    now = time.time()
    with _LOCK, _conn(path) as c:
        c.execute("UPDATE resets SET used_at=? WHERE id=?", (now, row["id"]))
        c.execute("UPDATE resets SET cancelled_at=? WHERE username=? AND used_at IS NULL "
                  "AND cancelled_at IS NULL", (now, row["username"]))
    return True, row["username"]


def pending(path: Path, limit: int = 100, include_done: bool = False) -> list[dict]:
    """What the admin screen shows: who asked, for what, and whether mail left."""
    ensure(path)
    q = ("SELECT id, username, system, identifier, created_at, expires_at, used_at, cancelled_at,"
         " ip, delivery, delivery_note FROM resets")
    if not include_done:
        q += " WHERE used_at IS NULL AND cancelled_at IS NULL"
    q += " ORDER BY id DESC LIMIT ?"
    now = time.time()
    with _conn(path) as c:
        rows = [dict(r) for r in c.execute(q, (min(limit, 500),))]
    for r in rows:
        r["expired"] = r["expires_at"] < now and not r["used_at"]
        r["state"] = ("used" if r["used_at"] else "cancelled" if r["cancelled_at"]
                      else "expired" if r["expired"] else "open")
        r["system_label"] = SYSTEMS.get(r["system"], {}).get("label", r["system"])
    return rows


def cancel(path: Path, req_id: int) -> bool:
    with _LOCK, _conn(path) as c:
        n = c.execute("UPDATE resets SET cancelled_at=? WHERE id=? AND used_at IS NULL",
                      (time.time(), req_id)).rowcount
    return bool(n)


def purge(path: Path, older_than_days: int = 30) -> int:
    with _LOCK, _conn(path) as c:
        return c.execute("DELETE FROM resets WHERE created_at < ?",
                         (time.time() - older_than_days * 86400,)).rowcount


# --- the messages ------------------------------------------------------------
def link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/reset?t={token}"


def user_mail(display_name: str, url: str, ttl_minutes: int) -> tuple[str, str]:
    return ("إعادة تعيين كلمة المرور — STLIX Hub", f"""أهلاً {display_name},

وصلنا طلب لإعادة تعيين كلمة المرور بتاعتك على STLIX Hub.

افتح اللينك ده واختار كلمة مرور جديدة:
{url}

اللينك صالح {ttl_minutes} دقيقة وبيشتغل مرة واحدة بس.
أول ما تغيّرها، كل الجلسات المفتوحة بحسابك هتتقفل وهتحتاج تسجّل دخول من تاني.

لو مش إنت اللي طلبت، متعملش حاجة — اللينك هينتهي لوحده. ولو ده بيتكرر، بلّغ الـ IT.

— STLIX Hub
""")


def owner_mail(system_label: str, identifier: str, username: str, ip: str,
               how: str, url: str = "") -> tuple[str, str]:
    who = f"المستخدم: {username}" if username else f"اللي كتبه: {identifier}"
    body = f"""طلب إعادة تعيين كلمة مرور.

النظام: {system_label}
{who}
IP: {ip or "—"}

طريقة الاسترجاع للنظام ده:
{how}
"""
    if url:
        body += f"\nصفحة الاسترجاع: {url}\n"
    body += "\nالطلب متسجّل في: https://hub.stlixvalley.com/hub/admin.html (تبويب استرجاع كلمات السر)\n"
    return (f"[STLIX] طلب استرجاع كلمة سر — {system_label}", body)
