"""Static files the website needs, generated from the backend's layout.

    python -m scripts.export_frontend_assets [../frontend/public/kt]

Writes template page thumbnails, the list of cells (for the specimen grid),
and an example drawing for every fragment cell. layout.json carries the
layout fingerprint; tests/test_frontend_assets.py fails if it goes stale.
"""

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

from app.basefont import base_shaper, headline_units
from app.charset import OPTIONAL_PAGES, PAGE_TITLES
from app.coverage import complete_coverage, pages_1_2_coverage
from app.glyphmap import build_layout, fingerprint
from app.template import build_template_pdf

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "frontend" / "public" / "kt")


def svg_path(name: str, dx: float, dy: float) -> str:
    gs = base_shaper().tt.getGlyphSet()
    pen = SVGPathPen(gs)
    gs[name].draw(TransformPen(pen, (1, 0, 0, -1, dx, -dy)))  # y down for SVG
    return pen.getCommands()


def fragment_example(cell) -> dict:
    """The conjunct with the rest printed faint and the piece to write dark,
    in font units with y pointing down."""
    ghost = " ".join(svg_path(g.name, g.x, g.y) for g in cell.ghost_glyphs)
    piece = svg_path(cell.glyph, cell.target_x, cell.target_y)
    return {"id": cell.id, "text": cell.text, "ghost": ghost, "piece": piece, "viewBox": [-60, -1000, max(cell.run_advance, 400) + 120, 1330]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    layout = build_layout()
    doc = pdfium.PdfDocument(build_template_pdf())
    for i in range(len(doc)):
        doc[i].render(scale=72 / 72).to_pil().convert("L").save(OUT / f"template-p{i + 1}.png", optimize=True)

    pages = {}
    for n in (1, 2, 3):
        cells = layout.page(n)
        pages[n] = {
            "title_bn": PAGE_TITLES[n][0],
            "title_en": PAGE_TITLES[n][1],
            "optional": n in OPTIONAL_PAGES,
            "cells": [
                {"id": c.id, "text": c.text, "group": c.group, "kind": c.kind, "fragment": c.group == "part"}
                for c in cells
            ],
        }
    data = {
        "fingerprint": fingerprint(),
        "headline": headline_units(),
        "pages": pages,
        "fragments": [fragment_example(c) for c in layout.cells if c.group == "part"],
        "coverage_targets": {"pages_1_2": pages_1_2_coverage(), "all_pages": complete_coverage()},
    }
    (OUT / "layout.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: 3 thumbnails, {sum(len(p['cells']) for p in pages.values())} cells, {len(data['fragments'])} fragment examples")


if __name__ == "__main__":
    main()
