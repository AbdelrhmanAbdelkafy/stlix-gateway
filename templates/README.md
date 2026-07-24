# Templates — build any backlog item fast

Reusable scaffolds so the ~180 backlog items follow one pattern. Replace
`{{...}}` placeholders (`{{key}}` slug, `{{Key}}` PascalCase, `{{TITLE}}`, `{{COLUMNS}}`).

## Add a NEW connector (new data source)
1. `app/integrations/{{key}}/` ← copy `connector/{client,connector,router,test}.py.tmpl`.
2. `config.py`: add `{{key}}_mode="read_only"`, its creds, and a `{{key}}_configured` property.
3. `main.py`: import the router, mount it under `API_PREFIX`, add `"{{key}}"` to `live_keys`.
4. `registry.py`: set that system's `Status.LIVE`.
5. `providers.py`: paste `workspace_provider.py.tmpl`, add to `PROVIDERS`.
6. `.env` + `.env.example`: add the creds (real ones only in gitignored `.env`).
7. `pytest -q`, then restart the preview and verify live.

## Add a REPORT (over an existing connector — most backlog items)
Most items are reports over Nama, **not** new connectors. Add an endpoint to the
existing connector's `router.py` that queries + shapes data, returning `respond(...)`.
Pick the matching **engine** so logic is reused:
- Planned-vs-Actual · Renewals/Deadlines · Reconciliation · Live-vs-Pending ·
  Watchlist · Market-Feeds (see `../VISION.md`).

## Add a WORKSPACE section
Paste `workspace_provider.py.tmpl` into `providers.py`, add to `PROVIDERS`. Done —
the unified dashboard and `/api/v1/workspace` pick it up automatically.

## Add a MODULE (front-end, e.g. Finance OS)
`modules/{{name}}/` with a README mapping each panel → connector. Wire live panels
first (connectors that already exist), keep secrets server-side.

## Add a WRITE / AI step (later)
- Write = flip the connector to `read_write` **deliberately**, behind an audited
  Layer-5 workflow with HITL (see NameBuilder).
- AI task = Layer-4 orchestrator skill over the read connectors.

Golden rules: read-only by default · secrets server-side (never in browser) ·
HTML+JSON via `respond()` · one test file per connector · verify live before done.
