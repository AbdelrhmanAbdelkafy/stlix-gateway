# Stlix Gateway

**نقطة تكامل واحدة لكل الأنظمة** — one FastAPI service that fronts every company
system so clients (mobile apps, website, internal tools) talk to *one* API with
*one* auth, and never hold each system's secrets.

## The map

Nothing about the landscape is written down here, because a copied table goes
stale silently — this one still called `crm` and `inventory` "planned" long
after both went live. The running service is the map:

| Endpoint | Answers |
|---|---|
| `GET /systems` · `GET /systems/{key}` | every company system, and the requirements waiting on it |
| `GET /connectors` · `GET /connectors/{key}` | every connector, its mode, its routes, and what it unblocks |
| `GET /api/v1/map` | the whole graph: systems × connectors × endpoints × ideas × engines |
| `GET /tools/platform` | the hub — the human entry point |
| `GET /tools/ideas` | all 181 owner requirements, each wired to its data |

Planned systems answer at `/api/v1/<key>` with `501` **and name what building
them would unlock**, so the whole surface is visible and nothing is a dead end.

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

Browsers get the same key back as an `sg_key` cookie when the gateway serves a
`/tools/*` page, because a plain `<a href="/api/v1/...">` cannot send a header —
without it every endpoint link on the hub and the ideas board would 401. The
cookie is HttpOnly, SameSite=lax, and **accepted for GET/HEAD only**, so an
ambient credential can never write.

## Adding a new system

1. `app/integrations/<key>/` → `client.py`, `router.py`, `schemas.py`.
2. Include its router in `app/main.py`.
3. Flip its `status` to `Status.LIVE` in `app/registry.py`.
4. Add its connector and its routes to `app/catalog.py` — `tests/test_catalog.py`
   fails if the app and the map disagree in either direction.
5. Optionally add a `workspace/providers.py` Provider so it joins the dashboard.

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
