"""Strokes like a person drawing on the site's canvas: following the faint
tracing guide with a finger, not quite on it.

The guide is the base font's letter (or sign) where the canvas shows it.
Its centre line is found by thinning (synth_strokes.py) and then drawn the
way a hand does: a little bigger or smaller, shifted, slanted, wobbling,
and sampled like a touch screen samples a finger. Signs next to a ghost
are drawn by the same hand, around where the dashed box asks for them.

    python -X utf8 -m tests.trace_strokes [out.json] [seed]
"""

from __future__ import annotations

import json
import math

import cv2
import numpy as np

from app import config as C
from app.basefont import base_shaper
from app.glyphmap import Cell, build_layout
from app.guides import baseline_mm, run_left_mm
from app.outline import glyph_polygons
from tests.synth_strokes import follow, thin

PX_PER_MM = 12  # tracing resolution
TOUCH_STEP_MM = 0.35  # a finger's points are about this far apart (frontend/lib/strokes.ts)


def guide_polygons_mm(cell: Cell) -> list[np.ndarray]:
    """The tracing guide in cell mm (origin top-left, y down), as the canvas
    shows it (scripts/export_frontend_assets.py, draw_geometry)."""
    s = C.MM_PER_UNIT
    x, y, _, _ = cell.box_mm()
    base = baseline_mm(cell) - y
    left = run_left_mm(cell) - x + cell.target_x * s
    gs = base_shaper().tt.getGlyphSet()
    return [np.array([(left + px * s, base - (py + cell.target_y) * s) for px, py in poly]) for poly in glyph_polygons(gs, cell.glyph)]


def centre_lines(polys: list[np.ndarray], w: float, h: float) -> list[np.ndarray]:
    img = np.zeros((round(h * PX_PER_MM), round(w * PX_PER_MM)), np.uint8)
    cv2.fillPoly(img, [np.round(p * PX_PER_MM * 16).astype(np.int32) for p in polys], 1, cv2.LINE_AA, shift=4)
    lines = []
    for path in follow(thin(img > 0)):
        line = np.array([((c + 0.5) / PX_PER_MM, (r + 0.5) / PX_PER_MM) for r, c in path])
        if len(path) < 4:
            # A dot (the nukta, a bindu): a tap, if nothing else drew there.
            centre = line.mean(axis=0)
            if all(np.linalg.norm(other - centre, axis=1).min() > 1.0 for other in lines):
                lines.append(centre[None])
            continue
        lines.append(line)
    return lines


def _resample(line: np.ndarray, step: float) -> np.ndarray:
    seg = np.linalg.norm(np.diff(line, axis=0), axis=1)
    t = np.concatenate([[0], np.cumsum(seg)])
    if t[-1] < step:
        return line[[0, -1]]
    at = np.arange(0, t[-1], step)
    return np.stack([np.interp(at, t, line[:, 0]), np.interp(at, t, line[:, 1])], 1)


def hand_strokes(cell: Cell, rng: np.random.Generator, sloppy: bool = False) -> list[list[list[float]]]:
    """One cell drawn by a hand that follows the guide, roughly. A sloppy
    hand draws letters bigger or smaller still, and puts a sign anywhere
    inside its dashed box (export_frontend_assets pads it by 1.2 mm), even
    touching the ghost."""
    _, _, w, h = cell.box_mm()
    polys = guide_polygons_mm(cell)
    if not polys:
        return []
    pts = np.concatenate(polys)
    cx, cy = (pts[:, 0].min() + pts[:, 0].max()) / 2, (pts[:, 1].min() + pts[:, 1].max()) / 2
    sign = bool(cell.ghost_glyphs)
    # A whole letter: often drawn a bit big, off the guide by up to a mm.
    # A sign: smaller errors, the dashed box is small.
    scale = rng.uniform(0.95, 1.18) if not sign else rng.uniform(0.92, 1.1)
    shift = rng.normal(0, 0.45 if not sign else 0.3, 2)
    if sloppy:
        scale = rng.uniform(0.85, 1.35) if not sign else rng.uniform(0.9, 1.2)
        shift = rng.uniform(-1.2, 1.2, 2) if sign else rng.normal(0, 0.8, 2)
    slant = rng.uniform(-0.12, 0.06)  # fingers lean right more than left
    out = []
    for line in centre_lines(polys, w, h):
        if len(line) == 1:  # a tap
            x = cx + (line[0, 0] - cx) * scale + shift[0]
            y = cy + (line[0, 1] - cy) * scale + shift[1]
            out.append([[round(float(np.clip(x, 0, w)), 3), round(float(np.clip(y, 0, h)), 3)]])
            continue
        line = _resample(line, 0.1)
        # Wobble: slow drift along the stroke, plus jitter.
        n = len(line)
        phase = rng.uniform(0, 2 * math.pi, 2)
        k = np.arange(n)[:, None]
        drift = 0.18 * np.sin(k / max(8, n / 2) * math.pi + phase) + rng.normal(0, 0.03, (n, 2))
        x = cx + (line[:, 0] - cx) * scale + slant * (cy - line[:, 1]) + shift[0] + drift[:, 0]
        y = cy + (line[:, 1] - cy) * scale + shift[1] + drift[:, 1]
        line = _resample(np.stack([x, y], 1), TOUCH_STEP_MM)
        line[:, 0] = np.clip(line[:, 0], 0, w)
        line[:, 1] = np.clip(line[:, 1], 0, h)
        out.append([[round(float(a), 3), round(float(b), 3)] for a, b in line])
    return out


def traced_cells(ids: list[str] | None = None, seed: int = 11, sloppy: bool = False) -> dict[str, list]:
    """{cell id: strokes} for Bangla cells (all of them, or `ids`)."""
    rng = np.random.default_rng(seed)
    cells = [c for c in build_layout().cells if c.kind != "latin" and (ids is None or c.id in ids)]
    return {c.id: hand_strokes(c, rng, sloppy) for c in cells}


if __name__ == "__main__":
    import sys

    data = traced_cells(seed=int(sys.argv[2]) if len(sys.argv) > 2 else 11, sloppy="--sloppy" in sys.argv)
    path = sys.argv[1] if len(sys.argv) > 1 else "traced-cells.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"{len(data)} cells, {sum(len(s) for s in data.values())} strokes -> {path}")
