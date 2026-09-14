"""نسيت كلمة السر — the public pages, the public API, and the admin view.

Public by design (`/forgot`, `/reset`, and their two API calls): a person who
cannot log in cannot be asked to log in first. Everything public here answers
the same way whether the account exists or not, issues nothing an anonymous
caller can read, and is rate-limited per account and per IP.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..core import mailer
from . import reset, service

_log = logging.getLogger("gateway.auth.reset")
_HUB = Path(__file__).resolve().parent.parent.parent / "modules" / "hub"
_VOICE = '<script src="/tools/voice.js" defer></script>'

pages = APIRouter(tags=["auth"])
api = APIRouter(prefix="/auth", tags=["auth"])


def _page(name: str) -> HTMLResponse:
    body = (_HUB / name).read_text(encoding="utf-8")
    if "/tools/voice.js" not in body:
        body = body.replace("</body>", _VOICE + "\n</body>", 1)
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


def _ip(request: Request) -> str:
    """Client IP for rate limiting only.

    Apache is the reverse proxy in front of this, so `request.client` is always
    127.0.0.1 and `X-Forwarded-For` is what carries the real address. A header
    can be forged, which is why this value guards nothing but a counter — it is
    never an identity and never grants anything.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def _db(settings: Settings) -> Path:
    return service.db_path(settings)


def owners(settings: Settings) -> list[str]:
    """Who gets told about every request. Comma-separated in `.env`.

    More than one on purpose: receiving is not the same problem as sending. An
    inbox that cannot authenticate SMTP (a personal outlook.com/hotmail account,
    since Microsoft retired basic auth for those) is still a perfectly good place
    to be notified — and a second address means a locked-out owner is not also
    a blind one.
    """
    raw = getattr(settings, "auth_owner_email", "") or ""
    return [a.strip() for a in raw.replace(";", ",").split(",") if a.strip()]


def _ttl(settings: Settings) -> int:
    return int(getattr(settings, "reset_ttl_minutes", reset.TTL_MINUTES_DEFAULT) or
               reset.TTL_MINUTES_DEFAULT)


def _base(settings: Settings, request: Request) -> str:
    configured = getattr(settings, "public_base_url", "")
    if configured:
        return configured
    # Fall back to the host the person is actually on, so a link is never built
    # against a domain that was right on somebody else's machine.
    return str(request.base_url).rstrip("/")


# --- pages --------------------------------------------------------------------
@pages.get("/forgot", response_class=HTMLResponse)
async def forgot_page() -> HTMLResponse:
    """نسيت كلمة السر — الهَب وكل الأنظمة المرتبطة."""
    return _page("forgot.html")


@pages.get("/reset", response_class=HTMLResponse)
async def reset_page() -> HTMLResponse:
    """اختيار كلمة مرور جديدة من لينك الاسترجاع."""
    return _page("reset.html")


# --- public API ---------------------------------------------------------------
class ForgotIn(BaseModel):
    identifier: str = Field(default="", max_length=200)
    system: str = "hub"


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=200)


@api.get("/systems")
async def recovery_systems() -> dict:
    """كل نظام وطريقة استرجاعه — اللي ليه استرجاع ذاتي واللي محتاج الـ IT."""
    return {"systems": reset.systems()}


