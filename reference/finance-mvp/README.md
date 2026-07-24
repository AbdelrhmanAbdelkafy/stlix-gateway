# Finance OS — MVP Backend

A runnable MVP for the **Finance Module** (Accounts Payable invoice lifecycle) of the Enterprise AI Platform, built as a **FastAPI Modular Monolith** and governed by the project Constitution:

- **ERP is the System of Record.** This service stores workflow state and the audit trail, not the financial truth.
- **No direct writes to the ERP.** Posting happens **only** through the approved workflow, via the integration adapter. Write credentials live in the integration layer — never in the AI/service layer.
- **Every business action passes through an auditable workflow** and produces **structured logs** + an **append-only audit trail**.
- **RBAC + Segregation of Duties**: the creator of an invoice can never approve it.

## Architecture (maps to the Runbook)

```
app/
  core/         config, database, security (JWT), rbac, audit, logging   (Ch. 24-42)
  models/       users, vendors, invoices, audit_logs                     (Ch. 41-42)
  schemas/      pydantic request/response models                         (Ch. 43)
  modules/
    identity/     auth (login/refresh/me), user management               (Ch. 25-27)
    finance/      vendors + invoice workflow state machine               (Ch. 58-64)
    integration/  ERP adapter (read-only + workflow-gated post) + reads  (Ch. 44-45)
    governance/   read-only audit-trail endpoint                         (Ch. 28)
  main.py       app wiring, correlation-id middleware, health
  seed.py       demo roles-as-users + a vendor
tests/          auth, rbac, workflow, segregation-of-duties, audit
```

## Invoice workflow

```
DRAFT ──submit──▶ SUBMITTED ──approve──▶ APPROVED ──post──▶ POSTED(→ERP doc id)
                       └────reject─────▶ REJECTED
```
`approve` requires `invoice:approve` **and** approver ≠ creator (SoD). `post` calls the ERP adapter (idempotent) and stores the returned `erp_document_id`.

## Roles → permissions

| Role | Permissions |
|---|---|
| ADMIN | all |
| AP_CLERK | vendor:read, invoice:read, invoice:create, invoice:submit |
| AP_MANAGER | vendor:read/write, invoice:read, invoice:approve, invoice:post |
| AUDITOR | vendor:read, invoice:read, audit:read |

## Run locally (SQLite, no Docker)

```bash
pip install -r requirements.txt
python -m app.seed                       # creates tables + demo users/vendor
uvicorn app.main:app --reload            # http://localhost:8000/docs
```

## Run the full stack (Docker: API + MySQL + Redis)

```bash
docker compose up --build                # API on http://localhost:8000
```

## Demo users (seeded)

| Email | Password | Role |
|---|---|---|
| admin@finance.local | Admin#12345 | ADMIN |
| clerk@finance.local | Clerk#12345 | AP_CLERK |
| manager@finance.local | Manager#12345 | AP_MANAGER |
| auditor@finance.local | Auditor#12345 | AUDITOR |

## Quick end-to-end (curl)

```bash
# 1) login as clerk
TOKEN=$(curl -s localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"clerk@finance.local","password":"Clerk#12345"}' | jq -r .access_token)

# 2) create + submit an invoice
curl -s localhost:8000/api/v1/invoices -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"invoice_number":"INV-1001","vendor_id":1,"amount":2500.00,"currency":"USD"}'
curl -s -X POST localhost:8000/api/v1/invoices/1/submit -H "Authorization: Bearer $TOKEN"

# 3) login as manager, approve + post (goes to ERP via the workflow)
MGR=$(curl -s localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"manager@finance.local","password":"Manager#12345"}' | jq -r .access_token)
curl -s -X POST localhost:8000/api/v1/invoices/1/approve -H "Authorization: Bearer $MGR"
curl -s -X POST localhost:8000/api/v1/invoices/1/post -H "Authorization: Bearer $MGR"
```

## Tests

```bash
pip install -r requirements.txt
pytest            # runs against in-memory SQLite
```

## Scope & next steps

This MVP is backend-only and uses a mock ERP adapter so it runs end-to-end without a real ERP. Next increments: real ERP adapter implementation, Alembic migrations, Next.js UI for the AP queue, AR/Treasury workflows, and the AI agents (read/suggest only) from Chapters 61-68.
