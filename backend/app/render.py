"""Render text with a font through HarfBuzz, for checking a build by eye."""

from __future__ import annotations

import io

import cv2
import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont

from .guides import glyph_polygons

INK_BGR = (0x40, 0x21, 0x1D)
PAPER_BGR = (0xE6, 0xF0, 0xF4)


def shape_names(font_bytes: bytes, text: str) -> list[str]:
    tt = TTFont(io.BytesIO(font_bytes))
    order = tt.getGlyphOrder()
    font = hb.Font(hb.Face(hb.Blob(font_bytes)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    return [order[i.codepoint] for i in buf.glyph_infos]


def render_lines(font_bytes: bytes, lines: list[str], px_per_em: int = 72, pad: int = 24, labels: list[str] | None = None) -> np.ndarray:
    tt = TTFont(io.BytesIO(font_bytes))
    upm = tt["head"].unitsPerEm
    order, gs = tt.getGlyphOrder(), tt.getGlyphSet()
    font = hb.Font(hb.Face(hb.Blob(font_bytes)))
    s = px_per_em / upm
    line_h = round(1.6 * px_per_em)
    label_h = 22 if labels else 0

    runs = []
    for text in lines:
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        x, glyphs = 0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            glyphs.append((order[info.codepoint], x + pos.x_offset, pos.y_offset))
            x += pos.x_advance
        runs.append((glyphs, x))

    width = max(round(x * s) for _, x in runs) + 2 * pad
    height = len(lines) * (line_h + label_h) + 2 * pad
    img = np.full((height, max(width, 400), 3), PAPER_BGR, np.uint8)
    for i, (glyphs, _) in enumerate(runs):
        top = pad + i * (line_h + label_h)
        if labels:
            cv2.putText(img, labels[i], (pad, top + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0x68, 0x74, 0x7A), 1, cv2.LINE_AA)
        base = top + label_h + round(1.1 * px_per_em)
        cv2.line(img, (pad, base), (img.shape[1] - pad, base), (0xE0, 0xC6, 0xB9), 1)
        for name, gx, gy in glyphs:
            polys = [
                np.array([(pad + (gx + px) * s, base - (gy + py) * s) for px, py in poly]) * 16
                for poly in glyph_polygons(gs, name)
            ]
            if polys:
                cv2.fillPoly(img, [p.astype(np.int32) for p in polys], INK_BGR, cv2.LINE_AA, shift=4)
    return img


def png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()
