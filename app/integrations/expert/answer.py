"""Turning retrieved passages into an answer — or refusing to.

Two modes, and the second one is the reason this module is worth reading.

**grounded** — an Anthropic key is configured *server-side*. The question, the
retrieved passages and (optionally) a screenshot go out from the gateway; the
browser never holds the key. The model is instructed that the passages are the
only permitted ground, that every claim carries the `[S#]` it came from, and
that «مش عارف» is a correct answer.

**sources_only** — no key configured. The expert returns the passages it found,
ranked, with their links, and says plainly that no model is attached. It does
not paraphrase them into something that reads like an answer.

That second mode exists because of the rule this whole platform is built around:
a figure that is old is bad, a figure that is wrong is far worse. An expert that
invents a Nama field name under pressure is the same failure wearing a different
hat — so when it cannot ground an answer it hands over its evidence instead.
"""
from __future__ import annotations

import re

import httpx

from ...config import Settings
from .retrieve import Hit

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"

# Datauri prefix a browser produces when a screenshot is pasted in.
_DATAURI = re.compile(r"^data:(image/(?:png|jpeg|jpg|gif|webp));base64,(.+)$", re.S)

SYSTEM = """\
إنت «Nama Expert» — الخبير الداخلي لمنصّة ستليكس. بتشتغل جوّه STLIX Gateway.

قواعدك، وهي مش قابلة للتفاوض:

1. مصدرك الوحيد هو المقاطع المرقّمة تحت (S1، S2 …). ما تجاوبش من حفظك عن نما ولا
   عن المنصّة. لو المقاطع مافيهاش الإجابة، قول «مش عارف» وقول إيه المستند أو الـ
   endpoint اللي محتاجينه — «مش عارف» إجابة صح ومقبولة.
2. كل جملة فيها معلومة تنتهي بمصدرها بين قوسين مربعين: [S2]. جملة من غير مصدر
   ممنوعة.
3. **ما تنطقش رقم فلوس ولا عدد ولا تاريخ إلا لو مكتوب حرفيًا في مقطع.** ومعاه
   المصدر. لو المستخدم عايز رقم حيّ، دلّه على الـ endpoint اللي بيرجّعه بدل ما
   تخمّنه.
4. لو الجواب فيه كتابة في نما (إنشاء/تعديل/حذف): اقترحها كخطوة محتاجة workflow
   مدقّق وموافقة بشرية. كل الكنكتورات read-only بشكل افتراضي — ما تقولش «اعمل
   كذا» كأنه هيتنفّذ.
5. اتكلّم عربي مصري مختصر. أسماء الحقول والكيانات والـ endpoints بالإنجليزي زي
   ما هي.
6. لو معاك صورة (سكرين شوت من نما): اقرا رسالة الإرور اللي فيها بالحرف قبل أي
   تفسير، وقول إنت قريت إيه — فيه فرق بين «الصورة بتقول X» و«أنا فاكر إن X».

الشكل: إجابة قصيرة الأول، بعدين الخطوات لو فيه خطوات، وبعدين سطر «الناقص» لو
لسه فيه حاجة مش متأكد منها.
"""


def _passages(hits: list[Hit]) -> str:
    return "\n\n".join(
        f"[S{i}] ({h.chunk.kind} · {h.chunk.ref})\n{h.chunk.title}\n{h.chunk.text}"
        for i, h in enumerate(hits, 1)
    )


def _image_block(image: str) -> dict | None:
    """Accept either a full data URI or bare base64 (assume PNG)."""
    if not image:
        return None
    m = _DATAURI.match(image.strip())
    media, data = (m.group(1), m.group(2)) if m else ("image/png", image.strip())
    if media == "image/jpg":
        media = "image/jpeg"
    return {"type": "image",
            "source": {"type": "base64", "media_type": media, "data": data}}


def cited_ids(text: str) -> list[str]:
    """Which [S#] markers the answer actually used — the check on rule 2."""
    return sorted(set(re.findall(r"\[S(\d+)\]", text)), key=int)


async def compose(question: str, hits: list[Hit], settings: Settings,
                  image: str = "") -> dict:
    """Answer `question` from `hits`, or hand back the evidence.

    Never raises on an upstream failure: a model that is down produces
    `mode="sources_only"` with the reason attached, because the passages are
    still useful and a 500 is not.
    """
    base = {
        "question": question,
        "sources": [h.as_dict(i) for i, h in enumerate(hits, 1)],
        "had_image": bool(image),
    }
    if not hits:
        return {**base, "mode": "no_match", "grounded": False, "answer": "",
                "note": "مالقيتش أي مقطع في المصادر يخصّ السؤال ده. "
                        "جرّب صيغة تانية، أو ضيف الوثيقة الناقصة للريبو "
                        "وشغّل /api/v1/expert/reindex."}

    if not settings.anthropic_api_key:
        return {**base, "mode": "sources_only", "grounded": False, "answer": "",
                "note": "مفيش موديل موصول (ANTHROPIC_API_KEY فاضي) — دي المقاطع "
                        "اللي المصادر بتقولها في الموضوع ده، من غير أي صياغة "
                        "زيادة من عندي."}

    content: list[dict] = []
    img = _image_block(image)
    if img:
        content.append(img)
    content.append({"type": "text", "text":
                    f"المقاطع المتاحة:\n\n{_passages(hits)}\n\n---\n\nالسؤال: {question}"})

    try:
        async with httpx.AsyncClient(timeout=settings.expert_timeout) as client:
            r = await client.post(
                _API,
                headers={"x-api-key": settings.anthropic_api_key,
                         "anthropic-version": _VERSION,
                         "content-type": "application/json"},
                json={"model": settings.expert_model,
                      "max_tokens": settings.expert_max_tokens,
                      "system": SYSTEM,
                      "messages": [{"role": "user", "content": content}]},
            )
        if r.status_code != 200:
            detail = r.text[:400]
            return {**base, "mode": "sources_only", "grounded": False, "answer": "",
                    "note": f"الموديل ردّ {r.status_code} — بعرض المصادر بس. {detail}"}
        payload = r.json()
    except Exception as exc:  # noqa: BLE001 - upstream shape is not ours to trust
        return {**base, "mode": "sources_only", "grounded": False, "answer": "",
                "note": f"مافيش وصول للموديل ({type(exc).__name__}) — بعرض المصادر بس."}

    text = "".join(b.get("text", "") for b in payload.get("content", [])
                   if b.get("type") == "text").strip()
    used = cited_ids(text)
    return {**base, "mode": "grounded", "grounded": True, "answer": text,
            "cited": [f"S{i}" for i in used],
            "model": payload.get("model", settings.expert_model),
            # An answer that cites nothing broke rule 2. Say so rather than
            # letting it pass as grounded — the reader can then weigh it.
            "note": "" if used else
                    "⚠️ الجواب ده مافيهوش استشهاد بمصدر — اقراه بحذر وراجع المقاطع تحت."}
