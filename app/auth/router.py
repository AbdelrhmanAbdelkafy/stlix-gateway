"""Login/logout pages, `/api/v1/auth/*` for the browser, and the admin API."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from . import service
from .resources import ACTION_LABELS, ACTIONS, as_dicts as resources_as_dicts

_ROOT = Path(__file__).resolve().parent.parent.parent
_HUB = _ROOT / "modules" / "hub"
_VOICE = '<script src="/tools/voice.js" defer></script>'

router = APIRouter(tags=["auth"])
api = APIRouter(prefix="/auth", tags=["auth"])
admin = APIRouter(prefix="/auth/admin", tags=["auth-admin"])


def _safe_to(to: str | None) -> str:
    """Only same-site paths — never an absolute URL someone pasted into ?to=."""
    if to and to.startswith("/") and not to.startswith("//") and not to.startswith("/login"):
        return to
    return "/hub/"


def _page(name: str) -> HTMLResponse:
    body = (_HUB / name).read_text(encoding="utf-8")
    if "/tools/voice.js" not in body:
        body = body.replace("</body>", _VOICE + "\n</body>", 1)
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


# --- browser pages ------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, to: str | None = None,
                     settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """صفحة الدخول — username / password."""
    if settings.auth_enabled and service.current_user(request, settings):
        return RedirectResponse(_safe_to(to), status_code=302)  # type: ignore[return-value]
    return _page("login.html")


@router.post("/login")
async def login_submit(request: Request, settings: Settings = Depends(get_settings)):
    """استقبال الفورم: صح → cookie + رجوع للصفحة المطلوبة، غلط → /login?e=1.

    The urlencoded body is parsed by hand so the gateway needs no multipart
    dependency for a three-field form."""
    form = parse_qs((await request.body()).decode("utf-8", "replace"), keep_blank_values=True)
    username = form.get("username", [""])[0]
    password = form.get("password", [""])[0]
    to = form.get("to", ["/hub/"])[0]
    st = service.store(settings)
    user = st.authenticate(username, password)
    dest = _safe_to(to)
    if not user:
        return RedirectResponse(f"/login?e=1&to={quote(dest, safe='')}", status_code=303)
    resp = RedirectResponse(dest, status_code=303)
    _, kw = service.issue_cookie(settings, user)
    resp.set_cookie(**kw)
    return resp


@router.get("/logout")
async def logout(settings: Settings = Depends(get_settings)):
    """تسجيل الخروج — بيمسح الـ cookie ويرجّع لصفحة الدخول."""
    resp = RedirectResponse("/login?out=1", status_code=303)
    resp.delete_cookie(**service.clear_cookie_kwargs(settings))
    return resp


# --- JSON for the pages -------------------------------------------------------
class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=8)


@api.get("/me")
async def me(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """مين اللي داخل دلوقتي وصلاحياته الفعلية (resource → actions)."""
    return service.me(request, settings)


@api.post("/login")
async def api_login(body: LoginIn, settings: Settings = Depends(get_settings)):
    """نفس الدخول لكن JSON (للصفحات الديناميكية)."""
    user = service.store(settings).authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غلط")
    resp = JSONResponse({"ok": True, "username": user["username"]})
    _, kw = service.issue_cookie(settings, user)
    resp.set_cookie(**kw)
    return resp


@api.post("/logout")
async def api_logout(settings: Settings = Depends(get_settings)):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(**service.clear_cookie_kwargs(settings))
    return resp


@api.post("/password")
async def change_own_password(body: PasswordIn, request: Request,
                              settings: Settings = Depends(get_settings)) -> dict:
    """المستخدم يغيّر كلمة مروره بنفسه (لازم يعرف الحالية)."""
    user = service.current_user(request, settings)
    if not user:
        raise HTTPException(401, "Login required.")
    st = service.store(settings)
    if not st.authenticate(user["username"], body.current):
        raise HTTPException(400, "كلمة المرور الحالية غلط")
    st.set_password(user["username"], body.new, actor=user["username"])
    return {"ok": True, "note": "سجّل دخول تاني بكلمة المرور الجديدة"}


# --- admin ---------------------------------------------------------------------
def _actor(request: Request) -> str:
    u = getattr(request.state, "user", None) or {}
    return u.get("username", "?")


class UserIn(BaseModel):
    username: str
    password: str = Field(min_length=8)
    display_name: str = ""
    roles: list[str] = []


class UserPatch(BaseModel):
    display_name: str | None = None
    active: bool | None = None
    roles: list[str] | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=8)


class RoleIn(BaseModel):
    name: str
    desc: str = ""
    perms: dict[str, list[str]]


class OverrideItem(BaseModel):
    resource: str
    action: str
    effect: str


def _err(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, "مش موجود")
    return HTTPException(400, str(exc))


@admin.get("/resources")
async def admin_resources() -> dict:
    """كل الموارد اللي ممكن تتحط عليها صلاحية + الأفعال."""
    return {"resources": resources_as_dicts(), "actions": list(ACTIONS), "labels": ACTION_LABELS}


@admin.get("/users")
async def admin_users(settings: Settings = Depends(get_settings)) -> dict:
    st = service.store(settings)
    users = st.list_users()
    for u in users:
        u["effective"] = st.effective(u["username"])
        u["overrides"] = st.overrides(u["username"])
    return {"users": users}


@admin.post("/users", status_code=201)
async def admin_create_user(body: UserIn, request: Request,
                            settings: Settings = Depends(get_settings)) -> dict:
    try:
        return service.store(settings).create_user(
            body.username, body.password, display_name=body.display_name,
            roles=body.roles, actor=_actor(request))
    except (ValueError, KeyError) as exc:
        raise _err(exc)


@admin.patch("/users/{username}")
async def admin_update_user(username: str, body: UserPatch, request: Request,
                            settings: Settings = Depends(get_settings)) -> dict:
    st = service.store(settings)
    if username == _actor(request) and body.active is False:
        raise HTTPException(400, "ما تقدرش تعطّل حسابك وأنت داخل بيه")
    try:
        return st.update_user(username, display_name=body.display_name, active=body.active,
                              roles=body.roles, actor=_actor(request))
    except (ValueError, KeyError) as exc:
        raise _err(exc)


@admin.post("/users/{username}/password")
async def admin_set_password(username: str, body: PasswordSet, request: Request,
                             settings: Settings = Depends(get_settings)) -> dict:
    try:
        service.store(settings).set_password(username, body.password, actor=_actor(request))
    except (ValueError, KeyError) as exc:
        raise _err(exc)
    return {"ok": True}


@admin.delete("/users/{username}")
async def admin_delete_user(username: str, request: Request,
                            settings: Settings = Depends(get_settings)) -> dict:
    if username == _actor(request):
        raise HTTPException(400, "ما تقدرش تمسح حسابك وأنت داخل بيه")
    st = service.store(settings)
    if not st.get_user(username):
        raise HTTPException(404, "مش موجود")
    admins = [u for u in st.list_users() if u["active"] and st.allowed(u["username"], "users", "admin")]
    if len(admins) == 1 and admins[0]["username"] == username:
        raise HTTPException(400, "ده آخر مدير — أضف مدير تاني الأول")
    st.delete_user(username, actor=_actor(request))
    return {"ok": True}


@admin.get("/users/{username}/overrides")
async def admin_get_overrides(username: str, settings: Settings = Depends(get_settings)) -> dict:
    st = service.store(settings)
    if not st.get_user(username):
        raise HTTPException(404, "مش موجود")
    return {"username": username, "overrides": st.overrides(username), "effective": st.effective(username)}


@admin.put("/users/{username}/overrides")
async def admin_put_overrides(username: str, items: list[OverrideItem], request: Request,
                              settings: Settings = Depends(get_settings)) -> dict:
    st = service.store(settings)
    try:
        ov = st.set_overrides(username, [i.model_dump() for i in items], actor=_actor(request))
    except KeyError as exc:
        raise _err(exc)
    return {"username": username, "overrides": ov, "effective": st.effective(username)}


@admin.get("/roles")
async def admin_roles(settings: Settings = Depends(get_settings)) -> dict:
    return {"roles": service.store(settings).list_roles()}


@admin.put("/roles/{key}")
async def admin_save_role(key: str, body: RoleIn, request: Request,
                          settings: Settings = Depends(get_settings)) -> dict:
    try:
        return service.store(settings).save_role(key, name=body.name, desc=body.desc,
                                                 perms=body.perms, actor=_actor(request))
    except ValueError as exc:
        raise _err(exc)


@admin.delete("/roles/{key}")
async def admin_delete_role(key: str, request: Request,
                            settings: Settings = Depends(get_settings)) -> dict:
    try:
        service.store(settings).delete_role(key, actor=_actor(request))
    except (ValueError, KeyError) as exc:
        raise _err(exc)
    return {"ok": True}


@admin.get("/audit")
async def admin_audit(limit: int = 200, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {"audit": service.store(settings).audit(min(limit, 1000))}
