"""Application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the `app` package. Load .env from here so settings
# resolve no matter what working directory the server is launched from.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # --- Gateway ---
    app_name: str = "Stlix Gateway"
    app_env: str = Field(default="dev", description="dev | staging | prod")
    # Shared secret clients must send as `X-API-Key`. Empty string disables the check.
    gateway_api_key: str = Field(default="")
    # Additional accepted keys (comma-separated), on top of gateway_api_key.
    gateway_api_keys: str = Field(default="")

    # --- Layer 6: logs / monitoring / security ---
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    # Fixed-window requests/minute per client (0 = disabled).
    rate_limit_per_minute: int = Field(default=120)
    # Comma-separated allowed CORS origins ("*" = any).
    cors_origins: str = Field(default="*")
    security_headers: bool = Field(default=True)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    # --- Users / permissions (PA2/PA3) ------------------------------------
    # auto = on in prod, off elsewhere (so the test suite and local dev run
    # without a users table); on/off force it.
    auth_mode: str = Field(default="auto", pattern="^(auto|on|off)$")
    auth_db_path: str = Field(default="", description="SQLite file; blank = data/auth/auth.db")
    # Cookie domain so one login covers hub.* and gw.* (e.g. ".stlixvalley.com").
    auth_cookie_domain: str = Field(default="")
    auth_session_hours: float = Field(default=12.0)
    # First admin, created only when the users table is empty.
    auth_bootstrap_user: str = Field(default="stlix")
    auth_bootstrap_password: str = Field(default="")
    # Seconds between live-status refreshes pushed to the hub.
    hub_live_interval: float = Field(default=20.0)

    @property
    def auth_enabled(self) -> bool:
        if self.auth_mode == "on":
            return True
        if self.auth_mode == "off":
            return False
        return self.app_env == "prod"

    @property
    def api_keys(self) -> set[str]:
        keys = {k.strip() for k in self.gateway_api_keys.split(",") if k.strip()}
        if self.gateway_api_key:
            keys.add(self.gateway_api_key)
        return keys

    # --- Nama ERP REST v1 ---
    # Cloud: https://stlixvalley.namasoft.net/erp/rest/v1
    # Local: http://localhost:8080/erp/rest/v1
    nama_base_url: str = Field(default="https://stlixvalley.namasoft.net/erp/rest/v1")
    nama_client_id: str = Field(default="")
    nama_client_secret: str = Field(default="")
    nama_timeout: float = Field(default=30.0)
    # Connector mode: read_only (default, safe) | read_write
    nama_mode: str = Field(default="read_only")
    # Banks connector reuses the Nama REST creds; its own mode:
    banks_mode: str = Field(default="read_only")

    # --- Finance connector (customer/supplier balances) ---
    # Namasoft report/query entities that expose computed balances (REST doesn't
    # expose them natively — see docs/nama-balance-report-spec.md). Once Namasoft
    # publishes these, the finance endpoints go live with zero code changes.
    # Which source answers /api/v1/finance/* when the caller does not say.
    #
    # `live` (rebuilt from Nama REST documents) is the intended destination and
    # the owner's choice — but only once `scripts/reconcile_live_vs_sql.py`
    # passes on this machine. It ships as `sql` so the switch is a deliberate
    # act with a reconciliation behind it, not a default nobody checked. A
    # figure that is old is bad; a figure that is wrong is far worse.
    finance_default_source: str = Field(default="sql", pattern="^(sql|live)$")

    # Seconds between background live sweeps. 0 = off, so importing the app (as
    # the test suite does) never reaches the ERP. A sweep is ~14,000 documents,
    # so this is the thing that makes `live` usable as a default at all: without
    # it the first visitor after every restart pays eight minutes for the page.
    live_finance_refresh_seconds: int = Field(default=0)

    # --- drift guard -------------------------------------------------------
    # After each sweep, one closed month is re-reconciled against SQL. It is
    # what turns "the figure is current" into "the figure is current AND still
    # adds up" — a sweep can succeed and still come back short if Nama renames a
    # field or the credential loses reach on some documents.
    finance_guard_enabled: bool = Field(default=True)
    # Blank = a month far enough back that no new invoice will be issued into it.
    # Pin it (YYYYMM) only to investigate a specific window.
    finance_guard_period: str = Field(default="")
    # Documents whose payment legitimately moved BACKWARDS, i.e. a voucher
    # cancelled after the backup was taken. There is no benign reading of that,
    # so each one is named by hand — the guard must not learn to shrug.
    finance_allowed_reversals: str = Field(default="FP22026060000105")

    @property
    def allowed_reversals(self) -> set[str]:
        return {c.strip() for c in self.finance_allowed_reversals.split(",") if c.strip()}

    # --- Nama Expert (Layer 4) ---------------------------------------------
    # The key lives here and only here. The chat page is served by the gateway
    # and calls /api/v1/expert/ask; it never sees this value — same rule that
    # took the Nama and Anthropic creds out of the NameBuilder page.
    #
    # Empty is a supported state, not a broken one: with no key the expert
    # answers in `sources_only` mode — it returns the passages it retrieved and
    # says no model is attached, instead of paraphrasing them into something
    # that reads like knowledge.
    anthropic_api_key: str = Field(default="")
    expert_model: str = Field(default="claude-sonnet-4-5")
    expert_max_tokens: int = Field(default=1600)
    expert_timeout: float = Field(default=90.0)

    @property
    def expert_grounded(self) -> bool:
        return bool(self.anthropic_api_key)

    finance_customer_entity: str = Field(default="StlixCustomerBalance")
    finance_supplier_entity: str = Field(default="StlixSupplierBalance")
    finance_statement_entity: str = Field(default="StlixCustomerStatement")

    # --- Nama SQL (read-only) — real balances from the restored Nama DB backup.
    # REST exposes no balances, so finance reads them straight from SQL. Use a
    # read-only login (db_datareader). Server/db mirror the local restore.
    nama_sql_server: str = Field(default="")
    nama_sql_database: str = Field(default="NAMA_TEST")
    nama_sql_user: str = Field(default="")
    nama_sql_password: str = Field(default="")
    nama_sql_driver: str = Field(default="ODBC Driver 17 for SQL Server")

    @property
    def nama_sql_configured(self) -> bool:
        return bool(self.nama_sql_server and self.nama_sql_user and self.nama_sql_password)

    # --- CRM connector (Vtiger) ---
    crm_backend: str = Field(default="vtiger")
    crm_mode: str = Field(default="read_only")
    vtiger_url: str = Field(default="", description="Vtiger base URL, e.g. https://crm.example.com")
    vtiger_username: str = Field(default="")
    vtiger_access_key: str = Field(default="")
    crm_timeout: float = Field(default=30.0)

    @property
    def crm_configured(self) -> bool:
        return bool(self.vtiger_url and self.vtiger_username and self.vtiger_access_key)

    # --- Inventory / Stocktake connector (count app) ---
    inventory_base_url: str = Field(default="", description="Stocktake app base, e.g. https://crm.stlixvalley.com/count")
    inventory_key: str = Field(default="", description="sync.php ?k= key")
    inventory_mode: str = Field(default="read_only")
    inventory_timeout: float = Field(default=30.0)

    @property
    def inventory_configured(self) -> bool:
        return bool(self.inventory_base_url and self.inventory_key)

    # --- CCTV (Hikvision, via the LAN agent) ---
    # The agent on the factory LAN authenticates its pushes with this key
    # (`X-CCTV-Agent-Key`). Empty = pushes need a gateway key instead.
    cctv_agent_key: str = Field(default="")
    cctv_data_dir: str = Field(default="", description="blank = data/cctv")
    # Agent silent longer than this -> the card turns stale (not "down": the
    # cameras may be fine, we just cannot see them).
    cctv_stale_seconds: float = Field(default=180.0)

    @property
    def cctv_configured(self) -> bool:
        return bool(self.cctv_agent_key)

    # --- ETA e-invoicing (بورتال الضرايب) + ض.ق.م planner ---
    # JSON list, one object per legal entity:
    # [{"key":"group","name":"المجموعة","rin":"...","client_id":"...","client_secret":"...",
    #   "k_manufacturing":7.5,"k_trading":1.5,"customs_issuer_ids":[]}, {...}]
    eta_entities_json: str = Field(default="")
    eta_env: str = Field(default="prod", pattern="^(prod|preprod)$")
    eta_db_path: str = Field(default="", description="blank = data/eta/eta.db")
    vat_db_path: str = Field(default="", description="blank = data/vat/vat.db")
    # total: k_total ‰ × all sales (the owner's wording); per_activity: k_m × manufacturing + k_t × trading
    vat_k_mode: str = Field(default="total", pattern="^(total|per_activity)$")

    # The portal browser agent on this host (agents/eta-browser) and the screen
    # it draws on. Both are 127.0.0.1 services; from inside Docker they are
    # reached through host.docker.internal.
    eta_agent_url: str = Field(default="http://host.docker.internal:8021")
    eta_vnc_url: str = Field(default="http://host.docker.internal:6081")
    # The browser agent's own key (X-ETA-Browser-Key): it may upload documents
    # scraped from the portal as the signed-in user, and nothing else.
    eta_browser_key: str = Field(default="")
    # Pre-shared key ETA sends as `Authorization: ApiKey <key>` when it pings our
    # callback base during system registration. Blank = the ping is refused.
    eta_erp_callback_key: str = Field(default="")
    # Cancel/reject on the portal. Off by default: both are irreversible at ETA.
    eta_allow_state_changes: bool = Field(default=False)
    # 0 = off. On the VPS this is what makes the routine run without anyone asking.
    vat_sync_interval_minutes: float = Field(default=0)

    @property
    def eta_configured(self) -> bool:
        return bool(self.eta_entities_json.strip())

    @property
    def nama_base(self) -> str:
        return self.nama_base_url.rstrip("/")

    @property
    def nama_configured(self) -> bool:
        return bool(self.nama_client_id and self.nama_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
