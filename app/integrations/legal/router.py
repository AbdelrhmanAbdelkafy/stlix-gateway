"""المستشار القانوني — ask, draft, review, verify.

`/verify` is the endpoint worth noticing: it takes any text and checks its
article citations against the loaded statutes, with no model involved at all. It
therefore works on a machine with nothing configured, and it works on text this
system did not write — a draft from a counterparty, an old contract, a clause
somebody was sent on WhatsApp. The guard is not a property of our answers; it is
a tool that can be pointed at anything.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from ..expert import answer as compose_mod
from ..expert.retrieve import Index
from . import citations, corpus, templates

router = APIRouter(prefix="/legal", tags=["legal"],
                   dependencies=[Depends(require_api_key)])

SYSTEM = """\
إنت «المستشار القانوني» بتاع مجموعة ستليكس. بتشتغل جوّه STLIX Gateway.

القاعدة الأولى، وكل حاجة تانية بتيجي بعدها:

**ما تكتبش رقم مادة إلا لو الرقم ده مكتوب حرفيًا في مقطع من المقاطع اللي تحت.**
مش «فاكر»، مش «غالبًا»، مش «المادة 147 تقريبًا». لو النصّ مش قدّامك، قول اسم
القانون اللي بيحكم الموضوع وقول إن نصّه مش محمّل. فيه حارس آلي بيفحص كل رقم مادة
في ردّك ويشيل اللي مش متأكَّد منه — فالتخمين مش هيعدّي، هيوسّخ الردّ بس.

باقي القواعد:

1. مصدرك هو المقاطع المرقّمة (S1، S2 …). كل جملة فيها حكم أو التزام تنتهي
   بمصدرها [S2].
2. اعرف الفرق وقوله بوضوح:
   - **نصّ قانون** (tier: statute) = حجّة.
   - **عقد من عقودنا** (tier: precedent) = ده اللي إحنا وقّعناه قبل كده، مش اللي
     القانون بيقوله. ما تقولش «القانون بيقول» وإنت بتقرا من عقد.
   - **لائحة داخلية** (tier: internal) = ملزمة لينا إحنا بس، ولو خالفت القانون
     فالقانون هو اللي بينفَّذ.
3. «مش عارف» إجابة صح. الأحسن منها: «الموضوع ده محكوم بقانون كذا، والنصّ مش
   محمّل عندي — حمّله وأنا أجاوب بالمادة».
4. لو البند اللي بتراجعه بيخالف قاعدة آمرة (حق مقرر للعامل، حد أقصى، شكل واجب)،
   قول إنه **باطل ولو الطرفين وقّعوا عليه** — ده أهم تحذير بتقوله.
5. لما تكتب مسودة: اكتب بنود كاملة قابلة للتوقيع، وسيب الفراغات بين ⟨ ⟩ بدل ما
   تخترع أسماء أو تواريخ أو مبالغ.
6. إنت مش محامي ومش بديل عنه. اقفل أي رأي بسطر بيقول إيه اللي محتاج مراجعة
   بشرية، وليه.
7. عربي مصري واضح. المصطلح القانوني بالفصحى زي ما هو («الإعذار»، «الفسخ»،
   «القوة القاهرة»).
