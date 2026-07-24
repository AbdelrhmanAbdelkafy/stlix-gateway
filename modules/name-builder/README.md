# Module — Nama NameBuilder (item creation)

Smart item-creation portal for Nama. A purchasing user types a free-text item in
Arabic ("كوع ٢ بوصة ستيل ٣١٦ لحام") → AI (or a local market-dictionary parser)
maps it to structured attributes → builds a descriptive identity code + Arabic
name → checks Nama for duplicates → creates the `InvItem` in Nama. 45 item types,
live Nama attribute lists, zero-duplicate guarantee.

`demo.redacted.html` is the owner's working tool **with secrets removed** (see below).

## 🔴 Security finding (why this belongs behind the gateway)
The original embeds **live API keys in client-side JavaScript**:
- Anthropic API key (`sk-ant-…`) — a billing credential; anyone loading the page
  can extract and spend it.
- Nama `apiKey` + `X-API-SECRET`.

This is the exact anti-pattern the gateway removes. **Action: rotate all three keys
now.** In the gateway version, keys live server-side; the browser holds none.

## Valuable Nama protocol this reveals (item write path)
- Alt auth: headers `apiKey` + `X-API-SECRET` (different from our clientId/clientSecret).
- List with filters: `POST {Entity}/list` body `{pageSize, orderBy, textCriteria:"field,Op,val,AND;"}`.
- Create/update: `POST InvItem/save?addRecord=true&updateRecord=true`, body `{"InvItem":[{...}]}`.
- **Identity code = `description1`** (the built descriptive code); dup check =
  `InvItem/list textCriteria "description1,Equal,<code>,AND;"`.
- Next code: `Inv######` sequence, paginated via orderBy/textCriteria.
- Attribute lists are live entities: `ItemClass3` (standard), `4` (schedule),
  `5/6` (size), `7` (thickness), `9` (finish), `10` (connection); mapped to
  `itemClass1..10` on the item.

## Gateway integration plan
1. **Secrets server-side**: gateway holds Nama creds; an AI-parse endpoint proxies
   to Anthropic with the key server-side. Browser calls the gateway only.
2. **AI parsing → Layer 4** (AI Orchestrator): free-text → structured item is a
   reusable orchestrator skill.
3. **Item creation = first WRITE workflow** (Layer 5): flips the Nama connector to
   `read_write` deliberately, with dup-check + audit log (Layer 6) + HITL.
4. Reuse the 45-type KB + code grammar as the connector's item-builder module.
