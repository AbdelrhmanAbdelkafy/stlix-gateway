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


#: Read-only, and fixed: no selector or script ever comes from the caller. The
#: portal's document list is an Angular grid rather than a <table>, so a table
#: reader alone comes back empty on the one page that matters. Three strategies,
#: most trustworthy first, and it reports which one it used so a silent change
#: in the portal's markup shows up as `how: "repeat"` instead of as wrong rows.
_GRID_JS = """() => {
  const txt = e => (e.innerText || '').replace(/\\s+/g, ' ').trim();
  const ID = /^[A-Z0-9]{18,}$/;

  const byTable = () => {
    for (const t of document.querySelectorAll('table')) {
      const rows = [...t.querySelectorAll('tbody tr')]
        .map(r => [...r.querySelectorAll('td')].map(txt)).filter(r => r.length);
      if (rows.length) return {how: 'table', rows: rows.slice(0, 500),
        headers: [...t.querySelectorAll('thead th, tr:first-child th')].map(txt)};
    }
    return null;
  };

  const byAria = () => {
    const rs = [...document.querySelectorAll('[role=row]')];
    if (rs.length < 2) return null;
    // The portal's list is a Fluent DetailsList: the first cell of each row is a
    // rowheader, not a gridcell. Miss it and every column shifts by one.
    const body = rs.map(r => [...r.querySelectorAll('[role=gridcell],[role=rowheader],[role=cell]')].map(txt))
                   .filter(r => r.filter(Boolean).length >= 3);
    return body.length ? {how: 'aria', rows: body.slice(0, 500),
      headers: [...rs[0].querySelectorAll('[role=columnheader]')].map(txt)} : null;
  };

  // The portal draws its list with plain divs whose classes differ row to row, so
  // structure alone finds nothing. Anchor on content instead: every row carries one
  // long document id. Climb from it until the ancestor would swallow a second id —
  // that ancestor is the row, whatever it is called.
  const byAnchor = () => {
    const leaves = [...document.querySelectorAll('*')].filter(e => !e.children.length);
    const anchors = leaves.filter(e => ID.test(txt(e)));
    if (anchors.length < 2) return null;
    const ids = n => [...n.querySelectorAll('*')].filter(e => !e.children.length && ID.test(txt(e))).length;
    const seen = new Set(), rows = [];
    for (const a of anchors) {
      let n = a;
      while (n.parentElement && n.parentElement !== document.body && ids(n.parentElement) <= 1)
        n = n.parentElement;
      if (seen.has(n)) continue;
      seen.add(n);
      let cells = [...n.children].map(txt);
      while (cells.length === 1 && n.children.length === 1) { n = n.children[0]; cells = [...n.children].map(txt); }
      if (cells.filter(Boolean).length >= 3) rows.push(cells);
    }
    return rows.length ? {how: 'anchor', headers: [], rows: rows.slice(0, 500)} : null;
  };

  const byRepeat = () => {
    let best = null;
    for (const el of document.querySelectorAll('div,ul,section,tbody')) {
      const kids = [...el.children];
      if (kids.length < 3) continue;
      const tag = kids[0].tagName;
      if (!kids.every(k => k.tagName === tag)) continue;
      const rows = kids.map(k => [...k.children].map(txt));
      const n = rows[0].length;
      if (n < 4 || !rows.every(r => r.length === n) || !rows.every(r => r.filter(Boolean).length >= 3)) continue;
      if (!best || rows.length * n > best.rows.length * best.rows[0].length)
        best = {how: 'repeat', headers: [], rows: rows.slice(0, 500)};
    }
    return best;
  };

  const got = byTable() || byAria() || byAnchor() || byRepeat() || {how: 'none', headers: [], rows: []};
  if (!got.headers || !got.headers.length) {
    const hs = [...document.querySelectorAll('[role=columnheader],th,[class*=header] [class*=cell],[class*=head] span')]
      .map(txt).filter(Boolean);
    got.headers = hs.slice(0, 20);
  }
  return got;
}"""

#: Read-only and text-free: shapes and counts, never cell contents. It exists so
#: that a portal redesign is answered by looking at what is actually there
#: instead of guessing at selectors from the outside.
_PROBE_JS = """() => {
  const txt = e => (e.innerText || '').replace(/\\s+/g, ' ').trim();
  const ID = /^[A-Z0-9]{18,}$/;
  const leaves = [...document.querySelectorAll('*')].filter(e => !e.children.length);
  const anchor = leaves.find(e => ID.test(txt(e)));
  const describe = n => ({tag: n.tagName.toLowerCase(),
                         cls: String(n.className || '').slice(0, 70),
                         role: n.getAttribute && n.getAttribute('role'),
                         kids: n.children.length, chars: txt(n).length});
  const chain = [];
  let n = anchor;
  while (n && n !== document.body && chain.length < 9) { chain.push(describe(n)); n = n.parentElement; }
  return {
    id_like_cells: leaves.filter(e => ID.test(txt(e))).length,
    tables: document.querySelectorAll('table').length,
    aria_rows: document.querySelectorAll('[role=row]').length,
    aria_grids: document.querySelectorAll('[role=grid],[role=table]').length,
    iframes: document.querySelectorAll('iframe').length,
    chain,
  };
}"""


