"""Nama Expert: what it knows, how it finds it, and what it does when it can't.

The tests worth having here are not "does the endpoint return 200". They are the
two ways an expert fails quietly:

* it answers from nothing and sounds right — locked by the sources_only path and
  by the citation check;
* it cannot find the passage that holds the answer, so the model never sees it —
  locked by the retrieval cases below, each of which is a question the owner has
  actually asked.
"""
from __future__ import annotations

import re

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.catalog import get_connector, get_endpoint
from app.config import Settings
from app.integrations.expert import answer as answer_mod
from app.integrations.expert import knowledge, retrieve
from app.main import app
from app.registry import SYSTEMS, Status

client = TestClient(app)


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


# --- the corpus --------------------------------------------------------------

def test_the_index_holds_both_the_documents_and_the_map():
    """Either half alone leaves a blind spot.

    Documents without the map cannot answer "which endpoint serves this"; the
    map without documents cannot answer "why does Nama behave like that".
    """
    kinds = knowledge.stats()["by_kind"]
    for kind in ("doc", "system", "connector", "endpoint", "idea"):
        assert kinds.get(kind, 0) > 0, f"nothing indexed of kind {kind}"


def test_every_chunk_carries_a_source_and_somewhere_to_open():
    """An answer's citation is only worth anything if it resolves."""
    for c in knowledge.get_index():
        assert c.ref and c.source, f"chunk without provenance: {c.id}"
        assert c.link.startswith("/") or c.link.startswith("http"), c.link


def test_the_backlog_is_indexed_row_by_row():
    """One backlog row is one requirement. Indexed as a single 200-row blob it
    retrieves everything and answers nothing."""
    rows = [c for c in knowledge.get_index()
            if c.source == "BACKLOG.md" and c.kind == "doc"]
    assert len(rows) > 50, f"backlog collapsed into {len(rows)} chunks"


# --- Arabic ------------------------------------------------------------------

def test_the_mark_stripper_does_not_eat_arabic_letters():
    """The regression this guards is silent and total.

    Arabic letters (U+0621–U+064A) sit between two blocks of diacritics. A range
    written one codepoint too wide deletes the alphabet, every document
    tokenises to nothing, and retrieval returns nothing for every question —
    with no error anywhere.
    """
    assert retrieve.normalize("فاتورة") == "فاتوره"
    assert retrieve.tokens("نما") == ["نما"]
    assert retrieve.tokens("مستند") == ["مستند"]


def test_the_same_word_spelled_two_ways_is_one_term():
    """«العهدة» and «العهده» are the same word typed in a hurry."""
    assert retrieve.tokens("العهدة") == retrieve.tokens("العهده")
    assert retrieve.tokens("إزاي") == retrieve.tokens("ازاي")
    assert retrieve.tokens("الفاتورة") == retrieve.tokens("فاتورة")


def test_tashkeel_and_tatweel_are_ignored():
    assert retrieve.tokens("مُستنَد") == retrieve.tokens("مستند")
    assert retrieve.tokens("نـــما") == retrieve.tokens("نما")


def test_punctuation_is_not_a_term():
    assert "،" not in retrieve.tokens("فاتورة، ومستند؟")


# --- retrieval ---------------------------------------------------------------

def _sources(hits) -> set[str]:
    return {h.chunk.source for h in hits}


def test_a_where_question_finds_the_address_not_an_essay():
    """«الشهادة فين» should surface the route, which is the actual answer."""
    hits = retrieve.search("الشهاده بتاعه الاستيراد فين", 6)
    links = {h.chunk.link for h in hits}
    assert "/tools/certificate" in links


def test_a_nama_rule_question_finds_the_rule():
    hits = retrieve.search("ليه pageSize بيقطع في نما", 6)
    assert any("pageSize" in h.chunk.text for h in hits), \
        f"pageSize rule not retrieved; got {[h.chunk.title for h in hits]}"


def test_question_scaffolding_does_not_outrank_the_subject():
    """In a corpus of formal documents the colloquial «ليه» is as rare as
    `pageSize`, so plain IDF rated them equally informative and a chunk matching
    only «ليه … نما» beat the one chunk that explains the truncation. Rarity is
    not aboutness."""
    assert "ليه" not in retrieve._content_terms(retrieve.tokens("ليه بيقطع"))
    # …unless scaffolding is all there is, in which case searching for it beats
    # searching for nothing.
    assert retrieve._content_terms(retrieve.tokens("ليه")) == ["ليه"]


