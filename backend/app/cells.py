"""Cut the straightened ink image into cells and check each one."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import config as C
from .glyphmap import Cell, build_layout

MIN_INK_PX = 25  # a full stop from a fine pen is ~50 px
EDGE_PX = 15  # this much ink on the cut edge: the letter ran out of the box


@dataclass
class CellInk:
    cell: Cell
    bitmap: np.ndarray  # bool, True = ink, cropped to the cell's inner area
    x0: int  # crop origin in canonical px
    y0: int
    ink_px: int
    status: str  # "ok" | "missing" | "touches_edge"


def cut_cells(ink: np.ndarray, page: int) -> list[CellInk]:
    k = C.PX_PER_MM
    inset = round(C.CELL_CUT_INSET_MM * k)
    out = []
    for cell in build_layout().page(page):
        x, y, w, h = cell.box_mm()
        x0, y0 = round(x * k) + inset, round(y * k) + inset
        x1, y1 = round((x + w) * k) - inset, round((y + h) * k) - inset
        crop = ink[y0:y1, x0:x1] > 0

        # Pieces cut off at the crop edge can be small: clean again.
        n, labels, stats, _ = cv2.connectedComponentsWithStats(crop.astype(np.uint8), connectivity=8)
        small = stats[:, cv2.CC_STAT_AREA] < 12
        small[0] = False
        crop = crop & ~small[labels]

        ink_px = int(crop.sum())
        edge = int(crop[0].sum() + crop[-1].sum() + crop[:, 0].sum() + crop[:, -1].sum())
        status = "missing" if ink_px < MIN_INK_PX else "touches_edge" if edge > EDGE_PX else "ok"
        out.append(CellInk(cell, crop, x0, y0, ink_px, status))
    return out
