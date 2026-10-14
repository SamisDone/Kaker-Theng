"""All three pages end to end, and what the finished font does."""

import cv2
import numpy as np
import pytest

from app.cells import cut_cells
from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.ink import extract_ink
from app.pipeline import decode_image
from app.render import shape_names
from app.scan import find_page
from app.vectorize import vectorize
from scripts.bangla_report import SENTENCES, check_font
from tests.synth import make_page


def _page(page: int, mode: str):
    synth = make_page(page, mode)
    found = find_page(decode_image(synth.photo_jpeg), expected_page=page)
    ink, _ = extract_ink(found.gray, page)
    return synth, cut_cells(ink, page)


@pytest.fixture(scope="module")
def colour_font():
    drawings = []
    for page in (1, 2, 3):
        _, cells = _page(page, "colour")
        assert [c.cell.text for c in cells if c.status == "missing"] == []
        drawings += [vectorize(c) for c in cells]
    return build_font(drawings, "Test Bangla")


def test_sentences_have_no_missing_glyphs(colour_font):
    for s in SENTENCES:
        assert ".notdef" not in shape_names(colour_font.ttf, s), s


def test_font_shapes_exactly_as_planned(colour_font):
    report = check_font(colour_font.ttf, build_layout())
    assert report["shaping_differs_from_plan"] == []
    assert report["conjuncts"][".notdef"] == 0


def test_parts_are_derived_not_written(colour_font):
    written = {c.glyph for c in build_layout().cells if c.group == "part"}
    planned = {p.glyph for p in build_layout().plans() if p.method != "written"}
    assert set(colour_font.derived) == planned
    assert not written & planned


@pytest.mark.parametrize("mode", ["colour", "ballpoint"])
def test_small_marks_survive(mode):
    synth, cells = _page(2, mode)
    for ci in cells:
        if ci.cell.text not in ("কঁ", "কং", "য়"):
            continue
        h, w = ci.bitmap.shape
        truth = synth.truth[ci.y0 : ci.y0 + h, ci.x0 : ci.x0 + w]
        near = cv2.dilate(ci.bitmap.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        n, labels = cv2.connectedComponents(truth.astype(np.uint8), connectivity=8)
        for i in range(1, n):
            piece = labels == i
            assert (near & piece).sum() >= 0.5 * piece.sum(), f"lost a piece of {ci.cell.text}"


def test_sign_written_on_the_wrong_side_still_builds():
    """A pre-base sign written right of its ghost must not give a negative
    advance (that crashed the font build)."""
    from app.vectorize import Contour, Drawing

    cell = next(c for c in build_layout().cells if c.text == "কি")
    box = [Contour((1300, 0), [("L", (1300, 500)), ("L", (1400, 500)), ("L", (1400, 0))])]
    drawing = Drawing(cell.id, cell.glyph, cell.kind, None, box, (1300, 0, 1400, 500))
    font = build_font([drawing], "Wrong Side")
    assert font.ttf[:4] in (b"\x00\x01\x00\x00", b"true")
