"""المستشار القانوني — and above all, the guard on article numbers.

Most of this file is about one failure. A language model asked a legal question
produces article numbers the way it produces any other token: fluently, and
sometimes wrongly. «المادة 147 من القانون المدني» is four words that a
non-lawyer has no way to check and every reason to trust, and a wrong one voids
a clause or loses a case.

So the tests below do not check that the model was told to behave. They check
that a fabricated article cannot reach the reader even if it was.
"""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.catalog import get_connector, get_endpoint
from app.config import Settings
from app.integrations.legal import citations, corpus, templates
from app.integrations.legal.router import _reset_index
from app.main import app
from app.registry import SYSTEMS, Status

client = TestClient(app)

_MADANI = """---
slug: madani
title: القانون المدني المصري
tier: statute
jurisdiction: مصر
---
مادة 1 - تسري النصوص التشريعية على المسائل التي تتناولها في لفظها أو فحواها.

المادة (147) العقد شريعة المتعاقدين، فلا يجوز نقضه ولا تعديله إلا باتفاق
الطرفين أو للأسباب التي يقررها القانون.

مادة ١٤٨ يجب تنفيذ العقد طبقًا لما اشتمل عليه وبطريقة تتفق مع ما يوجبه حسن النية.
"""

_CONTRACT = """---
slug: oqoud-mowaqqaa
title: عقد إيجار ستليكس
tier: precedent
jurisdiction: مصر
---
البند الأول: يؤجر الطرف الأول للطرف الثاني الوحدة المبينة بالعقد.

البند الثاني: مدة الإيجار خمس سنوات تبدأ من تاريخ التسليم.
"""


@pytest.fixture()
def loaded(tmp_path, monkeypatch):
    """A corpus with one statute and one of our own contracts in it."""
    (tmp_path / "madani.txt").write_text(_MADANI, encoding="utf-8")
    (tmp_path / "lease.txt").write_text(_CONTRACT, encoding="utf-8")
    monkeypatch.setattr(corpus, "CORPUS", tmp_path)
    corpus.reset()
    _reset_index()
    yield tmp_path
    monkeypatch.undo()
    corpus.reset()
    _reset_index()


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


# --- parsing -----------------------------------------------------------------

def test_articles_are_addressable_one_by_one(loaded):
    """A statute indexed as one blob cannot answer «إيه نصّ المادة 147»."""
    assert corpus.statute_articles() >= {"madani#1", "madani#147", "madani#148"}


def test_arabic_indic_numerals_are_the_same_article(loaded):
    """Scanned Egyptian statutes are typeset with ١٤٨, people type 148."""
    assert "madani#148" in corpus.statute_articles()
    assert corpus.arabic_int("١٤٧") == "147"


def test_a_contract_contributes_no_articles(loaded):
    """Our own signed contract proves what we agreed, never what the law says.

    If a precedent could supply an article, a clause we wrote would start
    confirming citations about the law — which is the confusion this whole
    module exists to prevent.
    """
    assert not any(a.startswith("oqoud") for a in corpus.statute_articles())
    tiers = {c.kind for c in corpus.chunks()}
    assert "precedent" in tiers and "statute" in tiers


# --- the guard ---------------------------------------------------------------

def test_a_real_article_is_confirmed(loaded):
    claims = citations.find("العقد شريعة المتعاقدين طبقًا للمادة 147 من القانون المدني.")
    assert [c.verdict for c in claims] == [citations.CONFIRMED]
    assert claims[0].law_slug == "madani"


def test_an_article_that_is_not_in_the_loaded_law_is_called_fabricated(loaded):
    """The only verdict with no innocent reading: we hold the text, and the
    article is not in it."""
    claims = citations.find("راجع المادة 9999 من القانون المدني.")
    assert claims[0].verdict == citations.FABRICATED
    assert "مفيهوش مادة 9999" in claims[0].note


def test_an_article_of_an_unloaded_law_is_unverifiable_not_denied(loaded):
    """Absence of the text is not evidence the article is wrong — say which
    file would settle it instead of guessing either way."""
    claims = citations.find("طبقًا للمادة 47 من قانون العمل.")
    assert claims[0].verdict == citations.UNVERIFIABLE
    assert "قانون العمل" in claims[0].law_name


def test_an_article_with_no_named_law_cannot_be_checked(loaded):
    claims = citations.find("ده مخالف للمادة 12.")
    assert claims[0].verdict == citations.UNVERIFIABLE
    assert claims[0].law_slug == ""


def test_the_law_carries_forward_to_later_articles(loaded):
    """People name the code once and then keep citing articles."""
    claims = citations.find(
        "القانون المدني بيقول في المادة 147 كذا، وكمان المادة 148 بتقول كذا.")
    assert [c.law_slug for c in claims] == ["madani", "madani"]
    assert all(c.verdict == citations.CONFIRMED for c in claims)


