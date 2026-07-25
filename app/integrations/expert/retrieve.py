"""Finding the passages that bear on a question — in Arabic, offline.

BM25 over the corpus in `knowledge.py`. No embedding service, for three reasons
that all matter here: it would need a third credential and a network round-trip
on every question, it would make `/api/v1/expert/search` fail on a machine with
nothing configured, and it would make retrieval unreproducible — the same
question could return different passages tomorrow with no change in the repo.
Lexical scoring is weaker at paraphrase and stronger at everything this corpus
is made of: entity names, endpoint paths, backlog ids, Nama field names.

The Arabic handling is the part that earns its keep. Egyptian Arabic typed in a
hurry spells the same word several ways — «العهده / العهدة», «إزاي / ازاي» — so
both sides are normalised identically before a single token is compared.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .knowledge import Chunk, get_index

# Tashkeel, the honorific marks, superscript alef, and tatweel. Written as
# escapes on purpose: spelled as literal characters these ranges are
# impossible to review, and a range one codepoint too wide here silently
# deletes the Arabic letters themselves — U+0621–U+064A sit directly
# between two blocks of marks.
_MARKS = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
# Alef forms → ا · alef maqsura → ي · ta marbuta → ه · hamza carriers → base.
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي",
                       "ة": "ه", "ؤ": "و", "ئ": "ي"})
# Latin/digits, or Arabic letters and Arabic-Indic digits. Punctuation is
# not a token.
_TOKEN = re.compile("[a-zA-Z0-9_]+|[\u0621-\u064A\u0660-\u0669]+")

# The definite article is stripped from words long enough to survive it, so
# «الفاتورة» and «فاتورة» are one term. Applied to query and document alike.
_AL_MIN = 5

_K1 = 1.5
# Lower than the textbook 0.75 on purpose: chunk sizes here run from a
# one-line backlog row to a 6 KB decision entry, and a full-strength length
# penalty buries the long chunk that actually contains the rule.
_B = 0.5

# The scaffolding of a spoken Egyptian question. Dropped from the *query* only —
# the corpus keeps them, so document frequencies stay honest.
#
# This exists because of a real misranking: in a corpus of formal documents the
# colloquial «ليه» is as rare as «pageSize», so IDF rated them equally
# informative and a chunk matching only «ليه … نما» outranked the one chunk that
# actually explains why pageSize truncates. Rarity is not the same as aboutness.
_STOP = frozenset("""
ليه ايه ازاي فين امتى مين هو هي هم انا احنا انت انتوا ده دي دول اللي الي
في من الى على عن مع عند بعد قبل تحت فوق بين
و او ام لو ان اذا يعني بس كمان برضه خالص اوي جدا
مش ما لا نعم ايوه
كان يكون تكون بيكون هيكون عايز عاوز محتاج ممكن لازم
ايه_رايك الموضوع حاجه حاجة شي شيء
what why how where when which the a an is are of to in on for and or
""".split())


def _content_terms(query_tokens: list[str]) -> list[str]:
    """Query terms minus the scaffolding — unless that is all there was."""
    kept = [t for t in query_tokens if t not in _STOP]
    return kept or query_tokens


def normalize(text: str) -> str:
    return _MARKS.sub("", text).translate(_FOLD).lower()


def _stem(tok: str) -> str:
    if len(tok) >= _AL_MIN and tok.startswith("ال"):
        return tok[2:]
    return tok


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(normalize(text))]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float

    def as_dict(self, rank: int) -> dict:
        c = self.chunk
        return {"id": f"S{rank}", "score": round(self.score, 3), "title": c.title,
                "ref": c.ref, "link": c.link, "kind": c.kind, "source": c.source,
                "text": c.text}


class Index:
    """Tokenised corpus + document frequencies. Rebuilt whenever the corpus is."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.docs: list[Counter[str]] = []
        self.lengths: list[int] = []
        self.norm_text: list[str] = []
        df: Counter[str] = Counter()
        for c in chunks:
            # The title is part of the searchable text: a chunk headed
            # «قواعد نما الحرجة» should match "قواعد نما" even if the body
            # never repeats the phrase.
            toks = tokens(f"{c.title}\n{c.text}")
            counts = Counter(toks)
            self.docs.append(counts)
            self.lengths.append(len(toks))
            self.norm_text.append(normalize(f"{c.title}\n{c.text}"))
            df.update(counts.keys())
        self.df = df
        self.n = len(chunks)
        self.avgdl = (sum(self.lengths) / self.n) if self.n else 0.0

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 6) -> list[Hit]:
        q = set(_content_terms(tokens(query)))
        if not q:
            return []
        nq = normalize(query).strip()
        phrase = nq if len(nq) >= 6 else ""
        weights = {t: self.idf(t) for t in q}
        total_idf = sum(weights.values()) or 1.0
        scored: list[Hit] = []
        for i, counts in enumerate(self.docs):
            dl = self.lengths[i] or 1
            s = 0.0
            covered = 0.0
            for term in q:
                f = counts.get(term, 0)
                if not f:
                    continue
                denom = f + _K1 * (1 - _B + _B * dl / self.avgdl)
                s += weights[term] * (f * (_K1 + 1)) / denom
                covered += weights[term]
            if s <= 0:
                continue
            # Coverage, weighted by rarity. Plain BM25 sums per-term scores, so
            # a chunk that hits three common words can beat the one chunk that
            # hits the single rare word the question is *about*. Scaling by how
            # much of the query's information mass a chunk accounts for is what
            # makes "why does pageSize truncate" find the pageSize rule.
            s *= 0.3 + 0.7 * (covered / total_idf)
            # And a chunk containing the question as written beats one that
            # merely contains its words scattered.
            if phrase and phrase in self.norm_text[i]:
                s *= 1.35
            scored.append(Hit(self.chunks[i], s))
        scored.sort(key=lambda h: h.score, reverse=True)
        return self._spread(scored, top_k)

    @staticmethod
    def _spread(scored: list[Hit], top_k: int, per_section: int = 3) -> list[Hit]:
        """At most `per_section` passages from any one section.

        Without this a single section wins every slot — a question about
        customer balances came back as six consecutive rows of one table and
        nothing else, so the model never saw the endpoint that actually serves
        them. Three still lets a table answer a question about that table.
        """
        seen: dict[str, int] = {}
        out: list[Hit] = []
        for h in scored:
            # Group by section, not by chunk: prose pieces of one section share
            # a ref, table rows differ only by their trailing label.
            key = f"{h.chunk.source}|{h.chunk.title.split(' · ')[0]}"
            if seen.get(key, 0) >= per_section:
                continue
            seen[key] = seen.get(key, 0) + 1
            out.append(h)
            if len(out) >= top_k:
                break
        return out


_INDEX: Index | None = None


def get() -> Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(get_index())
    return _INDEX


def reset() -> None:
    global _INDEX
    _INDEX = None


def search(query: str, top_k: int = 6) -> list[Hit]:
    return get().search(query, top_k)
