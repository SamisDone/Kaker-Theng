"""Build dist/: the Python the browser runs, plus CPython reference results.

    backend/.venv/Scripts/python -X utf8 build_bundle.py

dist/bundle.zip   backend/app and backend/assets unchanged, potrace (pure
                  Python), the reportlab modules stringWidth needs, and the
                  uharfbuzz shim
dist/sample-page1.jpg   the photo the page processes by default
dist/expected.json      what CPython makes of that photo, and HarfBuzz
                  results to check the shim against
"""

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BACKEND = REPO / "backend"
SITE = Path(subprocess.check_output([sys.executable, "-c", "import potrace, os; print(os.path.dirname(os.path.dirname(potrace.__file__)))"], text=True).strip())
DIST = HERE / "dist"
SAMPLE = BACKEND / "tests" / "data" / "sample-page1.jpg"

# Imported only by the server, the offline scripts and the template PDF.
SKIP_APP = {"main.py", "jobs.py", "template.py", "render.py"}


def reportlab_files() -> list[Path]:
    """Exactly the reportlab modules that stringWidth pulls in."""
    code = (
        "import sys, json; from reportlab.pdfbase.pdfmetrics import stringWidth; stringWidth('Ag', 'Helvetica', 9);"
        "print(json.dumps(sorted(m.__file__ for n, m in sys.modules.items() if n.startswith('reportlab') and getattr(m, '__file__', None))))"
    )
    return [Path(p) for p in json.loads(subprocess.check_output([sys.executable, "-c", code], text=True))]


def build_zip():
    out = DIST / "bundle.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted((BACKEND / "app").glob("*.py")):
            if f.name not in SKIP_APP:
                z.write(f, f"backend/app/{f.name}")
        for f in sorted((BACKEND / "assets").iterdir()):
            z.write(f, f"backend/assets/{f.name}")
        for f in sorted((SITE / "potrace").rglob("*.py")):
            z.write(f, f.relative_to(SITE).as_posix())
        for f in reportlab_files():
            z.write(f, f.relative_to(SITE).as_posix())
        z.write(HERE / "uharfbuzz.py", "uharfbuzz.py")
    return out


def glyph_summary(ttf: bytes) -> dict:
    """Per glyph: advance and outline bounds. Enough to see if two builds differ."""
    import io

    from fontTools.ttLib import TTFont

    f = TTFont(io.BytesIO(ttf))
    glyf, hmtx = f["glyf"], f["hmtx"]
    out = {}
    for name in f.getGlyphOrder():
        g = glyf[name]
        box = [g.xMin, g.yMin, g.xMax, g.yMax] if g.numberOfContours else None
        out[name] = {"adv": hmtx[name][0], "box": box, "contours": g.numberOfContours}
    return out


def shaping_sample() -> list[str]:
    """Bangla clusters from the corpus counts, to compare shaping results."""
    counts = json.loads((BACKEND / "assets" / "conjunct_counts.json").read_text(encoding="utf-8"))
    clusters = counts.get("clusters", counts)
    return sorted(clusters, key=lambda c: -clusters[c] if isinstance(clusters[c], (int, float)) else 0)[:300]


def reference():
    # The real uharfbuzz here, not the browser shim next to this script.
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
    sys.path.insert(0, str(BACKEND))
    import time

    from app.basefont import base_shaper
    from app.coverage import complete_coverage, pages_1_2_coverage
    from app.fontbuild import build_font
    from app.pipeline import decode_image, process_page

    t = time.time()
    r = process_page(decode_image(SAMPLE.read_bytes()))
    t_page = time.time() - t
    t = time.time()
    font = build_font(r.drawings, "Prototype")
    t_font = time.time() - t
    texts = shaping_sample()
    shaped = [[(g.name, g.cluster, g.x_advance, g.x_offset, g.y_offset) for g in base_shaper().shape(s)] for s in texts]
    return {
        "full": full_reference(),
        "page": r.page,
        "cells_read": sum(1 for c in r.cells if c["status"] != "missing"),
        "cells_total": len(r.cells),
        "statuses": {c["id"]: c["status"] for c in r.cells},
        "glyphs": glyph_summary(font.ttf),
        "ttf_bytes": len(font.ttf),
        "woff2_bytes": len(font.woff2),
        "complete_coverage": complete_coverage(),
        "pages_1_2_coverage": pages_1_2_coverage(),
        "shaping_texts": texts,
        "shaping": shaped,
        "shaping_sha256": hashlib.sha256(json.dumps(shaped, ensure_ascii=False).encode()).hexdigest(),
        "cpython_seconds": {"process_page": round(t_page, 2), "build_font": round(t_font, 2)},
    }, font.ttf


def full_reference() -> dict:
    """Pages 1+2 (synthetic laser prints) through to the Bangla font and its
    coverage: the derived conjunct parts, GSUB packing and HarfBuzz on the
    user's font. Built twice: with uharfbuzz's repacker (the server today)
    and with fontTools' own packer (what the browser uses)."""
    import time

    import fontTools.ttLib.tables.otBase as otBase

    from app.coverage import font_coverage
    from app.fontbuild import build_font
    from app.pipeline import decode_image, process_page
    from tests.synth import make_page

    out, drawings = {"process_page": {}}, []
    for page in (1, 2):
        photo = make_page(page, "laser").photo_jpeg
        (DIST / f"full-p{page}.jpg").write_bytes(photo)
        t = time.time()
        r = process_page(decode_image(photo))
        out["process_page"][page] = round(time.time() - t, 2)
        drawings += r.drawings
    written = {d.glyph for d in drawings if d.kind != "latin"}
    for packer, use_hb in (("uharfbuzz", True), ("fonttools", False)):
        otBase.have_uharfbuzz = use_hb
        t = time.time()
        font = build_font(drawings, "Prototype")
        out[packer] = {"build_font": round(time.time() - t, 2), "ttf_bytes": len(font.ttf), "glyphs": len(font.glyphs),
                       "coverage": font_coverage(font.ttf, written)}
    otBase.have_uharfbuzz = True
    return out


def main():
    DIST.mkdir(exist_ok=True)
    z = build_zip()
    shutil.copyfile(SAMPLE, DIST / "sample-page1.jpg")
    ref, ttf = reference()
    (DIST / "expected.json").write_text(json.dumps(ref, ensure_ascii=False), encoding="utf-8")
    (DIST / "cpython.ttf").write_bytes(ttf)
    print(f"bundle.zip {z.stat().st_size / 2**20:.2f} MB; reference: page {ref['page']}, {ref['cells_read']}/{ref['cells_total']} cells, "
          f"{len(ref['glyphs'])} glyphs, coverage {ref['complete_coverage']:.4f} / {ref['pages_1_2_coverage']:.4f}, "
          f"CPython {ref['cpython_seconds']}")
    print(f"pages 1+2 reference: {ref['full']}")


if __name__ == "__main__":
    main()
