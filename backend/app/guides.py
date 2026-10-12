"""Geometry of everything printed inside a cell, in one place.

The PDF draws these guides; the scanner rasterises the same guides at
canonical resolution to know where printed residue can be.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np
from reportlab.pdfbase.pdfmetrics import stringWidth

from . import config as C
from .basefont import base_shaper, headline_units
from .glyphmap import Cell, build_layout
from .outline import glyph_polygons

BORDER_PT = 0.6
GUIDE_PT = 0.5
GUIDE_INSET_MM = 1.5  # guide lines stop short of the border
LATIN_LABEL = ("Helvetica-Bold", 7.5)
LABEL_X_MM, LATIN_LABEL_BASE_MM, BANGLA_LABEL_BASE_MM, BANGLA_LABEL_HEAD_MM = 1.2, 3.4, 3.6, 1.9
PT_TO_MM = 25.4 / 72


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    width_pt: float
    dashed: bool = False


def baseline_mm(cell: Cell) -> float:
    return cell.box_mm()[1] + C.BASELINE_FROM_TOP_MM


def headline_mm(cell: Cell) -> float:
    return baseline_mm(cell) - headline_units() * C.MM_PER_UNIT


def run_left_mm(cell: Cell) -> float:
    """Where the shaped run (ghost + written glyph) starts, page coordinates."""
    return cell.box_mm()[0] + (C.CELL_MM - cell.run_advance * C.MM_PER_UNIT) / 2


def cell_lines(cell: Cell) -> list[Line]:
    x, y, w, h = cell.box_mm()
    lines = [
        Line(x, y, x + w, y, BORDER_PT),
        Line(x, y + h, x + w, y + h, BORDER_PT),
        Line(x, y, x, y + h, BORDER_PT),
        Line(x + w, y, x + w, y + h, BORDER_PT),
    ]
    x1, x2 = x + GUIDE_INSET_MM, x + w - GUIDE_INSET_MM
    for gy in (baseline_mm(cell), headline_mm(cell)):
        lines.append(Line(x1, gy, x2, gy, GUIDE_PT))
    if cell.kind == "latin":
        xh = baseline_mm(cell) - headline_units() * C.LATIN_XHEIGHT_RATIO * C.MM_PER_UNIT
        lines.append(Line(x1, xh, x2, xh, GUIDE_PT, dashed=True))
    return lines


def label_box_mm(cell: Cell) -> tuple[float, float, float, float]:
    """x0, y0, x1, y1 of the small label in the top-left corner."""
    x, y, _, _ = cell.box_mm()
    if cell.kind == "latin":
        w = stringWidth(cell.text, *LATIN_LABEL) * PT_TO_MM
        top = LATIN_LABEL_BASE_MM - LATIN_LABEL[1] * 0.75 * PT_TO_MM
        bottom = LATIN_LABEL_BASE_MM + LATIN_LABEL[1] * 0.22 * PT_TO_MM
    else:
        s = BANGLA_LABEL_HEAD_MM / headline_units()
        w = sum(g.x_advance for g in base_shaper().shape(cell.text)) * s
        top = BANGLA_LABEL_BASE_MM - 950 * s
        bottom = BANGLA_LABEL_BASE_MM + 300 * s
    return x + LABEL_X_MM, y + top, x + LABEL_X_MM + w, y + bottom


def ghost_polygons_mm(cell: Cell) -> list[np.ndarray]:
    """Ghost glyph outlines in page millimetres."""
    gs = base_shaper().tt.getGlyphSet()
    left, base, s = run_left_mm(cell), baseline_mm(cell), C.MM_PER_UNIT
    out = []
    for g in cell.ghost_glyphs:
        for poly in glyph_polygons(gs, g.name):
            out.append(np.array([(left + (g.x + px) * s, base - (g.y + py) * s) for px, py in poly]))
    return out


@lru_cache(maxsize=3)
def guide_masks(page: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(lines, labels, ghosts) masks for a page at canonical resolution,
    undilated. Lines: borders and guide lines. Labels: the small label boxes.
    Ghosts: the outlines of the faint ghost letters."""
    k = C.PX_PER_MM
    lines = np.zeros((C.CANON_H_PX, C.CANON_W_PX), np.uint8)
    labels = np.zeros_like(lines)
    ghosts = np.zeros_like(lines)
    for cell in build_layout().page(page):
        for ln in cell_lines(cell):
            t = max(1, round(ln.width_pt * PT_TO_MM * k))
            cv2.line(lines, (round(ln.x1 * k), round(ln.y1 * k)), (round(ln.x2 * k), round(ln.y2 * k)), 255, t)
        x0, y0, x1, y1 = label_box_mm(cell)
        cv2.rectangle(labels, (round(x0 * k), round(y0 * k)), (round(x1 * k), round(y1 * k)), 255, -1)
        polys = [np.round(p * k).astype(np.int32) for p in ghost_polygons_mm(cell)]
        for poly in polys:  # one by one: a union, so counters are covered too
            cv2.fillPoly(ghosts, [poly], 255)
    return lines, labels, ghosts
