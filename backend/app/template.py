"""The printable A4 template: 3 pages, ArUco corners, dropout-blue guides."""

from __future__ import annotations

import io

import cv2
import numpy as np
from fontTools.pens.basePen import BasePen
from reportlab.lib.colors import Color
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from . import config as C
from .basefont import base_shaper, headline_units
from .charset import PAGE_TITLES
from .glyphmap import Cell, build_layout

DROPOUT = Color(*(v / 255 for v in C.DROPOUT_RGB))
INK = Color(*(v / 255 for v in C.INK_RGB))
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _y(mm_from_top: float) -> float:
    """Top-down millimetres to reportlab points (bottom-up)."""
    return (C.PAGE_H_MM - mm_from_top) * mm


class _CanvasPen(BasePen):
    """Draws font outlines onto a reportlab path, with a scale and offset."""

    def __init__(self, glyph_set, path, x0_mm, base_mm, mm_per_unit):
        super().__init__(glyph_set)
        self.path, self.x0, self.b, self.s = path, x0_mm, base_mm, mm_per_unit

    def _pt(self, p):
        return (self.x0 + p[0] * self.s) * mm, _y(self.b - p[1] * self.s)

    def _moveTo(self, p):
        self.path.moveTo(*self._pt(p))

    def _lineTo(self, p):
        self.path.lineTo(*self._pt(p))

    def _curveToOne(self, p1, p2, p3):
        self.path.curveTo(*self._pt(p1), *self._pt(p2), *self._pt(p3))

    def _closePath(self):
        self.path.close()


def _draw_glyphs(c, glyphs, x_mm, base_mm, mm_per_unit, color):
    """glyphs: iterable of (name, x_units, y_units)."""
    gs = base_shaper().tt.getGlyphSet()
    path = c.beginPath()
    for name, gx, gy in glyphs:
        pen = _CanvasPen(gs, path, x_mm + gx * mm_per_unit, base_mm - gy * mm_per_unit, mm_per_unit)
        gs[name].draw(pen)
    c.setFillColor(color)
    c.drawPath(path, stroke=0, fill=1)


def _runs(text: str) -> list[tuple[bool, str]]:
    """Split into (is_bangla_font, text) runs. The base font has no ASCII
    punctuation, so commas, hyphens and slashes go to Helvetica."""
    cmap = base_shaper().tt.getBestCmap()
    runs: list[tuple[bool, str]] = []
    for ch in text:
        ours = ord(ch) in cmap and (ch != " " or (runs and runs[-1][0]))
        if runs and runs[-1][0] == ours:
            runs[-1] = (ours, runs[-1][1] + ch)
        else:
            runs.append((ours, ch))
    return runs


def _bangla(c, text, x_mm, base_mm, headline_mm, color=INK, draw=True) -> float:
    """Draw mixed Bangla/Latin text, sized by the মাত্রা height; returns width in mm."""
    s = headline_mm / headline_units()
    latin_pt = headline_mm / 0.72 / 0.3528  # Helvetica cap height ~ 0.72 em
    x_mm0 = x_mm
    for ours, run in _runs(text):
        if ours:
            x, glyphs = 0, []
            for g in base_shaper().shape(run):
                glyphs.append((g.name, x + g.x_offset, g.y_offset))
                x += g.x_advance
            if draw:
                _draw_glyphs(c, glyphs, x_mm, base_mm, s, color)
            x_mm += x * s
        else:
            x_mm += _latin(c, run, x_mm, base_mm, latin_pt, color, draw=draw)
    return x_mm - x_mm0


def _bangla_width(c, text, headline_mm) -> float:
    return _bangla(c, text, 0, 0, headline_mm, draw=False)


def _latin(c, text, x_mm, base_mm, size_pt, color=INK, font="Helvetica", draw=True) -> float:
    if draw:
        c.setFillColor(color)
        c.setFont(font, size_pt)
        c.drawString(x_mm * mm, _y(base_mm), text)
    return c.stringWidth(text, font, size_pt) / mm


def _marker_bits(marker_id: int) -> np.ndarray:
    d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, C.ARUCO_DICT))
    img = cv2.aruco.generateImageMarker(d, marker_id, 6)  # 4x4 + 1-module border
    return img < 128


def _draw_marker(c, marker_id, x_mm, y_mm, size_mm):
    bits = _marker_bits(marker_id)
    n = bits.shape[0]
    m = size_mm / n
    c.setFillColor(Color(0, 0, 0))
    for r in range(n):
        for k in range(n):
            if bits[r, k]:
                c.rect((x_mm + k * m) * mm, _y(y_mm + (r + 1) * m), m * mm, m * mm, stroke=0, fill=1)


def cell_run_left_mm(cell: Cell) -> float:
    """Where the shaped run (ghost + written glyph) starts inside the cell."""
    return (C.CELL_MM - cell.run_advance * C.MM_PER_UNIT) / 2


