"""Static files the website needs, generated from the backend's layout.

    python -m scripts.export_frontend_assets [../frontend/public/kt]

Writes template page thumbnails, the list of cells (for the specimen grid
and, with guides and ghosts in cell mm, for the drawing canvas), the drawing order,
and an example drawing for every fragment cell. layout.json carries the
layout fingerprint; tests/test_frontend_assets.py fails if it goes stale.
"""

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

from app import config as C
from app.basefont import base_shaper, headline_units
from app.charset import OPTIONAL_PAGES, PAGE_TITLES
from app.coverage import complete_coverage, pages_1_2_coverage
from app.draworder import draw_order
from app.wordcov import complete_word_coverage, pages_1_2_word_coverage
from app.glyphmap import build_layout, fingerprint
from app.guides import GUIDE_INSET_MM, baseline_mm, headline_mm, run_left_mm
from app.strokes import PEN_MM
from app.template import build_template_pdf

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "frontend" / "public" / "kt")


def svg_path(name: str, dx: float, dy: float) -> str:
    gs = base_shaper().tt.getGlyphSet()
    pen = SVGPathPen(gs)
    gs[name].draw(TransformPen(pen, (1, 0, 0, -1, dx, -dy)))  # y down for SVG
    return pen.getCommands()


def mm(v: float) -> float:
    return round(v, 2)


def draw_geometry(cell) -> dict:
    """What the drawing canvas shows, in mm inside the cell box (origin
    top-left, y down): the same guides and faint ghost as the template."""
    x, y, w, h = cell.box_mm()
    base, head = baseline_mm(cell) - y, headline_mm(cell) - y
    s, left = C.MM_PER_UNIT, run_left_mm(cell) - x
    ghost = []
    gs = base_shaper().tt.getGlyphSet()
    for g in cell.ghost_glyphs:
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        gs[g.name].draw(TransformPen(pen, (s, 0, 0, -s, left + g.x * s, base - g.y * s)))
        ghost.append(pen.getCommands())
    out = {"w": mm(w), "h": mm(h), "base": mm(base), "head": mm(head), "inset": GUIDE_INSET_MM, "ghost": " ".join(p for p in ghost if p)}
    if cell.kind == "latin":
        out["xh"] = mm(base - headline_units() * C.LATIN_XHEIGHT_RATIO * s)
    return out


def missing_font() -> bytes:
    """A tiny font where every Bangla and ASCII character is one faint grey
    box (a colour layer, so it stays grey whatever the text colour). The site
    puts it after the user's preview font: letters not drawn yet show as
    boxes, never in another typeface."""
    import io

    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    def box(x0, y0, x1, y1):
        pen = TTGlyphPen(None)
        pen.moveTo((x0, y0)), pen.lineTo((x0, y1)), pen.lineTo((x1, y1)), pen.lineTo((x1, y0)), pen.closePath()
        return pen.glyph()

    empty = TTGlyphPen(None).glyph()
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "space", "zero", "box"])
    cmap = {0x20: "space", 0xA0: "space", 0x200C: "zero", 0x200D: "zero"}
    for cp in [*range(0x21, 0x7F), *range(0x0980, 0x0A00), 0x0964, 0x0965, 0x25CC]:
        cmap[cp] = "box"
    fb.setupCharacterMap(cmap)
    fb.setupGlyf({".notdef": box(80, -60, 520, 680), "space": empty, "zero": empty, "box": box(80, -60, 520, 680)})
    fb.setupHorizontalMetrics({".notdef": (600, 80), "space": (300, 0), "zero": (0, 0), "box": (600, 80)})
    fb.setupHorizontalHeader(ascent=900, descent=-300)
    fb.setupNameTable({"familyName": "KT Missing", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-300, usWinAscent=900, usWinDescent=300)
    fb.setupPost()
    fb.setupCPAL([[(0x1D / 255, 0x21 / 255, 0x40 / 255, 0.13)]])  # ink at 13%: faint on paper
    fb.setupCOLR({"box": [("box", 0)]})
    fb.font.flavor = "woff2"
    out = io.BytesIO()
    fb.save(out)
    return out.getvalue()


def fragment_example(cell) -> dict:
    """The conjunct with the rest printed faint and the piece to write dark,
    in font units with y pointing down."""
    ghost = " ".join(svg_path(g.name, g.x, g.y) for g in cell.ghost_glyphs)
    piece = svg_path(cell.glyph, cell.target_x, cell.target_y)
    return {"id": cell.id, "text": cell.text, "ghost": ghost, "piece": piece, "viewBox": [-60, -1000, max(cell.run_advance, 400) + 120, 1330]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    layout = build_layout()
    pdf = build_template_pdf()
    # A static copy: the "print" step works instantly, even while the free
    # backend is still waking up.
    for old in OUT.glob("kaker-theng-template-v*.pdf"):
        old.unlink()
    pdf_name = f"kaker-theng-template-v{C.TEMPLATE_VERSION}.pdf"
    (OUT / pdf_name).write_bytes(pdf)
    doc = pdfium.PdfDocument(pdf)
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
                {"id": c.id, "text": c.text, "ghost": c.ghost, "group": c.group, "kind": c.kind, "fragment": c.group == "part", "draw": draw_geometry(c)}
                for c in cells
            ],
        }
    data = {
        "fingerprint": fingerprint(),
        "template_version": C.TEMPLATE_VERSION,
        "template_pdf": pdf_name,
        "headline": headline_units(),
        "pages": pages,
        "fragments": [fragment_example(c) for c in layout.cells if c.group == "part"],
        "draw_order": draw_order(),
        "pen_mm": PEN_MM,
        "coverage_targets": {
            "pages_1_2": pages_1_2_coverage(),
            "all_pages": complete_coverage(),
            "words_pages_1_2": pages_1_2_word_coverage(),
            "words_all_pages": complete_word_coverage(),
        },
    }
    (OUT / "layout.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    (OUT / "missing.woff2").write_bytes(missing_font())
    print(f"wrote {OUT}: 3 thumbnails, {sum(len(p['cells']) for p in pages.values())} cells, {len(data['fragments'])} fragment examples")


if __name__ == "__main__":
    main()
