# modules/legal — المستشار القانوني

`counsel.html`, served at **`/tools/legal`**. Four modes over `/api/v1/legal/*`:
ask, draft, review, verify.

**Verify is the one to understand.** It checks the article numbers in any text
against the statutes on disk with no model in the path — so it works with
nothing configured, and it works on text this system did not write: the other
side's draft, an old contract, a clause someone was sent on WhatsApp. The guard
is not a property of our answers; it is a tool that can be pointed at anything.

Answers arrive **already redacted**. An article the gateway could not confirm
has been replaced in the body of the sentence before this page ever saw it — not
footnoted. A legal answer gets copied into an email, and whatever qualification
sits at the bottom does not travel with the sentence that gets quoted.

Sources are colour-coded by tier, because the distinction is the whole point: a
`statute` passage is authority, a `precedent` passage is only what we ourselves
signed once, and an `internal` bylaw binds us and nobody else.

Full design note — the guard, the tiers, the empty corpus as a designed state,
why no template cites an article — in
[`docs/legal-counsel.md`](../../docs/legal-counsel.md).