@api.post("/forgot")
async def forgot(body: ForgotIn, request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """طلب استرجاع. الرد واحد دايمًا — سواء الحساب موجود أو لأ.

    A different answer for a real account turns this endpoint into a way to test
    whether a username exists, so the only thing the caller learns is that the
    request was accepted.
    """
    db = _db(settings)
    system = body.system if body.system in reset.SYSTEMS else "hub"
    ident = (body.identifier or "").strip()[:200]
    username = reset.find_user(db, ident) or ""

    limited = reset.throttled(db, username, _ip(request))
    if limited:
        raise HTTPException(429, limited)

    info = reset.SYSTEMS[system]
    if system == "hub" and username:
        await _hub_request(db, settings, request, username, ident, system, info)
    else:
        # Another system, or an identifier we do not recognise. The row is still
        # written for the unknown case: a burst of requests for names that do not
        # exist is itself worth seeing on the admin screen.
        req_id, _ = reset.record(db, username=username, system=system, identifier=ident,
                                 ip=_ip(request), ttl_minutes=_ttl(settings), with_token=False)
        _notify_owner(settings, db, req_id, system, ident, username, _ip(request), info)

    # Whether mail works at all is a property of the server, not of the account,
    # so telling the truth about it here reveals nothing and saves somebody from
    # refreshing an inbox for an hour.
    mail_on = mailer.configured(settings)
    if system != "hub":
        answer = ("الطلب اتسجّل واتبعت لمسؤول النظام." if mail_on
                  else "الطلب اتسجّل عند مسؤول النظام (الإيميل مقفول على السيرفر دلوقتي).")
    else:
        answer = reset.SAME_ANSWER if mail_on else reset.NO_MAIL_ANSWER
    return {"ok": True, "system": system, "self_service": bool(info.get("self")),
            "url": info.get("url"), "mail": mail_on,
            "note": info["how"] if system != "hub" else answer,
            "answer": answer}


async def _hub_request(db: Path, settings: Settings, request: Request, username: str,
                       ident: str, system: str, info: dict) -> None:
    st = service.store(settings)
    user = st.get_user(username) or {}
    email = reset.get_email(db, username)
    ttl = _ttl(settings)
    req_id, token = reset.record(db, username=username, system=system, identifier=ident,
                                 ip=_ip(request), ttl_minutes=ttl, with_token=True)
    url = reset.link(_base(settings, request), token)

    if email:
        subject, text = reset.user_mail(user.get("display_name") or username, url, ttl)
        ok, detail = mailer.send(settings, email, subject, text)
        reset.mark_delivery(db, req_id, "sent" if ok else "failed", detail)
        if not ok:
            # The link exists and nobody has it. Say so where an admin will see
            # it, rather than leaving a person waiting for a mail that never left.
            _log.warning("reset mail for %s failed: %s", username, detail)
    else:
        reset.mark_delivery(db, req_id, "manual", "مفيش إيميل مسجّل على الحساب")
    st.note("forgot", "reset.request", username,
            {"system": system, "email": bool(email), "id": req_id})
    _notify_owner(settings, db, req_id, system, ident, username, _ip(request), info,
                  extra=("" if email else "الحساب ده مفيش عليه إيميل — لازم تعيد التعيين له "
                                          "من شاشة المستخدمين أو تولّد لينك من هناك."))


def _notify_owner(settings: Settings, db: Path, req_id: int, system: str, ident: str,
                  username: str, ip: str, info: dict, extra: str = "") -> None:
    """Every request reaches the owner's inbox. A reset you did not ask for is
    something you want to hear about the same day, not next month in a log."""
    to = owners(settings)
    if not to:
        return
    subject, text = reset.owner_mail(info["label"], ident, username, ip, info["how"],
                                     info.get("url") or "")
    if extra:
        text += f"\n{extra}\n"
    for addr in to:
        ok, detail = mailer.send(settings, addr, subject, text)
        if not ok:
            _log.warning("owner notification for request %s not sent to %s: %s",
                         req_id, addr, detail)


@api.get("/reset/check")
async def reset_check(t: str = "", settings: Settings = Depends(get_settings)) -> dict:
    """هل اللينك لسه صالح — عشان الصفحة تقول قبل ما الشخص يكتب كلمة مرور."""
    row = reset.check(_db(settings), t)
    return {"valid": bool(row), "expires_at": row["expires_at"] if row else None}


@api.post("/reset")
async def do_reset(body: ResetIn, settings: Settings = Depends(get_settings)) -> dict:
    ok, detail = reset.consume(_db(settings), body.token, body.password, service.store(settings))
    if not ok:
        raise HTTPException(400, detail)
    return {"ok": True, "username": detail,
            "note": "اتغيّرت. كل الجلسات القديمة اتقفلت — سجّل دخول بالجديدة."}


# --- admin --------------------------------------------------------------------
admin = APIRouter(prefix="/auth/admin", tags=["auth-admin"])


class EmailIn(BaseModel):
    email: str = Field(default="", max_length=200)


def _actor(request: Request) -> str:
    u = getattr(request.state, "user", None) or {}
    return u.get("username", "?")


@admin.get("/resets")
async def admin_resets(limit: int = 100, all: bool = False,
                       settings: Settings = Depends(get_settings)) -> dict:
    """طلبات الاسترجاع: مين طلب، لأي نظام، والإيميل خرج ولا لأ."""
    db = _db(settings)
    return {"requests": reset.pending(db, limit, include_done=all),
            "emails": reset.emails(db),
            "mail": {"configured": mailer.configured(settings),
                     "why_not": mailer.why_not(settings),
                     "owners": owners(settings)}}


@admin.post("/resets/{req_id}/cancel")
async def admin_cancel(req_id: int, request: Request,
                       settings: Settings = Depends(get_settings)) -> dict:
    if not reset.cancel(_db(settings), req_id):
        raise HTTPException(404, "الطلب مش موجود أو اتنفّذ خلاص")
    service.store(settings).note(_actor(request), "reset.cancel", str(req_id), {})
    return {"ok": True}


@admin.post("/users/{username}/link")
async def admin_issue_link(username: str, request: Request,
                           settings: Settings = Depends(get_settings)) -> dict:
    """ولّد لينك استرجاع وسلّمه بإيدك — للحالات اللي الإيميل فيها مش شغال.

    The link is returned once, to an admin, and is not stored anywhere in
    readable form; reopening the screen will not show it again. That is the
    point: a link that can be re-read later is a password sitting in a table.
    """
    db = _db(settings)
    st = service.store(settings)
    if not st.get_user(username):
        raise HTTPException(404, "المستخدم مش موجود")
    ttl = _ttl(settings)
    req_id, token = reset.record(db, username=username, system="hub", identifier=username,
                                 ip=_ip(request), ttl_minutes=ttl, with_token=True)
    reset.mark_delivery(db, req_id, "manual", f"اتولّد بإيد {_actor(request)}")
    st.note(_actor(request), "reset.manual_link", username, {"id": req_id})
    return {"ok": True, "url": reset.link(_base(settings, request), token),
            "expires_in_minutes": ttl,
            "note": "اللينك ده مش هيتعرض تاني — انسخه دلوقتي وسلّمه للشخص."}


@admin.put("/users/{username}/email")
async def admin_set_email(username: str, body: EmailIn, request: Request,
                          settings: Settings = Depends(get_settings)) -> dict:
    """الإيميل اللي لينك الاسترجاع بيروح عليه."""
    db = _db(settings)
    try:
        if not reset.set_email(db, username, body.email):
            raise HTTPException(404, "المستخدم مش موجود")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    service.store(settings).note(_actor(request), "user.email", username,
                                 {"set": bool(body.email.strip())})
    return {"ok": True, "username": username, "email": body.email.strip()}


@admin.post("/mail/test")
async def admin_mail_test(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """ابعت رسالة تجربة لإيميل المالك — عشان نعرف الـ SMTP شغال قبل ما حد يحتاجه."""
    to = owners(settings)
    if not to:
        raise HTTPException(400, "AUTH_OWNER_EMAIL مش متحط في .env")
    results = []
    for addr in to:
        ok, detail = mailer.send(settings, addr, "[STLIX] تجربة إرسال",
                                 "الرسالة دي معناها إن إعدادات الـ SMTP على الهَب شغالة.\n\n— STLIX Hub")
        results.append({"to": addr, "ok": ok, "detail": detail})
    service.store(settings).note(_actor(request), "mail.test", ",".join(to),
                                 {"ok": all(r["ok"] for r in results)})
    return {"ok": all(r["ok"] for r in results), "results": results}