def test_one_section_cannot_take_every_slot():
    """A question about customer balances came back as six consecutive rows of
    one table, so the model never saw the endpoint that serves them."""
    hits = retrieve.search("أرصدة العملاء بتيجي منين وازاي اشوفها", 6)
    keys = [f"{h.chunk.source}|{h.chunk.title.split(' · ')[0]}" for h in hits]
    worst = max(keys.count(k) for k in set(keys))
    assert worst <= 3, f"one section took {worst} of {len(hits)} slots"


def test_an_unrelated_question_returns_nothing_rather_than_the_nearest_thing():
    assert retrieve.search("zzzqqqxx", 5) == []


# --- the honest path: no model attached --------------------------------------

@pytest.mark.asyncio
async def test_with_no_key_it_returns_passages_and_says_so():
    """The rule the whole platform rests on, applied to prose: a figure that is
    old is bad, one that is wrong is far worse. With no model, the expert hands
    over its evidence instead of writing something that reads like knowledge."""
    hits = retrieve.search("قواعد الكتابة في نما", 4)
    out = await answer_mod.compose("قواعد الكتابة في نما", hits, _settings())
    assert out["mode"] == "sources_only"
    assert out["grounded"] is False
    assert out["answer"] == ""
    assert out["sources"], "it must at least hand back what it found"
    assert "مفيش موديل" in out["note"]


@pytest.mark.asyncio
async def test_no_match_says_no_match():
    out = await answer_mod.compose("zzzqqqxx", [], _settings())
    assert out["mode"] == "no_match"
    assert out["answer"] == ""
    assert "reindex" in out["note"]


# --- the grounded path -------------------------------------------------------

def _reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"model": "test-model",
                                     "content": [{"type": "text", "text": text}]})


@pytest.mark.asyncio
@respx.mock
async def test_a_grounded_answer_reports_which_sources_it_used():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_reply("الجواب كده [S1] وكمان [S3]."))
    hits = retrieve.search("قواعد الكتابة في نما", 4)
    out = await answer_mod.compose("قواعد الكتابة في نما", hits,
                                   _settings(anthropic_api_key="k"))
    assert route.called
    assert out["mode"] == "grounded" and out["grounded"] is True
    assert out["cited"] == ["S1", "S3"]
    assert out["note"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_the_key_goes_in_the_header_and_the_passages_go_in_the_body():
    """The browser never holds this credential — the gateway does."""
    captured = {}

    def _capture(request):
        captured["key"] = request.headers.get("x-api-key")
        captured["version"] = request.headers.get("anthropic-version")
        captured["body"] = request.content.decode()
        return _reply("تمام [S1].")

    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
    hits = retrieve.search("قواعد الكتابة في نما", 3)
    await answer_mod.compose("سؤال", hits, _settings(anthropic_api_key="secret-key"))
    assert captured["key"] == "secret-key"
    assert captured["version"] == "2023-06-01"
    assert "[S1]" in captured["body"], "the passages must be sent, not just the question"


@pytest.mark.asyncio
@respx.mock
async def test_an_answer_with_no_citation_is_flagged_not_passed_off():
    """Citing nothing breaks the expert's own rule. Saying so lets the reader
    weigh it; staying quiet is how an ungrounded answer becomes a fact."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_reply("أنا متأكد إن ده الحل."))
    hits = retrieve.search("قواعد الكتابة في نما", 3)
    out = await answer_mod.compose("س", hits, _settings(anthropic_api_key="k"))
    assert out["cited"] == []
    assert "استشهاد" in out["note"]


@pytest.mark.asyncio
@respx.mock
async def test_a_model_that_is_down_degrades_to_sources_rather_than_to_a_500():
    """The passages are still useful; an error page is not."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(529, text="overloaded"))
    hits = retrieve.search("قواعد الكتابة في نما", 3)
    out = await answer_mod.compose("س", hits, _settings(anthropic_api_key="k"))
    assert out["mode"] == "sources_only"
    assert out["sources"]
    assert "529" in out["note"]


@pytest.mark.asyncio
@respx.mock
async def test_a_transport_failure_also_degrades():
    respx.post("https://api.anthropic.com/v1/messages").mock(
        side_effect=httpx.ConnectError("no route"))
    hits = retrieve.search("قواعد الكتابة في نما", 3)
    out = await answer_mod.compose("س", hits, _settings(anthropic_api_key="k"))
    assert out["mode"] == "sources_only" and out["grounded"] is False


# --- screenshots -------------------------------------------------------------

def test_a_pasted_screenshot_is_understood_in_both_shapes():
    """Browsers hand over a data URI; a script may send bare base64."""
    uri = answer_mod._image_block("data:image/jpeg;base64,QUJD")
    assert uri["source"]["media_type"] == "image/jpeg"
    assert uri["source"]["data"] == "QUJD"
    bare = answer_mod._image_block("QUJD")
    assert bare["source"]["media_type"] == "image/png"
    assert answer_mod._image_block("") is None
    # `image/jpg` is not a media type the API accepts.
    assert answer_mod._image_block(
        "data:image/jpg;base64,QUJD")["source"]["media_type"] == "image/jpeg"


@pytest.mark.asyncio
@respx.mock
async def test_the_screenshot_reaches_the_model_as_an_image_block():
    captured = {}

    def _capture(request):
        captured["body"] = request.content.decode()
        return _reply("قريت الصورة [S1].")

    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
    hits = retrieve.search("قواعد الكتابة في نما", 2)
    out = await answer_mod.compose("إيه ده", hits, _settings(anthropic_api_key="k"),
                                   image="data:image/png;base64,QUJD")
    assert '"type": "image"' in captured["body"] or '"type":"image"' in captured["body"]
    assert out["had_image"] is True


# --- the routes --------------------------------------------------------------

def test_status_reports_the_index_and_the_mode():
    r = client.get("/api/v1/expert?format=json")
    assert r.status_code == 200
    d = r.json()
    assert d["index"]["chunks"] > 0
    assert d["mode"] in ("grounded", "sources_only")
    assert d["endpoints"]["page"] == "/tools/expert"


def test_search_needs_no_model_and_returns_links():
    r = client.get("/api/v1/expert/search?q=الشهاده فين&format=json")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] > 0
    assert all(h["link"] for h in d["results"])
    assert [h["id"] for h in d["results"]] == [f"S{i}" for i in range(1, d["count"] + 1)]


