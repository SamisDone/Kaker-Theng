"""How much one piece of a shaped cluster lies on the others: each glyph
of the run filled on its own, at its shaped position."""

from __future__ import annotations

import io

import cv2
import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont

from app.outline import glyph_polygons

RES = 0.25  # px per font unit


def pieces(font: bytes, text: str) -> list[tuple[str, np.ndarray]]:
    """(glyph name, ink mask) for each glyph of the shaped run, on one canvas."""
    tt = TTFont(io.BytesIO(font))
    order, gs = tt.getGlyphOrder(), tt.getGlyphSet()
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb.Font(hb.Face(hb.Blob(font))), buf, {})
    placed, x = [], 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        placed.append((order[info.codepoint], x + pos.x_offset, pos.y_offset))
        x += pos.x_advance
    polys = [(n, [[(px + dx, py + dy) for px, py in p] for p in glyph_polygons(gs, n)]) for n, dx, dy in placed]
    pts = [q for _, ps in polys for p in ps for q in p]
    if not pts:
        return []
    x0, y0 = min(p[0] for p in pts) - 20, min(p[1] for p in pts) - 20
    x1, y1 = max(p[0] for p in pts) + 20, max(p[1] for p in pts) + 20
    w, h = int((x1 - x0) * RES) + 1, int((y1 - y0) * RES) + 1
    out = []
    for name, ps in polys:
        img = np.zeros((h, w), np.uint8)
        for p in ps:
            arr = np.array([((px - x0) * RES, (y1 - py) * RES) for px, py in p]) * 16
            cv2.fillPoly(img, [arr.astype(np.int32)], 1, cv2.LINE_AA, shift=4)
        out.append((name, img > 0))
    return out


def overlap(font: bytes, text: str, piece: str) -> float:
    """Share of the ink of the first glyph whose name starts with `piece`
    that lies on the other glyphs' ink (0 if there is no such glyph)."""
    ps = pieces(font, text)
    mine = [m for n, m in ps if n.startswith(piece)]
    if not mine or not mine[0].any():
        return 0.0
    rest = np.zeros_like(mine[0])
    for n, m in ps:
        if not n.startswith(piece):
            rest |= m
    return float((mine[0] & rest).sum() / mine[0].sum())


def body_overlap(font: bytes, text: str, piece: str = "raphala", join: float = 0.25) -> float:
    """overlap(), leaving out the join: the right `join` of the piece's
    width, where a ra-phala's stem meets its consonant's stem by design."""
    ps = pieces(font, text)
    mine = [m for n, m in ps if n.startswith(piece)]
    if not mine or not mine[0].any():
        return 0.0
    m = mine[0].copy()
    cols = m.any(axis=0).nonzero()[0]
    m[:, int(cols[-1] - join * (cols[-1] - cols[0])) :] = False
    rest = np.zeros_like(m)
    for n, o in ps:
        if not n.startswith(piece):
            rest |= o
    return float((m & rest).sum() / max(mine[0].sum(), 1))


def thickness(mask: np.ndarray) -> float:
    """A stroke's width, font units: twice its area over its outline's length."""
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    perimeter = sum(cv2.arcLength(c, True) for c in contours)
    return 2 * float(mask.sum()) / max(perimeter, 1) / RES


def wave_rise(font: bytes, text: str, piece: str = "raphala", join: float = 0.25) -> float:
    """How far (font units) the top of a ra-phala's wave (its stem left out)
    reaches above the lowest ink of the letter it goes under."""
    ps = pieces(font, text)
    mine = [m for n, m in ps if n.startswith(piece)]
    if not mine:
        return 0.0
    m = mine[0].copy()
    cols = m.any(axis=0).nonzero()[0]
    m[:, int(cols[-1] - join * (cols[-1] - cols[0])) :] = False
    base = np.zeros_like(m)
    for n, o in ps:
        if not n.startswith((piece, "headline")):
            base |= o
    wave_top = m.any(axis=1).nonzero()[0][0]
    base_bottom = base.any(axis=1).nonzero()[0][-1]
    return float(base_bottom - wave_top) / RES
