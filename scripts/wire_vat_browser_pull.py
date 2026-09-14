"""Point the VAT planner's pull button at the door that actually opens.

The button called `POST /api/v1/vat/{entity}/{month}/sync`, which asks ETA for
an API token. This tenant has no registered ERP — `ETA_ENTITIES_JSON` carries
the portal *login* email and password, not a client id and secret — so that
call can only ever answer `invalid_client`, and the screen showed the raw
`token 400` to whoever pressed it.

Meanwhile the door that works was already built: a signed-in Chromium on the
server, and `POST /api/v1/eta/browser/do/ingest {"entity": …, "grid": true}`,
which reads the portal's own document grid and files it in the same cache the
planner reads. Measured on the live tenant: 34 documents, two months, nothing
skipped.

So the button now pulls through the browser, and falls back to the API only for
an entity that really does have credentials. Two things it deliberately does
NOT do:

* pretend the browser pull fetched the month the page is showing — it takes
  what is on the portal's screen, so the result says which months arrived;
* hide a failure behind a generic message — if the browser is not signed in or
  not on the documents page, it says so and names the page to open.

    python scripts/wire_vat_browser_pull.py          # apply
    python scripts/wire_vat_browser_pull.py --check  # report only
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "modules" / "vat" / "planner.html"

MARKER = "eta/browser/do/ingest"
#: The line to replace, matched by how it starts so trailing edits do not break it.
OLD_PREFIX = '$("#sync").onclick'

NEW = r'''$("#sync").onclick = async () => {
  // The portal is reached through the signed-in browser on the server, not
  // through the API: this tenant has no registered ERP, so a token request can
  // only answer invalid_client. The API is tried only for an entity that has
  // real credentials, and only after the browser door is closed.
  const btn = $("#sync"); btn.disabled = true;
  $("#syncInfo").textContent = "بيسحب من شاشة البورتال…";
  let r = {};
  try {
    r = await (await api("/api/v1/eta/browser/do/ingest", {method: "POST",
      body: JSON.stringify({entity: ent, grid: true})})).json();
  } catch (e) { r = {ok: false, error: "مش قادر أوصل للسيرفر"}; }
  const configured = plan && plan.entity && plan.entity.configured;
  if (!r.ok && configured) {
    $("#syncInfo").textContent = "الشاشة مش متاحة — بجرّب الـ API…";
    try { r = await (await api(`/api/v1/vat/${ent}/${month()}/sync`, {method: "POST"})).json(); }
    catch (e) { r = {ok: false, error: "مش قادر أوصل للسيرفر"}; }
  }
  btn.disabled = false;
  if (!r.ok) {
    $("#syncInfo").textContent = "آخر سحب فشل";
    alert((r.error || "السحب مانفعش") + "\n\nافتح /tools/portal، سجّل دخولك على الشاشة، " +
          "وافتح صفحة المستندات (invoicing.eta.gov.eg/documents)، وبعدين جرّب تاني.");
  } else if (r.stored != null) {
    $("#syncInfo").textContent = `اتسحب ${r.stored} مستند من الشاشة` +
      ((r.months || []).length ? ` — ${(r.months || []).join("، ")}` : "") +
      (r.skipped_count ? ` · ${r.skipped_count} اتخطّوا` : "");
  }
  load();
};'''


def main(check_only: bool = False) -> int:
    if not PAGE.exists():
        print("!", f"{PAGE.relative_to(ROOT)}: مش موجود")
        return 1
    text = PAGE.read_text(encoding="utf-8")
    if MARKER in text:
        print("=", "planner.html: متوصّل بالفعل")
        return 0
    lines = text.splitlines(keepends=True)
    hits = [i for i, ln in enumerate(lines) if ln.lstrip().startswith(OLD_PREFIX)]
    if len(hits) != 1:
        print("!", f"planner.html: لقيت {len(hits)} سطر يبدأ بـ {OLD_PREFIX} — المتوقع واحد. "
                   "عدّلها بإيدك.")
        return 1
    if check_only:
        print("+", "planner.html: محتاج توصيل")
        return 1
    lines[hits[0]] = NEW + "\n"
    PAGE.write_text("".join(lines), encoding="utf-8")
    print("+", "planner.html: زرار السحب بقى بيمرّ على شاشة البورتال")
    print("""
وحاجة في .env لازم تتعمل معاها: client_id و client_secret بتوع ETA مش مفاتيح
API — دول إيميل وباسورد الدخول للبورتال. سيبهم فاضيين في ETA_ENTITIES_JSON:

  "client_id": "", "client_secret": ""

ساعتها الكيان يبقى «مش متسجّل» بصراحة، الووتشر يبطّل يضرب id.eta.gov.eg
بمفاتيح غلط كل ساعة، وباسورد البورتال يخرج من ملف الإعدادات.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
