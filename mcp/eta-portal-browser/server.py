#!/usr/bin/env python3
"""The tax portal through a real browser, signed in as the person — no ERP, no API keys.

The owner does not want a system registered with ETA, so there are no API
credentials to hold. This drives `invoicing.eta.gov.eg` in a real Chromium with
a **persistent profile on this machine**: the person signs in by hand once
(including the OTP), the session survives restarts, and every tool after that
runs inside that session.

Deliberately, the password is neither stored nor typed by this program. There is
no `password` setting and no tool that accepts one. `portal_open_login` opens a
visible window and waits for the person to finish; that is the only way in. A
saved government-portal password is the kind of thing that turns one leaked file
into a filed return, and the session cookie in a local profile is a far smaller
blast radius for the same convenience.

Writes on the portal ask before they happen: `portal_click` refuses anything
that looks like submit/cancel/reject/pay unless `confirm=True` is passed, and
takes a screenshot first either way.

Claude Desktop (claude_desktop_config.json):
    "stlix-portal": {
      "command": "python",
      "args": ["D:/Nama Code project/stlix-gateway/mcp/eta-portal-browser/server.py"],
      "env": {"STLIX_GATEWAY_URL": "https://gw.stlixvalley.com",
              "STLIX_ETA_BROWSER_KEY": "<ETA_BROWSER_KEY from the VPS .env>",
              "ETA_PROFILE_DIR": "D:/stlix-portal-profile"}
    }
Deps: pip install mcp playwright httpx  &&  playwright install chromium
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

PORTAL = os.environ.get("ETA_PORTAL_URL", "https://invoicing.eta.gov.eg").rstrip("/")
PROFILE = Path(os.environ.get("ETA_PROFILE_DIR", Path.home() / ".stlix-eta-profile"))
DOWNLOADS = Path(os.environ.get("STLIX_DOWNLOAD_DIR", Path(__file__).with_name("downloads")))
GW = os.environ.get("STLIX_GATEWAY_URL", "https://gw.stlixvalley.com").rstrip("/")
GW_KEY = os.environ.get("STLIX_ETA_BROWSER_KEY", "")
HEADLESS = os.environ.get("ETA_HEADLESS", "1") not in ("0", "false", "False")

#: Anything that changes state at the tax authority. Never clicked on a guess.
DANGEROUS = re.compile(
    r"(submit|send|confirm|cancel|reject|delete|pay|sign|إرسال|ارسال|تأكيد|تاكيد|"
    r"إلغاء|الغاء|رفض|حذف|دفع|اعتماد|توقيع)", re.I)

mcp = FastMCP("stlix-portal", instructions=(
    "The Egyptian tax portal driven as the signed-in user, for entities 'group' (المجموعة) and "
    "'stlix'. Start with portal_status; if signed_in is false, call portal_open_login and tell the "
    "person to sign in — you cannot sign in for them and there is no password anywhere in this tool. "
    "Read with portal_documents / portal_document / portal_page_text. portal_scrape_month also uploads "
    "what it read to the STLIX gateway, which is what makes the VAT planner work without API keys.\n"
    "Anything that submits, cancels, rejects, pays or signs is a real, irreversible act at the tax "
    "authority: show the person the screenshot, say exactly what will happen, and only then call "
    "portal_click with confirm=True. Never do it on your own initiative."))

_pw = None
_ctx = None
_lock = asyncio.Lock()


async def _context():
    """One persistent browser profile, opened lazily and kept for the session."""
    global _pw, _ctx
    async with _lock:
        if _ctx is not None:
            return _ctx
        from playwright.async_api import async_playwright
        PROFILE.mkdir(parents=True, exist_ok=True)
        _pw = await async_playwright().start()
        _ctx = await _pw.chromium.launch_persistent_context(
            str(PROFILE), headless=HEADLESS, viewport={"width": 1440, "height": 900},
            accept_downloads=True, locale="ar-EG")
        return _ctx


async def _page():
    ctx = await _context()
    if ctx.pages:
        return ctx.pages[0]
    return await ctx.new_page()


async def _goto(path: str = "/"):
    page = await _page()
    url = path if path.startswith("http") else PORTAL + ("" if path.startswith("/") else "/") + path
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1200)
    return page


def _looks_signed_in(url: str, text: str) -> bool:
    if re.search(r"/(login|signin|account/login)", url, re.I):
        return False
    return bool(re.search(r"(تسجيل الخروج|logout|sign out|لوحة|dashboard|documents)", text, re.I))


async def _shot(name: str) -> str:
    page = await _page()
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    p = DOWNLOADS / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.png"
    await page.screenshot(path=str(p), full_page=False)
    return str(p)


# --- session -----------------------------------------------------------------------
@mcp.tool()
async def portal_status() -> dict:
    """Is the browser signed in to the portal, and on what page? Always call this first."""
    page = await _goto("/")
    text = await page.inner_text("body")
    return {"signed_in": _looks_signed_in(page.url, text), "url": page.url,
            "title": await page.title(), "profile_dir": str(PROFILE), "headless": HEADLESS,
            "hint": "call portal_open_login and ask the person to sign in" if not _looks_signed_in(page.url, text) else None}


@mcp.tool()
async def portal_open_login(wait_seconds: int = 180) -> dict:
    """Open a VISIBLE browser at the portal's login page so the person signs in themselves.

    This tool has no username or password parameter on purpose: the person types
    their own credentials and OTP into the real portal. The session is then kept
    in the local profile and every other tool uses it.
    """
    global _pw, _ctx
    async with _lock:
        if _ctx is not None:
            await _ctx.close()
            _ctx = None
        if _pw is not None:
            await _pw.stop()
            _pw = None
    from playwright.async_api import async_playwright
    PROFILE.mkdir(parents=True, exist_ok=True)
    _pw = await async_playwright().start()
    _ctx = await _pw.chromium.launch_persistent_context(
        str(PROFILE), headless=False, viewport={"width": 1440, "height": 900},
        accept_downloads=True, locale="ar-EG")
    page = _ctx.pages[0] if _ctx.pages else await _ctx.new_page()
    await page.goto(PORTAL, wait_until="domcontentloaded", timeout=60_000)
    deadline = asyncio.get_event_loop().time() + max(30, min(wait_seconds, 900))
    while asyncio.get_event_loop().time() < deadline:
        await page.wait_for_timeout(3000)
        try:
            if _looks_signed_in(page.url, await page.inner_text("body")):
                return {"signed_in": True, "url": page.url,
                        "note": "الجلسة اتحفظت على الجهاز — مش محتاج تسجّل تاني إلا لما تنتهي"}
        except Exception:  # noqa: BLE001 — mid-navigation
            continue
    return {"signed_in": False, "url": page.url,
            "note": "الوقت خلص من غير تسجيل دخول — النافذة لسه مفتوحة، سجّل وبعدين نادِ portal_status"}


# --- reading -------------------------------------------------------------------------
@mcp.tool()
async def portal_goto(path: str = "/") -> dict:
    """Open any portal page (path or full URL) and report where we landed."""
    page = await _goto(path)
    return {"url": page.url, "title": await page.title()}


@mcp.tool()
async def portal_page_text(max_chars: int = 6000) -> dict:
    """The visible text of the current page — the honest way to see what is there."""
    page = await _page()
    text = await page.inner_text("body")
    return {"url": page.url, "text": text[:max_chars], "truncated": len(text) > max_chars}


@mcp.tool()
async def portal_screenshot() -> dict:
    """Save a screenshot of the current page and return its path."""
    return {"saved_to": await _shot("portal")}


@mcp.tool()
async def portal_tables() -> dict:
    """Every table on the current page as header + rows — the document lists come out of this."""
    page = await _page()
    return {"url": page.url, "tables": await page.evaluate("""() =>
        [...document.querySelectorAll('table')].map(t => ({
            headers: [...t.querySelectorAll('thead th, tr:first-child th, tr:first-child td')].map(c => c.innerText.trim()),
            rows: [...t.querySelectorAll('tbody tr')].slice(0, 300).map(r =>
                [...r.querySelectorAll('td')].map(c => c.innerText.trim()))
        })).filter(t => t.rows.length)
    """)}


@mcp.tool()
async def portal_find(text: str) -> dict:
    """Where a piece of text appears on the page — use it before clicking anything."""
    page = await _page()
    return {"matches": await page.evaluate("""(needle) =>
        [...document.querySelectorAll('a,button,[role=button],td,th,label,span')]
            .filter(e => e.innerText && e.innerText.trim().includes(needle))
            .slice(0, 25).map(e => ({tag: e.tagName.toLowerCase(), text: e.innerText.trim().slice(0, 120),
                                     href: e.getAttribute('href') || null}))
    """, text)}


# --- acting --------------------------------------------------------------------------
@mcp.tool()
async def portal_click(text: str, confirm: bool = False, nth: int = 0) -> dict:
    """Click the element whose text matches. Anything that submits, cancels, rejects,
    pays or signs is refused unless confirm=True — ask the person first, with the
    screenshot in front of them."""
    before = await _shot("before-click")
    if DANGEROUS.search(text) and not confirm:
        return {"clicked": False, "refused": "دي عملية بتغيّر حاجة على البورتال — محتاجة تأكيد صريح",
                "screenshot": before, "text": text,
                "how": "أعرض اللقطة على المستخدم، قوله هيحصل إيه بالظبط، وبعد موافقته نادِ نفس الأداة بـ confirm=True"}
    page = await _page()
    try:
        await page.get_by_text(text, exact=False).nth(nth).click(timeout=15_000)
    except Exception as exc:  # noqa: BLE001
        return {"clicked": False, "error": f"{type(exc).__name__}: {exc}"[:200], "screenshot": before}
    await page.wait_for_timeout(2000)
    return {"clicked": True, "url": page.url, "screenshot_before": before,
            "screenshot_after": await _shot("after-click")}


@mcp.tool()
async def portal_fill(label: str, value: str) -> dict:
    """Type into a field found by its label/placeholder. Refuses password fields:
    credentials are the person's to type, never this tool's."""
    page = await _page()
    if re.search(r"(password|كلمة السر|كلمة المرور|otp|رمز)", label, re.I):
        return {"filled": False, "refused": "الباسورد/الرمز بيتكتب من المستخدم نفسه في النافذة"}
    try:
        field = page.get_by_label(label, exact=False)
        if await field.count() == 0:
            field = page.get_by_placeholder(label, exact=False)
        await field.first.fill(value, timeout=15_000)
    except Exception as exc:  # noqa: BLE001
        return {"filled": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    return {"filled": True, "label": label}


@mcp.tool()
async def portal_download(link_text: str) -> dict:
    """Click a download/export link and save what the portal hands back."""
    page = await _page()
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    try:
        async with page.expect_download(timeout=120_000) as dl:
            await page.get_by_text(link_text, exact=False).first.click()
        d = await dl.value
        target = DOWNLOADS / (d.suggested_filename or "download.bin")
        await d.save_as(str(target))
    except Exception as exc:  # noqa: BLE001
        return {"downloaded": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    return {"downloaded": True, "saved_to": str(target)}


# --- the bridge back to the platform --------------------------------------------------
@mcp.tool()
async def portal_scrape_month(entity: str, month: str, rows: list[dict] | None = None) -> dict:
    """Send documents read off the portal to the STLIX gateway for `entity`/`month`.

    Pass `rows` you assembled from `portal_tables` — each row as
    {internal_id, direction: Sent|Received, status, date, net, vat, total,
     issuer_name, receiver_name}. Missing VAT is fine and honest: the gateway
    marks it estimated rather than pretending the page showed a zero.
    """
    if not rows:
        return {"ok": False, "error": "rows فاضية — اقرا الجدول بـ portal_tables الأول"}
    if not GW_KEY:
        return {"ok": False, "error": "STLIX_ETA_BROWSER_KEY مش متحط في إعدادات الـ MCP"}
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{GW}/api/v1/eta/{entity}/ingest",
                         json={"documents": rows, "source": f"browser:{month}"},
                         headers={"X-ETA-Browser-Key": GW_KEY})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def portal_close() -> dict:
    """Close the browser (the signed-in session stays in the profile)."""
    global _pw, _ctx
    async with _lock:
        if _ctx is not None:
            await _ctx.close()
            _ctx = None
        if _pw is not None:
            await _pw.stop()
            _pw = None
    return {"closed": True}


if __name__ == "__main__":
    mcp.run()
