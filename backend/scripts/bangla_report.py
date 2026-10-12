"""Step 3 check: all three pages, four print/pen modes, full fonts.

    python -m scripts.bangla_report [out_dir] [modes...]

Per mode: ink agreement, cut strokes, dots, missing cells. Per font: .notdef
check on the test sentences, conjunct coverage, the final font's shaping
compared with the simulation the template was planned from, and rendered
PNGs. Also renders words with derived conjunct parts next to the same words
with hand-written parts.
"""

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from app.basefont import base_shaper, simulated_shaper
from app.cells import cut_cells
from app.fontbuild import build_font
from app.glyphmap import HALANT, _specials, build_layout
from app.ink import extract_ink
from app.outline import glyph_polygons
from app.pipeline import decode_image
from app.render import png, render_lines, shape_names
from app.scan import find_page
from app.vectorize import Contour, Drawing, vectorize
from scripts.make_template import COMMON_CONJUNCTS
from tests.synth import MODES, cells_ink, ink_agreement, make_page

SENTENCES = [
    "আমি প্রতিদিন সকালে চা খাই।",
    "কর্মী ক্ষমা চাইল।",
    "বিদ্যালয়ের সামনে বৃষ্টি পড়ছে।",
    "The quick brown fox jumps over the lazy dog.",
]
COMPARE = ["শক্ত", "অন্ত", "আনন্দ", "আস্তে", "চিহ্ন", "অল্প"]
DOT_CELLS = {1: ["i", "j", "!", "?", ";", ":"], 2: ["কঁ", "কং", "য়"]}
DOT_NAMES = {"কঁ": "ঁ", "কং": "ং", "য়": "nukta"}


def pieces(mask: np.ndarray) -> int:
    return cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)[0] - 1


