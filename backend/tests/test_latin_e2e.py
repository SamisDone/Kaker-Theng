"""Page 1 end to end: synthetic handwriting, printed, photographed, read back."""

import pytest

from app.cells import cut_cells
from app.fontbuild import FontNameError, build_font, clean_family_name
from app.ink import extract_ink
from app.pipeline import decode_image
from app.render import shape_names
from app.scan import ScanError, find_page
from app.vectorize import vectorize
from tests.synth import cells_ink, ink_agreement, make_page

PANGRAM = "The quick brown fox jumps over the lazy dog."


@pytest.mark.parametrize("mode", ["colour", "laser", "copy", "ballpoint"])
def test_page1_builds_latin_font(mode):
    synth = make_page(1, mode)
    found = find_page(decode_image(synth.photo_jpeg), expected_page=1)
    assert found.page == 1

    ink, _ = extract_ink(found.gray, 1)
    cells = cut_cells(ink, 1)
    scores = ink_agreement(cells_ink(cells, ink.shape), synth.truth, 1)
    assert min(p for p, _, _ in scores.values()) >= 0.94, "printed residue or noise got into a cell"
    assert min(r for _, r, _ in scores.values()) >= 0.95, "handwriting was lost"

    assert [c.cell.text for c in cells if c.status == "missing"] == []
    font = build_font([vectorize(c) for c in cells], "Test Hand")
    assert ".notdef" not in shape_names(font.ttf, PANGRAM)
    assert font.woff2[:4] == b"wOF2"


def test_blank_photo_names_the_problem():
    import numpy as np

    with pytest.raises(ScanError) as err:
        find_page(np.full((2000, 1500), 230, np.uint8))
    assert err.value.code == "no_markers"


def test_cropped_photo_names_missing_corners():
    image = decode_image(make_page(1, "colour").photo_jpeg)
    with pytest.raises(ScanError) as err:
        find_page(image[:, image.shape[1] // 5 :])  # left side cut off
    assert err.value.code == "missing_corners"
    assert set(err.value.details["missing_corners"]) == {"top-left", "bottom-left"}


@pytest.mark.parametrize("name",["", "Noto Hand", "x" * 41])
def test_bad_font_names_are_refused(name):
    with pytest.raises(FontNameError):
        clean_family_name(name)
