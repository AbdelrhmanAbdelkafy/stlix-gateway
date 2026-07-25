"""Nama Expert endpoints — ask, search, sources, reindex.

`/search` is a GET on purpose: it is pure retrieval, it needs no model and no
credential beyond the gateway's own, so it stays reachable from a plain link on
any page (the `sg_key` cookie covers GET). `/ask` is a POST — it can send a
screenshot upstream, and it must carry the header, not an ambient cookie.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ...config import Settings, get_settings
from ...core.render import respond
from ...core.security import require_api_key
from . import answer as compose_mod
from . import knowledge, retrieve

router = APIRouter(prefix="/expert", tags=["expert"],
                   dependencies=[Depends(require_api_key)])

_MAX_IMAGE_CHARS = 6_000_000  # ~4.5 MB decoded — a screenshot, not a video.


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    #: Data URI or bare base64. A screenshot of the Nama error, usually.
    image: str = Field(default="", max_length=_MAX_IMAGE_CHARS)
    top_k: int = Field(default=6, ge=1, le=20)


def _state(settings: Settings) -> dict:
    st = knowledge.stats()
    attached = bool(settings.anthropic_api_key)
    return {
        "expert": "Nama Expert",
        "index": st,
        "model_attached": attached,
        "model": settings.expert_model if attached else "",
        "mode": "grounded" if attached else "sources_only",
        "rules": [
            "الإجابة من المصادر بس — ومعاها المصدر [S#]",
            "«مش عارف» إجابة مقبولة",
            "ما ينطقش رقم مش مكتوب في مصدر",
            "أي كتابة = اقتراح محتاج workflow وموافقة بشرية",
            "المفتاح server-side — المتصفح ما بياخدش سرّ",
        ],
        "endpoints": {
            "ask": "POST /api/v1/expert/ask",
            "search": "GET /api/v1/expert/search?q=",
            "reindex": "POST /api/v1/expert/reindex",
            "page": "/tools/expert",
        },
    }


@router.get("")
async def status(request: Request, settings: Settings = Depends(get_settings)):
    """What the expert can see, and whether a model is attached to it."""
    data = _state(settings)
    st = data["index"]
    rows = [{"metric": "مقاطع مفهرسة", "value": st["chunks"]},
            {"metric": "وثائق", "value": len(st["documents"])},
            {"metric": "حروف", "value": st["characters"]},
            {"metric": "موديل موصول", "value": "أيوه" if data["model_attached"] else "لأ"},
            {"metric": "الوضع", "value": data["mode"]},
            {"metric": "الصفحة", "value": "/tools/expert"}]
    rows += [{"metric": f"نوع: {k}", "value": v} for k, v in st["by_kind"].items()]
    return respond(request, data, title="Nama Expert", rows=rows,
                   columns=["metric", "value"])


@router.get("/search")
async def search(request: Request, q: str = Query(min_length=2, max_length=4000),
                 top_k: int = Query(default=8, ge=1, le=20)):
    """Retrieval only — the passages, with no model in the loop.

    This is the floor the expert can never fall below: it works with nothing
    configured, and its output is reproducible from the repo alone.
    """
    hits = retrieve.search(q, top_k)
    rows = [{"id": f"S{i}", "score": round(h.score, 2), "kind": h.chunk.kind,
             "title": h.chunk.title, "link": h.chunk.link}
            for i, h in enumerate(hits, 1)]
    return respond(request, {"query": q, "count": len(hits),
                             "results": [h.as_dict(i) for i, h in enumerate(hits, 1)]},
                   title=f"بحث الخبير · {q}", rows=rows,
                   columns=["id", "score", "kind", "title", "link"])


@router.post("/ask")
async def ask(body: Ask, settings: Settings = Depends(get_settings)):
    """Ask a question, optionally with a screenshot. JSON only — this is the
    chat page's endpoint, and a table of one answer helps nobody."""
    hits = retrieve.search(body.question, body.top_k)
    return await compose_mod.compose(body.question, hits, settings, body.image)


@router.post("/reindex")
async def reindex(settings: Settings = Depends(get_settings)):
    """Re-read the repo. Needed after a document changes while the server is up."""
    knowledge.reset()
    retrieve.reset()
    return {"reindexed": True, **_state(settings)}
