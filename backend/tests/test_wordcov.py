"""What a font writes: the words, the sentences and the site's name shown
to a visitor are only ones the font renders fully and correctly."""

from functools import lru_cache

from app.basefont import Shaper
from app.coverage import plain_glyphs
from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.strokes import drawing
from app.wordcov import TITLE, _sentences, writable_sentences, writable_words, writes
from tests.trace_strokes import traced_cells


@lru_cache(maxsize=None)
def font(groups: tuple[str, ...]):
    """A font from the test hand: the page 2 cells in these groups (all of page 2 if empty)."""
    cells = {c.id: c for c in build_layout().cells}
    ids = [c.id for c in build_layout().cells if c.page == 2 and (not groups or c.group in groups)]
    ds = [drawing(cells[k], v) for k, v in traced_cells(ids, seed=11).items() if v]
    built = build_font(ds, "Wordcov Test")
    return Shaper(built.ttf), plain_glyphs({d.glyph for d in ds})


def test_the_sentences_are_short_bangla_lines():
    assert 35 <= len(_sentences()) <= 50
    assert all(len(s.split()) <= 6 and s[-1] in "।?" for s in _sentences())


def test_vowels_alone_write_no_sentence_and_not_the_name():
    shaper, plain = font(("vowel",))
    assert writable_sentences(shaper, plain) == []
    assert not writes(shaper, plain, TITLE)
    assert all(set(w) <= set("অআইঈউঊঋএঐওঔ") for w in writable_words(shaper, plain))


def test_letters_signs_and_phala_write_most_sentences_and_the_name():
    shaper, plain = font(())
    sentences = writable_sentences(shaper, plain)
    assert len(sentences) >= 30, sentences
    assert writes(shaper, plain, TITLE)  # ঠ্য: the ya-phala is drawn on page 2


def test_without_the_ya_phala_the_name_is_not_written():
    shaper, plain = font(("vowel", "consonant", "sign", "other", "tall", "nukta"))
    assert not writes(shaper, plain, TITLE)  # ঠ্য would show a visible hasanta
