"""How much real Bangla text a font renders correctly.

Counts of consonant clusters (conjuncts, reph, phala) from Bangla Wikipedia
(assets/conjunct_counts.json, made by scripts/count_conjuncts.py). A cluster
is covered only when it is built correctly: no hasanta glyph, no .notdef,
and either built exactly the way the base font builds it, or only from
glyphs the user wrote whole (প + ra-phala, a whole conjunct...). A cluster
that starts one of the base font's constructions but can't finish it (the
half-built ক্র) does not count.
"""

from __future__ import annotations

import json
from functools import lru_cache

from .basefont import Shaper, base_shaper, simulated_shaper
from .config import ASSETS_DIR
from .glyphmap import HALANT, _specials, build_layout

COUNTS_PATH = ASSETS_DIR / "conjunct_counts.json"


@lru_cache(maxsize=1)
def cluster_counts() -> dict[str, int]:
    return json.loads(COUNTS_PATH.read_text(encoding="utf-8"))["clusters"]


@lru_cache(maxsize=1)
def _base_runs() -> dict[str, list[str]]:
    base = base_shaper()
    return {t: base.names(t) for t in cluster_counts()}


@lru_cache(maxsize=1)
def _halant() -> str:
    return base_shaper().tt.getBestCmap()[ord(HALANT)]


@lru_cache(maxsize=None)
def base_run(text: str) -> list[str]:
    runs = _base_runs()
    return runs[text] if text in runs else base_shaper().names(text)


def cluster_ok(shaper: Shaper, text: str, plain: set[str]) -> bool:
    """Built correctly: no hasanta glyph, no .notdef, and either exactly as
    the base font builds it or only from glyphs written whole."""
    names = shaper.names(text)
    if ".notdef" in names or _halant() in names:
        return False
    return names == base_run(text) or all(g in plain for g in names)


def coverage(shaper: Shaper, plain: set[str]) -> float:
    """Share of cluster occurrences the font builds correctly. `plain`: the
    glyphs the user wrote as whole units (letters, signs, whole conjuncts)."""
    counts = cluster_counts()
    good = sum(n for text, n in counts.items() if cluster_ok(shaper, text, plain))
    return good / sum(counts.values())


def plain_glyphs(written: set[str]) -> set[str]:
    """Of the glyphs a user wrote, the ones written as whole units."""
    whole = {c.glyph for c in build_layout().cells if c.kind != "latin" and c.group != "part"}
    return (written & whole) | _specials()


def font_coverage(font_bytes: bytes, written: set[str]) -> float:
    return coverage(Shaper(font_bytes), plain_glyphs(written))


@lru_cache(maxsize=1)
def complete_coverage() -> float:
    """Coverage of a font with every cell of all three pages written."""
    layout = build_layout()
    written = {c.glyph for c in layout.cells if c.kind != "latin"}
    return coverage(simulated_shaper(layout.bangla_glyphs() | _specials()), plain_glyphs(written))


def derivable_from(written: set[str]) -> set[str]:
    """Parts that can be made from these written glyphs (bars need nothing;
    a variant's source may itself be derived)."""
    plans = [p for p in build_layout().plans() if p.method != "written"]
    have = set(written)
    while True:
        new = {p.glyph for p in plans if p.glyph not in have and (p.method == "bar" or p.source in have)}
        if not new:
            return have - set(written)
        have |= new


@lru_cache(maxsize=1)
def pages_1_2_coverage() -> float:
    """Coverage with pages 1 and 2 complete and page 3 blank."""
    written = {c.glyph for c in build_layout().cells if c.kind != "latin" and c.page == 2}
    glyphs = written | derivable_from(written) | _specials()
    return coverage(simulated_shaper(glyphs), plain_glyphs(written))
