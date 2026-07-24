# Stlix Gateway — Handoff (start here in a new chat)

Single integration platform ("نقطة تكامل واحدة") fronting all company systems.
Read this + the linked files to continue with zero context loss.

## Where / how
- Path: `D:\Nama Code project\stlix-gateway` · **local git only** (no remote, by choice).
- Python 3.14 venv `.venv`. Deps need current pins (pydantic 2.13+; 3.14 has no old wheels).
- Run: `.claude/launch.json` name **stlix-gateway** (uvicorn :8000). Browser preview verified.
  Restart after code/registry changes (no --reload). Reply to owner in **Egyptian Arabic**.
- Creds: gitignored `.env`. Backup of ALL gate keys: `secrets/gates-keys.backup.md` (gitignored).

## Architecture — 6 layers
1 Gateway ✅ · 2 Connectors · 3 Unified Workspace ✅ · 4 AI Orchestrator ⚪ ·
5 n8n workflows ⚪ · 6 Logs/Monitoring/Security ✅.

## Built & verified live (5 connectors, all read-only)
| Connector | Source | Notes |
|---|---|---|
| nama | Nama REST (cloud) | employees + generic entity read |
| attendance | Nama TimeAttendance | punch push guarded (read-only → 403) |
| crm | Vtiger `crm.stlixvalley.com` | contacts/leads/accounts — live data |
| banks | Nama Bank/BankAccount | **accounts** only; numeric balances NOT on Nama REST |
| inventory (الجرد) | count app `crm.stlixvalley.com/count/sync.php?k=KELMETAK` | {rev,items,manual} |

Also live: `/health`, `/systems`, `/connectors`, `/metrics` (HTML+Prometheus+JSON),
`/api/v1/workspace` (concurrent aggregation), structured JSON logs, rate-limit,
security headers, multi API-key. 35 tests passing.

## Pattern (how to add anything)
Connector = `app/integrations/<key>/{client,connector,router}.py` + register in
`main.py` live_keys + `registry.py` LIVE + a `workspace/providers.py` Provider + a
test. Scaffolds in `templates/` (see `templates/README.md`). Every read endpoint
does HTML+JSON via `respond()`. Read-only by default; `guard_write()` → 403.

## The insight (VISION.md)
~180 backlog requirements = ~24 domains collapsing into **6 reusable engines**:
Planned-vs-Actual · Renewals/Deadlines · Reconciliation · Live-vs-Pending ·
Watchlist · Market-Feeds. Most items are **reports over Nama**, not new systems.

## Modules (front-ends, "develop together" — demos captured, not wired)
- `modules/finance-os/` — role-based financial cockpit + AI team + HITL + audit.
  Principle "ERP=system of record, AI never writes directly, audited workflow" = our design.
- `modules/name-builder/` — free-text → AI → Nama InvItem create. First WRITE case
  (Layer 5) + first AI (Layer 4). Reveals Nama write protocol (see its README).

## Verified facts / gotchas
- Nama REST exposes **NO account balances** (master entities only; balances via SQL/report).
- Nama dates = `DD-MM-YYYY` (YYYY-MM-DD silently mis-parsed). Times `HH:MM`.
- Nama save: `POST {Entity}/save` body `{"<Entity>":[{...}]}`; item write uses
  `apiKey`+`X-API-SECRET` auth, identity=`description1`, ItemClass3-10 attributes.
- Key files: `README.md` `VISION.md` `BACKLOG.md` `RESOURCES.md` `templates/` `modules/`.

## Open / next
1. 🔴 **ROTATE exposed keys** (Anthropic first, then Nama/Vtiger/inventory) — see
   `secrets/gates-keys.backup.md` checklist.
2. Bank **balances**: decide source (SQL vs Nama report) — REST has none.
3. Build first **engine** (suggest Renewals/Alerts — covers 7-8 items) or a report.
4. Wire **Finance OS** live panels (Treasury ← banks, Customers ← CRM) when owner says.
5. The 3 published Google Sheets (RESOURCES.md) are candidate data sources — inspect.

Memory: `stlix-gateway-project`, `nama-rest-protocol`, `attendance-app-project`
(auto-loaded via MEMORY.md in every session).
