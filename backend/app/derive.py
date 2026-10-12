"""Conjunct parts made from glyphs the user already wrote.

Noto builds some conjuncts from parts (half forms, below-base forms, headline
pieces). Asking people to write fragments is unfriendly, so each part is
classified once, offline, from the base font alone:

  bar    a plain piece of মাত্রা: drawn at the user's measured মাত্রা height
         and stroke thickness.
  slice  part of a letter at the same scale (a half form is the top of the
         consonant before the hasanta; some parts are a clear match to part of
         a letter in the same conjunct or of a vowel sign): cut from the user's
         letter.
  body   a below-base form: the body (no মাত্রা) of the consonant after the
         hasanta, scaled down into the part's box.
  written  nothing fits: the user writes it in its own cell.

At font build time the plan is applied to the user's drawings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

from .basefont import base_shaper, headline_units
from .outline import Raster, contour_polygons, glyph_polygons, polys_bbox

HALANT = "্"
MATCH_RES = 0.08  # px per unit for planning
BUILD_RES = 0.25  # px per unit when deriving from the user's drawings
SLICE_MIN_IOU = 0.80
TIE = 0.12
MAX_STRETCH = 1.35  # body: horizontal / vertical scale at most this far apart


@dataclass
class DerivePlan:
    glyph: str
    method: str  # "bar" | "slice" | "body" | "written"
    source: str | None
    score: float
    offset: tuple[float, float] | None  # slice: source coords = part coords + offset
    bbox: tuple[float, float, float, float]  # the part's box in the base font
    advance: int
    context: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _noto_raster(name: str) -> Raster | None:
    tt = base_shaper().tt
    g = tt["glyf"][name]
    if not g.numberOfContours:
        return None
    r = Raster(g.xMin, g.yMin, g.xMax, g.yMax, MATCH_RES, margin=20)
    r.fill(glyph_polygons(tt.getGlyphSet(), name))
    return r


def _ink_crop(img: np.ndarray) -> tuple[np.ndarray, int, int]:
    ys, xs = np.nonzero(img)
    return img[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], int(xs.min()), int(ys.min())


def _match(part: Raster, source: Raster) -> tuple[float, tuple[float, float]] | None:
    """Best placement of the part inside the source letter, at the same scale."""
    pc, pcx, pcy = _ink_crop(part.img)
    if source.img.shape[0] < pc.shape[0] or source.img.shape[1] < pc.shape[1]:
        return None
    scores = cv2.matchTemplate(source.img.astype(np.float32), pc.astype(np.float32), cv2.TM_CCORR)
    _, _, _, (x, y) = cv2.minMaxLoc(scores)
    win = source.img[y : y + pc.shape[0], x : x + pc.shape[1]] > 0
    iou = float((win & (pc > 0)).sum() / max((win | (pc > 0)).sum(), 1))
    # Same pixel in both: part coords + offset = source coords.
    px, py = part.to_units(pcx, pcy)
    sx, sy = source.to_units(x, y)
    return iou, (sx - px, sy - py)


def _has_headline_bar(r: Raster) -> bool:
    pc, _, _ = _ink_crop(r.img)
    return pc.mean() > 0.9 and pc.shape[0] < 110 * MATCH_RES


def plan_part(part: str, context: str, signs: list[str], user: set[str]) -> DerivePlan:
    tt = base_shaper().tt
    cmap = tt.getBestCmap()
    g = tt["glyf"][part]
    bbox = (g.xMin, g.yMin, g.xMax, g.yMax)
    advance = tt["hmtx"][part][0]
    letters = [cmap[ord(ch)] for ch in context if ch != HALANT and ord(ch) in cmap]
    letters = [n for n in letters if n in user]

    def plan(method, source=None, score=0.0, offset=None, reason=""):
        return DerivePlan(part, method, source, round(score, 3), offset, bbox, advance, context, reason)

    pr = _noto_raster(part)
    if _has_headline_bar(pr):
        return plan("bar", reason="solid bar the height of a মাত্রা")

    matches = []
    for rank, src in enumerate(dict.fromkeys(letters + [s for s in signs if s in user])):
        m = _match(pr, _noto_raster(src))
        if m:
            matches.append((m[0], -rank, src, m[1]))
    matches.sort(reverse=True)
    if matches and matches[0][0] >= SLICE_MIN_IOU:
        best = matches[0][0]
        # Near-ties go to the earlier candidate: the conjunct's own letters
        # first, then vowel signs in template order.
        iou, _, src, off = max((m for m in matches if m[0] >= best - TIE), key=lambda m: m[1])
        return plan("slice", src, iou, off, f"matches part of {src} (IoU {iou:.2f})")

    head_top = tt["glyf"][cmap[ord("ক")]].yMax
    if advance > 0 and g.yMax >= head_top - 25 and letters:
        first = next(m for m in matches if m[2] == letters[0])
        return plan("slice", letters[0], first[0], first[3], f"half form: top of {letters[0]}")
    if advance == 0 and g.yMin < 0 and letters:
        return plan("body", letters[-1], reason=f"below-base form: body of {letters[-1]}, scaled")
    return plan("written", reason="no letter the user writes has this shape")


# --- Applying the plan to the user's drawings -----------------------------------


def measure_matra(drawings: dict, matra_glyphs: set[str]) -> tuple[float, float]:
    """(centre y, thickness) of the user's মাত্রা, in font units."""
    centres, thicknesses = [], []
    for name, d in drawings.items():
        if name not in matra_glyphs or not d.contours:
            continue
        polys = contour_polygons(d.contours)
        x0, y0, x1, y1 = polys_bbox(polys)
        r = Raster(x0, y0, x1, y1, BUILD_RES, margin=0)
        r.fill(polys)
        cover = r.img.mean(axis=1)
        top_rows = int(r.h * 0.45)
        rows = [i for i in range(top_rows) if cover[i] >= 0.55]
        if not rows:
            continue
        band = [rows[0]]
        for i in rows[1:]:
            if i != band[-1] + 1:
                break
            band.append(i)
        top = r.to_units(0, band[0])[1]
        bottom = r.to_units(0, band[-1] + 1)[1]
        centres.append((top + bottom) / 2)
        thicknesses.append(top - bottom)
    if len(centres) < 3:
        return float(headline_units()), 60.0
    return float(np.median(centres)), float(np.median(thicknesses))