def test_the_chinese_civil_code_is_not_the_egyptian_one(loaded):
    """Alias matching is longest-first for exactly this reason: «القانون المدني
    الصيني» contains «القانون المدني» as a substring."""
    claims = citations.find("المادة 147 من القانون المدني الصيني.")
    assert claims[0].law_slug == "cn-civil-code"
    assert claims[0].verdict == citations.UNVERIFIABLE


def test_arabic_indic_digits_in_a_citation_resolve(loaded):
    claims = citations.find("المادة ١٤٧ من القانون المدني.")
    assert claims[0].number == "147" and claims[0].verdict == citations.CONFIRMED


def test_redaction_happens_in_the_sentence_not_in_a_footnote(loaded):
    """A legal answer gets copied into an email. Whatever qualification lives at
    the bottom of the page does not travel with the sentence that gets quoted.
    """
    text = "ده مخالف للمادة 9999 من القانون المدني، وصحيح طبقًا للمادة 147 منه."
    out, claims = citations.redact(text)
    assert "9999" not in out
    assert "مادة محذوفة" in out
    assert "147" in out, "a confirmed article must survive untouched"
    assert citations.summary(claims)["clean"] is False


def test_nothing_is_confirmed_when_the_corpus_is_empty():
    """The shipped state. Every citation is unverifiable, none is endorsed."""
    corpus.reset()
    claims = citations.find("المادة 147 من القانون المدني.")
    assert claims[0].verdict == citations.UNVERIFIABLE
    out, _ = citations.redact("المادة 147 من القانون المدني.")
    assert "147" not in out


# --- coverage: the useful half of an empty corpus ----------------------------

def test_the_missing_laws_are_named():
    """«مالقيتش حاجة» is useless. «ده محكوم بقانون العمل ونصّه مش عندي» is not."""
    corpus.reset()
    st = corpus.stats()
    assert st["expected"] > 15
    assert "قانون العمل" in st["missing"]
    assert st["loaded_of_expected"] == 0


def test_the_manifest_states_no_law_numbers():
    """Law numbers get read out of a loaded text, never typed from memory.

    Writing «131 لسنة 1948» into a Python file is the same act this platform
    spent a session deleting from the finance pages, in the domain where being
    wrong costs most.
    """
    from app.integrations.legal import manifest
    import re
    src = (manifest.__file__)
    body = open(src, encoding="utf-8").read()
    entries = re.findall(r'Expected\(\s*"[^"]+",\s*"([^"]+)"', body)
    assert entries, "no manifest entries parsed — the check is not running"
    for name in entries:
        assert not re.search(r"\d{2,}", name), f"a law number crept into: {name}"


# --- templates ---------------------------------------------------------------

def test_no_template_cites_an_article():
    """A template is not model output, so it would sail straight past the guard.

    That makes it the one place an invented article number could still reach a
    signed document.
    """
    offenders = []
    for t in templates.TEMPLATES:
        rendered = templates.render(t.key, {}, include_optional=True)
        for c in citations.find(rendered["markdown"]):
            offenders.append((t.key, c.text))
    assert not offenders, f"templates citing articles: {offenders}"


def test_an_unfilled_blank_stays_visible():
    """A contract that reads finished while a party name silently vanished is
    worse than one with an obvious hole in it."""
    out = templates.render("nda", {"party_a": "ستليكس فالي"})
    assert "ستليكس فالي" in out["markdown"]
    assert "⟨الطرف الثاني⟩" in out["markdown"]
    assert any(f["key"] == "party_b" for f in out["missing_fields"])


def test_every_template_ends_with_what_a_human_must_check():
    for t in templates.TEMPLATES:
        assert t.check, f"{t.key} has no human-review checklist"
        assert any("محام" in c for c in t.check), f"{t.key} never says to get a lawyer"


def test_every_template_names_the_law_that_governs_it():
    from app.integrations.legal.manifest import BY_SLUG
    for t in templates.TEMPLATES:
        assert t.governed_by, t.key
        for slug in t.governed_by:
            assert slug in BY_SLUG, f"{t.key} points at unknown law {slug}"


# --- the model path ----------------------------------------------------------

def _reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"model": "test",
                                     "content": [{"type": "text", "text": text}]})


@respx.mock
def test_a_fabricated_article_never_reaches_the_reader(loaded, monkeypatch):
    """The test this module exists for.

    The model is told not to invent articles. Here it does anyway — and the
    answer that comes out of the gateway does not contain the number.
    """
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_reply("طبقًا للمادة 9999 من القانون المدني ده باطل [S1]."))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        r = client.post("/api/v1/legal/ask", json={"question": "العقد شريعة المتعاقدين"})
        d = r.json()
        assert "9999" not in d["answer"]
        assert "9999" in d["answer_raw"], "the original must be kept for audit"
        assert d["citations"]["fabricated"] == 1
        assert "الحارس" in d["note"]
    finally:
        get_settings.cache_clear()


