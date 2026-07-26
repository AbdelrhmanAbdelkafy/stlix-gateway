"""ابنِ ملف الديمو — HTML واحد يشتغل من غير سيرفر.

    .venv\Scripts\python.exe scripts\build_demo.py

بيطلّع `dist/stlix-demo.html`: لقطة من الخريطة والمتطلبات، **و**الحارس القانوني
والصيغ والبحث الصوتي شغّالين فعلًا جوّه الملف — لأن الـregex وجدول تحديد القانون
والصيغ بتتصدّر من الكود نفسه وقت البناء، مش بتتكتب تاني بالإيد. فالملف مايقدرش
يختلف بالساكت عن النظام اللي بيعرضه.

**واللي مقصود إنه مش جوّاه: أرقام الفلوس.** أول قاعدة في المنصّة إن مافيش رقم فلوس
يتكتب في صفحة، وملف ديمو شايل أرصدة كان هيكسر القاعدة وهو بيشرحها — وكان هيبقى رقم
بتاريخ يوم البناء بيتقري صح لحد ما حد يبني عليه قرار.

اعمله من أول وجديد بعد أي تغيير في الخريطة أو الصيغ، وإلا اللقطة بتقدم.
"""
from __future__ import annotations

import datetime
import io
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient  # noqa: E402

from app import __version__  # noqa: E402
from app.integrations.expert import knowledge, retrieve as R  # noqa: E402
from app.integrations.legal import citations as C, corpus as LC, templates as T  # noqa: E402
from app.main import app  # noqa: E402

_client = TestClient(app)


def _get(path: str) -> dict:
    r = _client.get(path)
    r.raise_for_status()
    return r.json()


def collect() -> dict:
    m = _get("/api/v1/map?format=json")
    lg = _get("/api/v1/legal?format=json")
    cov = _get("/api/v1/legal/coverage?format=json")
    ex = knowledge.stats()
    return {
        "snapshot": {"version": __version__, "service": "Stlix Gateway"},
        "coverage": m["coverage"],
        "systems": m["systems"],
        "connectors": [{k: c[k] for k in
                        ("key", "name_ar", "name_en", "system", "upstream", "live",
                         "note", "endpoints")} for c in m["connectors"]],
        "endpoints": m["endpoints"],
        "engines": m.get("engines", []),
        "ideas": [{k: i.get(k) for k in
                   ("id", "title", "domain", "status", "readiness", "needs",
                    "systems", "engine", "source")} for i in m["ideas"]],
        "expert": {"chunks": ex["chunks"], "documents": ex["documents"],
                   "by_kind": ex["by_kind"], "characters": ex["characters"]},
        "legal": {"expected": cov["rows"], "guard": lg["guard"], "corpus": lg["corpus"]},
        "templates": [
            {"key": t.key, "title": t.title, "summary": t.summary,
             "governed_by": list(t.governed_by),
             "fields": [{"key": f.key, "label": f.label, "example": f.example,
                         "required": f.required} for f in t.fields],
             "clauses": [{"heading": c.heading, "body": c.body, "basis": c.basis,
                          "optional": c.optional} for c in t.clauses],
             "check": list(t.check)} for t in T.TEMPLATES],
        "aliases": [[a, s] for a, s in C._ALIASES],
        # Exported, never retyped — this is what keeps the offline copy honest.
        "rx": {"cite": C._CITE.pattern, "marks": R._MARKS.pattern,
               "article_head": LC._ARTICLE.pattern},
        "fold": dict(zip("\u0623\u0625\u0622\u0671\u0649\u0629\u0624\u0626",
                         ["\u0627", "\u0627", "\u0627", "\u0627",
                          "\u064A", "\u0647", "\u0648", "\u064A"])),
    }


D = collect()
VOICE = (ROOT / "modules" / "platform" / "voice.js").read_text(encoding="utf-8")
STAMP = datetime.date.today().isoformat()

DEMO_LAW = """---
slug: madani
title: [عرض] القانون المدني — نصّ تجريبي
tier: statute
---
مادة 1 - نصّ تجريبي للمادة الأولى، موجود هنا علشان تشوف الحارس وهو شغّال.

المادة (147) العقد شريعة المتعاقدين، فلا يجوز نقضه ولا تعديله إلا باتفاق الطرفين
أو للأسباب التي يقررها القانون.

المادة ١٤٨ يجب تنفيذ العقد طبقًا لما اشتمل عليه وبطريقة تتفق مع ما يوجبه حسن النية.
"""

HTML = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STLIX Gateway — ديمو (ملف واحد)</title>
<!--
  A single file, no server, no network.

  What is REAL and interactive here: the platform map (systems, connectors,
  endpoints), all 214 requirements with their readiness, the legal citation
  guard, the six contract templates, the 24-law coverage table, and voice
  search. The map data was exported from the running platform; the guard and
  the templates are the same logic, generated out of the Python at build time
  rather than retyped, so this file cannot quietly disagree with the system.

  What is deliberately NOT here: money. This platform's first rule is that no
  figure is ever written into a page, and a demo file that carried AR and AP
  totals would break that rule to demonstrate it. The numbers live at
  /tools/finance-reports, behind the reconciliation and the drift guard.
