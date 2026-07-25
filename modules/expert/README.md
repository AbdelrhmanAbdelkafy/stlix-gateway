# modules/expert — Nama Expert chat

`chat.html`, served at **`/tools/expert`**.

RTL Arabic chat over `/api/v1/expert/*`. Text, a pasted or dragged screenshot,
or voice via the browser's own Web Speech API (`ar-EG`) — no vendor and no key
for the speech half.

**The page states no fact of its own.** Every answer, source, and count on it is
what the API returned; there is no fallback copy that would keep reading as true
after the server stopped agreeing with it. The `[S#]` markers in an answer are
links down to the passage they name, so a citation can be followed rather than
merely displayed.

The only credential it holds is the gateway key every `/tools/*` page is handed.
The Anthropic credential lives in the server's settings and the question is
composed server-side; `tests/test_expert.py` asserts the page contains no
outbound `fetch` to any host but this gateway.

Full design note — sources, Arabic retrieval, the two modes, what is still
missing — in [`docs/nama-expert.md`](../../docs/nama-expert.md).
