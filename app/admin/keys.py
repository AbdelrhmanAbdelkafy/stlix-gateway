"""Changing a secret without ever showing one.

The owner's problem was not that a password was weak; it was that it lived in a
PHP file on a server and nobody remembered it. The answer is not a screen that
prints secrets back — that turns one forgotten password into a single page
worth stealing. It is a screen that can *replace* a secret and say nothing
about it: whether it is set, when it changed and who changed it.

Three rules hold this together:

- **Write-only.** No endpoint here returns a stored value, and no value is ever
  written to a log, an audit row or an error message. Forgetting a key is
  answered by setting a new one.
- **A generated key is shown once.** Keys that other machines must carry (the
  CCTV agent on the factory PC, the portal agent's key) are useless if nobody
  can copy them, so `generate` returns the new value in that one response and
  never again.
- **A session, not an API key.** Every served page carries the gateway API key
  in its HTML, so anyone who can open any screen holds it. That key must not
  open this door: these routes require a signed-in user with the `secrets`
  permission, which by default only an admin has.

Changes land in `.env` (so they survive a restart) *and* in this process's
environment (so they take effect now, without one).
"""
from __future__ import annotations

import os
import re
import secrets as _secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import service as auth_service
from ..config import Settings, get_settings

_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = _ROOT / ".env"
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,48}$")
_KEEP_BACKUPS = 5


@dataclass(frozen=True)
class Key:
    """One setting the screen may change. `note` is what a person needs to know
    before changing it — a key that also lives on another machine, or a service
    that has to be told separately, is where the damage happens."""
    name: str
    label: str
    group: str
    kind: str = "secret"          # secret | password | text
    note: str = ""
    generate: bool = False        # may be machine-generated (random token)
    restart: str = ""             # what still has to happen after the change


G_GATE = "بوابة المنصة"
G_NAMA = "نما"
G_CRM = "vTiger"
G_AGENTS = "الأجهزة والوكلاء"
G_ETA = "بورتال الضرايب"

KEYS: tuple[Key, ...] = (
    Key("GATEWAY_API_KEY", "مفتاح الـ API الرئيسي", G_GATE, "secret", generate=True,
        note="كل الصفحات المخدومة بتحمل المفتاح ده جوه الـ HTML. لو غيّرته، أي سكريبت أو MCP "
             "بيستخدم القديم هيقف لحد ما تحطّ الجديد عنده.",
        restart="السكريبتات والـ MCPs اللي بتستخدم المفتاح القديم"),
    Key("GATEWAY_API_KEYS", "مفاتيح API إضافية (مفصولة بفاصلة)", G_GATE, "secret",
        note="بتتقبل مع المفتاح الرئيسي. مفيدة وإنت بتدوّر مفتاح: حطّ الجديد هنا، غيّر المستخدمين، "
             "بعدين شيل القديم."),
    Key("AUTH_BOOTSTRAP_PASSWORD", "باسورد أدمن الإقلاع", G_GATE, "password",
        note="بيستخدم مرة واحدة وقت إنشاء أول مستخدم. تغيير باسورد مستخدم موجود بيتم من شاشة "
             "المستخدمين مش من هنا."),
    Key("NAMA_CLIENT_ID", "Nama client id", G_NAMA, "secret"),
    Key("NAMA_CLIENT_SECRET", "Nama client secret", G_NAMA, "secret"),
    Key("NAMA_SQL_USER", "مستخدم SQL Server", G_NAMA, "text"),
    Key("NAMA_SQL_PASSWORD", "باسورد SQL Server", G_NAMA, "password"),
    Key("VTIGER_USERNAME", "مستخدم vTiger", G_CRM, "text"),
    Key("VTIGER_ACCESS_KEY", "vTiger access key", G_CRM, "secret",
        note="بيتولّد من داخل vTiger نفسه (My Preferences) — مش من هنا."),
    Key("ANTHROPIC_API_KEY", "مفتاح Anthropic", G_GATE, "secret",
        note="بيتولّد من console.anthropic.com — مش من هنا."),
    Key("CCTV_AGENT_KEY", "مفتاح وكيل الكاميرات", G_AGENTS, "secret", generate=True,
        note="نفس المفتاح لازم يتحطّ في config.json على PC المصنع، وإلا الكاميرات تبطّل ترفع.",
        restart="agents/cctv-agent/config.json على PC المصنع"),
    Key("ETA_BROWSER_KEY", "مفتاح متصفح البورتال", G_AGENTS, "secret", generate=True,
        note="متصفح البورتال على نفس السيرفر بيستخدمه علشان يرفع المستندات.",
        restart="systemctl restart stlix-portal بعد تحديث الـ unit"),
    Key("ETA_ERP_CALLBACK_KEY", "مفتاح ping بتاع مصلحة الضرايب", G_ETA, "secret", generate=True,
        note="بيتحطّ عند تسجيل النظام كـ ERP على البورتال. إحنا مش مسجّلين دلوقتي."),
    Key("VAT_SYNC_INTERVAL_MINUTES", "كل كام دقيقة نقرا البورتال", G_ETA, "text",
        note="0 = يدوي بس. 60 = كل ساعة."),
)
_BY_NAME = {k.name: k for k in KEYS}


