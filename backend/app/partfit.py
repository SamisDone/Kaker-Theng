"""Conjunct parts made from the writer's letters, fitted where they go.

derive.py plans each part and applies the plan; this adjusts two kinds of
part after that, at font build time. (Kept out of derive.py on purpose: the
layout's fingerprint hashes derive.py, and a new fingerprint would drop
every drawing kept in visitors' browsers.)

- A ra-phala variant (প্র গ্র দ্র শ্র...). The base font's variants are one
  stroke, as thick, only wider or narrower, with the stem on the right
  raised to meet each consonant. The plan fits the writer's ra-phala into
  the variant's box, which stretched it to twice its height: a thick
  scribble crowding the letter above. Instead: the writer's stroke at its
  own height, stretched across to the variant's width, and placed against
  the writer's own consonants (which may reach lower than the base font's):
  clear of them by the base font's gap, its right stem reaching into them
  only as far as the base font's does.
- A piece stacked on or under another (the two ন of ন্ন), cut from a
  letter written taller than the base font's, comes out bigger than its
  place and crowds the pieces around it: shrunk evenly into its box.

And one change to the base font's rules (whole_ka_before_raphala), which
the coverage predictions apply too (final_shaper).
"""

from __future__ import annotations

import io
from functools import lru_cache

import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont

from .basefont import Shaper, base_shaper, base_ttfont, subset_font
from .derive import BUILD_RES, DerivePlan
from .outline import Raster, contour_polygons, polys_bbox
from .vectorize import Contour, Drawing, contours_bbox, trace_bitmap

RAPHALA = "raphala-beng"


@lru_cache(maxsize=1)
def raphala_bases() -> dict[str, list[tuple[str, int]]]:
    """Ra-phala variant -> [(the consonant glyph it goes under, the
    variant's height relative to it)], from shaping every consonant + ্র in
    the base font."""
    tt = base_shaper().tt
    data = io.BytesIO()
    tt.save(data)
    font, order = hb.Font(hb.Face(hb.Blob(data.getvalue()))), tt.getGlyphOrder()
    out: dict[str, list[tuple[str, int]]] = {}
    for cp in [*range(0x0995, 0x09BA), 0x09DC, 0x09DD, 0x09DF]:
        buf = hb.Buffer()
        buf.add_str(chr(cp) + "্র")
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        placed, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            placed.append((order[info.codepoint], pos.y_offset))
            x += pos.x_advance
        for k, (name, dy) in enumerate(placed):
            bases = [n for n, _ in placed[:k] if not n.startswith(("headline", "dottedCircle"))]
            if name.startswith(RAPHALA + ".") and bases:
                out.setdefault(name, []).append((bases[-1], dy))
    return out


def raphala_variant(plan: DerivePlan, d: Drawing, have: dict[str, Drawing] | None = None, res: float = BUILD_RES) -> list[Contour]:
    polys = contour_polygons(d.contours)
    bx0, by0, bx1, by1 = polys_bbox(polys)
    tx0, ty0, tx1, ty1 = plan.bbox
    sx = (tx1 - tx0) / max(bx1 - bx0, 1)
    sy = min(1.0, (ty1 - ty0) / max(by1 - by0, 1))
    wave = (by1 - by0) * sy
    floor, top = ty0, ty1
    # Against the writer's consonants this variant goes under: the base
    # font's gap below each (its wave is as tall as its plain ra-phala) and
    # its stem's reach into each, kept.
    glyf = base_shaper().tt["glyf"]
    plain = glyf[RAPHALA]
    noto_wave = plain.yMax - plain.yMin
    for base, dy in raphala_bases().get(plan.glyph, []):
        b = (have or {}).get(base)
        if b is None or not b.contours or base not in glyf or not glyf[base].numberOfContours:
            continue
        noto_limit = glyf[base].yMin - dy  # the consonant's lowest ink, in the variant's frame
        mine = contours_bbox(b.contours)[1] - dy
        floor = min(floor, mine - (noto_limit - (ty0 + noto_wave)) - wave)
        top = min(top, mine + (ty1 - noto_limit))
    top = max(top, floor + wave)
    moved = [[(tx0 + (x - bx0) * sx, floor + (y - by0) * sy) for x, y in p] for p in polys]
    r = Raster(tx0 - 10, min(floor, ty0) - 10, tx1 + 10, max(top, ty1) + 10, res)
    r.fill(moved)
    ink = r.img > 0
    cols = np.nonzero(ink.any(axis=0))[0]
    if not len(cols):
        return []
    # The stem: the right quarter's columns whose ink reaches near the top of
    # that quarter (the wave's tail curls down and stays low).
    right = cols[cols >= cols[0] + 0.75 * (cols[-1] - cols[0])]
    tops = {int(c): int(np.nonzero(ink[:, c])[0][0]) for c in right}
    highest = min(tops.values())
    stem = [c for c, t in tops.items() if t <= highest + max(2, int(0.08 * ink.shape[0]))]
    top_row = int(round((r.y1 - top) * r.res + r.m))
    if stem and top_row < highest:
        ink[max(top_row, 0) : highest + 1, min(stem) : max(stem) + 1] = True
    return trace_bitmap(ink, r.to_units)


