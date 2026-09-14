"""Outgoing email — one place, and it never lies about whether it sent.

The platform had no way to reach a person outside the browser, which is why
"forgot my password" had to be a phone call to whoever had the admin screen
open. This is the smallest thing that fixes that: plain SMTP, credentials from
`.env`, no vendor, no dependency.

Two rules matter more than the code:

* **Not configured is a normal state.** With no SMTP host the send returns
  `ok=False` and says so, and every caller must then tell the user the truth —
  "الطلب اتسجّل، الـ IT هيبعتلك" — instead of "بعتنالك إيميل" over a mail that
  never left. A password-reset flow that silently drops the mail is worse than
  one that was never built: the person sits waiting instead of asking.
* **The body never carries a password.** It carries a one-time link that dies in
  30 minutes; see `app/auth/reset.py`.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from ..config import Settings

_log = logging.getLogger("gateway.mail")

#: SMTP is a network call inside a request. Short, because a person is waiting.
TIMEOUT = 12.0


def configured(settings: Settings) -> bool:
    return bool(getattr(settings, "smtp_host", "") and getattr(settings, "smtp_from", ""))


def why_not(settings: Settings) -> str:
    if not getattr(settings, "smtp_host", ""):
        return "SMTP_HOST مش متحط في .env — الإيميلات مش هتتبعت"
    if not getattr(settings, "smtp_from", ""):
        return "SMTP_FROM مش متحط في .env"
    return ""


def send(settings: Settings, to: str, subject: str, body: str,
         reply_to: str = "") -> tuple[bool, str]:
    """(ok, detail). Never raises — a failed mail must not fail the request."""
    if not configured(settings):
        return False, why_not(settings)
    if not (to or "").strip():
        return False, "مفيش عنوان مستقبِل"

    msg = EmailMessage()
    msg["From"] = formataddr(("STLIX Hub", settings.smtp_from))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    host, port = settings.smtp_host, int(settings.smtp_port or 587)
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=ctx) as s:
                _auth_send(s, settings, msg)
        else:
            with smtplib.SMTP(host, port, timeout=TIMEOUT) as s:
                s.ehlo()
                if getattr(settings, "smtp_tls", True):
                    s.starttls(context=ctx)
                    s.ehlo()
                _auth_send(s, settings, msg)
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        # The reason travels back to the caller so the screen can show it to an
        # admin instead of a generic failure nobody can act on.
        _log.warning("mail to %s failed: %s", to, exc)
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def _auth_send(s: smtplib.SMTP, settings: Settings, msg: EmailMessage) -> None:
    if settings.smtp_user:
        s.login(settings.smtp_user, settings.smtp_password)
    s.send_message(msg)
