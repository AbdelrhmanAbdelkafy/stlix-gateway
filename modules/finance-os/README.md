# Module 1 — Finance OS

The first module of the AI-based enterprise platform. A role-based financial
cockpit that sits **on top of the gateway**: dashboard, an AI "financial team"
(chat + recommendations with human-in-the-loop approvals), AP approval workflow,
Customers 360, Treasury, GL, reports, and an append-only audit log.

`demo.html` is the owner's full front-end demo (hardcoded demo data). **`demo.gateway.html`
is the wired version, served at `GET /tools/finance-os`** (gateway key injected server-side).
Live now (read overlay, badged "نما · حيّ"): **Treasury ← live Nama bank accounts**,
**Customers 360 ← live Nama customers** (`GET /api/v1/nama/lists/Customer` — a finance
cockpit reads customers from the ERP, not the CRM). Banner flips to "متصل بالجيتواي ✅". Two roles
added: **PRESIDENT** (default; sees all + decides + chat) and **OPERATOR** (feeds data:
create/submit, no approve). Balances (SQL) + customer ledger + AP/GL write still pending.

## Why it fits our architecture exactly
The demo's own principle (sidebar footer):
> **ERP = System of Record · الذكاء الاصطناعي لا يكتب في ERP مباشرة · كل إجراء عبر Workflow مُدقّق.**

That is precisely the gateway design: **read-only connectors** by default, writes
only via a deliberate, audited workflow (Layer 5) with HITL. Finance OS is the UI
proof of the whole platform vision.

## Panel → connector mapping
| Finance OS panel | Data source | Gateway status |
|---|---|---|
| Treasury / Cash | Banks connector | 🟢 live (accounts; numeric balances pending) |
| Customers 360 (CRM fields) | Vtiger CRM connector | 🟢 live |
| Customers 360 (ledger / AR) | Nama customer ledger | 🟡 need Customer + ledger read on nama connector |
| GL (journal entries) | Nama `JournalEntry` | 🟡 need entity read |
| AP invoices | Nama supplier invoices | 🟡 need entity read (+ write workflow to approve/post) |
| Aging / DSO | Nama AR (backlog T14) | ⚪ report to build |
| Audit log | Gateway structured logs (Layer 6) | 🟢 live |
| RBAC + separation of duties | Gateway security (Layer 6) | 🟡 API keys live; role/permission model to add |
| Smart Financial Team (chat + recs) | AI Orchestrator (Layer 4) | ⚪ planned |

## Incremental wiring plan
1. **Serve it**: gateway serves `demo.html` at `/modules/finance-os` (static).
2. **Wire the live panels first** (connectors already exist):
   - Treasury ← `GET /api/v1/banks`
   - Customers 360 CRM fields ← `GET /api/v1/crm/...`
   - Audit ← gateway logs/metrics
3. **Add Nama reads** the module needs: Customer+ledger, SupplierInvoice, JournalEntry.
4. **RBAC**: roles → permission sets in the gateway security layer.
5. **AI financial team** → Layer 4 orchestrator over the connectors.
6. **Write actions** (approve/post invoice) → Layer 5 audited workflow, HITL;
   flips the relevant connector to `read_write` deliberately, logged end-to-end.

Start = step 2 (Treasury + Customers CRM), since those connectors are live today.
