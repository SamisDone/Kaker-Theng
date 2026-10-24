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
"""

from __future__ import annotations

import json
from functools import lru_cache

from .basefont import Shaper, simulated_shaper
from .config import ASSETS_DIR
from .coverage import _specials, cluster_ok, derivable_from, plain_glyphs
from .glyphmap import build_layout

WORDS_PATH = ASSETS_DIR / "word_needs.json"


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
def complete_word_coverage() -> float:
    """Words covered with every cell of all three pages written."""
    layout = build_layout()
    written = {c.glyph for c in layout.cells if c.kind != "latin"}
    return word_coverage(simulated_shaper(layout.bangla_glyphs() | _specials()), plain_glyphs(written))


@lru_cache(maxsize=1)
def pages_1_2_word_coverage() -> float:
    written = {c.glyph for c in build_layout().cells if c.kind != "latin" and c.page == 2}
    return word_coverage(simulated_shaper(written | derivable_from(written) | _specials()), plain_glyphs(written))
