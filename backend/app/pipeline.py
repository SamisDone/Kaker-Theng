"""One page photo in, straightened page + traced glyphs out."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import config as C
from .cells import CellInk, cut_cells
from .ink import InkStats, extract_ink
from .scan import ScanError, find_page
from .vectorize import Drawing, vectorize

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MARGIN_RED_BGR = (0x2D, 0x41, 0xC2)
THUMB_W = 900


@dataclass
class PageResult:
    page: int
    drawings: list[Drawing]
    cells: list[dict]  # id, text, status, box (thumbnail px)
    missing_corners: list[str]
    thumbnail_png: bytes
    ink_png: bytes
    stats: InkStats


def decode_image(data: bytes) -> np.ndarray:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ScanError("too_large", "That photo is over 10 MB. Please use a smaller one.", "ছবিটা ১০ MB-র বেশি। আরেকটু ছোট ছবি দিন।")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ScanError("not_an_image", "That file isn't a photo we can read (JPEG or PNG).", "ফাইলটা পড়া গেল না। JPEG বা PNG ছবি দিন।")
    return img


def _thumbnail(gray: np.ndarray, cells: list[CellInk]) -> tuple[bytes, list[dict]]:
    """Straightened page with missing or unreadable cells circled in red."""
    s = THUMB_W / gray.shape[1]
    thumb = cv2.cvtColor(cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
    info = []
    for ci in cells:
        x, y, w, h = (v * C.PX_PER_MM * s for v in ci.cell.box_mm())
        box = [round(x), round(y), round(w), round(h)]
        if ci.status != "ok":
            center = (round(x + w / 2), round(y + h / 2))
            axes = (round(w * 0.55), round(h * 0.5))
            cv2.ellipse(thumb, center, axes, -8, 20, 340, MARGIN_RED_BGR, 2, cv2.LINE_AA)
        info.append({"id": ci.cell.id, "text": ci.cell.text, "glyph": ci.cell.glyph, "status": ci.status, "box": box})
    ok, buf = cv2.imencode(".png", thumb)
    return buf.tobytes(), info


def process_page(image: np.ndarray, expected_page: int | None = None) -> PageResult:
    found = find_page(image, expected_page)
    del image
    ink, stats = extract_ink(found.gray, found.page)
    cells = cut_cells(ink, found.page)
    drawings = [vectorize(ci) for ci in cells if ci.status != "missing"]
    thumb, info = _thumbnail(found.gray, cells)
    ok, ink_png = cv2.imencode(".png", cv2.resize(255 - ink, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA))
    return PageResult(found.page, drawings, info, found.missing_corners, thumb, ink_png.tobytes(), stats)
