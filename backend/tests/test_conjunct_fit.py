"""Ra-phala, ন্ন and । in fonts from the test hands, against the base
font: a ra-phala is the writer's stroke as thick as they drew it, under its
consonant and not on it; the stacked ন of ন্ন don't crowd each other more
than the base font's; । stands clear of the letter before it."""

import io
from functools import lru_cache

import numpy as np
import pytest

from app.basefont import base_shaper
from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.strokes import drawing
from tests.overlap import body_overlap, overlap, pieces, thickness, wave_rise
from tests.synth_strokes import drawn_cells
from tests.trace_strokes import traced_cells

RAPHALA = ["প্র", "ক্র", "ত্র", "ব্র", "গ্র", "শ্র", "দ্র", "ধ্র", "ম্র"]


def _page2() -> list[str]:
    return [c.id for c in build_layout().cells if c.page == 2]


HANDS = {
    "careful": lambda: traced_cells(_page2(), seed=11),
    "sloppy": lambda: traced_cells(_page2(), seed=9, sloppy=True),
    "synthetic": lambda: {k: v for k, v in drawn_cells((2,)).items() if k in set(_page2())},
}


@lru_cache(maxsize=None)
def font(hand: str) -> bytes:
    cells = {c.id: c for c in build_layout().cells}
    return build_font([drawing(cells[k], v) for k, v in HANDS[hand]().items() if v], "Fit Test").ttf


@lru_cache(maxsize=1)
def noto() -> bytes:
    buf = io.BytesIO()
    base_shaper().tt.save(buf)
    return buf.getvalue()


def raphala(f: bytes, text: str) -> np.ndarray:
    return next(m for n, m in pieces(f, text) if n.startswith("raphala"))


@pytest.mark.parametrize("hand", HANDS)
@pytest.mark.parametrize("text", RAPHALA)
def test_a_raphala_stays_off_its_consonant(hand, text):
    f = font(hand)
    # Its ink on the consonant's body (the stem's join left out): no more than the base font's.
    assert body_overlap(f, text) <= body_overlap(noto(), text) + 0.01
    # Its wave reaches no higher into the consonant than the base font's
    # (or than touching, where the base font's sits below).
    assert wave_rise(f, text) <= max(wave_rise(noto(), text), 0) + 10
    # It is the writer's stroke, not stretched thick (প্র was 1.3-1.5 times).
    assert thickness(raphala(f, text)) <= 1.2 * thickness(raphala(f, "ত্র"))


def test_the_stacked_na_of_nna_crowd_no_more_than_the_base_fonts():
    f = font("careful")
    for piece in ("n-beng.float", "na-beng.blws"):
        assert overlap(f, "ন্ন", piece) <= overlap(noto(), "ন্ন", piece) + 0.03, piece


@pytest.mark.parametrize("hand", HANDS)
@pytest.mark.parametrize("word", ["খাই।", "চাইল।"])
def test_the_danda_stands_clear_of_the_letter_before(hand, word):
    ps = pieces(font(hand), word)
    danda = next(m for n, m in ps if n == "danda-deva")
    before = np.zeros_like(danda)
    for n, m in ps:
        if n != "danda-deva":
            before |= m
    gap = (danda.any(axis=0).nonzero()[0][0] - before.any(axis=0).nonzero()[0][-1]) / 0.25  # px -> font units
    assert gap >= 100, gap