"""

_NO_MATCH = ("مالقيتش نصّ عندي يخصّ السؤال ده. أغلب الظن إن القانون المطلوب مش "
             "محمّل — شوف /api/v1/legal/coverage، وحطّ ملف النصّ في corpus/legal "
             "وشغّل /api/v1/legal/reindex.")

_INDEX: Index | None = None


def _index() -> Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(corpus.chunks())
    return _INDEX


def _reset_index() -> None:
    global _INDEX
    _INDEX = None


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=6000)
    image: str = Field(default="", max_length=6_000_000)
    top_k: int = Field(default=8, ge=1, le=20)


class Draft(BaseModel):
    template: str
    values: dict[str, str] = Field(default_factory=dict)
    include_optional: bool = False


class Review(BaseModel):
    text: str = Field(min_length=20, max_length=120_000)
    kind: str = Field(default="", max_length=80)   # عقد عمل · لائحة · …


class Verify(BaseModel):
    text: str = Field(min_length=1, max_length=120_000)


def _state(settings: Settings) -> dict:
    st = corpus.stats()
    attached = bool(settings.anthropic_api_key)
    return {
        "advisor": "المستشار القانوني",
        "corpus": st,
        "model_attached": attached,
        "mode": "grounded" if attached else "sources_only",
        "guard": {
            "what": "كل «مادة N» في أي ردّ بتتفحص ضد النصوص المحمّلة",
            "verdicts": {
                citations.CONFIRMED: "المادة موجودة في نصّ محمّل — تعدّي",
                citations.UNVERIFIABLE: "القانون مش محمّل — الرقم بيتعلّم عليه",
                citations.FABRICATED: "القانون محمّل ومفيهوش المادة دي — بتتشال",
            },
            "checked_against": "tier=statute فقط — العقود واللوائح مش حجّة على القانون",
        },
        "disclaimer": "مساعد صياغة وبحث. مش محامي ومش بديل عن مراجعة قانونية.",
        "endpoints": {
            "ask": "POST /api/v1/legal/ask",
            "draft": "POST /api/v1/legal/draft",
            "review": "POST /api/v1/legal/review",
            "verify": "POST /api/v1/legal/verify (من غير موديل خالص)",
            "search": "GET /api/v1/legal/search?q=",
            "coverage": "GET /api/v1/legal/coverage",
            "page": "/tools/legal",
        },
    }


@router.get("")
async def status(request: Request, settings: Settings = Depends(get_settings)):
    """إيه المحمّل، وإيه الناقص، والحارس شغّال إزاي."""
    data = _state(settings)
    st = data["corpus"]
    rows = [{"metric": "نصوص محمّلة", "value": st["sources"]},
            {"metric": "مواد قانونية", "value": st["statute_articles"]},
            {"metric": "مقاطع", "value": st["chunks"]},
            {"metric": "من المطلوب", "value": f'{st["loaded_of_expected"]} / {st["expected"]}'},
            {"metric": "موديل موصول", "value": "أيوه" if data["model_attached"] else "لأ"},
            {"metric": "مجلد النصوص", "value": st["corpus_dir"]},
            {"metric": "الصفحة", "value": "/tools/legal"}]
    return respond(request, data, title="المستشار القانوني", rows=rows,
                   columns=["metric", "value"])


@router.get("/coverage")
async def coverage(request: Request):
    """كل قانون المفروض يكون عندي — محمّل ولا لأ.

    الناقص هو النصف المفيد: مستشار بيقول «القانون ده مش عندي» أنفع بكتير من
    واحد بيجاوب من فراغ.
    """
    rows = corpus.coverage()
    view = [{"القانون": r["name"], "الجهة": r["jurisdiction"],
             "النوع": r["tier"], "محمّل": "✔" if r["loaded"] else "—",
             "مواد": r["articles"] or "", "slug": r["slug"]} for r in rows]
    loaded = sum(1 for r in rows if r["loaded"])
    return respond(request, {"count": len(rows), "loaded": loaded, "rows": rows},
                   title="تغطية النصوص القانونية", rows=view,
                   columns=["القانون", "الجهة", "النوع", "محمّل", "مواد", "slug"],
                   badges=f'<span class="badge">{loaded} / {len(rows)}</span>')


@router.get("/search")
async def search(request: Request, q: str = Query(min_length=2, max_length=4000),
                 top_k: int = Query(default=10, ge=1, le=30)):
    """بحث في النصوص المحمّلة — من غير موديل."""
    hits = _index().search(q, top_k)
    rows = [{"id": f"S{i}", "score": round(h.score, 2), "النوع": h.chunk.kind,
             "المصدر": h.chunk.title} for i, h in enumerate(hits, 1)]
    return respond(request, {"query": q, "count": len(hits),
                             "results": [h.as_dict(i) for i, h in enumerate(hits, 1)]},
                   title=f"بحث قانوني · {q}", rows=rows,
                   columns=["id", "score", "النوع", "المصدر"])


@router.get("/law/{slug}")
async def one_law(request: Request, slug: str):
    src, chunks = corpus.law(slug)
    if src is None:
        raise HTTPException(404, f"«{slug}» مش محمّل. شوف /api/v1/legal/coverage")
    rows = [{"المادة": c.title.split("·")[-1].strip(),
             "النص": c.text[:160] + ("…" if len(c.text) > 160 else "")}
            for c in chunks]
    return respond(request, {"slug": slug, "title": src.title, "tier": src.tier,
                             "articles": len(chunks),
                             "records": [c.as_dict() for c in chunks]},
                   title=src.title, rows=rows, columns=["المادة", "النص"])


@router.post("/verify")
async def verify(body: Verify):
    """افحص أرقام المواد في أي نص — نصّنا أو نصّ الطرف التاني.

    مافيش موديل في الطريق: النتيجة بتتحسب من الملفات المحمّلة، فبتشتغل على أي
    جهاز وبتديك نفس الإجابة كل مرة.
    """
    claims = citations.find(body.text)
    redacted, _ = citations.redact(body.text, claims)
    return {**citations.summary(claims), "redacted": redacted}


@router.get("/templates")
async def list_templates(request: Request):
    ts = templates.as_dicts()
    rows = [{"key": t["key"], "المستند": t["title"], "بنود": t["clauses"],
             "حقول": len(t["fields"]), "محكوم بـ": ", ".join(t["governed_by"])}
            for t in ts]
    return respond(request, {"count": len(ts), "templates": ts},
                   title="صيغ المستندات", rows=rows,
                   columns=["key", "المستند", "بنود", "حقول", "محكوم بـ"])


@router.post("/draft")
async def draft(body: Draft):
    """اكتب مسودة من صيغة. الفراغات اللي ماتملتش بتفضل ظاهرة ⟨كده⟩."""
    try:
        out = templates.render(body.template, body.values, body.include_optional)
    except KeyError:
        raise HTTPException(404, f"مافيش صيغة اسمها «{body.template}»") from None
    # A template must not smuggle an article number past the guard.
    out["citations"] = citations.summary(citations.find(out["markdown"]))
    return out


@router.post("/review")
async def review(body: Review, settings: Settings = Depends(get_settings)):
    """راجع مستند: فحص أرقام المواد اللي فيه + مراجعة بنوده مقابل النصوص المحمّلة."""
    doc_claims = citations.find(body.text)
    hits = _index().search(body.text[:2000] + " " + (body.kind or ""), 8)
    prompt = (
        f"راجع المستند ده{(' — نوعه: ' + body.kind) if body.kind else ''}.\n"
        "قول: (1) البنود الناقصة اللي المفروض تكون فيه، (2) البنود اللي فيها خطر "
        "علينا، (3) أي بند بيخالف قاعدة آمرة فيبقى باطل ولو موقّع عليه، "
        "(4) صياغة بديلة للبنود الخطرة.\n\n"
        f"--- المستند ---\n{body.text[:40000]}")
    out = await compose_mod.compose(prompt, hits, settings, system=SYSTEM,
                                    no_match_note=_NO_MATCH)
    out["question"] = "مراجعة مستند"
    out["document_citations"] = citations.summary(doc_claims)
    return _guard(out)


@router.post("/ask")
async def ask(body: Ask, settings: Settings = Depends(get_settings)):
    hits = _index().search(body.question, body.top_k)
    out = await compose_mod.compose(body.question, hits, settings, body.image,
                                    system=SYSTEM, no_match_note=_NO_MATCH)
    return _guard(out)


def _guard(out: dict) -> dict:
    """Run every answer through the citation guard before it leaves the gateway.

    Applied here rather than trusted to the prompt: rule-following is a tendency,
    and this is the one claim where a tendency is not good enough.
    """
    answer = out.get("answer") or ""
    if answer:
        redacted, claims = citations.redact(answer)
        out["citations"] = citations.summary(claims)
        if redacted != answer:
            out["answer_raw"] = answer
            out["answer"] = redacted
            bad = sum(1 for c in claims if c.verdict == citations.FABRICATED)
            unk = sum(1 for c in claims if c.verdict == citations.UNVERIFIABLE)
            bits = []
            if bad:
                bits.append(f"{bad} مادة مش موجودة في النصّ المحمّل — اتشالت")
            if unk:
                bits.append(f"{unk} مادة قانونها مش محمّل — اتعلّم عليها")
            out["note"] = (out.get("note") or "") + \
                ("  " if out.get("note") else "") + "🛡️ الحارس: " + " · ".join(bits) + "."
    else:
        out["citations"] = citations.summary([])
    out["disclaimer"] = ("مساعد صياغة وبحث — مش رأي قانوني ولا بديل عن محامٍ. "
                         "أي مستند قبل التوقيع يتراجع بشريًا.")
    return out


@router.post("/reindex")
async def reindex(settings: Settings = Depends(get_settings)):
    """اقرا مجلد النصوص من أول وجديد — بعد ما تحطّ قانون جديد."""
    n = corpus.reset()
    _reset_index()
    return {"reindexed": True, "chunks": n, **_state(settings)}
