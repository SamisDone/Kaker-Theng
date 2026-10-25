"""The start screen's example: a line in a font built from drawn letters.

    python -X utf8 -m scripts.make_example [out.png]

Builds a font from the test hand (tests/trace_strokes.py) the way the site
builds one from drawn letters, and writes "আমার হাতের লেখা" in it as ink on
a transparent background, at twice the size it shows (300 x 72 CSS px), to
frontend/public/kt/example.png. Dev only.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.render import render_lines
from app.strokes import drawing
from tests.trace_strokes import traced_cells

TEXT = "আমার হাতের লেখা"
INK = (0x40, 0x21, 0x1D)  # BGR of #1d2140
SIZE = (600, 144)  # px: 2x the CSS size

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "frontend" / "public" / "kt" / "example.png"
cells = {c.id: c for c in build_layout().cells}
page2 = [c.id for c in build_layout().cells if c.page == 2]
font = build_font([drawing(cells[k], v) for k, v in traced_cells(page2, seed=11).items() if v], "Example")
img = render_lines(font.ttf, [TEXT], px_per_em=160, pad=0)
# The ink alone: no paper, no baseline rule.
ink = (img.astype(int) - np.array(INK)).__abs__().max(axis=2) < 90
ys, xs = np.nonzero(ink)
crop = ink[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1].astype(np.uint8) * 255
k = min((SIZE[0] - 8) / crop.shape[1], (SIZE[1] - 8) / crop.shape[0])
crop = cv2.resize(crop, (round(crop.shape[1] * k), round(crop.shape[0] * k)), interpolation=cv2.INTER_AREA)
rgba = np.zeros((SIZE[1], SIZE[0], 4), np.uint8)
y0, x0 = (SIZE[1] - crop.shape[0]) // 2, 4
rgba[y0 : y0 + crop.shape[0], x0 : x0 + crop.shape[1], :3] = INK
rgba[y0 : y0 + crop.shape[0], x0 : x0 + crop.shape[1], 3] = crop
cv2.imwrite(str(out), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])
print(f"{out}: {SIZE[0]}x{SIZE[1]}, {out.stat().st_size} bytes")