def _draw_cell(c, cell: Cell):
    x, y, w, h = cell.box_mm()
    s = C.MM_PER_UNIT
    base = y + C.BASELINE_FROM_TOP_MM
    head = base - headline_units() * s

    c.setStrokeColor(DROPOUT)
    c.setLineWidth(0.6)
    c.rect(x * mm, _y(y + h), w * mm, h * mm, stroke=1, fill=0)
    c.setLineWidth(0.45)
    c.line((x + 1.5) * mm, _y(base), (x + w - 1.5) * mm, _y(base))
    c.line((x + 1.5) * mm, _y(head), (x + w - 1.5) * mm, _y(head))
    if cell.kind == "latin":
        xh = base - headline_units() * C.LATIN_XHEIGHT_RATIO * s
        c.setDash(0.6 * mm, 1.2 * mm)
        c.line((x + 1.5) * mm, _y(xh), (x + w - 1.5) * mm, _y(xh))
        c.setDash()

    if cell.kind == "latin":
        _latin(c, cell.text, x + 1.2, y + 3.4, 7.5, DROPOUT, "Helvetica-Bold")
    else:
        _bangla(c, cell.text, x + 1.2, y + 3.6, 1.9, DROPOUT)

    if cell.ghost_glyphs:
        left = x + cell_run_left_mm(cell)
        _draw_glyphs(c, [(g.name, g.x, g.y) for g in cell.ghost_glyphs], left, base, s, DROPOUT)


def _fit(text_w, max_w, size):
    return size if text_w <= max_w else size * max_w / text_w


INSTRUCTIONS_BN = (
    "গাঢ় কালির কলম দিন, সরু ফেল্ট-টিপ সবচেয়ে ভালো। অক্ষর ঘরের ভেতরে রাখুন। "
    "মাত্রাওয়ালা বাংলা অক্ষরে মাত্রার রেখা ছুঁয়ে লিখুন।"
)
INSTRUCTIONS_EN = (
    "Use a dark pen (a fine felt-tip works best). Keep each letter inside its box. "
    "For Bangla letters with a matra, touch the top line."
)
GHOST_NOTE_BN = "হালকা অক্ষরটা লিখবেন না, শুধু চিহ্নটা লিখুন।"
GHOST_NOTE_EN = "Don't trace the faint letter; write only the sign around it."
PRINT_NOTE = "Print in colour at 100% (actual size). The blue lines disappear when we read the photo."


def _draw_page(c, page: int, cells: list[Cell]):
    for corner, mid in zip(C.CORNERS, C.marker_ids(page)):
        mx, my = C.marker_origin_mm(corner)
        _draw_marker(c, mid, mx, my, C.MARKER_MM)

    # Between the top markers: name and page number.
    left = C.MARKER_MARGIN_MM + C.MARKER_MM + 5
    right = C.PAGE_W_MM - C.MARKER_MARGIN_MM - C.MARKER_MM - 5
    w = _bangla(c, "কাকের ঠ্যাং", left, 15.0, 4.6)
    _latin(c, "Kaker Theng", left + w + 3, 15.0, 10)
    tag_en = f"page {page} of 3"
    en_w = _latin(c, tag_en, 0, 0, 9, draw=False)
    _latin(c, tag_en, right - en_w, 15.0, 9)
    tag_bn = f"পাতা {str(page).translate(BN_DIGITS)} / ৩"
    _bangla(c, tag_bn, right - en_w - 3 - _bangla_width(c, tag_bn, 2.8), 15.0, 2.8)
    bn, en = PAGE_TITLES[page]
    w = _bangla(c, bn, left, 21.0, 2.6)
    _latin(c, en, left + w + 3, 21.0, 9, INK, "Helvetica-Oblique")

    # Below the markers, across the grid width: how to write.
    grid_left, grid_w = C.GRID_X_MM, C.COLS * C.CELL_MM
    bn_h = _fit(_bangla_width(c, INSTRUCTIONS_BN, 2.0), grid_w, 2.0)
    _bangla(c, INSTRUCTIONS_BN, grid_left, 28.0, bn_h)
    size = _fit(_latin(c, INSTRUCTIONS_EN, 0, 0, 7.5, draw=False), grid_w, 7.5)
    _latin(c, INSTRUCTIONS_EN, grid_left, 32.0, size)
    if any(cell.ghost_glyphs for cell in cells):
        w = _bangla(c, GHOST_NOTE_BN, grid_left, 36.0, 2.0)
        _latin(c, GHOST_NOTE_EN, grid_left + w + 2.5, 36.0, 7.5, INK, "Helvetica-Oblique")

    for cell in cells:
        _draw_cell(c, cell)

    foot_y = C.PAGE_H_MM - C.MARKER_MARGIN_MM - 3
    _latin(c, PRINT_NOTE, left, foot_y, 6.5, INK, "Helvetica-Oblique")
    tag = f"kaker-theng template v1 · p{page}"
    _latin(c, tag, right - _latin(c, tag, 0, 0, 6.5, draw=False), foot_y, 6.5)


def build_template_pdf() -> bytes:
    layout = build_layout()
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(C.PAGE_W_MM * mm, C.PAGE_H_MM * mm))
    c.setTitle("Kaker Theng handwriting template")
    c.setAuthor("Kaker Theng")
    for page in (1, 2, 3):
        _draw_page(c, page, layout.page(page))
        c.showPage()
    c.save()
    return buf.getvalue()
