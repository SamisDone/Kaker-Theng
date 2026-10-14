"""Separate the user's ink from paper, shadows and the printed grey guides.

Works by darkness, not hue, so a black-and-white print or photocopy behaves
like a colour print:

1. Flatten the lighting: divide by a smooth estimate of the bare paper.
2. Measure how dark the printed guide lines and ghost letters came out on
   this photo (using the known template layout at canonical coordinates),
   and how dark this user's pen is (felt-tip near black, ballpoint lighter).
3. Ink = clearly darker than paper. On guide lines and ghost letters (with
   a few px of slack for warp error) ink must also be clearly darker than
   what is printed there. Thresholds sit between the two measurements.
4. Bridge strokes across guide lines so a line under a stroke never cuts it.
5. Drop printed residue: line- or ghost-shaped fragments, and small specks
   lighter than the user's own strokes (a real dot is small but as dark as
   the pen). cells.py then drops specks that sit alone inside a cell.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import config as C
from .guides import GHOST_BIT, LABEL_BIT, LINE_BIT, grid_box_px, guide_bits

MASK_SLACK_PX = 6  # warp error we tolerate around printed guides
SPECK_PX = 12  # smaller components are noise
SMALL_PX = 80  # components below this must be about as dark as real strokes
SMALL_PEAK_RATIO = 0.75  # ... i.e. peak darkness >= this x the user's stroke darkness


@dataclass
class InkStats:
    guide_darkness: float  # median darkness of printed guides (0 paper .. 1 black)
    guide_p95: float
    loose: float  # threshold off the guides
    strict: float  # threshold on the guides
    removed_components: int
    ink_darkness: float  # this user's strokes (75th percentile)
    ghost_darkness: float  # median darkness inside printed ghost letters
    strict_ghost: float  # threshold on ghost letters


def _background(gray: np.ndarray) -> np.ndarray:
    """Bare-paper brightness everywhere, estimated by closing the ink away."""
    small = cv2.resize(gray, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    small = cv2.dilate(small, kernel)
    small = cv2.medianBlur(small, 21)
    small = cv2.GaussianBlur(small, (0, 0), 6)
    return cv2.resize(small, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)


def _dilate(mask: np.ndarray, px: int) -> np.ndarray:
    return cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1)))


def extract_ink(gray: np.ndarray, page: int) -> tuple[np.ndarray, InkStats]:
    """Binary ink image (uint8, 255 = ink) at canonical resolution.

    Works on the grid area only, with darkness as uint8 (0 paper .. 255
    black), to keep memory low on a small server. Thresholds are fractions."""
    x0, y0, x1, y1 = grid_box_px(page, margin_px=40)
    smooth = cv2.GaussianBlur(gray[y0:y1, x0:x1], (0, 0), 1.0)  # averages laser halftone dots
    bg = np.maximum(_background(smooth), 1)
    dark = cv2.subtract(255, cv2.divide(smooth, bg, scale=255))  # saturates: brighter than paper -> 0
    del smooth, bg

    bits = guide_bits(page)[y0:y1, x0:x1]
    lines = (bits & LINE_BIT).astype(bool)
    ghosts = (bits & GHOST_BIT).astype(np.uint8)
    line_band = _dilate(lines.astype(np.uint8), MASK_SLACK_PX) > 0
    area_band = _dilate((bits & (LABEL_BIT | GHOST_BIT)).astype(np.uint8), MASK_SLACK_PX) > 0
    band = line_band | area_band

    # How dark did this printer/photo make the guides? Take the darkest pixel
    # near each line pixel, so a px or two of warp error doesn't hit paper.
    near = cv2.dilate(dark, np.ones((7, 7), np.uint8))[lines]
    g50 = float(np.median(near)) / 255 if near.size else 0.0
    g95 = float(np.percentile(near, 95)) / 255 if near.size else 0.0
    del near, lines

    # How dark is this user's pen on this photo? A felt-tip is near-black, a
    # blue ballpoint much lighter. Measure their strokes inside the grid.
    ink_dark = _stroke_darkness(dark, band, g50)
    loose = float(np.clip(max(g50 + 0.10, 0.42 * ink_dark), 0.18, 0.55))
    ink_cap = max(loose + 0.04, 0.85 * ink_dark)  # the user's strokes must always pass
    strict = float(min(max(g50 + 0.22, loose + 0.06), ink_cap, 0.72))
    # Filled ghost letters print much darker than thin lines on a photocopy,
    # so they get their own threshold, measured on their eroded cores.
    ghost_core = cv2.erode(ghosts, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))) > 0
    ga50 = float(np.median(dark[ghost_core])) / 255 if ghost_core.sum() > 500 else g50
    strict_area = float(min(max(ga50 + 0.18, loose + 0.06), ink_cap, 0.75))
    del ghost_core, ghosts

    def over(t: float) -> np.ndarray:
        return dark > round(t * 255)

    ink_loose = over(loose)
    on_lines = line_band & ~area_band
    ink = (ink_loose & ~band) | (over(strict) & on_lines) | (over(strict_area) & area_band)

    # Bridge strokes across guide lines: close small gaps, but only fill
    # pixels that are inked at the loose threshold and lie on a line (never
    # on a ghost letter, which could be dark enough to pass).
    k = 2 * MASK_SLACK_PX + 3
    closed = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    ink |= (closed > 0) & on_lines & ink_loose
    del closed, ink_loose, on_lines

    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    del ink
    area = stats[:, cv2.CC_STAT_AREA]
    w, h = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]
    frac_line = np.bincount(labels[line_band], minlength=n) / np.maximum(area, 1)
    frac_area = np.bincount(labels[area_band], minlength=n) / np.maximum(area, 1)
    del line_band, area_band, band

    band_px = 2 * MASK_SLACK_PX + 4
    long_px = round(3 * C.PX_PER_MM)
    drop = area < SPECK_PX
    line_like = ((w >= long_px) & (h <= band_px)) | ((h >= long_px) & (w <= band_px))
    ink_level = ink_dark * 255
    # Shaped like a printed line or a whole ghost letter, and lying on it.
    # A মাত্রা written right along the guide looks the same, so only drop it
    # if it is lighter than this user's strokes: printed residue just clears
    # the threshold, pen ink is as dark as the rest of their writing.
    suspect = ((frac_line >= 0.85) & line_like) | ((frac_area >= 0.95) & (area > 400))
    suspect[0] = False
    for i in np.nonzero(suspect)[0]:
        x, y, cw, ch = stats[i, :4]
        box = np.s_[y : y + ch, x : x + cw]
        if np.median(dark[box][labels[box] == i]) < SMALL_PEAK_RATIO * ink_level:
            drop[i] = True
    drop[0] = False

    # Small components (dots of i, j, !, ?, :, ঁ, ং, the nukta, and toner
    # specks) are judged against this user's own strokes on this page: a real
    # dot is small but as dark as the pen; specks are lighter.
    for i in np.nonzero((area < SMALL_PX) & ~drop)[0]:
        if i == 0:
            continue
        x, y, cw, ch = stats[i, :4]
        box = np.s_[y : y + ch, x : x + cw]
        if dark[box][labels[box] == i].max() < SMALL_PEAK_RATIO * ink_level:
            drop[i] = True
    del dark

    keep = ~drop
    keep[0] = False
    out = np.zeros(gray.shape, np.uint8)
    out[y0:y1, x0:x1] = keep[labels].view(np.uint8) * 255
    return out, InkStats(g50, g95, loose, strict, int(drop[1:].sum()), ink_dark, ga50, strict_area)


def _stroke_darkness(dark: np.ndarray, band: np.ndarray, guide: float) -> float:
    """Typical core darkness of the user's strokes (0..1): the 75th
    percentile of darkness over large ink components off the guides."""
    cand = ((dark > round(max(guide + 0.08, 0.15) * 255)) & ~band).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    del cand
    big = stats[:, cv2.CC_STAT_AREA] >= 300
    big[0] = False
    if not big.any():
        return 0.8
    return float(np.percentile(dark[big[labels]], 75)) / 255
