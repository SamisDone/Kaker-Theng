"""Word coverage along the drawing order: all consonants before the vowel
signs, or the signs after the 15 most used consonants (the site's order,
frontend/lib/chapters.ts).

    python -X utf8 -m scripts.words_curve

Builds fonts from the test hand (tests/trace_strokes.py) at each step and
prints the share of Bangla words they write, with a few of the words. Dev only.
"""

from app.basefont import Shaper
from app.coverage import plain_glyphs
from app.draworder import draw_order
from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.strokes import drawing
from app.wordcov import word_coverage, writable_words
from tests.trace_strokes import traced_cells

strokes = traced_cells(seed=11)
C = {c.id: c for c in build_layout().cells}


def chapter(c) -> str:
    """frontend/lib/chapters.ts chapterOf, before the consonants are split."""
    if c.kind == "latin":
        return "english"
    if c.id.startswith("p3-"):
        return "conjuncts"
    g = c.group
    if g in ("vowel", "consonant", "digit", "phala"):
        return {"vowel": "vowels", "consonant": "consonants", "digit": "digits", "phala": "phala"}[g]
    if g == "other":
        return "signs" if c.ghost else "consonants"
    if g == "tall":
        if not c.ghost:
            return "digits"
        return "phala" if c.text.startswith("র্") else "signs"
    return "signs"


def measure(ids: list[str]) -> tuple[float, list[str]]:
    ds = [drawing(C[i], strokes[i]) for i in ids if strokes.get(i)]
    font = build_font(ds, "Curve")
    written = {d.glyph for d in ds if d.kind != "latin"}
    sh, plain = Shaper(font.ttf), plain_glyphs(written)
    return word_coverage(sh, plain), writable_words(sh, plain, 12)


by: dict[str, list[str]] = {}
for i in draw_order():
    by.setdefault(chapter(C[i]), []).append(i)
v, k, s = by["vowels"], by["consonants"], by["signs"]
plans = {
    "all consonants, then signs": [("vowels", v), ("+15 consonants", k[:15]), ("+rest consonants", k[15:]), ("+signs", s)],
    "signs after 15 consonants": [("vowels", v), ("+15 consonants", k[:15]), ("+signs", s), ("+rest consonants", k[15:])],
}
for name, steps in plans.items():
    print("\n" + name)
    done: list[str] = []
    for label, ids in steps:
        done += ids
        cov, words = measure(done)
        print(f"  {label:18} {len(done):3} letters  words {cov:6.1%}  e.g. {' '.join(words[:8])}")
