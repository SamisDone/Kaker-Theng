"""The order the drawing screen asks for letters: the most useful first.

Bangla first, by how often each letter or sign occurs on Bangla Wikipedia
(assets/conjunct_counts.json): vowel signs by their own character, phalas
and reph by the clusters that use them. Then English, lowercase by English
letter frequency, then capitals, digits and punctuation. Then whole
conjuncts by cluster frequency, and the conjunct fragment parts last. The
hasanta (ক্) ranks by its own frequency, third of all: every conjunct
contains it, and without its glyph none can be built at all.
"""

from __future__ import annotations

import json
from functools import lru_cache

from .config import ASSETS_DIR
from .glyphmap import HALANT, Cell, build_layout

# Share of letters in English text (%), lowercase (Lewand, Cryptological Mathematics).
EN_FREQ = dict(zip("etaoinshrdlcumwfgypbvkjxqz", [12.7, 9.1, 8.2, 7.5, 7.0, 6.7, 6.3, 6.1, 6.0, 4.3, 4.0, 2.8, 2.8, 2.4, 2.4, 2.2, 2.0, 2.0, 1.9, 1.5, 1.0, 0.8, 0.15, 0.15, 0.10, 0.07]))


DARI, AU_LENGTH, AU_SIGN = "।", "ৗ", "ৌ"


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads((ASSETS_DIR / "conjunct_counts.json").read_text(encoding="utf-8"))


def _counts() -> tuple[dict[str, int], dict[str, int]]:
    return _data()["characters"], _data()["clusters"]


def _words() -> int:
    return _data()["bangla_words"]


def bangla_weight(cell: Cell) -> float:
    """How often what this cell adds occurs in Bangla text."""
    chars, clusters = _counts()
    if cell.group in ("conjunct", "part"):
        return clusters.get(cell.text, 0)
    written = cell.text.replace(cell.ghost, "", 1) if cell.ghost and cell.text.startswith(cell.ghost) else cell.text
    if cell.group == "phala" or (written.startswith(HALANT) and len(written) > 1):
        return sum(n for t, n in clusters.items() if HALANT + written.lstrip(HALANT) in t)
    if cell.text.startswith("র" + HALANT):  # reph
        return sum(n for t, n in clusters.items() if t.startswith("র" + HALANT))
    if written == DARI:
        # Not in the counts (outside the Bengali block). An estimate: about
        # one sentence end per 15 words.
        return _words() / 15
    if written == AU_LENGTH:  # the right half of ৌ, which the counts keep composed
        return chars.get(AU_LENGTH, 0) + chars.get(AU_SIGN, 0)
    return sum(chars.get(ch, 0) for ch in written) / max(1, len(written))


def _latin_key(cell: Cell) -> tuple:
    t = cell.text
    if t.islower():
        return (0, -EN_FREQ.get(t, 0))
    if t.isupper():
        return (1, -EN_FREQ.get(t.lower(), 0))
    if t.isdigit():
        return (2, t)
    return (3, cell.index)  # punctuation as the template lists it


def draw_order() -> list[str]:
    """Every cell id, most useful first."""
    cells = build_layout().cells
    core = [c for c in cells if c.kind != "latin" and c.page == 2]
    latin = [c for c in cells if c.kind == "latin"]
    conjuncts = [c for c in cells if c.page == 3 and c.group != "part"]
    parts = [c for c in cells if c.page == 3 and c.group == "part"]
    order = (
        sorted(core, key=lambda c: -bangla_weight(c))
        + sorted(latin, key=_latin_key)
        + sorted(conjuncts, key=lambda c: -bangla_weight(c))
        + sorted(parts, key=lambda c: -bangla_weight(c))
    )
    return [c.id for c in order]
