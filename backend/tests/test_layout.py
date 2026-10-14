"""The template layout and its cache."""

from app import config as C
from app.basefont import base_shaper, simulated_shaper
from app.charset import PART_CONJUNCTS
from app.glyphmap import _specials, build_layout, load_cached_layout


def test_layout_cache_is_fresh():
    assert load_cached_layout() is not None, "assets/layout.json is stale: run python -m scripts.make_template"


def test_every_page_fits():
    layout = build_layout()
    for page in (1, 2, 3):
        cells = layout.page(page)
        bottom = max(c.box_mm()[1] + c.box_mm()[3] for c in cells)
        assert cells and bottom <= C.GRID_Y_MM + C.GRID_H_MM + 1e-6


def test_part_conjuncts_form_from_written_glyphs():
    layout = build_layout()
    sim = simulated_shaper(layout.bangla_glyphs() | _specials())
    for text in PART_CONJUNCTS:
        assert sim.names(text) == base_shaper().names(text), text


def test_only_underivable_parts_get_cells():
    layout = build_layout()
    written = {p.glyph for p in layout.plans() if p.method == "written"}
    part_cells = {c.glyph for c in layout.cells if c.group == "part"}
    assert part_cells == written
    # Every written part is written because deriving it was tried and failed.
    for plan in layout.plans():
        if plan.method == "written":
            assert "doesn't reproduce" in plan.reason or "no letter" in plan.reason, plan.reason


def test_derived_parts_reproduce_the_base_font():
    from app.derive import self_check

    for plan in build_layout().plans():
        if plan.method != "written":
            assert self_check(plan).passes, (plan.glyph, plan.reason)