@respx.mock
def test_a_confirmed_article_passes_through_untouched(loaded, monkeypatch):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_reply("المادة 147 من القانون المدني بتقول كده [S1]."))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        d = client.post("/api/v1/legal/ask", json={"question": "العقد شريعة المتعاقدين"}).json()
        assert "147" in d["answer"]
        assert "answer_raw" not in d
        assert d["citations"]["confirmed"] == 1 and d["citations"]["clean"] is True
    finally:
        get_settings.cache_clear()


def test_with_no_model_it_returns_provisions_not_prose(loaded):
    d = client.post("/api/v1/legal/ask", json={"question": "العقد شريعة المتعاقدين"}).json()
    assert d["answer"] == ""
    assert d["sources"], "it must at least hand over the provisions it found"
    assert d["disclaimer"]


def test_an_empty_corpus_says_which_file_would_answer():
    corpus.reset()
    _reset_index()
    d = client.post("/api/v1/legal/ask", json={"question": "مدة الإخطار في إنهاء عقد العمل"}).json()
    assert d["mode"] == "no_match"
    assert "corpus/legal" in d["note"]


# --- routes ------------------------------------------------------------------

def test_verify_runs_with_no_model_and_no_network(loaded):
    r = client.post("/api/v1/legal/verify",
                    json={"text": "المادة 147 والمادة 9999 من القانون المدني."})
    d = r.json()
    assert d["confirmed"] == 1 and d["fabricated"] == 1
    assert "9999" not in d["redacted"]


def test_verify_works_on_text_we_did_not_write(loaded):
    """Point it at the other side's draft — that is half its value."""
    d = client.post("/api/v1/legal/verify", json={
        "text": "يقر الطرفان بخضوع العقد للمادة 500 من القانون المدني."}).json()
    assert d["fabricated"] == 1


def test_coverage_lists_loaded_and_missing(loaded):
    d = client.get("/api/v1/legal/coverage?format=json").json()
    slugs = {r["slug"]: r for r in d["rows"]}
    assert slugs["madani"]["loaded"] is True and slugs["madani"]["articles"] == 3
    assert slugs["amal"]["loaded"] is False


def test_one_law_can_be_read(loaded):
    d = client.get("/api/v1/legal/law/madani?format=json").json()
    assert d["articles"] == 3
    assert client.get("/api/v1/legal/law/amal").status_code == 404


def test_draft_returns_a_document_and_its_checklist():
    d = client.post("/api/v1/legal/draft",
                    json={"template": "import-purchase",
                          "values": {"party_b": "Foshan Amax"}}).json()
    assert "Foshan Amax" in d["markdown"]
    assert d["check"] and d["citations"]["total"] == 0
    assert client.post("/api/v1/legal/draft", json={"template": "nope"}).status_code == 404


def test_review_checks_the_document_own_citations(loaded):
    d = client.post("/api/v1/legal/review", json={
        "text": "البند الأول: يخضع هذا العقد للمادة 9999 من القانون المدني. " * 3,
        "kind": "عقد توريد"}).json()
    assert d["document_citations"]["fabricated"] >= 1


def test_search_needs_no_model(loaded):
    d = client.get("/api/v1/legal/search?q=العقد شريعة المتعاقدين&format=json").json()
    assert d["count"] > 0


def test_reindex_picks_up_a_new_file(loaded, tmp_path):
    before = client.get("/api/v1/legal?format=json").json()["corpus"]["statute_articles"]
    (tmp_path / "extra.txt").write_text(
        "---\nslug: oqubat\ntitle: قانون العقوبات\ntier: statute\n---\nمادة 336 النصب.\n",
        encoding="utf-8")
    after = client.post("/api/v1/legal/reindex").json()["corpus"]["statute_articles"]
    assert after == before + 1
    assert citations.find("المادة 336 من قانون العقوبات")[0].verdict == citations.CONFIRMED


# --- the map -----------------------------------------------------------------

def test_the_counsel_is_on_the_map():
    assert get_connector("legal").live is True
    for p in ("/api/v1/legal", "/api/v1/legal/coverage", "/api/v1/legal/verify",
              "/api/v1/legal/draft", "/api/v1/legal/law/{slug}", "/tools/legal"):
        assert get_endpoint(p) is not None, f"{p} missing from the catalogue"
    assert next(s for s in SYSTEMS if s.key == "legal").status is Status.LIVE


def test_the_page_holds_no_secret_and_calls_nobody_else():
    import re
    body = client.get("/tools/legal").text
    code = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    assert "/api/v1/legal/verify" in code
    assert "anthropic" not in code.lower()
    assert not re.findall(r'fetch\(\s*["\']https?://', code)


def test_the_page_says_it_is_not_a_lawyer():
    body = client.get("/tools/legal").text
    assert "مش رأي قانوني" in body or "بديل عن محام" in body
