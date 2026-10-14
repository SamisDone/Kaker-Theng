"""Build the template PDF, print the shaping log, and render page previews.

    python -m scripts.make_template [out_dir]

Previews need pypdfium2 (dev only, see requirements-dev.txt).
"""

import sys
from pathlib import Path

from app import config as C
from app.basefont import base_shaper, headline_units, simulated_shaper
from app.glyphmap import HALANT, compute_layout, layout_json, part_report
from app.template import build_template_pdf

COMMON_CONJUNCTS = (
    "ক্ক ক্ট ক্ত ক্ব ক্ম ক্ল ক্স ক্ষ গ্ধ গ্ন গ্ব গ্ম গ্ল ঘ্ন ঙ্ক ঙ্গ চ্চ চ্ছ জ্জ জ্ঞ জ্ব ঞ্চ ঞ্জ ট্ট ড্ড "
    "ণ্ট ণ্ড ত্ত ত্থ ত্ন ত্ব ত্ম দ্দ দ্ধ দ্ব দ্ভ দ্ম ধ্ব ন্ট ন্ড ন্ত ন্থ ন্দ ন্ধ ন্ন ন্ব ন্ম প্ট প্ত প্ন "
    "প্প প্ল প্স ব্জ ব্দ ব্ধ ব্ব ব্ল ভ্ল ম্ন ম্প ম্ব ম্ভ ম্ম ম্ল ল্ক ল্গ ল্ট ল্ড ল্প ল্ম ল্ল শ্চ শ্ন শ্ব "
    "শ্ম শ্ল ষ্ক ষ্ট ষ্ঠ ষ্ণ ষ্প ষ্ম স্ক স্খ স্ট স্ত স্থ স্ন স্প স্ফ স্ব স্ম স্ল হ্ন হ্ব হ্ম হ্ল"
).split()

TEST_SENTENCES = [
    "আমি প্রতিদিন সকালে চা খাই।",
    "কর্মী ক্ষমা চাইল।",
    "বিদ্যালয়ের সামনে বৃষ্টি পড়ছে।",
]


def report(layout):
    print(f"headline (মাত্রা centre) = {headline_units()} units, {C.MM_PER_UNIT:.5f} mm/unit\n")
    print(f"{'page':<5}{'cell':<8}{'ghost':<6}{'kind':<6}{'glyph':<26}status")
    for e in layout.log:
        if e["page"] == 1:
            continue
        print(f"{e['page']:<5}{e['text'] or '':<8}{e.get('ghost') or '':<6}{e.get('kind', '-'):<6}{str(e['glyph']):<26}{e['status']}")
        if e.get("base_font") and e["base_font"] != e["final_font"]:
            print(f"{'':<25}base font : {' '.join(e['base_font'])}")
            print(f"{'':<25}final font: {' '.join(e['final_font'])}")

    print("\nPARTS (glyph / visible in / rule chain needs it for)")
    for p in part_report(layout):
        print(f"  {p['glyph']:<22} visible in: {' '.join(p['visible_in']) or '-':<14} needed by: {' '.join(p['needed_by'])}")

    glyphs = layout.bangla_glyphs() | {"space", "nbspace", "dottedCircle"}
    sim = simulated_shaper(glyphs)
    halant = base_shaper().tt.getBestCmap()[ord(HALANT)]
    singles = {c.glyph for c in layout.cells if c.group == "conjunct"}
    parts = {p["glyph"] for p in layout.parts}
    rows = {"single glyph (written whole)": [], "from written parts": [], "visible hasanta": [], "other": []}
    for t in COMMON_CONJUNCTS:
        names = sim.names(t)
        if len(names) == 1 and names[0] in singles:
            rows["single glyph (written whole)"].append(t)
        elif halant in names:
            rows["visible hasanta"].append(t)
        elif any(n in parts for n in names):
            rows["from written parts"].append(f"{t}={'+'.join(names)}")
        else:
            rows["other"].append(f"{t}={'+'.join(names)}")
    print(f"\nCOMMON CONJUNCTS in the finished font ({len(COMMON_CONJUNCTS)} checked)")
    for k, v in rows.items():
        print(f"  {k} [{len(v)}]: {'  '.join(v)}")

    print("\nTEST SENTENCES in the finished font")
    for s in TEST_SENTENCES:
        print(f"  {s}\n    {' '.join(sim.names(s))}")

    print("\ncells per page: " + ", ".join(f"p{p}={len(layout.page(p))}" for p in (1, 2, 3)))
    used = {p: max(c.box_mm()[1] + c.box_mm()[3] for c in layout.page(p)) - C.GRID_Y_MM for p in (1, 2, 3)}
    print(f"grid height used (of {C.GRID_H_MM:.0f} mm): " + ", ".join(f"p{p}={h:.0f} mm" for p, h in used.items()))
    print("excluded: " + ", ".join(f"{e['text'] or e['glyph']} ({e['status']})" for e in layout.excluded))


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
    out.mkdir(parents=True, exist_ok=True)
    layout = compute_layout()
    C.LAYOUT_CACHE_PATH.write_text(layout_json(layout), encoding="utf-8", newline="\n")
    print(f"wrote {C.LAYOUT_CACHE_PATH}")
    report(layout)

    pdf = build_template_pdf()
    (out / "template.pdf").write_bytes(pdf)
    print(f"\nwrote {out / 'template.pdf'} ({len(pdf) // 1024} KB)")

    try:
        import pypdfium2 as pdfium
    except ImportError:
        return
    doc = pdfium.PdfDocument(pdf)
    for i in range(len(doc)):
        doc[i].render(scale=110 / 72).to_pil().save(out / f"template-p{i + 1}.png")
    print("wrote previews")


if __name__ == "__main__":
    main()
