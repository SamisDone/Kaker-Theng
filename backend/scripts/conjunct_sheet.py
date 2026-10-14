"""Render the most frequent clusters in a built font next to the base font.

    python -m scripts.conjunct_sheet <font.ttf> <out.png> [N]
"""

import sys
from pathlib import Path

import cv2
import numpy as np

from app.basefont import base_shaper
from app.render import render_lines
from scripts.conjunct_coverage import CHECK, load

font = Path(sys.argv[1]).read_bytes()
n = int(sys.argv[3]) if len(sys.argv) > 3 else 60
counts = load()
clusters = list(dict.fromkeys(list(counts)[:n] + CHECK + sys.argv[4:]))
rows = [clusters[i : i + 12] for i in range(0, len(clusters), 12)]
tiles = []
for row in rows:
    text = "  ".join(row)
    a = render_lines(font, [text], px_per_em=64, labels=["handwriting font"])
    b = render_lines(base_shaper().font_bytes, [text], px_per_em=64, labels=["Noto Sans Bengali"])
    w = max(a.shape[1], b.shape[1])
    tiles.append(np.vstack([np.pad(x, ((0, 0), (0, w - x.shape[1]), (0, 0)), constant_values=255) for x in (a, b)]))
w = max(t.shape[1] for t in tiles)
cv2.imwrite(sys.argv[2], np.vstack([np.pad(t, ((0, 8), (0, w - t.shape[1]), (0, 0)), constant_values=200) for t in tiles]))
