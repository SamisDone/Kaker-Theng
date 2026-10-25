"""How many Bangla words a font renders fully and correctly.

assets/word_needs.json (scripts/count_conjuncts.py --words) holds every word
of a Bangla Wikipedia sample reduced to what it needs, its characters and
its consonant clusters, with how many words need exactly that. A word is
right when the font has every one of its characters (shaping the character
alone gives no .notdef) and builds every one of its clusters correctly
(coverage.py's rule). Only the 40,000 most common needs are kept, standing
for about 95% of the words; the share is of those words. The rest, words
with rare letter combinations, are left out of the measure rather than
counted as missed (which would keep even a complete font below 100%).

assets/top_words.json (count_conjuncts.py --top) holds the 3,000 most
common words of its prose, and assets/sentences.txt short everyday
sentences, to show a visitor what their font can already write, by the
same rule.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from .basefont import Shaper, simulated_shaper
from .config import ASSETS_DIR
from .coverage import _specials, cluster_ok, derivable_from, plain_glyphs
from .glyphmap import build_layout

WORDS_PATH = ASSETS_DIR / "word_needs.json"
TOP_WORDS_PATH = ASSETS_DIR / "top_words.json"
SENTENCES_PATH = ASSETS_DIR / "sentences.txt"
TITLE = "কাকের ঠ্যাং"  # the site's name, on the start screen in the visitor's font once it writes it
# A consonant cluster, as count_conjuncts.py finds them.
_CONS = "[ক-হড়ঢ়য়]়?"
CLUSTER = re.compile(f"(?:{_CONS}্)+{_CONS}")


@lru_cache(maxsize=1)
def _needs() -> tuple[int, list[tuple[frozenset[str], tuple[str, ...], int]]]:
    data = json.loads(WORDS_PATH.read_text(encoding="utf-8"))
    needs = []
    for key, n in data["needs"].items():
        chars, clusters = key.split("|")
        needs.append((frozenset(chars), tuple(clusters.split()), n))
    return data["kept_words"], needs


def word_coverage(shaper: Shaper, plain: set[str]) -> float:
    """Share of word occurrences the font renders fully and correctly."""
    total, needs = _needs()
    chars = set().union(*(c for c, _, _ in needs))
    clusters = {x for _, cs, _ in needs for x in cs}
    have = {ch for ch in chars if ".notdef" not in shaper.names(ch)}
    good = {x for x in clusters if cluster_ok(shaper, x, plain)}
    return sum(n for c, cs, n in needs if c <= have and all(x in good for x in cs)) / total


@lru_cache(maxsize=1)
def _top_words() -> list[str]:
    return list(json.loads(TOP_WORDS_PATH.read_text(encoding="utf-8"))["words"])


def writable_words(shaper: Shaper, plain: set[str], limit: int = 60) -> list[str]:
    """The most common words the font renders fully and correctly, most common first."""
    out: list[str] = []
    have: dict[str, bool] = {}
    good: dict[str, bool] = {}
    for word in _top_words():
        if all(have.setdefault(ch, ".notdef" not in shaper.names(ch)) for ch in set(word)) and all(
            good.setdefault(x, cluster_ok(shaper, x, plain)) for x in set(CLUSTER.findall(word))
        ):
            out.append(word)
            if len(out) == limit:
                break
    return out


def writes(shaper: Shaper, plain: set[str], text: str) -> bool:
    """The font renders every character of `text` (spaces aside) and builds
    every consonant cluster in it correctly."""
    return all(".notdef" not in shaper.names(ch) for ch in set(text) - {" "}) and all(cluster_ok(shaper, x, plain) for x in set(CLUSTER.findall(text)))


@lru_cache(maxsize=1)
def _sentences() -> list[str]:
    lines = SENTENCES_PATH.read_text(encoding="utf-8").splitlines()
    return [s.strip() for s in lines if s.strip() and not s.startswith("#")]


def writable_sentences(shaper: Shaper, plain: set[str]) -> list[str]:
    """The sentences the font writes fully, in order. One whose words it
    writes but not its end mark (। or ?, not drawn yet) comes without it."""
    out = []
    for s in _sentences():
        if writes(shaper, plain, s):
            out.append(s)
        elif writes(shaper, plain, s.rstrip("।?")):
            out.append(s.rstrip("।?"))
    return out


@lru_cache(maxsize=1)
def complete_word_coverage() -> float:
    """Words covered with every cell of all three pages written."""
    layout = build_layout()
    written = {c.glyph for c in layout.cells if c.kind != "latin"}
    return word_coverage(simulated_shaper(layout.bangla_glyphs() | _specials()), plain_glyphs(written))


@lru_cache(maxsize=1)
def pages_1_2_word_coverage() -> float:
    written = {c.glyph for c in build_layout().cells if c.kind != "latin" and c.page == 2}
    return word_coverage(simulated_shaper(written | derivable_from(written) | _specials()), plain_glyphs(written))