def fit_into(contours: list[Contour], box: tuple[float, float, float, float]) -> list[Contour]:
    """Contours scaled down evenly (never up) to fit `box`, centred on it."""
    if not contours:
        return contours
    bx0, by0, bx1, by1 = contours_bbox(contours)
    tx0, ty0, tx1, ty1 = box
    k = min(1.0, (tx1 - tx0) / max(bx1 - bx0, 1), (ty1 - ty0) / max(by1 - by0, 1))
    if k >= 0.999:
        return contours
    cx, cy, tcx, tcy = (bx0 + bx1) / 2, (by0 + by1) / 2, (tx0 + tx1) / 2, (ty0 + ty1) / 2

    def f(p):
        return (tcx + (p[0] - cx) * k, tcy + (p[1] - cy) * k)

    return [Contour(f(c.start), [(seg[0], *[f(q) for q in seg[1:]]) for seg in c.segments]) for c in contours]


def refit(derived: list[Drawing], plans: list[DerivePlan], drawings: dict[str, Drawing]) -> list[Drawing]:
    """The derived parts, ra-phala variants and stacked pieces refitted."""
    by_plan = {p.glyph: p for p in plans}
    have = {**drawings, **{d.glyph: d for d in derived}}
    for d in derived:
        plan = by_plan.get(d.glyph)
        if plan is None:
            continue
        if plan.method == "variant" and plan.source == RAPHALA and d.glyph.startswith(RAPHALA + ".") and have.get(RAPHALA):
            contours = raphala_variant(plan, have[RAPHALA], have)
            if contours:
                d.contours = contours
        elif plan.method == "slice" and plan.advance == 0:
            d.contours = fit_into(d.contours, plan.bbox)
    return derived


def whole_ka_before_raphala(font: TTFont):
    """ক্র without its own shape. The base font makes ক্র from a half ক and
    a ra-phala variant, then replaces both with t_ra-beng (the ত্র-like
    body of ক্র). When the writer hasn't drawn that one, the steps before it
    leave a half ক and a stray arm: "কত্র". Stop at the start instead: a
    whole ক with the ra-phala under it, as ক্র is handwritten."""
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            if lookup.LookupType == 7:
                st = st.ExtSubTable
            if getattr(st, "LookupType", None) != 6 or st.Format != 3 or len(st.InputCoverage) != 1 or not st.LookAheadCoverage:
                continue
            inputs = st.InputCoverage[0].glyphs
            if "ka-beng" in inputs and "raphala-beng" in st.LookAheadCoverage[0].glyphs:
                inputs.remove("ka-beng")


def final_shaper(glyphs: set[str]) -> Shaper:
    """Like basefont.simulated_shaper, with the font build's own change to
    the rules: how the finished font will shape text when the writer has
    these glyphs."""
    font = base_ttfont()
    if "t_ra-beng" not in glyphs:
        whole_ka_before_raphala(font)
    font = subset_font(font, glyphs)
    out = io.BytesIO()
    font.save(out)
    return Shaper(out.getvalue())