# --- the file ------------------------------------------------------------------------
def _read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    out: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip()
    return out


def _backup() -> None:
    if not ENV_FILE.exists():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = ENV_FILE.with_name(f".env.bak-{stamp}")
    shutil.copy2(ENV_FILE, dest)
    os.chmod(dest, 0o600)
    old = sorted(ENV_FILE.parent.glob(".env.bak-*"))[:-_KEEP_BACKUPS]
    for f in old:
        f.unlink(missing_ok=True)


def _write_env(name: str, value: str) -> None:
    """Replace one line in place, keeping comments and order. Written to a
    temporary file and renamed, so a crash mid-write cannot leave the platform
    with half an `.env`."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{name}="):
            lines[i] = f"{name}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{name}={value}")
    _backup()
    tmp = ENV_FILE.with_name(".env.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(ENV_FILE)


def set_value(name: str, value: str, actor: str, reason: str = "") -> dict:
    """Persist it, make it live, and record that it happened — never what it is."""
    key = _BY_NAME.get(name)
    if key is None or not _NAME.match(name):
        raise KeyError(name)
    if "\n" in value or "\r" in value:
        raise ValueError("قيمة بسطر واحد بس")
    if len(value) > 4096:
        raise ValueError("القيمة طويلة أوي")
    _write_env(name, value)
    os.environ[name] = value      # live in this process, no restart needed
    get_settings.cache_clear()
    _note(actor, "key.set", name, {"reason": reason[:200], "empty": not value})
    return row(key, _read_env())


def generate(name: str, actor: str) -> str:
    key = _BY_NAME.get(name)
    if key is None or not key.generate:
        raise KeyError(name)
    value = _secrets.token_urlsafe(32)
    set_value(name, value, actor, reason="generated")
    _note(actor, "key.generate", name, {})
    return value


def row(key: Key, env: dict[str, str], history: dict | None = None) -> dict:
    """Everything the screen is allowed to know about one key."""
    value = env.get(key.name, "")
    last = (history or {}).get(key.name, {})
    return {"name": key.name, "label": key.label, "group": key.group, "kind": key.kind,
            "note": key.note, "can_generate": key.generate, "restart": key.restart,
            "set": bool(value), "updated_at": last.get("ts"), "updated_by": last.get("actor")}


def status(settings: Settings) -> list[dict]:
    env = _read_env()
    hist = _history(settings)
    return [row(k, env, hist) for k in KEYS]


# --- who changed what (never what to) -------------------------------------------------
def _note(actor: str, action: str, target: str, detail: dict) -> None:
    try:
        auth_service.store().note(actor, action, target, detail)
    except Exception:      # noqa: BLE001 — an audit that fails must not lose the change
        pass


def _history(settings: Settings) -> dict[str, dict]:
    try:
        rows = auth_service.store(settings).audit(400)
    except Exception:      # noqa: BLE001
        return {}
    out: dict[str, dict] = {}
    for r in rows:                      # newest first
        if str(r.get("action", "")).startswith("key.") and r["target"] not in out:
            out[r["target"]] = {"ts": r["ts"], "actor": r["actor"]}
    return out


# --- the door ------------------------------------------------------------------------
def admin_only(request: Request, settings: Settings = Depends(get_settings)) -> str:
    """A signed-in person with the `secrets` permission — not an API key.

    Every served page carries the gateway key in its HTML, so an API key proves
    only that someone opened a screen. It must not be enough to rotate the
    platform's credentials."""
    if not settings.auth_enabled:
        return "dev"
    user = auth_service.current_user(request, settings)
    if not user:
        raise HTTPException(status_code=403, detail="لازم تسجّل دخول")
    if not auth_service.store(settings).allowed(user["username"], "secrets", "edit"):
        raise HTTPException(status_code=403, detail="الشاشة دي للأدمن بس")
    return user["username"]


router = APIRouter(prefix="/keys", tags=["admin"])


@router.get("")
async def list_keys(actor: str = Depends(admin_only), settings: Settings = Depends(get_settings)):
    """What is set, when and by whom. Never what it is."""
    return {"keys": status(settings), "env_file": str(ENV_FILE)}


@router.put("/{name}")
async def put_key(name: str, request: Request, actor: str = Depends(admin_only)):
    body = await request.json()
    try:
        return {"ok": True, "key": set_value(name, str(body.get("value") or ""), actor,
                                             str(body.get("reason") or ""))}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"مفتاح مش معروف: {name}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{name}/generate")
async def generate_key(name: str, actor: str = Depends(admin_only)):
    """The one place a value is returned — once, to the person who asked for it."""
    try:
        return {"ok": True, "name": name, "value": generate(name, actor),
                "warning": "القيمة دي مش هتتعرض تاني. انسخها دلوقتي."}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"المفتاح ده مايتولّدش من هنا: {name}")


@router.get("/audit/log")
async def audit_log(actor: str = Depends(admin_only), settings: Settings = Depends(get_settings)):
    rows = [r for r in auth_service.store(settings).audit(200)
            if str(r.get("action", "")).startswith("key.")]
    return {"log": rows[:100]}
