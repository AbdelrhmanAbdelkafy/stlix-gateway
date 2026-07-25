"""The one guard that makes a legal assistant safe to put in front of anyone.

A wrong number on a finance page costs a bad decision. A wrong **article
number** in a legal answer costs a void clause, a lost case, or a contract that
does the opposite of what the person signing it believed. And it is the single
most likely thing a language model gets wrong about law: article numbers are
short, plausible, densely packed, and the model has read millions of them.

So this module does not ask the model to behave. It checks.

Every «مادة N» in an answer is pulled out, resolved to a law, and looked up in
what the corpus actually holds. Three verdicts:

- **`confirmed`** — that article is in a loaded statute. Stands.
- **`unverifiable`** — the law it cites is not loaded here. Cannot confirm,
  cannot deny; the claim is marked, not deleted, and the reader is told which
  file to load to settle it.
- **`fabricated`** — the law *is* loaded and that article is *not in it*. This
  is the only case with no innocent reading, and it is the reason the module
  exists. Redacted from the answer outright.

`redact()` rewrites the answer so an unconfirmed article can never be read as
authority: the number is replaced by a marker that says what happened. A footnote
would not do — people quote the body of a legal answer, not its footnotes.

Nothing here is confirmed against a contract or a bylaw, only against tier
`statute`. A clause in one of our own signed contracts proves what we agreed,
never what the law requires, and those two collapse into each other in the
mind of anyone reading at speed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..expert.retrieve import normalize
from . import corpus
from .manifest import EXPECTED

#: `مادة 147` · `المادة ١٤٧` · `للمادة 147` · `م. 147` · `مادة (147) مكرر`
#:
#: The attached prefix is part of the match on purpose. Arabic glues its
#: prepositions and its article onto the noun — «للمادة», «بالمادة», «والمادة» —
#: and matching only from «مادة» left the orphan letters behind when the
#: citation was struck out: «ده مخالف لل[مادة محذوفة]». A redaction that leaves
#: broken Arabic behind reads like a rendering bug, and a reader who thinks the
#: page is glitching does not read the warning in it.
_CITE = re.compile(
    # Not glued to the end of another word: the prefix must start a token.
    r"(?<![\u0621-\u064A])"
    r"(?:[\u0648\u0641\u0643\u0628]?(?:\u0644\u0644|\u0627\u0644|\u0644))?"  # و/ف/ك/ب + لل|ال|ل
    r"(?:\u0645\u0627\u062F\u0647|\u0645\u0627\u062F\u0629|\u0645\.)"        # ماده | مادة | م.
    # The closing bracket takes its own whitespace only if it is actually
    # there. Otherwise `مادة 9999 من` swallows the space after the number and
    # the redaction marker ends up glued to the next word.
    r"\s*[\(\[]?\s*([0-9\u0660-\u0669]{1,4})(?:\s*[\)\]])?"
    r"(\s*\u0645\u0643\u0631\u0631(?:\s*[0-9\u0660-\u0669]+)?)?"
)

#: How a law gets named in running Arabic text. Matched on normalised text, so
#: «القانون المدنى» and «القانون المدني» are one key. Longest first, because
#: «القانون المدني الصيني» must not resolve to the Egyptian civil code.
_ALIASES: tuple[tuple[str, str], ...] = (
    ("القانون المدني الصيني", "cn-civil-code"),
    ("قانون الشركات الصيني", "cn-company-law"),
    ("قانون التجاره الخارجيه الصيني", "cn-foreign-trade"),
    ("اتفاقيه نيويورك", "new-york-convention"),
    ("اتفاقيه فيينا", "cisg"),
    ("البيع الدولي للبضائع", "cisg"),
    ("cisg", "cisg"),
    ("انكوترمز", "incoterms"),
    ("incoterms", "incoterms"),
    ("قانون الاجراءات الجنائيه", "egraat-genaeya"),
    ("الاجراءات الجنائيه", "egraat-genaeya"),
    ("قانون الخدمه المدنيه", "khedma-madaniya"),
    ("الخدمه المدنيه", "khedma-madaniya"),
    ("قانون التامينات الاجتماعيه", "taminat"),
    ("التامينات الاجتماعيه", "taminat"),
    ("قانون حمايه البيانات الشخصيه", "hemayat-bayanat"),
    ("حمايه البيانات", "hemayat-bayanat"),
    ("قانون حمايه المنافسه", "monafasa"),
    ("حمايه المنافسه", "monafasa"),
    ("قانون التوقيع الالكتروني", "tawqee-electroni"),
    ("التوقيع الالكتروني", "tawqee-electroni"),
    ("ضريبه القيمه المضافه", "qema-modafa"),
    ("القيمه المضافه", "qema-modafa"),
    ("الضريبه علي الدخل", "dakhl"),
    ("ضريبه الدخل", "dakhl"),
    ("قانون الجمارك", "gamarek"),
    ("قانون الاستثمار", "estithmar"),
    ("قانون العقوبات", "oqubat"),
    ("قانون الشركات", "sharikat"),
    ("قانون التجاره", "tegari"),
    ("القانون التجاري", "tegari"),
    ("القانون المدني", "madani"),
    ("التقنين المدني", "madani"),
    ("قانون العمل", "amal"),
    ("الدستور", "dostor"),
    ("اللائحه الداخليه", "lawaeh-dakhiliya"),
)

_NAMES = {e.slug: e.name for e in EXPECTED}

CONFIRMED = "confirmed"
UNVERIFIABLE = "unverifiable"
FABRICATED = "fabricated"


@dataclass(frozen=True)
class Claim:
    """One «مادة N» found in a piece of text, and what became of it."""

    text: str          # exactly as written
    start: int
    end: int
    number: str        # normalised to Western digits
    suffix: str        # «مكرر» and friends, or ""
    law_slug: str      # "" when no law could be resolved
    law_name: str
    verdict: str
    note: str

    def as_dict(self) -> dict:
        return {"text": self.text, "number": self.number, "suffix": self.suffix,
                "law": self.law_name, "law_slug": self.law_slug,
                "verdict": self.verdict, "note": self.note}


def _law_at(norm: str, pos: int) -> str:
    """Which law the article at `pos` belongs to.

    Looks forward first — «مادة 147 من القانون المدني» is the explicit form and
    should win — then backwards to the nearest law named earlier, which is how
    people actually write once they have already said which code they mean.
    """
    ahead = norm[pos:pos + 90]
    for alias, slug in _ALIASES:
        if alias in ahead:
            return slug
    behind = norm[max(0, pos - 400):pos]
    best, best_at = "", -1
    for alias, slug in _ALIASES:
        at = behind.rfind(alias)
        if at > best_at:
            best, best_at = slug, at
    return best


def find(text: str) -> list[Claim]:
    """Every article claim in `text`, checked against the loaded statutes."""
    norm = normalize(text)
    have = corpus.statute_articles()
    loaded = corpus.loaded_slugs()
    out: list[Claim] = []
    for m in _CITE.finditer(text):
        number = corpus.arabic_int(m.group(1))
        suffix = (m.group(2) or "").strip()
        slug = _law_at(norm, m.end())
        name = _NAMES.get(slug, slug) if slug else "قانون غير محدَّد"
        if not slug:
            verdict = UNVERIFIABLE
            note = "ما حدّدش القانون، فمافيش حاجة أتأكد منها."
        elif slug not in loaded:
            verdict = UNVERIFIABLE
            note = f"نصّ «{name}» مش محمّل هنا — حمّله في corpus/legal وأتأكد."
        elif corpus.article_key(slug, number, suffix) in have:
            verdict = CONFIRMED
            note = ""
        else:
            verdict = FABRICATED
            note = (f"«{name}» محمّل عندي، ومفيهوش مادة {number}"
                    f"{' ' + suffix if suffix else ''}.")
        out.append(Claim(m.group(0), m.start(), m.end(), number, suffix,
                         slug, name, verdict, note))
    return out


def redact(text: str, claims: list[Claim] | None = None) -> tuple[str, list[Claim]]:
    """Rewrite `text` so no unconfirmed article can be read as authority.

    In the body, not a footnote. A legal answer gets copied into an email and
    sent; whatever qualification lives at the bottom does not travel with the
    sentence that gets quoted.
    """
    claims = find(text) if claims is None else claims
    out = text
    for c in sorted(claims, key=lambda c: c.start, reverse=True):
        if c.verdict == CONFIRMED:
            continue
        marker = ("[مادة محذوفة — مش موجودة في النصّ المحمّل]"
                  if c.verdict == FABRICATED
                  else f"[{c.law_name} — النصّ مش محمّل، الرقم مش متأكَّد منه]")
        out = out[:c.start] + marker + out[c.end:]
    return out, claims


def summary(claims: list[Claim]) -> dict:
    counts = {CONFIRMED: 0, UNVERIFIABLE: 0, FABRICATED: 0}
    for c in claims:
        counts[c.verdict] = counts.get(c.verdict, 0) + 1
    return {
        "total": len(claims),
        **counts,
        "clean": counts[FABRICATED] == 0,
        "claims": [c.as_dict() for c in claims],
    }
