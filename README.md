# Stlix Gateway

**نقطة تكامل واحدة لكل الأنظمة** — one FastAPI service that fronts every company
system so clients (mobile apps, website, internal tools) talk to *one* API with
*one* auth, and never hold each system's secrets.

## Systems landscape

| Key | System | العربية | Status |
|-----|--------|---------|--------|
| `nama` | Nama ERP | نما | ✅ live |
| `attendance` | Attendance & Fingerprint | البصمة والحضور | ✅ live |
| `crm` | CRM | سي آر إم | 🕓 planned |
| `callcenter` | Call Center | الكول سنتر | 🕓 planned |
| `email` | Email | الإيميل | 🕓 planned |
| `website` | Website | الويب سايت | 🕓 planned |
| `ai` | AI Services | الذكاء الاصطناعي | 🕓 planned |
| `archive` | Archive | الأرشيف | 🕓 planned |
| `inventory` | Inventory / Stocktaking | الجرد | 🕓 planned |
| `academy` | Academy | الأكاديمية | 🕓 planned |
| `regulations` | Regulations | اللوائح | 🕓 planned |

Live map at runtime: **`GET /systems`**. Planned systems already answer at
`/api/v1/<key>` with `501 Not Implemented` so the whole surface is visible.

## Run locally

```bash
cp .env.example .env      # fill NAMA_CLIENT_ID / NAMA_CLIENT_SECRET
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs**.

## Run with Docker

```bash
cp .env.example .env      # fill in creds
docker compose up --build
```

## Key endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + Nama auth/reachability |
| GET | `/systems` | Full integration landscape |
| GET | `/api/v1/nama/employees?max_records=25` | List employees |
| GET | `/api/v1/nama/employees/{code}` | One employee |
| GET | `/api/v1/nama/{entity}/{code}` | Generic Nama read |
| POST | `/api/v1/attendance/punch` | Push attendance to Nama TimeAttendance |

### Push attendance (ISO in → Nama format out)

```bash
curl -X POST http://localhost:8000/api/v1/attendance/punch \
  -H "Content-Type: application/json" \
  -d '{"punches":[{"employee":"E000001","day":"2026-07-24","check_in":"08:05","check_out":"17:00"}]}'
```

The gateway converts `2026-07-24` → `24-07-2026` before hitting Nama (sending
ISO to Nama is silently mis-parsed — the gateway exists partly to prevent that).

## Auth

Set `GATEWAY_API_KEY` in `.env` to require clients to send `X-API-Key`. Leave it
blank in dev to disable the check. Nama's `clientId`/`clientSecret` stay
server-side and are never exposed to clients.

## Adding a new system

1. `app/integrations/<key>/` → `client.py`, `router.py`, `schemas.py`.
2. Include its router in `app/main.py` and add `<key>` to `live_keys`.
3. Flip its `status` to `Status.LIVE` in `app/registry.py`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Layout

```
app/
  main.py            # app factory, mounts routers under /api/v1
  config.py          # settings (.env)
  registry.py        # the map of all systems (source of truth)
  core/              # security, error envelope
  routers/meta.py    # /health, /systems
  integrations/
    nama/            # ERP client + router + schemas  (LIVE)
    attendance/      # punch push -> Nama TimeAttendance (LIVE)
    ...              # crm, callcenter, email, ... (placeholders -> 501)
```
