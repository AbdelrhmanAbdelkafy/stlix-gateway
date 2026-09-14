"""Wire the الاستيراد والشحن module into the gateway. Run once; safe to re-run.

The module itself is self-contained (`app/integrations/imports/`, `modules/import/
shipments.html`, `tests/test_imports.py`). What it still needs is four small edits
in files that already exist — a settings field, a router mount, a page route, and
a hub resource. They are applied here rather than by hand so the wiring is
reviewable as a diff and identical on every machine.

    python scripts/wire_imports.py          # apply
    python scripts/wire_imports.py --check  # report only, exit 1 if not wired

Each edit is anchored on text that must be present; if an anchor is gone the
script says which file changed shape instead of writing something wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EDITS: list[tuple[str, str, str, str]] = [
    # (file, anchor, insertion, marker that means "already wired")
    (
        "app/config.py",
        '    vat_db_path: str = Field(default="", description="blank = data/vat/vat.db")\n',
        '    imports_db_path: str = Field(default="", description="blank = data/imports/imports.db")\n',
        "imports_db_path",
    ),
    (
        "app/main.py",
        "from .integrations.inventory.router import router as inventory_router\n",
        "from .integrations.imports.router import router as imports_router\n",
        "imports.router import router as imports_router",
    ),
    (
        "app/main.py",
        "    app.include_router(vat_router, prefix=API_PREFIX)\n",
        "    app.include_router(imports_router, prefix=API_PREFIX)\n",
        "include_router(imports_router",
    ),
    (
        "app/routers/tools.py",
        '@router.get("/certificate", response_class=HTMLResponse)\n',
        '''@router.get("/imports", response_class=HTMLResponse)
async def imports_shipments(settings: Settings = Depends(get_settings)) -> HTMLResponse:
    """الاستيراد والشحن — SOP-IMP-001 و SOP-IMP-002 كملف شحنة حيّ.

    The two SOPs are approved documents; this page does not retype them. It
    renders `/api/v1/imports/sop` — the same data the gates run on — so the
    screen and the procedure cannot drift apart. Everything else on it is
    derived: which step the shipment is on, whether the ACID survives the walk
    across the documents, how much free time is left, what the landed cost per
    ton came to. Nothing is estimated: with no demurrage tariff entered the page
    shows the days and says the tariff is missing, rather than a figure somebody
    would put in an email to a shipping line.

    The shipment's dates, BL number, ports and line come from Nama's sea-shipping
    module (LCShipment) through /api/v1/imports/{ref}/sync — نما هي سجل الشحنة،
    والهَب بيضيف عليها طبقة الإجراء.
    """
    return _serve("import/shipments.html", settings)


''',
        'def imports_shipments(',
    ),
    (
        "app/auth/resources.py",
        '    Resource("count-app",',
        '''    Resource("imports", "الاستيراد والشحن", G_DAILY, "🚢",
             "ملف الشحنة: خطوات SOP-IMP-001/002، مطابقة الـ ACID، عدّاد الأرضيات، والتكلفة للطن — مربوط بالشحن البحري في نما",
             "/tools/imports", paths=("/tools/imports", "/api/v1/imports"),
             host="hub.stlixvalley.com", audiences=("proc", "mgmt", "it"),
             kw="استيراد شحنة بوليصة acid نافذة اضافة اضافات ارضيات demurrage free time landed cost "
                "تخليص جمارك bl shipment import customs clearance نولون حاوية",
             live_key="nama", order=7),
''',
        'Resource("imports"',
    ),
]


def main(check_only: bool = False) -> int:
    todo, done, missing = [], [], []
    for rel, anchor, insert, marker in EDITS:
        path = ROOT / rel
        if not path.exists():
            missing.append(f"{rel}: مش موجود")
            continue
        text = path.read_text(encoding="utf-8")
        if marker in text:
            done.append(f"{rel}: متوصّل بالفعل ({marker})")
            continue
        if anchor not in text:
            missing.append(f"{rel}: مالقيتش نقطة الإدراج — الملف اتغيّر، وصّلها بإيدك")
            continue
        todo.append((path, anchor, insert, rel))

    for line in done:
        print("=", line)
    for line in missing:
        print("!", line)
    if check_only:
        for _p, _a, _i, rel in todo:
            print("+", f"{rel}: محتاج توصيل")
        return 1 if (todo or missing) else 0

    for path, anchor, insert, rel in todo:
        # Re-read here, not at scan time: two of these edits land in app/main.py,
        # and applying both to one stale snapshot made the second write drop the
        # first — silently, with the script reporting success for both.
        text = path.read_text(encoding="utf-8")
        if anchor not in text:
            missing.append(f"{rel}: نقطة الإدراج اختفت أثناء التطبيق")
            continue
        # tools.py / resources.py: insert BEFORE the anchor; the rest: after it
        before = rel.endswith(("tools.py", "resources.py"))
        path.write_text(text.replace(anchor, (insert + anchor) if before else (anchor + insert), 1),
                        encoding="utf-8")
        print("+", f"{rel}: اتوصّل")

    if missing:
        print("\nفيه ملفات محتاجة توصيل يدوي — شوف السطور اللي فوق.")
        return 1
    print("\nتمام. شغّل: pytest tests/test_imports.py -q")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