def _bar(plan: DerivePlan, matra: tuple[float, float]):
    from .vectorize import Contour

    centre, thick = matra
    x0, _, x1, _ = plan.bbox
    lo, hi = centre - thick / 2, centre + thick / 2
    return [Contour((x0, lo), [("L", (x0, hi)), ("L", (x1, hi)), ("L", (x1, lo))])]


def _slice(plan: DerivePlan, d):
    from .vectorize import trace_bitmap

    tt = base_shaper().tt
    sg = tt["glyf"][plan.source]
    polys = contour_polygons(d.contours)
    ux0, _, ux1, _ = polys_bbox(polys)
    kx = (sg.xMax - sg.xMin) / max(ux1 - ux0, 1)
    ox, oy = plan.offset
    # User letter -> base font's horizontal frame (y stays: one transform for
    # all glyphs) -> part coordinates.
    moved = [[(sg.xMin + (x - ux0) * kx - ox, y - oy) for x, y in p] for p in polys]
    x0, y0, x1, y1 = plan.bbox
    r = Raster(x0 - 10, y0 - 10, x1 + 10, y1 + 10, BUILD_RES)
    r.fill(moved)
    return trace_bitmap(r.img > 0, r.to_units)


def _body(plan: DerivePlan, d, matra: tuple[float, float]):
    from .vectorize import Contour, trace_bitmap

    polys = contour_polygons(d.contours)
    x0, y0, x1, y1 = polys_bbox(polys)
    r = Raster(x0, y0, x1, y1, BUILD_RES)
    r.fill(polys)
    centre, thick = matra
    cut_row = int(round((r.y1 - (centre - 0.75 * thick)) * r.res + r.m))
    r.img[: max(cut_row, 0)] = 0
    if not r.img.any():
        return []
    contours = trace_bitmap(r.img > 0, r.to_units)
    pts = [p for c in contours for seg in c.segments for p in seg[1:]] + [c.start for c in contours]
    bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
    bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)
    tx0, ty0, tx1, ty1 = plan.bbox
    # Fill the part's box: below-base forms are often flatter than the letter,
    # so allow up to MAX_STRETCH more scaling across than down.
    sy = (ty1 - ty0) / max(by1 - by0, 1)
    sx = float(np.clip((tx1 - tx0) / max(bx1 - bx0, 1), sy / MAX_STRETCH, sy * MAX_STRETCH))
    cx, tcx = (bx0 + bx1) / 2, (tx0 + tx1) / 2

    def f(p):
        return (tcx + (p[0] - cx) * sx, ty0 + (p[1] - by0) * sy)

    return [Contour(f(c.start), [(seg[0], *[f(p) for p in seg[1:]]) for seg in c.segments]) for c in contours]


def derive_parts(plans: list[DerivePlan], drawings: dict, matra: tuple[float, float]) -> list:
    """Drawings for every derivable part whose source the user wrote."""
    from .vectorize import Drawing

    out = []
    for plan in plans:
        if plan.method == "written":
            continue
        if plan.method == "bar":
            contours = _bar(plan, matra)
        else:
            src = drawings.get(plan.source)
            if not src or not src.contours:
                continue
            contours = _slice(plan, src) if plan.method == "slice" else _body(plan, src, matra)
        if not contours:
            continue
        kind = "mark" if plan.advance == 0 else "base"
        out.append(Drawing(f"derived:{plan.method}", plan.glyph, kind, None, contours, (0, 0, 0, 0), positioned=True, advance=plan.advance))
    return out
