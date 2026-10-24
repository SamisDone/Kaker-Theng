"""Render the CPython and browser fonts from the same photo, one above the
other, plus an overlay (CPython red, browser blue, both dark).

    backend/.venv/Scripts/python -X utf8 prototype/pyodide/compare_fonts.py
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DIST = Path(__file__).resolve().parent / "dist"
LINES = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", "0123456789 .,;:!?'\"()-&@#%/",
         "The quick brown fox jumps over the lazy dog."]
SIZE, W = 64, 1500


def render(path: Path) -> np.ndarray:
    font = ImageFont.truetype(str(path), SIZE)
    img = Image.new("L", (W, len(LINES) * SIZE * 3 // 2 + 20), 255)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(LINES):
        d.text((20, 10 + i * SIZE * 3 // 2), line, font=font, fill=0)
    return np.array(img)


cp, br = render(DIST / "cpython.ttf"), render(DIST / "browser.ttf")
overlay = np.full(cp.shape + (3,), 255, np.uint8)
a, b = cp < 128, br < 128
overlay[a & ~b] = (194, 65, 45)
overlay[b & ~a] = (40, 80, 200)
overlay[a & b] = (29, 33, 64)


def labelled(rgb: np.ndarray, label: str) -> Image.Image:
    img = Image.fromarray(rgb)
    ImageDraw.Draw(img).text((W - 520, 4), label, fill=(110, 104, 93), font=ImageFont.truetype("arial.ttf", 22))
    return img


parts = [labelled(np.stack([cp] * 3, -1), "CPython (server)"), labelled(np.stack([br] * 3, -1), "Pyodide (browser)"),
         labelled(overlay, "overlay: red CPython only, blue browser only")]
out = Image.new("RGB", (W, sum(p.height for p in parts)), "white")
y = 0
for p in parts:
    out.paste(p, (0, y))
    y += p.height
out.save(DIST / "font-compare.png")
print(f"differing pixels: {int((a ^ b).sum())} of {int((a | b).sum())} inked ({(a ^ b).sum() / max((a | b).sum(), 1):.2%})")
