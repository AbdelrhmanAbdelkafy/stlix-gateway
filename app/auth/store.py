"""SQLite-backed users / roles / overrides / audit.

Schema is created on first open. Everything is synchronous and tiny (a few
dozen users), so it runs inline; the file lives under `data/auth/` which the
prod compose file mounts as a volume so a rebuild does not wipe the users.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from .resources import ACTIONS, BY_KEY

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1

#: Built-in profiles — the Nama-style starting point. Editable afterwards from
#: the admin screen; `builtin` only stops them being deleted.
DEFAULT_ROLES: dict[str, dict] = {
    "admin": {"name": "مدير النظام", "desc": "كل حاجة — بما فيها إدارة المستخدمين",
              "perms": {"*": ["view", "edit", "admin"]}},
    "it": {"name": "IT", "desc": "كل الأدوات والسيرفرات بدون إدارة المستخدمين",
           "perms": {"*": ["view", "edit"]}},
    "mgmt": {"name": "إدارة", "desc": "يشوف كل حاجة، يعدّل في REP والأفكار",
             "perms": {"hub": ["view"], "platform": ["view"], "gateway": ["view"],
                       "name-builder": ["view"], "engineer": ["view"], "rep": ["view", "edit"],
                       "certificate": ["view"], "count-app": ["view"], "finance": ["view"], "vat": ["view", "edit"],
                       "expert": ["view", "edit"], "legal": ["view", "edit"],
                       "ideas": ["view", "edit"],
                       "crm-site": ["view"], "erp-site": ["view"],
                       "website": ["view"], "egygrouphs": ["view"],
                       "wp-admin": ["view"], "egy-admin": ["view"],
                       "attendance-site": ["view"], "fleet-dashboard": ["view", "edit"], "payroll-site": ["view"],
                       "notion": ["view"], "google": ["view"], "cameras": ["view"]}},
    "sales": {"name": "بياع", "desc": "المنصة، الرصيد، REP، الـ CRM، الموقع",
              "perms": {"hub": ["view"], "platform": ["view"], "name-builder": ["view"],
                        "engineer": ["view"], "rep": ["view", "edit"], "count-app": ["view"],
                        "fleet-dashboard": ["view"], "expert": ["view"], "crm-site": ["view"],
                        "website": ["view"], "egygrouphs": ["view"]}},
    "proc": {"name": "مشتريات", "desc": "NAME BUILDER، الشهادات، الجرد، نما",
             "perms": {"hub": ["view"], "platform": ["view"], "name-builder": ["view", "edit"],
                       "engineer": ["view"], "certificate": ["view", "edit"],
                       "count-app": ["view", "edit"], "expert": ["view"], "erp-site": ["view"]}},
    "factory": {"name": "مصنع", "desc": "المهندس، الجرد، REP، الكاميرات",
                "perms": {"hub": ["view"], "engineer": ["view"], "count-app": ["view", "edit"],
                          "rep": ["view"], "fleet-dashboard": ["view"], "cameras": ["view"]}},
    "viewer": {"name": "مشاهدة فقط", "desc": "الهَب والمنصة للقراءة",
               "perms": {"hub": ["view"], "platform": ["view"]}},
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  display_name TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  roles TEXT NOT NULL DEFAULT '[]',
  session_version INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL,
  last_login REAL
);
CREATE TABLE IF NOT EXISTS roles (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  desc TEXT NOT NULL DEFAULT '',
  perms TEXT NOT NULL DEFAULT '{}',
  builtin INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS overrides (
  username TEXT NOT NULL,
  resource TEXT NOT NULL,
  action TEXT NOT NULL,
  effect TEXT NOT NULL CHECK (effect IN ('allow','deny')),
  PRIMARY KEY (username, resource, action)
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N,
                            r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                              n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, TypeError):
        return False


def _clean_perms(perms: dict) -> dict[str, list[str]]:
    """Keep only known resources (or `*`) and known actions, deduplicated."""
    out: dict[str, list[str]] = {}
    for res, acts in (perms or {}).items():
        if res != "*" and res not in BY_KEY:
            continue
        keep = [a for a in ACTIONS if a in (acts or [])]
        out[res] = keep
    return out


class AuthStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._seed_roles()
            self._conn.commit()

    # --- setup -------------------------------------------------------------
    def _seed_roles(self) -> None:
        cur = self._conn.execute("SELECT COUNT(*) FROM roles")
        if cur.fetchone()[0]:
            return
        for key, r in DEFAULT_ROLES.items():
            self._conn.execute(
                "INSERT INTO roles (key, name, desc, perms, builtin) VALUES (?,?,?,?,1)",
                (key, r["name"], r["desc"], json.dumps(_clean_perms(r["perms"]), ensure_ascii=False)))

    def secret(self) -> str:
        """Cookie-signing secret, generated once and kept in the DB."""
        with self._lock:
            row = self._conn.execute("SELECT v FROM meta WHERE k='secret'").fetchone()
            if row:
                return row["v"]
            s = secrets.token_hex(32)
            self._conn.execute("INSERT INTO meta (k, v) VALUES ('secret', ?)", (s,))
            self._conn.commit()
            return s

    def bootstrap(self, username: str, password: str) -> bool:
        """Create the first admin when the users table is empty. Returns True if created."""
        with self._lock:
            if self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                return False
            self.create_user(username, password, display_name="Administrator",
                             roles=["admin"], actor="bootstrap")
            return True

    def user_count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # --- users -------------------------------------------------------------
    @staticmethod
    def _row_user(row) -> dict:
        return {"username": row["username"], "display_name": row["display_name"],
                "active": bool(row["active"]), "roles": json.loads(row["roles"]),
                "session_version": row["session_version"], "created_at": row["created_at"],
                "last_login": row["last_login"]}

    def get_user(self, username: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return self._row_user(row) if row else None

    def list_users(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM users ORDER BY username").fetchall()
        return [self._row_user(r) for r in rows]

    def create_user(self, username: str, password: str, *, display_name: str = "",
                    roles: list[str] | None = None, actor: str = "") -> dict:
        username = username.strip().lower()
        if not username or not username.replace(".", "").replace("_", "").replace("-", "").isalnum():
            raise ValueError("اسم المستخدم: حروف/أرقام/نقطة/شرطة بس")
        if len(password) < 8:
            raise ValueError("كلمة المرور 8 حروف على الأقل")
        roles = self._known_roles(roles or [])
        with self._lock:
            if self._conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                raise ValueError("المستخدم موجود بالفعل")
            self._conn.execute(
                "INSERT INTO users (username, display_name, password_hash, roles, created_at) VALUES (?,?,?,?,?)",
                (username, display_name or username, hash_password(password),
                 json.dumps(roles), time.time()))
            self._audit(actor, "user.create", username, {"roles": roles})
            self._conn.commit()
        return self.get_user(username)  # type: ignore[return-value]

    def update_user(self, username: str, *, display_name: str | None = None,
                    active: bool | None = None, roles: list[str] | None = None,
                    actor: str = "") -> dict:
        with self._lock:
            u = self.get_user(username)
            if not u:
                raise KeyError(username)
            changes: dict = {}
            if display_name is not None:
                self._conn.execute("UPDATE users SET display_name=? WHERE username=?", (display_name, username))
                changes["display_name"] = display_name
            if active is not None:
                self._conn.execute("UPDATE users SET active=?, session_version=session_version+1 WHERE username=?",
                                   (1 if active else 0, username))
                changes["active"] = active
            if roles is not None:
                roles = self._known_roles(roles)
                self._conn.execute("UPDATE users SET roles=?, session_version=session_version+1 WHERE username=?",
                                   (json.dumps(roles), username))
                changes["roles"] = roles
            if changes:
                self._audit(actor, "user.update", username, changes)
            self._conn.commit()
        return self.get_user(username)  # type: ignore[return-value]

    def set_password(self, username: str, password: str, *, actor: str = "") -> None:
        if len(password) < 8:
            raise ValueError("كلمة المرور 8 حروف على الأقل")
        with self._lock:
            if not self.get_user(username):
                raise KeyError(username)
            self._conn.execute(
                "UPDATE users SET password_hash=?, session_version=session_version+1 WHERE username=?",
                (hash_password(password), username))
            self._audit(actor, "user.password", username, {})
            self._conn.commit()

    def delete_user(self, username: str, *, actor: str = "") -> None:
        with self._lock:
            self._conn.execute("DELETE FROM users WHERE username=?", (username,))
            self._conn.execute("DELETE FROM overrides WHERE username=?", (username,))
            self._audit(actor, "user.delete", username, {})
            self._conn.commit()

    def authenticate(self, username: str, password: str) -> dict | None:
        username = (username or "").strip().lower()
        with self._lock:
            row = self._conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row or not row["active"] or not verify_password(password or "", row["password_hash"]):
                self._audit(username or "?", "login.fail", username, {})
                self._conn.commit()
                return None
            self._conn.execute("UPDATE users SET last_login=? WHERE username=?", (time.time(), username))
            self._audit(username, "login.ok", username, {})
            self._conn.commit()
        return self._row_user(row)

    # --- roles -------------------------------------------------------------
    def _known_roles(self, roles: list[str]) -> list[str]:
        known = {r["key"] for r in self.list_roles()}
        bad = [r for r in roles if r not in known]
        if bad:
            raise ValueError(f"أدوار غير معروفة: {', '.join(bad)}")
        return sorted(set(roles))

    def list_roles(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM roles ORDER BY builtin DESC, key").fetchall()
        return [{"key": r["key"], "name": r["name"], "desc": r["desc"],
                 "perms": json.loads(r["perms"]), "builtin": bool(r["builtin"])} for r in rows]

    def get_role(self, key: str) -> dict | None:
        return next((r for r in self.list_roles() if r["key"] == key), None)

    def save_role(self, key: str, *, name: str, desc: str = "", perms: dict, actor: str = "") -> dict:
        key = key.strip().lower()
        if not key.replace("-", "").replace("_", "").isalnum():
            raise ValueError("مفتاح الدور: حروف/أرقام/شرطة بس")
        perms = _clean_perms(perms)
        with self._lock:
            exists = self._conn.execute("SELECT 1 FROM roles WHERE key=?", (key,)).fetchone()
            if exists:
                self._conn.execute("UPDATE roles SET name=?, desc=?, perms=? WHERE key=?",
                                   (name, desc, json.dumps(perms, ensure_ascii=False), key))
            else:
                self._conn.execute("INSERT INTO roles (key, name, desc, perms, builtin) VALUES (?,?,?,?,0)",
                                   (key, name, desc, json.dumps(perms, ensure_ascii=False)))
            # a role change must reach every holder on their next request
            self._conn.execute("UPDATE users SET session_version=session_version+1 WHERE roles LIKE ?",
                               (f'%"{key}"%',))
            self._audit(actor, "role.save", key, {"perms": perms})
            self._conn.commit()
        return self.get_role(key)  # type: ignore[return-value]

    def delete_role(self, key: str, *, actor: str = "") -> None:
        with self._lock:
            row = self._conn.execute("SELECT builtin FROM roles WHERE key=?", (key,)).fetchone()
            if not row:
                raise KeyError(key)
            if row["builtin"]:
                raise ValueError("الأدوار الأساسية ما تتمسحش — عدّل صلاحياتها")
            for u in self.list_users():
                if key in u["roles"]:
                    self.update_user(u["username"], roles=[r for r in u["roles"] if r != key], actor=actor)
            self._conn.execute("DELETE FROM roles WHERE key=?", (key,))
            self._audit(actor, "role.delete", key, {})
            self._conn.commit()

    # --- overrides ---------------------------------------------------------
    def overrides(self, username: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT resource, action, effect FROM overrides WHERE username=? ORDER BY resource, action",
                (username,)).fetchall()
        return [dict(r) for r in rows]

    def set_overrides(self, username: str, items: list[dict], *, actor: str = "") -> list[dict]:
        """Replace a user's override list. Each item: {resource, action, effect}."""
        clean = []
        for it in items:
            res, act, eff = it.get("resource"), it.get("action"), it.get("effect")
            if (res == "*" or res in BY_KEY) and act in ACTIONS and eff in ("allow", "deny"):
                clean.append((username, res, act, eff))
        with self._lock:
            if not self.get_user(username):
                raise KeyError(username)
            self._conn.execute("DELETE FROM overrides WHERE username=?", (username,))
            self._conn.executemany("INSERT INTO overrides VALUES (?,?,?,?)", clean)
            self._conn.execute("UPDATE users SET session_version=session_version+1 WHERE username=?", (username,))
            self._audit(actor, "user.overrides", username, {"count": len(clean)})
            self._conn.commit()
        return self.overrides(username)

    # --- effective permissions --------------------------------------------
    def effective(self, username: str) -> dict[str, list[str]]:
        """resource -> actions, after roles (union) and overrides (deny wins).

        A `*` grant in a role expands to every resource so the result is
        always concrete — what the hub and the admin screen show is exactly
        what the middleware enforces.
        """
        u = self.get_user(username)
        if not u or not u["active"]:
            return {}
        roles = {r["key"]: r for r in self.list_roles()}
        granted: dict[str, set[str]] = {k: set() for k in BY_KEY}
        for rk in u["roles"]:
            for res, acts in roles.get(rk, {}).get("perms", {}).items():
                targets = list(BY_KEY) if res == "*" else [res]
                for t in targets:
                    granted.setdefault(t, set()).update(acts)
        for ov in self.overrides(username):
            targets = list(BY_KEY) if ov["resource"] == "*" else [ov["resource"]]
            for t in targets:
                if ov["effect"] == "allow":
                    granted.setdefault(t, set()).add(ov["action"])
        for ov in self.overrides(username):
            targets = list(BY_KEY) if ov["resource"] == "*" else [ov["resource"]]
            for t in targets:
                if ov["effect"] == "deny":
                    granted.get(t, set()).discard(ov["action"])
        return {k: [a for a in ACTIONS if a in v] for k, v in granted.items() if v}

    def allowed(self, username: str, resource: str, action: str) -> bool:
        return action in self.effective(username).get(resource, [])

    # --- audit -------------------------------------------------------------
    def _audit(self, actor: str, action: str, target: str, detail: dict) -> None:
        self._conn.execute("INSERT INTO audit (ts, actor, action, target, detail) VALUES (?,?,?,?,?)",
                           (time.time(), actor or "", action, target or "",
                            json.dumps(detail, ensure_ascii=False)))

    def audit(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, actor, action, target, detail FROM audit ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]


_stores: dict[str, AuthStore] = {}
_stores_lock = threading.Lock()


def get_store(path: Path) -> AuthStore:
    key = str(Path(path).resolve())
    with _stores_lock:
        st = _stores.get(key)
        if st is None:
            st = _stores[key] = AuthStore(path)
        return st


def env_bootstrap_password() -> str:
    return os.environ.get("AUTH_BOOTSTRAP_PASSWORD", "")
