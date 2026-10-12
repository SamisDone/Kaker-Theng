"""The template layout and its cache."""

from app.basefont import base_shaper, simulated_shaper
from app.charset import PART_CONJUNCTS
from app.glyphmap import _specials, build_layout, load_cached_layout


def test_layout_cache_is_fresh():
    assert load_cached_layout() is not None, "assets/layout.json is stale: run python -m scripts.make_template"


def test_every_page_fits():
    layout = build_layout()
    for page in (1, 2, 3):
        cells = layout.page(page)
        assert cells and max(c.row for c in cells) < 10


def test_part_conjuncts_form_from_written_glyphs():
    layout = build_layout()
    sim = simulated_shaper(layout.bangla_glyphs() | _specials())
    for text in PART_CONJUNCTS:
        assert sim.names(text) == base_shaper().names(text), text
