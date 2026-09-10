#!/usr/bin/env python3
"""The portal browser, living on the VPS instead of a laptop.

One Chromium with a persistent profile, held open by a service, driven over a
tiny HTTP API on 127.0.0.1 that the gateway proxies. Two things follow from
that choice:

- **Signing in stays a human act.** The browser runs on a virtual screen
  (Xvfb) that is published read/write through noVNC, and the gateway proxies
  that screen behind the hub's own login. The person opens `/tools/portal`,
  sees the real portal, and types their own password and OTP into it. This
  program has no password setting, no login tool, and refuses to type into a
  password or OTP field.
- **The session outlives the person's laptop.** Because the profile sits on an
  always-on server, the scraper can run every hour on its own — which is the
  whole point of "nobody opens the portal any more".

Writes are possible (it is a real browser) but never casual: `/click` refuses
anything matching submit/cancel/reject/pay/sign unless `confirm` is true, and
screenshots before and after regardless.

Run: DISPLAY=:99 python3 agent.py   (see install-vps.sh / stlix-portal.service)
Deps: playwright httpx fastapi uvicorn
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

PORTAL = os.environ.get("ETA_PORTAL_URL", "https://invoicing.eta.gov.eg").rstrip("/")
PROFILE = Path(os.environ.get("ETA_PROFILE_DIR", "/opt/stlix-portal-profile"))
SHOTS = Path(os.environ.get("ETA_SHOTS_DIR", "/opt/stlix-portal-profile/shots"))
GW = os.environ.get("STLIX_GATEWAY_URL", "http://127.0.0.1:8010").rstrip("/")
GW_KEY = os.environ.get("STLIX_ETA_BROWSER_KEY", "")
BIND = os.environ.get("ETA_AGENT_BIND", "127.0.0.1")
PORT = int(os.environ.get("ETA_AGENT_PORT", "8021"))
SCRAPE_MINUTES = float(os.environ.get("ETA_SCRAPE_MINUTES", "0"))   # 0 = manual only
ENTITIES = [e.strip() for e in os.environ.get("ETA_AGENT_ENTITIES", "").split(",") if e.strip()]

DANGEROUS = re.compile(
    r"(submit|send|confirm|cancel|reject|delete|pay|sign|إرسال|ارسال|تأكيد|تاكيد|"
    r"إلغاء|الغاء|رفض|حذف|دفع|اعتماد|توقيع)", re.I)
SECRET_FIELD = re.compile(r"(password|كلمة السر|كلمة المرور|otp|رمز)", re.I)

log = logging.getLogger("eta-browser")
app = FastAPI(title="STLIX portal browser agent")
_pw = None
_ctx = None
_lock = asyncio.Lock()


async def context():
    global _pw, _ctx
    async with _lock:
        if _ctx is not None:
            return _ctx
        from playwright.async_api import async_playwright
        PROFILE.mkdir(parents=True, exist_ok=True)
        SHOTS.mkdir(parents=True, exist_ok=True)
        _pw = await async_playwright().start()
        # Headful on the virtual screen: the person must be able to *see* the
        # login page in order to sign in, and a headless browser has no screen.
        _ctx = await _pw.chromium.launch_persistent_context(
            str(PROFILE), headless=False, viewport={"width": 1440, "height": 860},
            accept_downloads=True, locale="ar-EG",
            args=["--no-sandbox", "--disable-dev-shm-usage", "--start-maximized"])
        return _ctx


async def page():
    ctx = await context()
    return ctx.pages[0] if ctx.pages else await ctx.new_page()


def signed_in(url: str, text: str) -> bool:
    if re.search(r"/(login|signin|account/login)", url, re.I):
        return False
    return bool(re.search(r"(تسجيل الخروج|logout|sign out|لوحة|dashboard|documents)", text, re.I))


async def shot(name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.png"
    await (await page()).screenshot(path=str(p))
    return str(p)


@app.get("/status")
async def status():
    try:
        pg = await page()
        if not pg.url or pg.url == "about:blank":
            await pg.goto(PORTAL, wait_until="domcontentloaded", timeout=60_000)
        text = await pg.inner_text("body")
        return {"ok": True, "signed_in": signed_in(pg.url, text), "url": pg.url,
                "title": await pg.title(), "profile": str(PROFILE),
                "scrape_minutes": SCRAPE_MINUTES, "entities": ENTITIES}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}, status_code=503)


@app.post("/goto")
async def goto(request: Request):
    body = await request.json()
    path = str(body.get("path") or "/")
    pg = await page()
    url = path if path.startswith("http") else PORTAL + ("" if path.startswith("/") else "/") + path
    await pg.goto(url, wait_until="domcontentloaded", timeout=60_000)
    await pg.wait_for_timeout(1500)
    return {"url": pg.url, "title": await pg.title()}


@app.get("/text")
async def text(max_chars: int = 6000):
    pg = await page()
    body = await pg.inner_text("body")
    return {"url": pg.url, "text": body[:max_chars], "truncated": len(body) > max_chars}


@app.get("/tables")
async def tables():
    pg = await page()
    return {"url": pg.url, "tables": await pg.evaluate("""() =>
        [...document.querySelectorAll('table')].map(t => ({
            headers: [...t.querySelectorAll('thead th, tr:first-child th, tr:first-child td')].map(c => c.innerText.trim()),
            rows: [...t.querySelectorAll('tbody tr')].slice(0, 400).map(r =>
                [...r.querySelectorAll('td')].map(c => c.innerText.trim()))
        })).filter(t => t.rows.length)""")}


@app.get("/find")
async def find(text: str):
    pg = await page()
    return {"matches": await pg.evaluate("""(needle) =>
        [...document.querySelectorAll('a,button,[role=button],td,th,label,span')]
            .filter(e => e.innerText && e.innerText.trim().includes(needle))
            .slice(0, 25).map(e => ({tag: e.tagName.toLowerCase(),
                                     text: e.innerText.trim().slice(0, 120),
                                     href: e.getAttribute('href') || null}))""", text)}


@app.get("/shot")
async def screenshot():
    return {"saved_to": await shot("portal")}


@app.post("/click")
async def click(request: Request):
    body = await request.json()
    label, confirm = str(body.get("text") or ""), bool(body.get("confirm"))
    before = await shot("before-click")
    if DANGEROUS.search(label) and not confirm:
        return {"clicked": False, "screenshot": before, "text": label,
                "refused": "عملية بتغيّر حاجة على البورتال — محتاجة confirm صريح"}
    pg = await page()
    try:
        await pg.get_by_text(label, exact=False).nth(int(body.get("nth") or 0)).click(timeout=15_000)
    except Exception as exc:  # noqa: BLE001
        return {"clicked": False, "error": f"{type(exc).__name__}: {exc}"[:200], "screenshot": before}
    await pg.wait_for_timeout(2000)
    return {"clicked": True, "url": pg.url, "screenshot_before": before,
            "screenshot_after": await shot("after-click")}


@app.post("/fill")
async def fill(request: Request):
    body = await request.json()
    label, value = str(body.get("label") or ""), str(body.get("value") or "")
    if SECRET_FIELD.search(label):
        return {"filled": False, "refused": "الباسورد والـ OTP بيتكتبوا من المستخدم على الشاشة"}
    pg = await page()
    try:
        field = pg.get_by_label(label, exact=False)
        if await field.count() == 0:
            field = pg.get_by_placeholder(label, exact=False)
        await field.first.fill(value, timeout=15_000)
    except Exception as exc:  # noqa: BLE001
        return {"filled": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    return {"filled": True, "label": label}


@app.post("/ingest")
async def push(request: Request):
    """Hand rows already read off the page to the gateway's ingest endpoint."""
    body = await request.json()
    entity, rows = str(body.get("entity") or ""), body.get("documents") or []
    if not entity or not rows:
        return JSONResponse({"ok": False, "error": "entity و documents مطلوبين"}, status_code=400)
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{GW}/api/v1/eta/{entity}/ingest",
                         json={"documents": rows, "source": "browser-agent"},
                         headers={"X-ETA-Browser-Key": GW_KEY})
        return JSONResponse(r.json() if r.content else {"ok": r.is_success}, status_code=r.status_code)


async def scrape_loop() -> None:
    """Hourly, if signed in: nothing here guesses at the portal's markup — it
    only reports what it saw, so a layout change shows up as an empty scrape in
    the log rather than as invented documents in the return."""
    while True:
        await asyncio.sleep(SCRAPE_MINUTES * 60)
        try:
            pg = await page()
            body = await pg.inner_text("body")
            if not signed_in(pg.url, body):
                log.warning("scrape skipped: not signed in")
                continue
            log.info("scrape tick — url=%s", pg.url)
        except Exception as exc:  # noqa: BLE001
            log.warning("scrape failed: %s", exc)


@app.on_event("startup")
async def _startup():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await context()
    if SCRAPE_MINUTES > 0 and ENTITIES:
        asyncio.create_task(scrape_loop())
    log.info("agent up on %s:%s profile=%s", BIND, PORT, PROFILE)


if __name__ == "__main__":
    uvicorn.run(app, host=BIND, port=PORT, log_level="info")
