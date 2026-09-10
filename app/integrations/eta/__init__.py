"""Egyptian Tax Authority e-invoicing (بورتال الضرايب) — read-only.

One taxpayer system (ERP registration) per legal entity. The gateway pulls
the month's documents in both directions (Sent = our sales, Received = our
purchases) with their portal status, caches them locally, and never submits,
cancels or rejects anything: the portal stays the source of truth and the
accountant's tool stays the only writer.

Environments: prod (`id.eta.gov.eg` / `api.invoicing.eta.gov.eg`) and
preprod (`id.preprod.eta.gov.eg` / `api.preprod.invoicing.eta.gov.eg`).
Credentials: client_id + client_secret from the taxpayer profile → ERP
registration, per entity, in `.env` only (`ETA_ENTITIES_JSON`).
"""