-->
<style>
:root{color-scheme:light dark;--bg:#0e131a;--card:#151c26;--card2:#1b2431;--ln:#232e3d;--tx:#e9edf3;--sub:#7e8ba0;--ac:#2bc4c4;--acd:#0a6a6a;--gold:#c9a227;--ok:#2fbd6b;--warn:#e0a53a;--bad:#e0483a;--plan:#8497b0}
@media(prefers-color-scheme:light){:root{--bg:#f5f7f8;--card:#fff;--card2:#eef1f4;--ln:#e3e7ec;--tx:#131922;--sub:#6a7688;--ac:#0c8a8a;--acd:#0a6a6a;--gold:#8a6d10;--ok:#15914b;--warn:#c07a0a;--bad:#c0392b;--plan:#5b6b82}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font-family:"Segoe UI",system-ui,Tahoma,sans-serif;line-height:1.7;font-size:15px}
a{color:var(--ac)}
.hero{color:#eaf2f2;padding:34px 22px 30px;background:#0b121c radial-gradient(900px 460px at 82% 45%,rgba(43,196,196,.17),transparent 62%)}
.wrap{max-width:1000px;margin:0 auto;padding:0 22px}
.hero h1{font-size:31px;margin:0 0 5px;font-weight:800;letter-spacing:-.4px}
.hero .sub{color:#9fb4b4;font-size:15.5px;max-width:660px}
.snap{margin-top:16px;background:rgba(224,165,58,.13);border:1px solid rgba(224,165,58,.4);border-radius:12px;padding:11px 15px;font-size:12.5px;color:#f0e2c4;max-width:760px;line-height:1.85}
.snap b{color:#ffd479}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:9px;margin-top:18px}
.kpi{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:11px 13px}
.kpi .v{font-size:22px;font-weight:800;line-height:1.2}
.kpi .l{font-size:10.5px;color:#9fb4b4;margin-top:1px}
nav{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--ln);padding:8px 0}
nav .in{max-width:1000px;margin:0 auto;padding:0 22px;display:flex;gap:4px;flex-wrap:wrap}
.tab{font-size:13px;font-weight:700;color:var(--sub);padding:6px 13px;border-radius:999px;border:1px solid transparent;background:none;cursor:pointer;font-family:inherit}
.tab:hover{color:var(--tx);border-color:var(--ln)}
.tab[aria-selected=true]{background:var(--card);color:var(--tx);border-color:var(--ac)}
main{padding:26px 0 40px}
h2{font-size:11px;text-transform:uppercase;letter-spacing:1.3px;color:var(--ac);margin:0 0 4px;font-weight:700}
h3{font-size:23px;font-weight:800;margin:0 0 12px;letter-spacing:-.3px}
h4{font-size:15px;font-weight:800;margin:26px 0 8px}
p{margin:0 0 13px;max-width:76ch}
.lead{font-size:16.5px}
.muted{color:var(--sub)}
.panel{display:none}.panel.on{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:11px;margin-top:14px}
.card{background:var(--card);border:1px solid var(--ln);border-radius:13px;padding:14px 16px}
.card .t{font-weight:800;font-size:14.5px;margin-bottom:3px}
.card .d{font-size:12.5px;color:var(--sub)}
.tag{font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;display:inline-block;margin-top:8px}
.t-live{background:rgba(47,189,107,.15);color:var(--ok)}
.t-plan{background:rgba(132,151,176,.16);color:var(--plan)}
.t-warn{background:rgba(224,165,58,.16);color:var(--warn)}
.t-bad{background:rgba(224,72,58,.15);color:var(--bad)}
.rule{background:var(--card);border:1px solid var(--ln);border-inline-start:3px solid var(--ac);border-radius:0 13px 13px 0;padding:13px 16px;margin-bottom:10px}
.rule .q{font-weight:800;font-size:15.5px;margin-bottom:4px}
.rule .how{font-size:13.5px;color:var(--sub)}
.rule .how b{color:var(--tx)}
input,textarea,select{background:var(--card2);border:1px solid var(--ln);border-radius:9px;padding:9px 12px;color:var(--tx);font-family:inherit;font-size:13.5px;width:100%}
input:focus,textarea:focus,select:focus{outline:2px solid var(--ac);outline-offset:1px}
textarea{resize:vertical;min-height:110px;line-height:1.6}
label{display:block;font-size:11.5px;font-weight:700;color:var(--sub);margin:9px 0 3px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 11px}
.go{background:var(--ac);color:#04211f;border:0;border-radius:10px;padding:9px 19px;font-weight:800;font-size:13.5px;cursor:pointer;font-family:inherit;margin-top:12px;width:auto}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.chip{background:var(--card);border:1px solid var(--ln);border-radius:999px;padding:4px 11px;font-size:11.5px;cursor:pointer;color:var(--tx);font-family:inherit;width:auto}
.chip:hover{border-color:var(--ac)}
.chip[aria-pressed=true]{border-color:var(--ac);background:var(--card2);color:var(--tx)}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:11px}
th,td{text-align:right;padding:6px 9px;border-bottom:1px solid var(--ln);vertical-align:top}
th{color:var(--sub);font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;font-weight:700}
tr.miss td{color:var(--sub)}
.mono{font-family:ui-monospace,Consolas,monospace;direction:ltr;font-size:11.5px}
.answer{background:var(--card2);border:1px solid var(--ln);border-radius:11px;padding:13px 15px;white-space:pre-wrap;word-wrap:break-word;margin-top:12px}
.answer.doc{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}
.strike{background:rgba(224,72,58,.15);color:var(--bad);border-radius:5px;padding:0 5px;font-weight:700}
.note{font-size:12.5px;border-inline-start:3px solid var(--warn);color:var(--warn);padding-inline-start:10px;margin:11px 0 0}
.note.ok{color:var(--ok);border-color:var(--ok)}
.note.bad{color:var(--bad);border-color:var(--bad)}
.pill{font-size:10.5px;font-weight:700;padding:3px 9px;border-radius:999px;background:var(--card2);border:1px solid var(--ln);display:inline-block}
.pill.ok{background:rgba(47,189,107,.16);color:var(--ok);border-color:transparent}
.pill.warn{background:rgba(224,165,58,.16);color:var(--warn);border-color:transparent}
.pill.bad{background:rgba(224,72,58,.18);color:var(--bad);border-color:transparent}
.gap{background:var(--card2);border:1px dashed var(--ln);border-radius:12px;padding:12px 15px;margin-bottom:8px}
.gap .t{font-weight:700;font-size:14px}
.gap .w{font-size:12.5px;color:var(--sub);margin-top:2px}
.big{background:var(--card);border:1px dashed var(--ln);border-radius:14px;padding:24px;text-align:center}
.big .x{font-size:34px;color:var(--sub)}
.idea{border-bottom:1px solid var(--ln);padding:9px 0}
.idea .h{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.idea .id{font-weight:800;color:var(--ac);font-size:12px;direction:ltr;min-width:44px}
.idea .ti{font-size:13.5px;font-weight:600}
.idea .m{font-size:11.5px;color:var(--sub);margin-top:2px}
.r-ready{color:var(--ok)}.r-partial{color:var(--warn)}.r-blocked{color:var(--bad)}.r-done{color:var(--ac)}
footer{border-top:1px solid var(--ln);margin-top:36px;padding:20px 0 70px;font-size:11.5px;color:var(--sub);text-align:center;line-height:2}
.hid{display:none !important}
</style></head><body>

<div class="hero"><div class="wrap">
  <h1>STLIX Gateway <span style="font-size:13px;font-weight:400;color:#9fb4b4">— ديمو، ملف واحد</span></h1>
  <div class="sub">نقطة تكامل واحدة لكل أنظمة الشركة. نما تفضل مصدر الحقيقة —
  الجيتواي بيوحّد الوصول ليها وللباقي، ويحطّ قواعد على اللي يتعرض.</div>
  <div class="snap">
    <b>الملف ده شغّال لوحده — مافيش سيرفر ومافيش نت.</b>
    الخريطة والمتطلبات مسحوبة من المنصّة الشغّالة يوم <b>__STAMP__</b> (نسخة <b>v__VER__</b>).
    الحارس القانوني والصيغ والبحث الصوتي <b>شغّالين هنا فعلًا</b> — نفس المنطق، متولّد من الكود.
    <br><b>واللي مقصود إنه مش هنا: الفلوس.</b> أول قاعدة في المنصّة إن مافيش رقم فلوس يتكتب
    في صفحة — فملف ديمو شايل أرصدة كان هيكسر القاعدة وهو بيشرحها.
  </div>
  <div class="kpis" id="kpis"></div>
</div></div>

<nav><div class="in" role="tablist">
  <button class="tab" role="tab" data-p="tour"  aria-selected="true">الجولة</button>
  <button class="tab" role="tab" data-p="map"   aria-selected="false">الخريطة</button>
  <button class="tab" role="tab" data-p="ideas" aria-selected="false">المتطلبات</button>
  <button class="tab" role="tab" data-p="legal" aria-selected="false">المستشار القانوني</button>
  <button class="tab" role="tab" data-p="money" aria-selected="false">الأرقام</button>
  <button class="tab" role="tab" data-p="gaps"  aria-selected="false">اللي مش شغّال</button>
</div></nav>

<main class="wrap">

<section class="panel on" id="p-tour">
  <h2>The idea</h2><h3>ليه المنصّة دي موجودة</h3>
  <p class="lead">كل نظام عندنا شغّال لوحده: نما فيها الفلوس والموظفين، الـCRM فيه العملاء،
  الجرد في تطبيق تاني، والعقود في الدرايف. علشان تجاوب سؤال واحد بيمسّ اتنين منهم بتفتح
  شاشتين وتجمع بإيدك — والرقم اللي بتطلع بيه محدش يعرف جه منين.</p>
  <p><b>الجيتواي مش نظام جديد بيستبدل حاجة.</b> نما تفضل مصدر الحقيقة المالية والقانونية،
  والـCRM يفضل بتاع العميل. الجيتواي بيبقى <b>الباب الوحيد</b> اللي بيتقرا منه كل ده وبيفرض
  عليه قواعد. أي نظام جديد بيتوصّل مرة واحدة هنا بدل ما يتوصّل بكل حاجة تانية.</p>
  <p class="muted">وكل حاجة <b>read-only</b> بشكل افتراضي. أي كتابة في نما محتاجة workflow
  مدقّق وموافقة بشرية — مافيش شاشة بتعدّل في الـERP.</p>

  <h4>أربع قواعد، ومعاها الآلية اللي بتفرضها</h4>
  <p class="muted">دي مش نوايا. كل واحدة متحوّلة لكود بيفشل لو حد كسرها.</p>

  <div class="rule"><div class="q">١ · مافيش رقم فلوس مكتوب في صفحة</div>
  <div class="how">أي رقم بتشوفه جاي من endpoint. الكوكبيت كان فيه أرصدة بنوك موهومة <b>جنب</b>
  أرقام حقيقية — وده أوحش من إن كله يكون موهوم، لأن الحقيقي بيخلّي الموهوم يبان حقيقي.
  دلوقتي <b>اختبار بيفشل</b> لو أي صفحة موصّلة فيها رقم مكتوب بالإيد. ونفس القاعدة مطبّقة
  على الملف ده — بصّ في تاب «الأرقام».</div></div>

  <div class="rule"><div class="q">٢ · عمر الرقم ظاهر، وصحّته كمان</div>
  <div class="how">كل رد مالي شايل وقت آخر تحديث. وبعد كل سحب، حارس بيعيد مطابقة <b>شهر مقفول
  كامل</b> مع SQL — لأن الرقم ممكن يكون جديد وناقص في نفس الوقت لو نما غيّرت اسم حقل. لو لقى
  انحراف، المنصّة بترجع لـSQL لوحدها وبتقول كده. المطابقة على كل المجتمع فرقت
  <b>أقل من جنيه</b>.</div></div>

  <div class="rule"><div class="q">٣ · الذكاء بيجاوب من مصدر، مش من حفظه</div>
  <div class="how">الخبير بيقرا من <b id="ex-chunks">—</b> مقطع من وثائقنا وخريطة المنصّة، وكل
  جملة معاها مصدرها. ولو مفيش موديل موصول <b>ما بيصيغش كلام</b> — بيسلّمك المقاطع. ومستشار
  القانون فيه حارس بيشيل أي رقم مادة مش موجود في نصّ محمّل — <b>جرّبه في تاب المستشار</b>.</div></div>

  <div class="rule"><div class="q">٤ · المنصّة بتوصف نفسها</div>
  <div class="how">مافيش قايمة مكتوبة بالإيد لأي حاجة. الشاشات والأنظمة والـendpoints
  والمتطلبات بتتقرا من <b>خريطة واحدة</b>، و<b>اختبار بيفشل</b> لو endpoint اتضاف من غير ما
  يظهر عليها. الأرقام اللي فوق والتابات اللي جنب — كلها من الخريطة دي.</div></div>
</section>

<section class="panel" id="p-map">
  <h2>The map</h2><h3>الأنظمة والكنكتورات</h3>
  <p class="muted">مسحوبة من <span class="mono">/api/v1/map</span> — مش مكتوبة في الملف.</p>
  <div class="chips" id="map-filter"></div>
  <input id="map-q" type="search" placeholder="دوّر — نظام · كنكتور · endpoint" aria-label="بحث في الخريطة">
  <div id="map-out"></div>
</section>

<section class="panel" id="p-ideas">
  <h2>Requirements</h2><h3>كل متطلب اتقال — <span id="ideas-n">—</span></h3>
  <p class="muted">كل حاجة المالك طلبها، بحالتها وبإيه الناقص فيها. «جاهز» يعني كل الكنكتورات
  اللي محتاجها موجودة فعلًا — يعني محتاج تقرير يتبنى وخلاص.</p>
  <div class="chips" id="ideas-filter"></div>
  <input id="ideas-q" type="search" placeholder="دوّر في المتطلبات — كلمة · دومين · نظام · كود" aria-label="بحث في المتطلبات">
  <div id="ideas-count" class="muted" style="font-size:12px;margin-top:8px"></div>
  <div id="ideas-out"></div>
</section>

<section class="panel" id="p-legal">
  <h2>Legal</h2><h3>المستشار القانوني — الحارس شغّال هنا</h3>
  <div class="chips">
    <button class="chip" id="lt-verify" aria-pressed="true">افحص المواد</button>
    <button class="chip" id="lt-draft" aria-pressed="false">اكتب مستند</button>
    <button class="chip" id="lt-cover" aria-pressed="false">النصوص المطلوبة</button>
  </div>

  <div id="lp-verify">
    <p class="muted">الـregex وجدول تحديد القانون <b>متولّدين من</b>
    <span class="mono">citations.py</span> — مش متكتوبين تاني. فالملف ده مايقدرش يختلف عن
    اللي هيشتغل عندنا.</p>
    <div class="card" style="margin:10px 0">
      <label style="display:flex;gap:8px;align-items:flex-start;font-weight:400;color:var(--tx)">
        <input type="checkbox" id="demoLaw" style="width:auto;margin-top:5px">
        <span><b>حمّل نصّ عرض للقانون المدني</b> (٣ مواد: 1 · 147 · 148) علشان تشوف الأحكام
        التلاتة. من غيره كل إشارة هتطلع «قانونها مش محمّل» — وده بالظبط الوضع الحالي عندنا،
        لأن مجلد النصوص لسه فاضي.</span></label>
    </div>
    <div class="chips" id="egs"></div>
    <label for="vtext">النص</label>
    <textarea id="vtext"></textarea>
    <button class="go" id="verGo">افحص</button>
    <div id="verOut"></div>
  </div>

  <div id="lp-draft" class="hid">
    <p class="muted">الصيغ الستّة الحقيقية — نفس البنود والحقول اللي في
    <span class="mono">templates.py</span>. الفراغ اللي ماتملاش بيفضل ظاهر ⟨كده⟩.</p>
    <label for="tpl">الصيغة</label><select id="tpl"></select>
    <div id="tplGov" class="muted" style="font-size:12px;margin-top:6px"></div>
    <div class="row" id="tplFields"></div>
    <label style="display:flex;gap:7px;align-items:center;font-weight:400;margin-top:10px">
      <input type="checkbox" id="tplOpt" style="width:auto"> ضمّ البنود الاختيارية</label>
    <button class="go" id="draftGo">اكتب المسودة</button>
    <div id="draftOut"></div>
  </div>

  <div id="lp-cover" class="hid">
    <p class="muted">الـ٢٤ مصدر اللي المستشار المفروض يكون شايلهم. كلهم ناقصين دلوقتي — ودي
    مش شاشة خطأ: هي اللي بتخلّيه يقول «ده محكوم بقانون كذا ونصّه مش عندي» بدل ما يجاوب من فراغ.</p>
    <div id="coverOut"></div>
  </div>
</section>

<section class="panel" id="p-money">
  <h2>The numbers</h2><h3>الأرقام مش في الملف ده — عن قصد</h3>
  <div class="big">
    <div class="x">—</div>
    <p style="margin:10px auto 0;max-width:60ch"><b>أول قاعدة في المنصّة: مافيش رقم فلوس
    بيتكتب في صفحة.</b> ملف ديمو شايل أرصدة AR وAP كان هيكسر القاعدة وهو بيشرحها — وكان
    هيبقى رقم بتاريخ اليوم اللي اتعمل فيه، بيتقري صح لحد ما حد يبني عليه قرار.</p>
    <p style="margin:8px auto 0;max-width:60ch" class="muted">الأرقام الحقيقية على
    <span class="mono">/tools/finance-reports</span> — بتتبني من مستندات نما فاتورة فاتورة،
    ومعاها وقت آخر تحديث وحُكم حارس المطابقة.</p>
  </div>
  <h4>اللي بيحصل هناك</h4>
  <table><tbody>
    <tr><td style="width:32%">من فين</td><td>مستندات نما نفسها (فواتير · تحصيلات · مدفوعات) — REST مابيدّيش أرصدة محسوبة</td></tr>
    <tr><td>المطابقة</td><td>مع نسخة SQL مُرستَرة — الفرق كان أقل من جنيه على كل المجتمع</td></tr>
    <tr><td>الحارس</td><td>بعد كل سحب، شهر مقفول بيتطابق تاني · pass / drift / unknown</td></tr>
    <tr><td>لو انحرف</td><td>المنصّة بترجع لـSQL لوحدها وبتقول كده على الصفحة</td></tr>
    <tr><td>المتصفح</td><td>مابيجمّعش فلوس. كل مجموع جاي من endpoint واحد متطابق</td></tr>
  </tbody></table>
</section>

<section class="panel" id="p-gaps">
  <h2>Not yet</h2><h3>اللي لسه مش شغّال</h3>
  <p>محسوب من نفس الخريطة اللي فوق، مش من قايمة حد بيحدّثها. جولة بتعرض الحلو بس بيتصدّقها
  عشر دقايق.</p>
  <div id="gaps-out"></div>
</section>

</main>

<footer>
  <b>STLIX Gateway v__VER__</b> · لقطة __STAMP__ · ملف واحد، من غير سيرفر<br>
  النسخة الحيّة على <span class="mono">/tools/tour</span> — كل رقم فيها بلينك يثبته ·
  كل الكنكتورات read-only<br>
  البحث الصوتي شغّال هنا كمان: المايك تحت-يسار أو <span class="mono">Ctrl+M</span>
</footer>

<script>
const D = __DATA__;
const DEMO_TEXT = __DEMO__;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $ = id => document.getElementById(id);

/* ---- tabs -------------------------------------------------------------- */
const PANELS = ["tour","map","ideas","legal","money","gaps"];
document.querySelectorAll("nav .tab").forEach(t => t.onclick = () => {
  document.querySelectorAll("nav .tab").forEach(x => x.setAttribute("aria-selected", x === t));
  PANELS.forEach(p => $("p-" + p).classList.toggle("on", p === t.dataset.p));
  window.scrollTo({ top: 0, behavior: "smooth" });
});

/* ---- KPIs -------------------------------------------------------------- */
const liveConn = D.connectors.filter(c => c.live);
const pages = D.endpoints.filter(e => e.kind === "page" && !e.path.includes("{") && !e.path.endsWith(".js"));
const ready = D.ideas.filter(i => i.readiness === "ready");
$("kpis").innerHTML = [
  [D.coverage.systems, "نظام على الخريطة"], [liveConn.length, "كنكتور حيّ"],
  [D.endpoints.length, "endpoint"], [pages.length, "شاشة"],
  [D.ideas.length, "متطلب مسجّل"], [ready.length, "جاهز للبناء"]
].map(([v, l]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
$("ex-chunks").textContent = D.expert.chunks.toLocaleString("en-US");

/* ---- map --------------------------------------------------------------- */
let mapMode = "all";
const MF = [["all","الكل"],["live","شغّال"],["planned","مخطّط"]];
$("map-filter").innerHTML = MF.map(([k,l]) =>
  `<button class="chip" data-k="${k}" aria-pressed="${k===mapMode}">${l}</button>`).join("");
$("map-filter").querySelectorAll(".chip").forEach(b => b.onclick = () => {
  mapMode = b.dataset.k;
  $("map-filter").querySelectorAll(".chip").forEach(x => x.setAttribute("aria-pressed", x === b));
  paintMap();
});
$("map-q").addEventListener("input", paintMap);

function paintMap() {
  const q = ($("map-q").value || "").trim().toLowerCase();
  const hit = t => !q || String(t).toLowerCase().includes(q);
  const sys = D.systems.filter(s =>
    (mapMode === "all" || (mapMode === "live") === (s.status === "live")) &&
    (hit(s.name_ar) || hit(s.name_en) || hit(s.key) || hit(s.description)));
  const con = D.connectors.filter(c =>
    (mapMode === "all" || (mapMode === "live") === !!c.live) &&
    (hit(c.name_ar) || hit(c.name_en) || hit(c.key) || hit(c.upstream) || hit(c.note)));
  const eps = q ? D.endpoints.filter(e => hit(e.path) || hit(e.title_ar)) : [];
  let h = `<h4>الأنظمة · ${sys.length}</h4><div class="grid">` + sys.map(s =>
    `<div class="card"><div class="t">${esc(s.name_ar)}</div>
     <div class="d">${esc(s.description || s.name_en)}</div>
     <span class="tag ${s.status === "live" ? "t-live" : "t-plan"}">${s.status === "live" ? "موصّل" : "مخطّط"}</span></div>`
  ).join("") + `</div>`;
  h += `<h4>الكنكتورات · ${con.length}</h4><div class="grid">` + con.map(c =>
    `<div class="card"><div class="t">${esc(c.name_ar)}</div>
     <div class="d">بيكلّم: ${esc(c.upstream)}${c.note ? "<br>" + esc(c.note) : ""}</div>
     <span class="tag ${c.live ? "t-live" : "t-plan"}">${c.live ? (c.endpoints||[]).length + " endpoint" : "مبنيش لسه"}</span></div>`
  ).join("") + `</div>`;
  if (eps.length) h += `<h4>Endpoints · ${eps.length}</h4><table><thead><tr><th>المسار</th><th>إيه</th><th>الميثود</th></tr></thead><tbody>` +
    eps.slice(0, 60).map(e => `<tr><td class="mono">${esc(e.path)}</td><td>${esc(e.title_ar)}</td><td class="mono">${esc(e.method)}</td></tr>`).join("") +
    `</tbody></table>`;
  $("map-out").innerHTML = h;
}

/* ---- ideas ------------------------------------------------------------- */
$("ideas-n").textContent = D.ideas.length;
let ideaMode = "all";
const RL = {ready:"جاهز", partial:"جزئي", blocked:"متوقّف", done:"اتعمل"};
const IF_ = [["all","الكل"],["done","اتعمل"],["ready","جاهز للبناء"],["partial","جزئي"],["blocked","متوقّف"]];
$("ideas-filter").innerHTML = IF_.map(([k,l]) => {
  const n = k === "all" ? D.ideas.length : D.ideas.filter(i => i.readiness === k).length;
  return `<button class="chip" data-k="${k}" aria-pressed="${k===ideaMode}">${l} <span class="muted">${n}</span></button>`;
}).join("");
$("ideas-filter").querySelectorAll(".chip").forEach(b => b.onclick = () => {
  ideaMode = b.dataset.k;
  $("ideas-filter").querySelectorAll(".chip").forEach(x => x.setAttribute("aria-pressed", x === b));
  paintIdeas();
});
$("ideas-q").addEventListener("input", paintIdeas);

function paintIdeas() {
  const q = ($("ideas-q").value || "").trim().toLowerCase();
  const rows = D.ideas.filter(i =>
    (ideaMode === "all" || i.readiness === ideaMode) &&
    (!q || [i.id, i.title, i.domain, i.needs, i.engine, i.source, (i.systems||[]).join(" ")]
      .some(v => String(v ?? "").toLowerCase().includes(q))));
  $("ideas-count").textContent = `${rows.length} من ${D.ideas.length}`;
  $("ideas-out").innerHTML = rows.slice(0, 300).map(i =>
    `<div class="idea"><div class="h"><span class="id">${esc(i.id)}</span>
      <span class="ti">${esc(i.title)}</span>
      <span class="pill r-${esc(i.readiness)}">${esc(RL[i.readiness] || i.readiness)}</span></div>
     <div class="m">${esc(i.domain || "")}${i.engine ? " · محرّك: " + esc(i.engine) : ""}${(i.systems||[]).length ? " · " + esc(i.systems.join(" · ")) : ""}${i.needs ? "<br><b>الناقص:</b> " + esc(i.needs) : ""}</div>
     </div>`).join("") + (rows.length > 300 ? `<p class="muted" style="margin-top:10px">بيعرض أول 300 — ضيّق البحث.</p>` : "");
}

/* =======================================================================
   The citation guard. Regexes and the alias table come from DATA.rx and
   DATA.aliases, exported out of citations.py when this file was generated.
   ======================================================================= */
const CITE = new RegExp(D.rx.cite, "g");
const ARTICLE_HEAD = new RegExp(D.rx.article_head);
const MARKS = new RegExp(D.rx.marks, "g");
const arabicInt = s => String(s).replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x0660)).trim();
const normalize = t => String(t).replace(MARKS, "").replace(/./g, c => D.fold[c] || c).toLowerCase();
const LAWNAMES = {}; D.legal.expected.forEach(e => LAWNAMES[e.slug] = e.name);
let LOADED = new Set(), ARTICLES = new Set(), NSRC = 0;

function loadDemo(on) {
  LOADED = new Set(); ARTICLES = new Set(); NSRC = 0;
  if (on) {
    const m = DEMO_TEXT.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
    const meta = {}; let body = DEMO_TEXT;
    if (m) { m[1].split("\n").forEach(l => { const i = l.indexOf(":");
      if (i > 0) meta[l.slice(0, i).trim()] = l.slice(i + 1).trim(); }); body = m[2]; }
    const slug = meta.slug || "madani";
    body.split("\n").forEach(line => {
      const a = line.match(ARTICLE_HEAD);
      if (a) ARTICLES.add(slug + "#" + arabicInt(a[1]));
    });
    LOADED.add(slug); NSRC = 1;
  }
}

function lawAt(norm, pos) {
  const ahead = norm.slice(pos, pos + 90);
  for (const [a, s] of D.aliases) if (ahead.includes(a)) return s;
  const behind = norm.slice(Math.max(0, pos - 400), pos);
  let best = "", at = -1;
  for (const [a, s] of D.aliases) { const i = behind.lastIndexOf(a); if (i > at) { best = s; at = i; } }
  return best;
}

function findClaims(text) {
  const norm = normalize(text), out = [];
  CITE.lastIndex = 0;
  let m;
  while ((m = CITE.exec(text)) !== null) {
    if (m[0] === "") { CITE.lastIndex++; continue; }
    const n = arabicInt(m[1]);
    const slug = lawAt(norm, m.index + m[0].length);
    const name = slug ? (LAWNAMES[slug] || slug) : "قانون غير محدَّد";
    let verdict, note;
    if (!slug) { verdict = "unverifiable"; note = "ما حدّدش القانون، فمافيش حاجة أتأكد منها."; }
    else if (!LOADED.has(slug)) { verdict = "unverifiable"; note = "نصّ «" + name + "» مش محمّل هنا — حمّله في corpus/legal وأتأكد."; }
    else if (ARTICLES.has(slug + "#" + n)) { verdict = "confirmed"; note = ""; }
    else { verdict = "fabricated"; note = "«" + name + "» محمّل عندي، ومفيهوش مادة " + n + "."; }
    out.push({ text: m[0], start: m.index, end: m.index + m[0].length, number: n, law: name, verdict, note });
  }
  return out;
}

function redact(text, claims) {
  let out = text;
  [...claims].sort((a, b) => b.start - a.start).forEach(c => {
    if (c.verdict === "confirmed") return;
    out = out.slice(0, c.start) +
      (c.verdict === "fabricated" ? "[مادة محذوفة — مش موجودة في النصّ المحمّل]"
                                  : "[" + c.law + " — النصّ مش محمّل، الرقم مش متأكَّد منه]") +
      out.slice(c.end);
  });
  return out;
}

const sum = cs => { const c = {confirmed:0,unverifiable:0,fabricated:0}; cs.forEach(x => c[x.verdict]++);
  return {total: cs.length, ...c, claims: cs}; };

const fmtRedacted = t => esc(t).replace(/\[(مادة محذوفة[^\]]*|[^\]]*النصّ مش محمّل[^\]]*)\]/g,
  (_, m) => `<span class="strike">[${m}]</span>`);

function citeHtml(c, label) {
  if (!c || !c.total) return "";
  const bits = [];
  if (c.confirmed) bits.push(`<span class="pill ok">${c.confirmed} متأكَّد منها</span>`);
  if (c.unverifiable) bits.push(`<span class="pill warn">${c.unverifiable} قانونها مش محمّل</span>`);
  if (c.fabricated) bits.push(`<span class="pill bad">${c.fabricated} مش موجودة في النصّ</span>`);
  return `<h4>🛡️ ${esc(label)} — ${c.total} إشارة لمادة</h4>
    <div class="chips">${bits.join("")}</div>
    <table><thead><tr><th>الإشارة</th><th>القانون</th><th>الحكم</th><th>ملاحظة</th></tr></thead><tbody>` +
    c.claims.map(x => `<tr><td class="mono">${esc(x.text)}</td><td>${esc(x.law)}</td>
      <td>${x.verdict === "confirmed" ? "✔" : x.verdict === "fabricated" ? "✕" : "؟"}</td>
      <td>${esc(x.note)}</td></tr>`).join("") + `</tbody></table>`;
}

/* legal sub-tabs */
[["lt-verify","lp-verify"],["lt-draft","lp-draft"],["lt-cover","lp-cover"]].forEach(([b, p], _, all) => {
  $(b).onclick = () => all.forEach(([bb, pp]) => {
    $(bb).setAttribute("aria-pressed", bb === b);
    $(pp).classList.toggle("hid", pp !== p);
  });
});

const EGS = [
  ["مادة صحيحة", "العقد شريعة المتعاقدين طبقًا للمادة 147 من القانون المدني."],
  ["مادة مخترعة", "ده باطل طبقًا للمادة 9999 من القانون المدني."],
  ["قانون مش محمّل", "مدة الإخطار محكومة بالمادة 47 من قانون العمل."],
  ["الصيني مش المصري", "المادة 147 من القانون المدني الصيني."],
  ["أرقام هندية", "المادة ١٤٨ من القانون المدني."],
  ["القانون بيتنقل", "القانون المدني بيقول في المادة 147 كده، وكمان المادة 148 بتقول كده."],
  ["الاتنين مع بعض", "ده مخالف للمادة 9999 من القانون المدني، وصحيح طبقًا للمادة 147 منه."]
];
$("egs").innerHTML = EGS.map((e, i) => `<button class="chip" data-i="${i}">${esc(e[0])}</button>`).join("");
$("egs").querySelectorAll(".chip").forEach(b => b.onclick = () => {
  $("vtext").value = EGS[+b.dataset.i][1]; $("verGo").click();
});
$("demoLaw").onchange = e => { loadDemo(e.target.checked); if ($("vtext").value.trim()) $("verGo").click(); };
$("verGo").onclick = () => {
  const t = $("vtext").value.trim();
  if (!t) { $("verOut").innerHTML = `<p class="muted">اكتب نص أو اختار مثال فوق.</p>`; return; }
  const cs = findClaims(t), s = sum(cs);
  $("verOut").innerHTML = s.total
    ? citeHtml(s, "نتيجة الفحص") +
      `<h4>النص بعد شطب اللي مش متأكَّد منه</h4><div class="answer doc">${fmtRedacted(redact(t, cs))}</div>`
    : `<p class="note ok">مافيش أي إشارة لمادة في النص ده.</p>`;
};

/* templates */
$("tpl").innerHTML = D.templates.map(t => `<option value="${esc(t.key)}">${esc(t.title)}</option>`).join("");
function showFields() {
  const t = D.templates.find(x => x.key === $("tpl").value);
  $("tplGov").textContent = "محكوم بـ: " + t.governed_by.join(" · ");
  $("tplFields").innerHTML = t.fields.map(f =>
    `<div><label for="f-${esc(f.key)}">${esc(f.label)}${f.required ? "" : " (اختياري)"}</label>
     <input id="f-${esc(f.key)}" data-k="${esc(f.key)}" placeholder="${esc(f.example)}"></div>`).join("");
  $("draftOut").innerHTML = "";
}
$("tpl").onchange = showFields; showFields();
$("draftGo").onclick = () => {
  const t = D.templates.find(x => x.key === $("tpl").value);
  const vals = {}, labels = {}, missing = [];
  document.querySelectorAll("#tplFields input[data-k]").forEach(i => vals[i.dataset.k] = i.value.trim());
  t.fields.forEach(f => labels[f.key] = f.label);
  const sub = (_, k) => { if (vals[k]) return vals[k];
    if (!missing.includes(k)) missing.push(k); return "⟨" + (labels[k] || k) + "⟩"; };
  const parts = ["# " + t.title, ""], basis = [];
  let n = 0;
  t.clauses.forEach(c => {
    if (c.optional && !$("tplOpt").checked) return;
    parts.push("## " + (++n) + ". " + c.heading, "", c.body.replace(/\{\{(\w+)\}\}/g, sub), "");
    if (c.basis) basis.push(c);
  });
  const md = parts.join("\n").trim() + "\n";
  const req = missing.filter(k => (t.fields.find(f => f.key === k) || {required:true}).required);
  const cs = findClaims(md);
  let h = `<div class="answer doc">${esc(md)}</div>`;
  if (req.length) h += `<p class="note">لسه فاضل ${req.length} حقل مطلوب — ظاهرين في النص بين ⟨ ⟩.</p>`;
  h += citeHtml(sum(cs), "فحص المواد في المسودة");
  if (!cs.length) h += `<p class="note ok">✔ مافيش ولا رقم مادة في الصيغة. ده مقصود: الصيغة مش
    مخرَج موديل، فكانت هتعدّي من قدّام الحارس — وتبقى الطريق الوحيد اللي رقم مخترع يوصل منه
    لمستند موقَّع.</p>`;
  h += `<h4>لازم يتراجع بشريًا قبل التوقيع</h4><table><tbody>` +
       t.check.map(c => `<tr><td>☐ ${esc(c)}</td></tr>`).join("") + `</tbody></table>`;
  if (basis.length) h += `<h4>سند كل بند</h4><table><tbody>` +
    basis.map(c => `<tr><td style="width:32%">${esc(c.heading)}</td><td>${esc(c.basis)}</td></tr>`).join("") +
    `</tbody></table>`;
  h += `<p class="muted" style="font-size:11.5px;margin-top:12px">دي مسودة مبنية على هيكل بنود —
    مش رأي قانوني ولا بديل عن محامٍ.</p>`;
  $("draftOut").innerHTML = h;
};

$("coverOut").innerHTML =
  `<table><thead><tr><th>القانون</th><th>الجهة</th><th>بيحكم إيه</th><th>slug</th></tr></thead><tbody>` +
  D.legal.expected.map(r => `<tr class="${r.loaded ? "" : "miss"}"><td>${r.loaded ? "✔ " : "— "}${esc(r.name)}</td>
    <td>${esc(r.jurisdiction)}</td><td style="font-size:11.5px;color:var(--sub)">${esc(r.covers)}</td>
    <td class="mono">${esc(r.slug)}</td></tr>`).join("") + `</tbody></table>`;

/* ---- gaps, computed ---------------------------------------------------- */
const planned = D.systems.filter(s => s.status !== "live");
const deadConn = D.connectors.filter(c => !c.live);
const blocked = D.ideas.filter(i => i.readiness === "blocked");
const partial = D.ideas.filter(i => i.readiness === "partial");
const GAPS = [
  { t: "مفيش موديل موصول للصياغة",
    w: "الخبير والمستشار شغّالين وبيرجّعوا مصادرهم، بس مش بيصيغوا إجابة. مفتاح واحد في <span class='mono'>.env</span> بيفتح ده." },
  { t: `نصوص القوانين لسه ماترفعتش — ${D.legal.corpus.statute_articles} مادة محمّلة`,
    w: `المحرّك والحارس والصيغ شغّالين، والمجلد فاضي — فالمستشار بيقول «القانون ده مش عندي» بدل ما يخمّن. ${D.legal.corpus.expected} مصدر مطلوب، شوف تاب «النصوص المطلوبة».` },
  { t: "مافيش دخول موحّد ولا صلاحيات",
    w: "أي حد بيوصل للعنوان بيشوف كل حاجة. مقبول لعرض داخلي، مش مقبول لغير كده." },
  { t: `${planned.length} نظام على الخريطة ولسه ماتوصّلش`,
    w: planned.map(s => esc(s.name_ar)).join(" · ") },
  { t: `${deadConn.length} كنكتور مبنيش لسه`,
    w: deadConn.map(c => esc(c.name_ar)).join(" · ") },
  { t: `${blocked.length} متطلب متوقّف · ${partial.length} جزئي`,
    w: "مسجّلين كلهم بأسبابهم في تاب «المتطلبات» — مش منسيين." },
  { t: "REP — ١١ وحدة مبنية بره الجيتواي",
    w: "العهدة · الحركة · الوجبات · الناس · اللوائح · الأكاديمية · التنبيهات · المستندات. بتقرا نما باعتماد أدمن بتاعها، وده اللي الجيتواي موجود علشان يخلّصه." }
];
$("gaps-out").innerHTML = GAPS.map(g =>
  `<div class="gap"><div class="t">${g.t}</div><div class="w">${g.w}</div></div>`).join("");

loadDemo(false);
paintMap(); paintIdeas();
$("vtext").value = EGS[6][1];
$("verGo").click();
</script>

<!-- the platform-wide voice layer, inlined so it works offline too -->
<script>
__VOICE__
</script>
</body></html>
"""

out = (HTML.replace("__DATA__", json.dumps(D, ensure_ascii=False))
           .replace("__DEMO__", json.dumps(DEMO_LAW, ensure_ascii=False))
           .replace("__VOICE__", VOICE)
           .replace("__STAMP__", STAMP)
           .replace("__VER__", D["snapshot"]["version"]))
OUT = ROOT / "dist" / "stlix-demo.html"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(out, encoding="utf-8")
kb = round(len(out.encode()) / 1024, 1)
print(f"  {OUT.relative_to(ROOT)}  —  {kb} KB")
print(f"  لقطة {STAMP} · v{__version__} · {len(D['ideas'])} متطلب · "
      f"{len(D['systems'])} نظام · {len(D['templates'])} صيغة")
print("  الحارس والصيغ والصوت شغّالين جوّه الملف · أرقام الفلوس مش جوّاه عن قصد")
