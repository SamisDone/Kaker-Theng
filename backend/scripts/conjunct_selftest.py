"""Does every supported cluster assemble correctly from derived parts?

    python -m scripts.conjunct_selftest [--min-share 0.0001] [--sheet out.png]

Builds a font whose "handwriting" is the base font itself: every cell gets the
base font's own glyph, and the derived parts are made from those letters
exactly as they would be from a user's. Each cluster is then rendered with it
and with the base font cut to the same glyph set. If derivation and assembly
were perfect the two would be identical, so any difference is ours, not the
handwriting's. Prints the clusters that differ, weighted by how common they
are, and writes the list of failing clusters to build/selftest-failures.txt.
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from app.basefont import base_shaper, simulated_shaper
from app.charset import PART_CONJUNCTS
from app.derive import largest_miss, overlap_score
from app.fontbuild import build_font
from app.glyphmap import HALANT, _specials, build_layout
from app.outline import glyph_polygons
from app.render import render_lines
from app.vectorize import Contour, Drawing
from scripts.conjunct_coverage import PLAIN, covered, load, plain_glyphs

MIN_OVERLAP = 0.85
MAX_BLOB = 0.06


def noto_as_handwriting(layout) -> bytes:
    tt = base_shaper().tt
    gs = tt.getGlyphSet()
    drawings = []
    for cell in layout.cells:
        if cell.kind == "latin":
            continue
        polys = glyph_polygons(gs, cell.glyph)
        contours = [Contour(tuple(p[0]), [("L", tuple(q)) for q in p[1:]]) for p in polys]
        drawings.append(Drawing(cell.id, cell.glyph, cell.kind, None, contours, (0, 0, 0, 0), positioned=True, advance=tt["hmtx"][cell.glyph][0]))
    return build_font(drawings, "Selftest").ttf


def ink(font: bytes, text: str) -> np.ndarray:
    img = render_lines(font, [text], px_per_em=60, pad=10)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 128


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-share", type=float, default=0.0001, help="skip clusters rarer than this share")
    ap.add_argument("--sheet", default="")
    args = ap.parse_args()

    layout = build_layout()
    PLAIN.update(plain_glyphs(layout))
    glyphs = layout.bangla_glyphs() | _specials()
    sim = simulated_shaper(glyphs)
    halant = base_shaper().tt.getBestCmap()[ord(HALANT)]
    counts = load()
    total = sum(counts.values())
    texts = [t for t, n in counts.items() if n / total >= args.min_share and covered(sim, t, halant)]
    texts = list(dict.fromkeys(texts + [t for t in PART_CONJUNCTS if covered(sim, t, halant)]))

    test = noto_as_handwriting(layout)
    ref = sim.font_bytes
    failures = []
    for t in texts:
        a, b = ink(test, t), ink(ref, t)
        h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
        a = np.pad(a, ((0, h - a.shape[0]), (0, w - a.shape[1])))
        b = np.pad(b, ((0, h - b.shape[0]), (0, w - b.shape[1])))
        ov, blob = overlap_score(a, b), largest_miss(a, b)
        if ov < MIN_OVERLAP or blob > MAX_BLOB:
            failures.append((counts.get(t, 0), t, ov, blob))
    failures.sort(reverse=True)
    share = sum(f[0] for f in failures) / total
    print(f"{len(texts)} clusters checked; {len(failures)} assemble badly ({share:.2%} of cluster occurrences)")
    for n, t, ov, blob in failures[:40]:
        print(f"  {t:<7}{n / total:7.2%}  overlap {ov:.2f}  largest miss {blob:.0%}   {' '.join(sim.names(t))}")
    Path("build/selftest-failures.txt").write_text("\n".join(t for _, t, _, _ in failures) + "\n", encoding="utf-8")
    json.dump({"checked": len(texts), "failing": [f[1] for f in failures], "share": share}, open("build/selftest.json", "w", encoding="utf-8"), ensure_ascii=False)
    if args.sheet:
        rows = [t for _, t, _, _ in failures[:24]] or texts[:24]
        a = render_lines(test, ["  ".join(rows[i : i + 12]) for i in range(0, len(rows), 12)], px_per_em=56, labels=["derived from the base font's letters"] * 2)
        b = render_lines(ref, ["  ".join(rows[i : i + 12]) for i in range(0, len(rows), 12)], px_per_em=56, labels=["base font, same glyph set"] * 2)
        w = max(a.shape[1], b.shape[1])
        cv2.imwrite(args.sheet, np.vstack([np.pad(x, ((0, 0), (0, w - x.shape[1]), (0, 0)), constant_values=255) for x in (a, b)]))


if __name__ == "__main__":
    main()
