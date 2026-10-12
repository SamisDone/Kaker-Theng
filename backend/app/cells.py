"""Cut the straightened ink image into cells and check each one."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import config as C
from .glyphmap import Cell, build_layout

MIN_INK_PX = 25  # a full stop from a fine pen is ~50 px
EDGE_PX = 15  # this much ink on the cut edge: the letter ran out of the box
SMALL_PIECE_PX = 80  # pieces below this must sit near another piece ...
NEAR_MM = 4.5  # ... within this distance
DOT_WIDTH_RATIO = 0.8  # ... and be at least this x the pen's line width across


@dataclass
class CellInk:
    cell: Cell
    bitmap: np.ndarray  # bool, True = ink, cropped to the cell's inner area
    x0: int  # crop origin in canonical px
    y0: int
    ink_px: int
    status: str  # "ok" | "missing" | "touches_edge"


def _clean(crop: np.ndarray) -> np.ndarray:
    """Drop specks inside a cell. The largest piece always stays, and so does
    anything big. A small piece stays only if it sits near a piece already
    kept that is at least its size: the dot of i, j, ! ?, the dots of : ;,
    ঁ, the nukta. Stray specks are alone, and can't vouch for each other."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(crop.astype(np.uint8), connectivity=8)
    if n <= 2:
        return crop
    area = stats[:, cv2.CC_STAT_AREA]
    largest = 1 + int(np.argmax(area[1:]))
    near_px = NEAR_MM * C.PX_PER_MM
    # A pen dot is at least about as wide as the pen's line; specks are finer.
    pen_px = _stroke_width(labels == largest)
    min_area = np.pi * (DOT_WIDTH_RATIO * pen_px / 2) ** 2
    points = {i: np.argwhere(labels == i)[:: max(1, area[i] // 300)] for i in range(1, n)}
    kept = {i for i in range(1, n) if i == largest or area[i] >= SMALL_PIECE_PX}
    for i in sorted((i for i in range(1, n) if i not in kept and area[i] >= max(12, min_area)), key=lambda i: -area[i]):
        for j in kept:
            if area[j] >= area[i]:
                d = np.min(np.hypot(*(points[i][:, None, :] - points[j][None, :, :]).transpose(2, 0, 1)))
                if d <= near_px:
                    kept.add(i)
                    break
    keep = np.zeros(n, bool)
    keep[list(kept)] = True
    return crop & keep[labels]


def _stroke_width(mask: np.ndarray) -> float:
    """Typical line width of a stroke: twice its area over its perimeter."""
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    perimeter = sum(cv2.arcLength(c, True) for c in contours)
    return 2 * float(mask.sum()) / max(perimeter, 1)


def cut_cells(ink: np.ndarray, page: int) -> list[CellInk]:
    k = C.PX_PER_MM
    inset = round(C.CELL_CUT_INSET_MM * k)
    out = []
    for cell in build_layout().page(page):
        x, y, w, h = cell.box_mm()
        x0, y0 = round(x * k) + inset, round(y * k) + inset
        x1, y1 = round((x + w) * k) - inset, round((y + h) * k) - inset
        crop = ink[y0:y1, x0:x1] > 0

        crop = _clean(crop)

        ink_px = int(crop.sum())
        edge = int(crop[0].sum() + crop[-1].sum() + crop[:, 0].sum() + crop[:, -1].sum())
        status = "missing" if ink_px < MIN_INK_PX else "touches_edge" if edge > EDGE_PX else "ok"
        out.append(CellInk(cell, crop, x0, y0, ink_px, status))
    return out
