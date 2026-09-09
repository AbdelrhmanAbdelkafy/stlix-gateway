"""Enforce the permission matrix on every request when auth is on.

- Public paths (login, health, the voice asset) pass.
- A valid `X-API-Key` header still passes (scripts, AI clients) — that is the
  machine door, unchanged.
- Otherwise a session cookie is required. A browser asking for HTML is sent to
  `/login?to=…`; an API caller gets a 401 JSON body.
- The path maps to a resource (`resources.resource_for_path`); GET/HEAD need
  `view`, anything else needs `edit`; the users/roles admin needs `admin`.
"""
from __future__ import annotations

import html
from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..config import get_settings
from . import service
from .resources import BY_KEY, is_public, resource_for_path

_SAFE = ("GET", "HEAD", "OPTIONS")


def _wants_html(request: Request) -> bool:
    return request.method in ("GET", "HEAD") and "text/html" in request.headers.get("accept", "")


def _forbidden(request: Request, resource: str, action: str) -> HTMLResponse | JSONResponse:
    r = BY_KEY.get(resource)
    name = r.name if r else resource
    if _wants_html(request):
        body = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>غير مسموح — STLIX</title><style>body{{font-family:"IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif;background:#0F1C2E;color:#E9EDF3;display:grid;place-items:center;height:100vh;margin:0}}
.c{{background:#131C2B;border:1px solid #26344A;border-radius:16px;padding:28px;max-width:420px;text-align:center}} a{{color:#E0A53A}}</style></head>
<body><div class="c"><div style="font-size:40px">🔒</div><h2 style="margin:8px 0">مش مسموح لك هنا</h2>
<p style="color:#8E9BB0">حسابك ما عندوش صلاحية «{html.escape(action)}» على <b>{html.escape(name)}</b>.<br>لو محتاجها كلّم الـ IT.</p>
<p><a href="/hub/">← الرجوع للهَب</a> &nbsp;·&nbsp; <a href="/logout">خروج</a></p></div></body></html>"""
        return HTMLResponse(body, status_code=403)
    return JSONResponse({"error": "Forbidden", "resource": resource, "action": action,
                         "detail": f"No '{action}' permission on '{resource}'."}, status_code=403)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.auth_enabled:
            return await call_next(request)
        path = request.url.path
        host = request.headers.get("host", "")
        # hub.<domain>/ is the hub, not the gateway's own index
        if path == "/" and host.split(":")[0].startswith("hub."):
            return RedirectResponse("/hub/", status_code=302)
        if is_public(path):
            return await call_next(request)

        user = service.current_user(request, settings)
        if not user:
            key = request.headers.get("x-api-key")
            if key and key in settings.api_keys:
                request.state.user = {"username": f"api-key:{key[:6]}", "api_key": True}
                return await call_next(request)
            if _wants_html(request):
                to = path + (f"?{request.url.query}" if request.url.query else "")
                return RedirectResponse(f"/login?to={quote(to, safe='')}", status_code=302)
            return JSONResponse({"error": "Unauthorized", "detail": "Login required."},
                                status_code=401, headers={"WWW-Authenticate": "Cookie"})

        resource = resource_for_path(path)
        action = "view" if request.method in _SAFE else "edit"
        if resource == "users":
            action = "admin"
        st = service.store(settings)
        if not st.allowed(user["username"], resource, action):
            return _forbidden(request, resource, action)
        return await call_next(request)