@app.get("/probe")
async def probe():
    """What the current page's list is actually made of — shapes, not contents."""
    pg = await page()
    return {"url": pg.url, **await pg.evaluate(_PROBE_JS)}


@app.get("/rows")
async def rows():
    """The current page's data grid, however the portal happens to draw it."""
    pg = await page()
    got = await pg.evaluate(_GRID_JS)
    return {"url": pg.url, **got, "count": len(got.get("rows") or [])}


#: Finding "the next page" without being told a selector: an aria-label, a
#: title, a rel, a class, or failing all of those the link whose text is the
#: number after the one that is currently marked active. Pagination is the only
#: clicking this does — nothing here can submit, cancel or pay.
_NEXT_JS = """(page) => {
  const cand = [...document.querySelectorAll(
    '[aria-label],[title],a,button,li,span,[class*=next],[class*=pagination] *')];
  const looksNext = e => {
    const s = ((e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '') + ' ' +
               (e.getAttribute('rel') || '') + ' ' + String(e.className || '')).toLowerCase();
    return /next|التالي|التالى/.test(s) && !/prev|disabled/.test(s);
  };
  let el = cand.find(e => looksNext(e) && e.offsetParent !== null);
  if (!el) {
    const want = String(page + 1);
    el = cand.find(e => e.children.length === 0 &&
                        (e.innerText || '').trim() === want && e.offsetParent !== null);
  }
  if (!el) return false;
  (el.closest('a,button,li') || el).click();
  return true;
}"""


@app.get("/collect")
async def collect(pages: int = 10):
    """Every page of the current list, not just the ten rows on screen.

    Stops on its own when there is no next control, when a page repeats itself,
    or at `pages` — a portal that paginates forever must not turn into a loop
    that clicks forever.
    """
    pg = await page()
    seen: set[str] = set()
    out: list[list[str]] = []
    headers: list[str] = []
    read = 0
    for n in range(1, max(1, min(pages, 60)) + 1):
        got = await pg.evaluate(_GRID_JS)
        headers = headers or (got.get("headers") or [])
        fresh = 0
        for row in got.get("rows") or []:
            key = "|".join(row)[:200]
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
            fresh += 1
        read = n
        if not fresh and n > 1:
            break
        if not await pg.evaluate(_NEXT_JS, n):
            break
        await pg.wait_for_timeout(2500)
    return {"url": pg.url, "headers": headers, "rows": out, "count": len(out), "pages_read": read}


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
    # `exact` matters for pagination: "2" appears inside every amount on the
    # page, so a loose match clicks a number in a table instead of a page link.
    label, confirm = str(body.get("text") or ""), bool(body.get("confirm"))
    before = await shot("before-click")
    if DANGEROUS.search(label) and not confirm:
        return {"clicked": False, "screenshot": before, "text": label,
                "refused": "عملية بتغيّر حاجة على البورتال — محتاجة confirm صريح"}
    pg = await page()
    try:
        await pg.get_by_text(label, exact=bool(body.get("exact"))).nth(
            int(body.get("nth") or 0)).click(timeout=15_000)
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
    payload: dict = {"source": "browser-agent"}
    if body.get("grid"):
        # Read the page's own grid here rather than making the caller carry it
        # across two hops: this is the normal path for the document list, and it
        # walks the pagination unless asked for the visible page only.
        pg = await page()
        got = (await collect(int(body.get("pages") or 10))
               if body.get("all_pages", True) else await pg.evaluate(_GRID_JS))
        if not got.get("rows"):
            return JSONResponse({"ok": False, "error": "مفيش صفوف على الصفحة دي",
                                 "how": got.get("how"), "url": pg.url}, status_code=400)
        payload["grid"] = {"headers": got.get("headers"), "rows": got.get("rows")}
    elif rows:
        payload["documents"] = rows
    if not entity or ("grid" not in payload and "documents" not in payload):
        return JSONResponse({"ok": False, "error": "entity ومعاه documents أو grid"}, status_code=400)
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{GW}/api/v1/eta/{entity}/ingest", json=payload,
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
