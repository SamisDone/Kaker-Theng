"""End-to-end synthetic run for page 1 (English), colour and B&W laser.

    python -m scripts.synth_report [out_dir]

Writes, per mode: the simulated upload, the extracted ink, the marked-up
thumbnail, the built font, and a rendered pangram. Exits non-zero if a check
fails.
"""

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from app.cells import cut_cells
from app.fontbuild import build_font
from app.ink import extract_ink
from app.pipeline import decode_image, process_page
from app.render import png, render_lines, shape_names
from app.scan import find_page
from app.vectorize import vectorize
from tests.synth import ink_agreement, make_page

PANGRAM = "The quick brown fox jumps over the lazy dog."
SPECIMEN = [
    PANGRAM,
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789 .,;:!?'\"()-&@/",
]


def run(mode: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    synth = make_page(1, mode)
    t_synth = time.time() - t0
    (out / "upload.jpg").write_bytes(synth.photo_jpeg)

    t0 = time.time()
    image = decode_image(synth.photo_jpeg)
    result = process_page(image, expected_page=1)
    t_pipeline = time.time() - t0

    # Same steps again, keeping the full-resolution ink for scoring.
    found = find_page(image)
    ink, stats = extract_ink(found.gray, found.page)
    scores = ink_agreement(ink, synth.truth, 1)
    cells = cut_cells(ink, 1)
    font = build_font([vectorize(ci) for ci in cells if ci.status != "missing"], f"Synth {mode.title()}")
    (out / "font.ttf").write_bytes(font.ttf)
    (out / "font.woff2").write_bytes(font.woff2)

    (out / "thumbnail.png").write_bytes(result.thumbnail_png)
    (out / "ink.png").write_bytes(result.ink_png)
    (out / "specimen.png").write_bytes(png(render_lines(font.ttf, SPECIMEN, px_per_em=64)))

    names = shape_names(font.ttf, PANGRAM)
    precision = [p for p, _, _ in scores.values()]
    recall = [r for _, r, _ in scores.values()]
    stray = sum(s for _, _, s in scores.values())
    worst = sorted(scores.items(), key=lambda kv: min(kv[1][0], kv[1][1]))[:5]
    report = {
        "mode": mode,
        "page": result.page,
        "upload_kb": len(synth.photo_jpeg) // 1024,
        "seconds_pipeline": round(t_pipeline, 1),
        "seconds_synth": round(t_synth, 1),
        "guides": {"median_darkness": round(stats.guide_darkness, 3), "p95": round(stats.guide_p95, 3)},
        "thresholds": {"off_guides": round(stats.loose, 3), "on_guides": round(stats.strict, 3)},
        "residue_components_removed": stats.removed_components,
        "cells": {s: sum(1 for c in result.cells if c["status"] == s) for s in ("ok", "missing", "touches_edge")},
        "ink_precision_mean": round(float(np.mean(precision)), 3),
        "ink_precision_min": round(float(np.min(precision)), 3),
        "ink_recall_mean": round(float(np.mean(recall)), 3),
        "ink_recall_min": round(float(np.min(recall)), 3),
        "stray_ink_px_total": stray,
        "worst_cells": {k: [round(v[0], 3), round(v[1], 3), v[2]] for k, v in worst},
        "font_glyphs": len(font.glyphs),
        "font_kb": {"ttf": len(font.ttf) // 1024, "woff2": len(font.woff2) // 1024},
        "pangram_notdef": names.count(".notdef"),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report


def side_by_side(out: Path, modes: list[str]):
    """One image per mode: upload | extracted ink | marked thumbnail, specimen below."""
    for mode in modes:
        d = out / mode
        up = cv2.imread(str(d / "upload.jpg"))
        ink = cv2.imread(str(d / "ink.png"))
        th = cv2.imread(str(d / "thumbnail.png"))
        spec = cv2.imread(str(d / "specimen.png"))
        h = 900
        row = [cv2.resize(i, (round(i.shape[1] * h / i.shape[0]), h), interpolation=cv2.INTER_AREA) for i in (up, ink, th)]
        top = np.hstack([np.pad(r, ((0, 0), (0, 12), (0, 0)), constant_values=255) for r in row])
        s = top.shape[1] / spec.shape[1]
        spec = cv2.resize(spec, (top.shape[1], round(spec.shape[0] * s)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / f"{mode}-overview.png"), np.vstack([top, np.full((12, top.shape[1], 3), 255, np.uint8), spec]))


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/synth")
    modes = ["colour", "laser", "copy"]
    failed = False
    for mode in modes:
        r = run(mode, out / mode)
        print(json.dumps(r, indent=1, ensure_ascii=False))
        checks = {
            "page detected": r["page"] == 1,
            "no missing cells": r["cells"]["missing"] == 0,
            "pangram has no .notdef": r["pangram_notdef"] == 0,
            "ink recall >= 0.9 everywhere": r["ink_recall_min"] >= 0.9,
            "ink precision >= 0.9 everywhere": r["ink_precision_min"] >= 0.9,
        }
        for name, ok in checks.items():
            print(f"  [{'ok' if ok else 'FAIL'}] {mode}: {name}")
            failed |= not ok
    side_by_side(out, modes)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
