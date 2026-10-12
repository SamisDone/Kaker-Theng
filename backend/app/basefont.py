"""The base font, loaded once per process, plus HarfBuzz helpers."""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

import uharfbuzz as hb
from fontTools import subset
from fontTools.ttLib import TTFont

from .config import BASE_FONT_PATH

# Code points that every output font keeps, written or not.
ALWAYS_KEEP_UNICODES = [0x20, 0xA0, 0x200C, 0x200D, 0x25CC]

# Presentation-form features. Turning them off gives the basic Indic forms,
# which is what is left once the variant glyphs they produce are subset away.
PRESENTATION_FEATURES = ["init", "pres", "abvs", "blws", "psts", "haln", "calt", "liga"]


@dataclass(frozen=True)
class ShapedGlyph:
    name: str
    cluster: int
    x_advance: int
    x_offset: int
    y_offset: int


class Shaper:
    """A HarfBuzz font plus the glyph order needed to turn ids into names."""

    def __init__(self, font_bytes: bytes):
        self.font_bytes = font_bytes
        self.tt = TTFont(io.BytesIO(font_bytes))
        self.order = self.tt.getGlyphOrder()
        self.hb_font = hb.Font(hb.Face(hb.Blob(font_bytes)))

    def shape(self, text: str, features: dict | None = None) -> list[ShapedGlyph]:
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, features or {})
        return [
            ShapedGlyph(self.order[i.codepoint], i.cluster, p.x_advance, p.x_offset, p.y_offset)
            for i, p in zip(buf.glyph_infos, buf.glyph_positions)
        ]

    def names(self, text: str, features: dict | None = None) -> list[str]:
        return [g.name for g in self.shape(text, features)]


@lru_cache(maxsize=1)
def base_bytes() -> bytes:
    return BASE_FONT_PATH.read_bytes()


@lru_cache(maxsize=1)
def base_shaper() -> Shaper:
    return Shaper(base_bytes())


def base_ttfont() -> TTFont:
    """A fresh, editable copy of the base font."""
    return TTFont(io.BytesIO(base_bytes()))


def subset_options() -> subset.Options:
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.layout_closure = False  # keep exactly the glyphs we ask for
    opts.glyph_names = True
    opts.notdef_outline = True
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.drop_tables += ["meta"]
    opts.hinting = False
    return opts


def subset_font(font: TTFont, glyphs: set[str], unicodes: list[int] | None = None) -> TTFont:
    keep = set(glyphs) | {".notdef"}
    sub = subset.Subsetter(subset_options())
    sub.populate(glyphs=sorted(keep), unicodes=(unicodes or []) + ALWAYS_KEEP_UNICODES)
    sub.subset(font)
    return font


def simulated_shaper(glyphs: set[str]) -> Shaper:
    """Shaper for the base font cut down to `glyphs`.

    Outlines don't affect shaping, so this predicts exactly how the final
    handwriting font will shape text when the user has written those glyphs.
    """
    font = subset_font(base_ttfont(), glyphs)
    out = io.BytesIO()
    font.save(out)
    return Shaper(out.getvalue())


@lru_cache(maxsize=1)
def headline_units() -> int:
    """Centre of the মাত্রা bar, measured on the base font's ক."""
    from fontTools.pens.pointInsidePen import PointInsidePen

    tt = base_shaper().tt
    name = tt.getBestCmap()[ord("ক")]
    glyf = tt["glyf"][name]
    gs = tt.getGlyphSet()

    def inside(x: float, y: float) -> bool:
        pen = PointInsidePen(gs, (x, y))
        gs[name].draw(pen)
        return pen.getResult()

    # Walk down from the top at several x positions. Where only the bar is
    # inked, the ink run is the bar's thickness; stems make it longer.
    top = glyf.yMax
    thickness = top
    for x in range(glyf.xMin + 40, glyf.xMax - 40, 25):
        if not inside(x, top - 2):
            continue
        y = top - 2
        while y > 0 and inside(x, y):
            y -= 2
        thickness = min(thickness, top - y)
    return round(top - thickness / 2)
