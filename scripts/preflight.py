"""فحص ما قبل العرض — «هل ده جاهز يتعرض على ناس؟»

Run this before showing the platform to anyone. It answers one question in one
screen: what works, what is degraded, and what must be fixed before a person
who did not build it looks at it.

Two categories, and the split is the point:

- **مانع (blocking)** — the demo must not happen with this true. An advertised
  page that 500s, a connector left in `read_write`, a catalogue that disagrees
  with the running app. Exit code 1.
- **ملحوظة (warning)** — worth knowing and worth saying out loud while
  presenting, but not a reason to stop. No model attached, no statutes loaded.
  Exit code 0.

It runs entirely in-process against the app object — no server, no network, no
ERP call. So it is safe to run on a machine that is about to be presented from,
and it cannot itself be the thing that breaks the demo.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Quiet before the app is imported: this prints one screen a person reads on
# presentation day, and the access log for twelve page fetches buries it.
import logging  # noqa: E402

logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient  # noqa: E402

from app import __version__, catalog  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

OK, WARN, BAD = "✔", "▲", "✕"
_rows: list[tuple[str, str, str]] = []
_blocking = 0
_warnings = 0


def check(name: str, ok: bool, detail: str = "", blocking: bool = True) -> bool:
    global _blocking, _warnings
    if ok:
        mark = OK
    elif blocking:
        mark = BAD
        _blocking += 1
    else:
        mark = WARN
        _warnings += 1
    _rows.append((mark, name, detail))
    return ok


def note(name: str, detail: str) -> None:
    _rows.append(("·", name, detail))


def main() -> int:
    host = os.environ.get("SG_BIND_HOST", "")
    settings = get_settings()
    client = TestClient(app)

    print(f"\n  STLIX GATEWAY — فحص ما قبل العرض · v{__version__}\n")

    # --- 1. every advertised page must answer ------------------------------
    pages = [e for e in catalog.ENDPOINTS if e.kind == "page" and "{" not in e.path]
    broken = []
    for e in pages:
        try:
            if client.get(e.path).status_code != 200:
                broken.append(e.path)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{e.path} ({type(exc).__name__})")
    check(f"كل الصفحات بتردّ ({len(pages)} صفحة)", not broken,
          ", ".join(broken) if broken else "مافيش صفحة بتقع")

    # --- 2. the map must match the app -------------------------------------
    real = {p for p in app.openapi()["paths"]}
    listed = catalog.paths()
    missing = listed - real
    unlisted = real - listed
    check("الخريطة مطابقة للراوتس", not missing and not unlisted,
          f"في الكتالوج ومش موجودة: {sorted(missing)} · موجودة ومش في الكتالوج: {sorted(unlisted)}"
          if (missing or unlisted) else "الاتجاهين متطابقين")

    # --- 3. nothing may write --------------------------------------------
    writable = [c.key for c in catalog.CONNECTORS
                if c.mode_attr and getattr(settings, c.mode_attr, "") == "read_write"]
    check("كل الكنكتورات read-only", not writable,
          f"دول في وضع كتابة: {writable}" if writable else "مافيش كنكتور بيكتب")

    # --- 4. the key ---------------------------------------------------------
    public = host in ("0.0.0.0", "::")
    check("مفتاح الجيتواي متظبّط", bool(settings.api_keys),
          "GATEWAY_API_KEY فاضي — أي حد على الشبكة يقدر ينده الـ API مباشرة"
          if not settings.api_keys else "متظبّط",
          blocking=public)
    if public:
        note("العرض على الشبكة",
             "الصفحات بتدّي كوكي لأي حد يفتحها — ده مقصود علشان الزملاء "
             "مايكتبوش مفتاح. متعرّضهاش على الإنترنت، شبكة الشركة بس.")

    # --- 5. what the demo will actually show --------------------------------
    from app.integrations.expert import knowledge
    from app.integrations.legal import corpus as legal_corpus

    ex = knowledge.stats()
    check(f"فهرس Nama Expert ({ex['chunks']} مقطع · {len(ex['documents'])} وثيقة)",
          ex["chunks"] > 100, "الفهرس فاضي أو ناقص" if ex["chunks"] <= 100 else "")

    lg = legal_corpus.stats()
    check("نصوص القوانين محمّلة",
          lg["statute_articles"] > 0,
          f"صفر مادة محمّلة — المستشار هيقول «القانون مش عندي» في كل سؤال. "
          f"{lg['loaded_of_expected']}/{lg['expected']} قانون. حطّ الملفات في {lg['corpus_dir']}",
          blocking=False)

    check("موديل موصول (صياغة الإجابات)", settings.expert_grounded,
          "ANTHROPIC_API_KEY فاضي — الخبير والمستشار هيرجّعوا المقاطع من غير صياغة. "
          "شغّالين ومفيدين، بس العرض هيبقى أضعف",
          blocking=False)

    # --- 6. the money -------------------------------------------------------
    check("مصدر الأرقام المالية", settings.finance_default_source in ("sql", "live"),
          f"FINANCE_DEFAULT_SOURCE = {settings.finance_default_source}")
    if settings.finance_default_source == "live":
        note("اللقطة اللحظية",
             f"بتتحدّث كل {settings.live_finance_refresh_seconds}s. أول ~٨ دقايق بعد "
             "التشغيل الصفحات المالية هتقول «مافيش لقطة لسه» — شغّل السيرفر قبل "
             "العرض بربع ساعة.")
    check("حارس الانحراف شغّال", settings.finance_guard_enabled,
          "" if settings.finance_guard_enabled else "FINANCE_GUARD_ENABLED = false",
          blocking=False)

    # --- 7. credentials present --------------------------------------------
    for c in catalog.CONNECTORS:
        # `expert_grounded` is the Anthropic key, already reported above — and
        # reporting it again per connector said "الصفحات هتبان فاضية", which is
        # false: without it the expert and the counsel return their passages.
        # A preflight that misdescribes its own warnings is worse than silent.
        if not c.live or not c.configured_attr or c.configured_attr == "expert_grounded":
            continue
        ok = bool(getattr(settings, c.configured_attr, False))
        check(f"اعتماد: {c.name_ar}", ok,
              "" if ok else f"{c.configured_attr} مش متظبّط — الصفحات اللي بتقرا منه هتبان فاضية",
              blocking=False)

    # --- report -------------------------------------------------------------
    w = max(len(n) for _, n, _ in _rows) + 2
    for mark, name, detail in _rows:
        print(f"  {mark}  {name.ljust(w)}{detail}")

    live = [c.key for c in catalog.CONNECTORS if c.live]
    print(f"\n  {len(live)} كنكتور حيّ · {len(catalog.ENDPOINTS)} endpoint · {len(pages)} صفحة")

    if _blocking:
        print(f"\n  ✕ {_blocking} مانع — متعرضش قبل ما يتصلّحوا.\n")
        return 1
    if _warnings:
        print(f"\n  ✔ جاهز للعرض · {_warnings} ملحوظة — اقراها فوق وقولها بنفسك "
              "قبل ما حد يسأل.\n")
    else:
        print("\n  ✔ جاهز للعرض — مافيش مانع ولا ملحوظة.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