def test_ask_answers_without_a_model_configured():
    r = client.post("/api/v1/expert/ask", json={"question": "قواعد الكتابة في نما"})
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] in ("sources_only", "grounded")
    assert d["sources"]


def test_ask_rejects_an_empty_question():
    assert client.post("/api/v1/expert/ask", json={"question": "x"}).status_code == 422


def test_reindex_rebuilds():
    r = client.post("/api/v1/expert/reindex")
    assert r.status_code == 200 and r.json()["reindexed"] is True
    assert r.json()["index"]["chunks"] > 0


# --- the map agrees with itself ----------------------------------------------

def test_the_expert_is_on_the_map():
    """A module the platform cannot describe is a module nobody finds."""
    assert get_connector("expert").live is True
    for path in ("/api/v1/expert", "/api/v1/expert/search",
                 "/api/v1/expert/ask", "/api/v1/expert/reindex", "/tools/expert"):
        assert get_endpoint(path) is not None, f"{path} missing from the catalogue"


def test_the_ai_system_is_live_but_the_orchestrator_is_not():
    """Two different claims. The expert reads and cites; the orchestrator would
    act across connectors, and it does not exist."""
    ai = next(s for s in SYSTEMS if s.key == "ai")
    assert ai.status is Status.LIVE
    assert get_connector("ai-layer").live is False


def test_the_chat_page_is_served_with_the_key_injected_and_no_other_secret():
    """The page talks to the gateway and to nothing else.

    Checked against the code, not the comments: the comments explain *why* the
    Anthropic credential stays server-side, and a naive substring search on the
    whole file fails on its own explanation — the same trap that made the
    certificate's QR fix take three attempts.
    """
    r = client.get("/tools/expert")
    assert r.status_code == 200
    code = re.sub(r"<!--.*?-->", " ", r.text, flags=re.S)
    assert "/api/v1/expert/ask" in code
    assert "anthropic" not in code.lower(), "the page must not reach the model directly"
    assert "sk-ant" not in r.text
    # The only outbound addresses are this gateway's own.
    assert not re.findall(r'fetch\(\s*["\']https?://', code)


def test_the_chat_page_offers_voice_and_screenshots():
    body = client.get("/tools/expert").text
    assert "webkitSpeechRecognition" in body and "ar-EG" in body
    assert "readAsDataURL" in body and "paste" in body
