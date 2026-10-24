"""Letters drawn in the browser must not run into each other in words.

Fonts are built from drawn strokes three ways: a hand tracing the canvas
guide carefully, a sloppy hand that drops signs anywhere in their dashed
box (even on the ghost), and the synthetic handwriting. Sample words are
shaped and drawn; two neighbours may share ink only in the মাত্রা band.
"""

from functools import lru_cache

import pytest

from app import config as C
from app.basefont import base_shaper
from app.fontbuild import BANGLA_RSB, SIGN_CLEARANCE, _body_extent, _placement, build_font
from app.glyphmap import build_layout
from app.spacing import BODY_LIMIT, collisions
from app.strokes import drawing
from tests.synth_strokes import drawn_cells
from tests.trace_strokes import traced_cells

WORDS = ["আমি", "কলম", "বাংলা", "সকালে", "বিদ্যালয়", "কিছু", "বেশি", "দেশে", "নিজের", "তিনি", "পৌঁছে", "প্রতিদিন", "সূর্য", "ভালো", "রাতে", "কেন", "কোথায়", "নদী", "পাখি", "বৈশাখ"]
CONJUNCT_WORDS = ["ইচ্ছা", "রাষ্ট্র", "শক্তি", "অঞ্চল", "উদ্দেশ্য", "পুষ্প", "বিদ্যুৎ"]
JOIN = -BANGLA_RSB + 25  # how far two মাত্রাs may overlap: the join plus a round pen end

HANDS = {
    "careful": lambda ids: traced_cells(ids, seed=11),
    "sloppy, seed 9": lambda ids: traced_cells(ids, seed=9, sloppy=True),  # ল|া collided in বাংলা before the fix
    "sloppy, seed 2": lambda ids: traced_cells(ids, seed=2, sloppy=True),  # ি|ক, ে|শ
    "synthetic": lambda ids: {k: v for k, v in drawn_cells((2,)).items() if k in ids},
}


def cells():
    return {c.id: c for c in build_layout().cells}


@lru_cache(maxsize=None)
def font(hand: str):
    page2 = [c.id for c in build_layout().cells if c.page == 2]  # letters, signs, phala: no conjuncts drawn
    strokes = HANDS[hand](page2)
    return build_font([drawing(cells()[k], v) for k, v in strokes.items() if v], "Spacing Test")


@pytest.mark.parametrize("hand", list(HANDS))
def test_neighbouring_letters_do_not_collide(hand):
    built = font(hand)
    whole = {c.glyph for c in build_layout().cells if c.page == 2 and not c.ghost_glyphs}
    bad = []
    for word in WORDS + CONJUNCT_WORDS:
        for c in collisions(built.ttf, word, built.matra):
            if c.body > BODY_LIMIT:
                bad.append(f"{word}: {c.left} | {c.right} share {c.body:.0f} units² under the মাত্রা")
            # Two whole letters: only the মাত্রা join. (ি ী ৗ hooks reach over by design.)
            elif word in WORDS and c.left in whole and c.right in whole and c.band > JOIN:
                bad.append(f"{word}: {c.left} | {c.right} overlap {c.band:.0f} units in the মাত্রা band")
    assert not bad, "\n".join(bad)


def _sign(text: str, shift_mm: float):
    """The careful hand's drawing of a sign cell, moved sideways."""
    cell = next(c for c in build_layout().cells if c.text == text)
    strokes = [[[x + shift_mm, y] for x, y in s] for s in traced_cells([cell.id], seed=11)[cell.id]]
    return cell, drawing(cell, strokes)


def _place(cell, d):
    layout = build_layout()
    return _placement(d, cell, base_shaper().tt, set(layout.matra_glyphs), matra=(585.0, 60.0))  # no insets: the strictest


@pytest.mark.parametrize("text", ["কে", "কি", "কৈ"])
def test_a_pre_base_sign_keeps_the_gap_drawn_to_the_ghost(text):
    # Drawn further left of the ghost: the next letter starts that much
    # further on. The gap is measured to the ghost, not to the canvas edge.
    cell, near = _sign(text, -1.5)  # clear of the ghost: the gap is as drawn
    _, far = _sign(text, -2.5)
    adv_near, adv_far = _place(cell, near)[2], _place(cell, far)[2]
    assert abs((adv_far - adv_near) - 1.0 / C.MM_PER_UNIT) < 3


@pytest.mark.parametrize("text", ["কে", "কি", "কৈ"])
def test_a_pre_base_sign_drawn_on_the_ghost_still_clears_the_next_letter(text):
    cell, d = _sign(text, 1.5)  # pushed right, onto the faint ghost
    dx, _, advance = _place(cell, d)
    body = _body_extent(d, 585 - 30)
    assert body[1] + dx <= advance - SIGN_CLEARANCE + 1


@pytest.mark.parametrize("text", ["কা", "কী", "কৗ"])
def test_a_sign_after_the_ghost_keeps_its_gap_and_clears_the_letter(text):
    # Drawn further right of the ghost: its ink lands that much further
    # from the letter before it.
    cell, near = _sign(text, 1.0)
    _, far = _sign(text, 2.0)
    left = lambda d: d.bbox[0] + _place(cell, d)[0]
    assert abs((left(far) - left(near)) - 1.0 / C.MM_PER_UNIT) < 3
    _, onto = _sign(text, -1.5)  # pulled left, onto the ghost
    dx, _, _ = _place(cell, onto)
    body = _body_extent(onto, 585 - 30)
    assert body[0] + dx >= -BANGLA_RSB + SIGN_CLEARANCE - 1
