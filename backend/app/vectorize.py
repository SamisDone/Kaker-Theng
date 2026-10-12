"""Trace cell bitmaps with potrace and map them to font units.

All glyphs share ONE transform: the cell's baseline goes to y=0 and the
printed মাত্রা / cap line goes to the base font's headline height. Nothing is
scaled to its own bounding box, so relative sizes stay as the user wrote them.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import potrace

from . import config as C
from .cells import CellInk
from .guides import baseline_mm

UNITS_PER_PX = 1 / (C.MM_PER_UNIT * C.PX_PER_MM)

# A contour is a list of segments in font units:
#   ("L", (x, y))  or  ("C", (x1, y1), (x2, y2), (x, y)); it starts at .start
Point = tuple[float, float]


@dataclass
class Contour:
    start: Point
    segments: list[tuple]


@dataclass
class Drawing:
    """A written glyph in font units. x is measured from the cell's left edge."""

    cell_id: str
    glyph: str
    kind: str
    unicode: int | None
    contours: list[Contour]
    bbox: tuple[float, float, float, float]  # xMin, yMin, xMax, yMax
    positioned: bool = False  # True: already in final glyph coordinates (derived parts)
    advance: int | None = None  # set when positioned


def _trace(bitmap: np.ndarray):
    # Soften the pixel staircase a little before tracing.
    img = cv2.GaussianBlur(bitmap.astype(np.uint8) * 255, (0, 0), 0.8)
    smooth = img > 127
    # potracer fills False pixels.
    return potrace.Bitmap(~smooth).trace(turdsize=4, alphamax=1.0, opticurve=True, opttolerance=0.2)


def trace_bitmap(bitmap: np.ndarray, to_units) -> list[Contour]:
    """Trace a bool bitmap; `to_units(col, row)` maps pixel coords to font units."""
    contours = []
    for curve in _trace(bitmap):
        segs = []
        for s in curve.segments:
            if s.is_corner:
                segs.append(("L", to_units(s.c.x, s.c.y)))
                segs.append(("L", to_units(s.end_point.x, s.end_point.y)))
            else:
                segs.append(("C", to_units(s.c1.x, s.c1.y), to_units(s.c2.x, s.c2.y), to_units(s.end_point.x, s.end_point.y)))
        contours.append(Contour(to_units(curve.start_point.x, curve.start_point.y), segs))
    return contours


def contours_bbox(contours: list[Contour]) -> tuple[float, float, float, float]:
    pts = [c.start for c in contours] + [p for c in contours for seg in c.segments for p in seg[1:]]
    if not pts:
        return (0, 0, 0, 0)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def vectorize(ci: CellInk) -> Drawing:
    k = UNITS_PER_PX
    cell_left_px = ci.cell.box_mm()[0] * C.PX_PER_MM
    base_px = baseline_mm(ci.cell) * C.PX_PER_MM

    def to_units(x, y) -> Point:
        return ((x + ci.x0 - cell_left_px) * k, (base_px - (y + ci.y0)) * k)

    contours = trace_bitmap(ci.bitmap, to_units)
    c = ci.cell
    return Drawing(c.id, c.glyph, c.kind, c.unicode, contours, contours_bbox(contours))
