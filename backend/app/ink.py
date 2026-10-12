"""Separate the user's ink from paper, shadows and the printed grey guides.

Works by darkness, not hue, so a black-and-white print or photocopy behaves
like a colour print:

1. Flatten the lighting: divide by a smooth estimate of the bare paper.
2. Measure how dark the printed guides came out on this photo, using the
   known template layout at canonical coordinates.
3. Ink = clearly darker than paper. Where guides are printed (with a few px
   of slack for warp error), ink must also be clearly darker than the guides.
4. Bridge strokes across guide lines so a line under a stroke never cuts it.
5. Drop printed residue: toner clumps on guides, line- or ghost-shaped
   fragments, and small specks that are lighter than the user's own strokes
   (a real dot from a fine pen is small but as dark as the rest of the ink).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import config as C
from .guides import guide_masks

MASK_SLACK_PX = 6  # warp error we tolerate around printed guides
SPECK_PX = 12  # smaller components are noise
SMALL_PX = 80  # components below this must be about as dark as real strokes
SMALL_PEAK_RATIO = 0.75  # ... i.e. peak darkness >= this x the ink's median
TONER_CLUMP_PX = 70  # small components sitting on guides are residue


@dataclass
class InkStats:
    guide_darkness: float  # median darkness of printed guides (0 paper .. 1 black)
    guide_p95: float
    loose: float  # threshold off the guides
    strict: float  # threshold on the guides
    removed_components: int


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
    """Binary ink image (uint8, 255 = ink) at canonical resolution."""
    smooth = cv2.GaussianBlur(gray, (0, 0), 1.0)  # averages laser halftone dots
    bg = np.maximum(_background(smooth), 1).astype(np.float32)
    dark = np.clip(1.0 - smooth.astype(np.float32) / bg, 0, 1)
    del bg, smooth

    lines, areas = guide_masks(page)
    line_band = _dilate(lines, MASK_SLACK_PX) > 0
    area_band = _dilate(areas, MASK_SLACK_PX) > 0
    band = line_band | area_band

    # How dark did this printer/photo make the guides? Take the darkest pixel
    # near each line pixel, so a px or two of warp error doesn't hit paper.
    near = cv2.dilate(dark, np.ones((7, 7), np.uint8))[lines > 0]
    g50 = float(np.median(near)) if near.size else 0.0
    g95 = float(np.percentile(near, 95)) if near.size else 0.0
    del near
    loose = float(np.clip(g50 + 0.15, 0.30, 0.55))
    strict = float(np.clip(g50 + 0.27, loose + 0.08, 0.72))

    ink_loose = dark > loose
    ink = (ink_loose & ~band) | ((dark > strict) & band)

    # Bridge strokes across guides: close small gaps, but only fill pixels
    # that are inked at the loose threshold and lie on a guide.
    k = 2 * MASK_SLACK_PX + 3
    closed = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    ink |= (closed > 0) & band & ink_loose
    del closed, ink_loose

    ink_u8 = ink.astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink_u8, connectivity=8)
    area = stats[:, cv2.CC_STAT_AREA]
    w, h = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]
    in_line = np.bincount(labels[line_band], minlength=n)
    in_area = np.bincount(labels[area_band], minlength=n)
    in_band = np.bincount(labels[band], minlength=n)
    frac_band = in_band / np.maximum(area, 1)
    frac_line = in_line / np.maximum(area, 1)
    frac_area = in_area / np.maximum(area, 1)

    band_px = 2 * MASK_SLACK_PX + 4
    long_px = round(3 * C.PX_PER_MM)
    drop = area < SPECK_PX
    drop |= (frac_band >= 0.85) & (area < TONER_CLUMP_PX)
    line_like = ((w >= long_px) & (h <= band_px)) | ((h >= long_px) & (w <= band_px))
    drop |= (frac_line >= 0.85) & line_like
    drop |= (frac_area >= 0.95) & (area > 400)  # a whole ghost letter came through
    drop[0] = False

    # Small components must be about as dark as the user's real strokes.
    big = (area >= 400) & ~drop
    big[0] = False
    ink_dark = float(np.median(dark[big[labels]])) if big.any() else 0.8
    min_peak = max(strict, SMALL_PEAK_RATIO * ink_dark)
    for i in np.nonzero((area < SMALL_PX) & ~drop)[0]:
        if i == 0:
            continue
        x, y, cw, ch = stats[i, :4]
        box = np.s_[y : y + ch, x : x + cw]
        if dark[box][labels[box] == i].max() < min_peak:
            drop[i] = True
    del dark

    keep = ~drop
    keep[0] = False
    out = (keep[labels] * 255).astype(np.uint8)
    return out, InkStats(g50, g95, loose, strict, int(drop[1:].sum()))
