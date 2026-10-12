"""Synthetic pages: fake handwriting on the real template, printed and photographed.

Two print modes:
  colour  inkjet: smooth grey guides with a slight colour cast
  laser   black-and-white laser: guides halftoned with dot gain, toner specks,
          background haze and a faint drum streak
  copy    a worn photocopy of the laser print: heavier dot gain (22% grey
          comes out ~48%) and three times the toner noise. A stress test.
Then a phone photo: perspective, shadow, uneven warm light, blur, sensor
noise, JPEG, and the browser-side shrink to 2500 px.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import uharfbuzz as hb
from fontTools.ttLib import TTFont

from app import config as C
from app.basefont import headline_units
from app.glyphmap import Cell, build_layout
from app.guides import baseline_mm, glyph_polygons, run_left_mm
from app.template import build_template_pdf

FONTS = Path(__file__).parent / "fonts"
LATIN_HAND = FONTS / "PatrickHand-Regular.ttf"


@dataclass
class SynthPage:
    photo_jpeg: bytes  # what the browser would upload
    truth: np.ndarray  # bool, canonical: where handwriting ink is
    page: int


@lru_cache(maxsize=1)
def _template_pdf() -> bytes:
    return build_template_pdf()


def template_page_rgb(page: int) -> np.ndarray:
    doc = pdfium.PdfDocument(_template_pdf())
    img = doc[page - 1].render(scale=300 / 72).to_numpy()[..., :3]  # RGB
    img = cv2.resize(img, (C.CANON_W_PX, C.CANON_H_PX), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def print_colour(page_bgr: np.ndarray, rng) -> np.ndarray:
    img = page_bgr.astype(np.float32)
    shade = 255 - img
    cast = np.array([1.10, 1.0, 0.92], np.float32)  # inkjet greys lean blue
    img = 255 - shade * cast
    img = cv2.GaussianBlur(img, (0, 0), 0.6)
    return np.clip(img, 0, 255).astype(np.uint8)


def print_laser(page_bgr: np.ndarray, rng, gain: float = 1.6, noise: float = 1.0) -> np.ndarray:
    gray = cv2.cvtColor(page_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    cover = 1 - gray
    cover = 1 - (1 - cover) ** gain  # dot gain: at 1.6, 22% grey prints ~33%
    h, w = gray.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    period = 3.4  # ~88 lpi clustered-dot screen at 45 degrees, sampled at 300 dpi
    u = (xx + yy) / (period * math.sqrt(2)) * 2 * math.pi
    v = (xx - yy) / (period * math.sqrt(2)) * 2 * math.pi
    screen = (np.cos(u) + np.cos(v) + 2) / 4  # 0..1
    toner = (cover > screen).astype(np.float32)
    del yy, xx, u, v, screen
    toner = np.maximum(toner, (cover > 0.9).astype(np.float32))
    haze = rng.random((h, w), dtype=np.float32) < 0.004 * noise  # scattered toner
    toner = np.maximum(toner, haze * 0.7)
    for _ in range(int(900 * noise)):  # specks, 1-3 px
        x, y, r = rng.integers(0, w), rng.integers(0, h), rng.integers(1, 3)
        cv2.circle(toner, (int(x), int(y)), int(r), 1.0, -1)
    sx = int(rng.integers(w // 4, 3 * w // 4))  # faint drum streak
    toner[:, sx : sx + 3] = np.maximum(toner[:, sx : sx + 3], 0.12)
    img = 255 * (1 - 0.93 * toner)
    img = cv2.GaussianBlur(img, (0, 0), 0.5)
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


class Hand:
    """Draws text from a handwriting-style font with a little human jitter."""

    def __init__(self, path: Path):
        data = path.read_bytes()
        self.tt = TTFont(io.BytesIO(data))
        self.order = self.tt.getGlyphOrder()
        self.gs = self.tt.getGlyphSet()
        self.font = hb.Font(hb.Face(hb.Blob(data)))
        self.cap = self.tt["OS/2"].sCapHeight or 0.7 * self.tt["head"].unitsPerEm

    def polygons(self, text: str) -> list[np.ndarray]:
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {})
        x, out = 0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            for poly in glyph_polygons(self.gs, self.order[info.codepoint]):
                out.append(np.array([(x + pos.x_offset + px, pos.y_offset + py) for px, py in poly], np.float64))
            x += pos.x_advance
        return out


def _write_cell(alpha: np.ndarray, hand: Hand, cell: Cell, rng):
    """Write the cell's text into the alpha layer at canonical px."""
    k = C.PX_PER_MM
    polys = hand.polygons(cell.text)
    if not polys:
        return
    cap_mm = headline_units() * C.MM_PER_UNIT
    s = cap_mm / hand.cap * rng.uniform(0.92, 1.06)  # mm per handwriting unit
    pts = np.concatenate(polys)
    cx = (pts[:, 0].min() + pts[:, 0].max()) / 2
    x, y, w, _ = cell.box_mm()
    cell_cx = x + w / 2 + rng.uniform(-1.0, 1.0)
    base = baseline_mm(cell) + rng.uniform(-0.3, 0.3)
    angle = math.radians(rng.uniform(-4, 4))
    ca, sa = math.cos(angle), math.sin(angle)
    out = []
    for p in polys:
        dx, dy = (p[:, 0] - cx) * s, -p[:, 1] * s  # mm, y down
        rx, ry = dx * ca - dy * sa, dx * sa + dy * ca
        out.append(np.stack([(cell_cx + rx) * k, (base + ry) * k], 1))
    cv2.fillPoly(alpha, [np.round(p * 16).astype(np.int32) for p in out], 1.0, cv2.LINE_AA, shift=4)