def run_page(page: int, mode: str) -> tuple[dict, list[Drawing]]:
    synth = make_page(page, mode)
    found = find_page(decode_image(synth.photo_jpeg), expected_page=page)
    ink, stats = extract_ink(found.gray, page)
    cells = cut_cells(ink, page)
    scores = ink_agreement(cells_ink(cells, ink.shape), synth.truth, page)
    cut, dots = [], {}
    for ci in cells:
        h, w = ci.bitmap.shape
        truth = synth.truth[ci.y0 : ci.y0 + h, ci.x0 : ci.x0 + w]
        n_true, n_found = pieces(truth), pieces(ci.bitmap)
        if n_found != n_true:
            cut.append(f"{ci.cell.text}:{n_true}->{n_found}")
        if ci.cell.text in DOT_CELLS.get(page, []):
            # Every real piece (stroke or dot) must be found: at least half of
            # its pixels within 3 px of extracted ink.
            near = cv2.dilate(ci.bitmap.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
            n, labels = cv2.connectedComponents(truth.astype(np.uint8), connectivity=8)
            found = all((near & (labels == i)).sum() >= 0.5 * (labels == i).sum() for i in range(1, n))
            dots[DOT_NAMES.get(ci.cell.text, ci.cell.text)] = found
    precision = [p for p, _, _ in scores.values()]
    recall = [r for _, r, _ in scores.values()]
    status = {s: [c.cell.text for c in cells if c.status == s] for s in ("missing", "touches_edge")}
    report = {
        "page": page,
        "ink_darkness": round(stats.ink_darkness, 2),
        "guide_darkness": round(stats.guide_darkness, 2),
        "thresholds": [round(stats.loose, 2), round(stats.strict, 2)],
        "cells": len(cells),
        "missing": status["missing"],
        "touches_edge": status["touches_edge"],
        "precision_min": round(min(precision), 3),
        "recall_min": round(min(recall), 3),
        "stray_px": sum(s for _, _, s in scores.values()),
        "cut_or_merged": cut,
        "dots": dots,
    }
    drawings = [vectorize(ci) for ci in cells if ci.status != "missing"]
    return report, drawings


def check_font(ttf: bytes, layout) -> dict:
    """Shape with the built font and compare with the planned simulation."""
    import io

    import uharfbuzz as hb
    from fontTools.ttLib import TTFont

    tt = TTFont(io.BytesIO(ttf))
    order = tt.getGlyphOrder()
    font = hb.Font(hb.Face(hb.Blob(ttf)))

    def names(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        return [order[i.codepoint] for i in buf.glyph_infos]

    sim = simulated_shaper(layout.bangla_glyphs() | _specials())
    halant = base_shaper().tt.getBestCmap()[ord(HALANT)]
    texts = [c.text for c in layout.cells if c.kind != "latin"] + COMMON_CONJUNCTS + SENTENCES[:3]
    mismatches = [t for t in texts if names(t) != sim.names(t)]
    conj = {"single glyph": 0, "from parts": 0, "visible hasanta": 0, ".notdef": 0}
    for t in COMMON_CONJUNCTS:
        n = names(t)
        if ".notdef" in n:
            conj[".notdef"] += 1
        elif halant in n:
            conj["visible hasanta"] += 1
        elif len(n) == 1:
            conj["single glyph"] += 1
        else:
            conj["from parts"] += 1
    return {
        "notdef_in_sentences": {s: names(s).count(".notdef") for s in SENTENCES},
        "shaping_differs_from_plan": mismatches,
        "conjuncts": conj,
        "glyphs": len(order),
    }


def written_parts(layout, rng) -> list[Drawing]:
    """What the old template got: every part hand-written. Simulated as the
    base font's part with a little wobble, in place."""
    gs = base_shaper().tt.getGlyphSet()
    hmtx = base_shaper().tt["hmtx"]
    out = []
    for plan in layout.plans():
        polys = [np.array(p) + rng.normal(0, 6, (len(p), 2)) for p in glyph_polygons(gs, plan.glyph)]
        contours = [Contour(tuple(p[0]), [("L", tuple(q)) for q in p[1:]]) for p in polys]
        kind = "mark" if hmtx[plan.glyph][0] == 0 else "base"
        out.append(Drawing("written", plan.glyph, kind, None, contours, (0, 0, 0, 0), positioned=True, advance=hmtx[plan.glyph][0]))
    return out


def compare_image(derived_ttf: bytes, written_ttf: bytes, out: Path):
    noto = base_shaper().font_bytes
    cols = [render_lines(f, COMPARE, px_per_em=64, labels=[lab] + [""] * (len(COMPARE) - 1)) for f, lab in [(derived_ttf, "derived parts (new)"), (written_ttf, "hand-written parts (old template)"), (noto, "Noto Sans Bengali (reference)")]]
    h = max(c.shape[0] for c in cols)
    cols = [np.pad(c, ((0, h - c.shape[0]), (0, 16), (0, 0)), constant_values=255) for c in cols]
    cv2.imwrite(str(out), np.hstack(cols))


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/bangla")
    modes = sys.argv[2:] or MODES
    out.mkdir(parents=True, exist_ok=True)
    layout = build_layout()
    summary = {}
    for mode in modes:
        t0 = time.time()
        pages, drawings = [], []
        for page in (1, 2, 3):
            r, d = run_page(page, mode)
            pages.append(r)
            drawings += d
        font = build_font(drawings, f"Synth {mode.title()}")
        d = out / mode
        d.mkdir(exist_ok=True)
        (d / "font.ttf").write_bytes(font.ttf)
        (d / "font.woff2").write_bytes(font.woff2)
        (d / "sentences.png").write_bytes(png(render_lines(font.ttf, SENTENCES, px_per_em=72)))
        check = check_font(font.ttf, layout)
        summary[mode] = {"pages": pages, "font": check, "derived": font.derived, "matra": [round(v) for v in font.matra], "seconds": round(time.time() - t0)}
        print(json.dumps({mode: summary[mode]}, ensure_ascii=False, indent=1))
        if mode == modes[0]:
            others = [x for x in drawings if x.glyph not in {p.glyph for p in layout.plans()}]
            written = build_font(others + written_parts(layout, np.random.default_rng(3)), "Synth Written Parts")
            compare_image(font.ttf, written.ttf, out / "compare-parts.png")
            (out / "compare-written.ttf").write_bytes(written.ttf)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print_table(summary)


def print_table(s: dict):
    print(f"{'mode':<10}{'pg':<3}{'ink':<6}{'guide':<6}{'thr(off/on)':<13}{'miss':<5}{'edge':<20}{'prec':<7}{'rec':<7}{'stray':<6}{'cut/merged':<24}dots")
    for m, v in s.items():
        for p in v["pages"]:
            cut = " ".join(p["cut_or_merged"]) or "-"
            dots = " ".join(k + ("✓" if ok else "✗") for k, ok in p["dots"].items())
            print(f"{m:<10}{p['page']:<3}{p['ink_darkness']:<6}{p['guide_darkness']:<6}{str(p['thresholds']):<13}{len(p['missing']):<5}{' '.join(p['touches_edge']):<20}{p['precision_min']:<7}{p['recall_min']:<7}{p['stray_px']:<6}{cut:<24}{dots}")
        f = v["font"]
        print(f"   font: .notdef {sum(f['notdef_in_sentences'].values())} | shaping differs from plan: {f['shaping_differs_from_plan'] or 'none'} | {f['conjuncts']} | matra {v['matra']}")


if __name__ == "__main__":
    main()
