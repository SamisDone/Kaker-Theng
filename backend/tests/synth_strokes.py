"""Synthetic drawn letters: what a person drawing on the canvas would send.

The same handwriting fonts and placement as synth.py (Patrick Hand, Galada,
wobbled base-font parts), thinned to a one-pixel centre line (Zhang-Suen)
and followed into strokes: lists of [x, y] in cell millimetres, origin at
the cell's top-left, y down. That is the browser's format.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from app import config as C
from app.glyphmap import build_layout
from tests.synth import _write_cell

STEP_PX = 3  # keep every 3rd centre-line pixel: ~0.25 mm, like a decimated pointer trace


def thin(img: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning of a bool image."""
    img = img.astype(np.uint8)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = np.pad(img, 1)
            n = [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]
            b = sum(n)
            a = sum(((n[i] == 0) & (n[(i + 1) % 8] == 1)).astype(np.uint8) for i in range(8))
            p2, p4, p6, p8 = n[0], n[2], n[4], n[6]
            c = ((p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)) if step == 0 else ((p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0))
            m = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            if m.any():
                img[m] = 0
                changed = True
    return img.astype(bool)


def follow(skel: np.ndarray) -> list[list[tuple[int, int]]]:
    """Centre-line pixels -> polylines of (row, col), split at ends and forks.
    m-adjacency: a diagonal step only where no straight step connects."""
    pts = set(zip(*map(np.ndarray.tolist, np.nonzero(skel))))

    def nbrs(p):
        y, x = p
        out = [q for q in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)) if q in pts]
        for dy, dx in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            if (y + dy, x + dx) in pts and (y + dy, x) not in pts and (y, x + dx) not in pts:
                out.append((y + dy, x + dx))
        return out

    adj = {p: nbrs(p) for p in pts}
    used, paths = set(), []

    def walk(a, b):
        path, prev, cur = [a, b], a, b
        used.add(frozenset((a, b)))
        while len(adj[cur]) == 2:
            nxt = [q for q in adj[cur] if q != prev and frozenset((cur, q)) not in used]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            used.add(frozenset((prev, cur)))
            path.append(cur)
        return path

    for p in sorted(pts, key=lambda p: len(adj[p]) == 2):  # ends and forks first, then loops
        if not adj[p]:
            paths.append([p])
        for q in adj[p]:
            if frozenset((p, q)) not in used:
                paths.append(walk(p, q))
    return paths


def cell_strokes(alpha: np.ndarray, cell) -> list[list[list[float]]]:
    k = C.PX_PER_MM
    x, y, w, h = cell.box_mm()
    x0, y0 = round(x * k), round(y * k)
    crop = alpha[y0 : round((y + h) * k), x0 : round((x + w) * k)] > 0.5
    strokes = []
    for path in follow(thin(crop)):
        keep = path[::STEP_PX] + ([path[-1]] if (len(path) - 1) % STEP_PX else [])
        strokes.append([[round((x0 + c + 0.5) / k - x, 3), round((y0 + r + 0.5) / k - y, 3)] for r, c in keep])
    return strokes


@lru_cache(maxsize=4)
def drawn_cells(pages: tuple[int, ...] = (1, 2, 3), seed: int = 7) -> dict[str, list]:
    """{cell id: strokes} for every cell of these pages."""
    out = {}
    for page in pages:
        rng = np.random.default_rng(seed + page)
        alpha = np.zeros((C.CANON_H_PX, C.CANON_W_PX), np.float32)
        cells = build_layout().page(page)
        for cell in cells:
            _write_cell(alpha, cell, rng)
        for cell in cells:
            out[cell.id] = cell_strokes(alpha, cell)
    return out


if __name__ == "__main__":
    import sys

    data = drawn_cells()
    path = sys.argv[1] if len(sys.argv) > 1 else "drawn-cells.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    n = sum(len(s) for s in data.values())
    pts = sum(len(p) for s in data.values() for p in s)
    print(f"{len(data)} cells, {n} strokes, {pts} points -> {path}")