def handwrite(printed: np.ndarray, page: int, hand: Hand, rng) -> tuple[np.ndarray, np.ndarray]:
    alpha = np.zeros(printed.shape[:2], np.float32)
    for cell in build_layout().page(page):
        _write_cell(alpha, hand, cell, rng)
    pen = np.array([52, 38, 30], np.float32)  # blue-black felt-tip, BGR
    strength = alpha[..., None] * rng.uniform(0.88, 0.97)
    out = printed.astype(np.float32) * (1 - strength * (1 - pen / 255))
    return out.astype(np.uint8), alpha > 0.5


def photograph(page_bgr: np.ndarray, rng) -> bytes:
    H, W = 4032, 3024
    bg = np.empty((H, W, 3), np.float32)
    bg[:] = (58, 84, 112)  # wooden table
    bg += rng.normal(0, 9, (H, W, 1)).astype(np.float32)
    src = np.float32([[0, 0], [C.CANON_W_PX, 0], [C.CANON_W_PX, C.CANON_H_PX], [0, C.CANON_H_PX]])
    dst = np.float32([[300, 380], [2760, 270], [2880, 3760], [170, 3700]])
    dst += rng.uniform(-40, 40, dst.shape).astype(np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page_bgr, m, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32)
    inside = cv2.warpPerspective(np.ones(page_bgr.shape[:2], np.float32), m, (W, H))[..., None]
    img = warped * inside + bg * (1 - inside)
    del warped, bg

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    light = 0.62 + 0.38 * (0.6 * xx / W + 0.4 * (1 - yy / H))  # brighter towards a window
    shadow = np.zeros((H, W), np.float32)
    cv2.ellipse(shadow, (int(W * 0.25), int(H * 0.85)), (900, 600), 20, 0, 360, 1.0, -1)
    shadow = cv2.GaussianBlur(shadow, (0, 0), 180)
    light *= 1 - 0.38 * shadow
    del yy, xx, shadow
    img *= light[..., None] * np.array([0.90, 0.97, 1.04], np.float32)  # warm room light
    img = cv2.GaussianBlur(img, (0, 0), 1.3)
    img += rng.normal(0, 4, img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])

    # What the browser does before upload: long side to 2500 px, JPEG 0.85.
    img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
    s = 2500 / max(img.shape[:2])
    img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return jpg.tobytes()


def make_page(page: int, mode: str, seed: int = 7, hand_path: Path = LATIN_HAND) -> SynthPage:
    rng = np.random.default_rng(seed)
    printed = template_page_rgb(page)
    if mode == "colour":
        printed = print_colour(printed, rng)
    elif mode == "laser":
        printed = print_laser(printed, rng)
    else:
        printed = print_laser(printed, rng, gain=2.6, noise=3.0)
    written, truth = handwrite(printed, page, Hand(hand_path), rng)
    return SynthPage(photograph(written, rng), truth, page)


def ink_agreement(found: np.ndarray, truth: np.ndarray, page: int, tol_px: int = 3) -> dict:
    """Per-cell precision/recall of extracted ink against the ground truth,
    with a few px of tolerance for warp error."""
    k = C.PX_PER_MM
    inset = round(C.CELL_CUT_INSET_MM * k)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol_px + 1, 2 * tol_px + 1))
    per_cell = {}
    for cell in build_layout().page(page):
        x, y, w, h = cell.box_mm()
        sl = np.s_[round(y * k) + inset : round((y + h) * k) - inset, round(x * k) + inset : round((x + w) * k) - inset]
        f, t = found[sl] > 0, truth[sl]
        near_t = cv2.dilate(t.astype(np.uint8), kern) > 0
        near_f = cv2.dilate(f.astype(np.uint8), kern) > 0
        precision = (f & near_t).sum() / max(f.sum(), 1)
        recall = (t & near_f).sum() / max(t.sum(), 1)
        per_cell[cell.text] = (float(precision), float(recall), int((f & ~near_t).sum()))
    return per_cell
