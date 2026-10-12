"""Build the template PDF, print the shaping log, and render page previews.

    python -m scripts.make_template [out_dir]

Previews need PyMuPDF (dev only: pip install pymupdf).
"""

import sys
from pathlib import Path

from app import config as C
from app.basefont import headline_units
from app.glyphmap import build_layout, layout_json
from app.template import build_template_pdf


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
    out.mkdir(parents=True, exist_ok=True)
    layout = build_layout()

    print(f"headline (মাত্রা centre) = {headline_units()} units, {C.MM_PER_UNIT:.5f} mm/unit")
    print(f"{'page':<5}{'cell':<8}{'ghost':<6}{'kind':<6}{'glyph':<26}status / base font -> final font")
    for e in layout.log:
        if e["page"] == 1:
            continue
        print(
            f"{e['page']:<5}{e['text']:<8}{e.get('ghost') or '':<6}{e.get('kind', '-'):<6}"
            f"{str(e['glyph']):<26}{e['status']}"
        )
        if e["base_font"] != e["final_font"]:
            print(f"{'':<25}base font : {' '.join(e['base_font'])}")
            print(f"{'':<25}final font: {' '.join(e['final_font'])}")
    print(f"\ncells per page: " + ", ".join(f"p{p}={len(layout.page(p))}" for p in (1, 2, 3)))
    print("excluded:", ", ".join(f"{e['text']} ({e['status']})" for e in layout.excluded) or "none")

    pdf = build_template_pdf()
    (out / "template.pdf").write_bytes(pdf)
    (out / "glyphmap.json").write_text(layout_json(layout), encoding="utf-8")
    print(f"\nwrote {out / 'template.pdf'} ({len(pdf) // 1024} KB)")

    try:
        import fitz
    except ImportError:
        return
    doc = fitz.open(stream=pdf, filetype="pdf")
    for i, page in enumerate(doc, 1):
        page.get_pixmap(dpi=110).save(str(out / f"template-p{i}.png"))
    page = doc[2]
    clip = fitz.Rect(15 * 2.835, 30 * 2.835, 110 * 2.835, 120 * 2.835)
    page.get_pixmap(dpi=300, clip=clip).save(str(out / "template-p3-zoom.png"))
    print("wrote previews")


if __name__ == "__main__":
    main()
