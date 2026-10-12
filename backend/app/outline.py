"""Outline helpers: flatten glyphs and drawings to polygons, rasterise them."""

from __future__ import annotations

import cv2
import numpy as np
from fontTools.pens.basePen import BasePen


class PolygonPen(BasePen):
    """Flattens outlines into polygons (lists of (x, y) in font units)."""

    def __init__(self, glyph_set=None, steps: int = 8):
        super().__init__(glyph_set)
        self.polys: list[list[tuple[float, float]]] = []
        self.steps = steps

    def _moveTo(self, p):
        self.polys.append([p])

    def _lineTo(self, p):
        self.polys[-1].append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.polys[-1][-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            u = 1 - t
            self.polys[-1].append(
                (
                    u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
                )
            )

    def _closePath(self):
        pass


def glyph_polygons(glyph_set, name: str) -> list[list[tuple[float, float]]]:
    pen = PolygonPen(glyph_set)
    glyph_set[name].draw(pen)
    return [p for p in pen.polys if len(p) > 2]


def contour_polygons(contours) -> list[list[tuple[float, float]]]:
    """Polygons from vectorize.Contour lists (start + L/C segments)."""
    pen = PolygonPen()
    for c in contours:
        pen.moveTo(c.start)
        for seg in c.segments:
            if seg[0] == "L":
                pen.lineTo(seg[1])
            else:
                pen.curveTo(*seg[1:])
        pen.closePath()
    return [p for p in pen.polys if len(p) > 2]


class Raster:
    """A bitmap covering a box in font units, at `res` px per unit (y up)."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, res: float, margin: int = 4):
        self.x0, self.y1, self.res, self.m = x0, y1, res, margin
        self.w = int(np.ceil((x1 - x0) * res)) + 2 * margin
        self.h = int(np.ceil((y1 - y0) * res)) + 2 * margin
        self.img = np.zeros((self.h, self.w), np.uint8)

    def to_px(self, pts) -> np.ndarray:
        pts = np.asarray(pts, np.float64)
        return np.stack([(pts[:, 0] - self.x0) * self.res + self.m, (self.y1 - pts[:, 1]) * self.res + self.m], 1)

    def to_units(self, col: float, row: float) -> tuple[float, float]:
        return (col - self.m) / self.res + self.x0, self.y1 - (row - self.m) / self.res

    def fill(self, polys, even_odd: bool = True):
        px = [np.round(self.to_px(p) * 16).astype(np.int32) for p in polys if len(p) > 2]
        if not px:
            return
        if even_odd:
            cv2.fillPoly(self.img, px, 1, cv2.LINE_8, shift=4)
        else:
            for p in px:
                cv2.fillPoly(self.img, [p], 1, cv2.LINE_8, shift=4)


def polys_bbox(polys) -> tuple[float, float, float, float]:
    pts = np.concatenate([np.asarray(p) for p in polys])
    return float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 0].max()), float(pts[:, 1].max())
