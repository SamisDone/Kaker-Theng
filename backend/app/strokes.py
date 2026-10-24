"""Letters drawn in the browser: strokes straight to outlines, no photo.

The browser sends each stroke as points in millimetres inside the cell box
the template prints (origin top-left, y down), so the ONE transform applies
unchanged (vectorize.py): baseline -> y=0, 1 font unit = C.MM_PER_UNIT.
Each stroke is smoothed the way the browser drew it (quadratic curves
through the midpoints), widened to the pen width with round ends and joins,
and all strokes are merged into one outline (pyclipper). No raster, no
OpenCV, no potrace.
"""

from __future__ import annotations

import math

import pyclipper

from . import config as C
from .glyphmap import Cell
from .guides import baseline_mm
from .vectorize import Contour, Drawing, contours_bbox

PEN_MM = 0.9  # about the line of a felt-tip pen; fontbuild's default stroke is 60 units
SAMPLE_MM = 0.15  # spacing of points along the smoothed centre line
SCALE = 16  # Clipper works in integers: 1/16 font unit
ARC_TOLERANCE_UNITS = 0.4  # how closely round ends follow a true circle
SIMPLIFY_UNITS = 1.0  # drop outline points closer than this to a straight line

# Limits per cell, so one request can't make the server do unbounded work.
MAX_STROKES = 80
MAX_POINTS = 6000
MARGIN_MM = 2.0  # points may stray this far outside the cell box


class StrokeError(ValueError):
    pass


def check_strokes(strokes, cell: Cell) -> list[list[tuple[float, float]]]:
    """Validate what the browser sent: a list of strokes, each a list of
    [x, y] in cell millimetres. Returns clean float tuples."""
    if not isinstance(strokes, list) or len(strokes) > MAX_STROKES:
        raise StrokeError(f"at most {MAX_STROKES} strokes per letter")
    _, _, w, h = cell.box_mm()
    out, total = [], 0
    for s in strokes:
        if not isinstance(s, list) or not s:
            raise StrokeError("a stroke is a non-empty list of points")
        pts = []
        for p in s:
            if not (isinstance(p, (list, tuple)) and len(p) >= 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[:2])):
                raise StrokeError("a point is [x, y] in millimetres")
            x, y = float(p[0]), float(p[1])
            if not (-MARGIN_MM <= x <= w + MARGIN_MM and -MARGIN_MM <= y <= h + MARGIN_MM):
                raise StrokeError("a point is outside the letter's box")
            pts.append((x, y))
        total += len(pts)
        out.append(pts)
    if total > MAX_POINTS:
        raise StrokeError(f"at most {MAX_POINTS} points per letter")
    return out


def smooth(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The centre line the browser draws: straight to the first midpoint,
    quadratic curves through each point's midpoints, straight to the end."""
    if len(points) < 3:
        return list(points)
    mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(points, points[1:])]
    out = [points[0], mids[0]]
    for i in range(1, len(points) - 1):
        p0, c, p1 = mids[i - 1], points[i], mids[i]
        n = max(2, math.ceil((math.dist(p0, c) + math.dist(c, p1)) / SAMPLE_MM))
        for k in range(1, n + 1):
            t = k / n
            u = 1 - t
            out.append((u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0], u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]))
    out.append(points[-1])
    return out


def outline(strokes: list[list[tuple[float, float]]], cell: Cell) -> list[Contour]:
    """Strokes in cell mm -> merged outline contours in font units."""
    base = baseline_mm(cell) - cell.box_mm()[1]  # baseline, mm below the cell top
    k = SCALE / C.MM_PER_UNIT
    paths = []
    for s in strokes:
        line = [(round(x * k), round((base - y) * k)) for x, y in smooth(s)]
        line = [p for i, p in enumerate(line) if i == 0 or p != line[i - 1]]
        if len(line) == 1:  # a dot: a tiny segment gets round ends, a circle
            line.append((line[0][0] + 1, line[0][1]))
        paths.append(line)
    if not paths:
        return []
    off = pyclipper.PyclipperOffset(arc_tolerance=ARC_TOLERANCE_UNITS * SCALE)
    off.AddPaths(paths, pyclipper.JT_ROUND, pyclipper.ET_OPENROUND)
    pen_units = PEN_MM / C.MM_PER_UNIT
    polys = pyclipper.CleanPolygons(off.Execute(pen_units / 2 * SCALE), SIMPLIFY_UNITS * SCALE)
    contours = []
    for poly in polys:
        if len(poly) < 3:
            continue
        # Clipper's outer outlines run counter-clockwise (y up); TrueType's
        # run clockwise, holes the other way round: reverse them all.
        pts = [(x / SCALE, y / SCALE) for x, y in reversed(poly)]
        contours.append(Contour(pts[0], [("L", p) for p in pts[1:]]))
    return contours


def drawing(cell: Cell, strokes: list[list[tuple[float, float]]]) -> Drawing:
    contours = outline(strokes, cell)
    return Drawing(cell.id, cell.glyph, cell.kind, cell.unicode, contours, contours_bbox(contours))
