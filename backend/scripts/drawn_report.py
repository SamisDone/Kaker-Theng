"""Fonts from drawn strokes only (no photo): time, coverage, peak memory, PNG.

    python -X utf8 -m scripts.drawn_report <out dir> [strokes.json]

Strokes default to tests/synth_strokes.py's synthetic drawing; a file
({cell id: strokes}) can be given instead. Builds the font twice: pages 1+2
drawn, and every cell drawn. For the free server's numbers run it in the
image at its limits (the image has no scripts/ or tests/, so mount them):

    docker run --rm --cpus 0.1 -m 512m --memory-swap 512m -e PYTHONPATH=/srv \
      -v <backend>/scripts:/srv/scripts -v <out dir>:/out kaker-theng \
      python -m scripts.drawn_report /out /out/drawn-cells.json
"""

import json
import sys
import time
from pathlib import Path

from app.coverage import font_coverage
from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.render import png, render_lines
from app.strokes import drawing

SAMPLE = [
    "আমি বাংলায় গান গাই। কাকের ঠ্যাং বকের ঠ্যাং",
    "প্রতিদিন সকালে চা খাই, স্কুলে যাই। ক্ষমা",
    "The quick brown fox jumps over the lazy dog.",
]


def peak_mb() -> float | None:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:  # Windows
        return None


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2:
        cells_strokes = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    else:
        from tests.synth_strokes import drawn_cells

        cells_strokes = drawn_cells()
    layout = {c.id: c for c in build_layout().cells}
    t = time.time()
    build_layout()
    print(f"startup (layout): {time.time() - t:.1f} s, peak {peak_mb()} MB")

    for label, pages in (("pages 1+2", {1, 2}), ("all pages", {1, 2, 3})):
        ids = [i for i in cells_strokes if layout[i].page in pages]
        t = time.time()
        drawings = [drawing(layout[i], cells_strokes[i]) for i in ids]
        t_outline = time.time() - t
        t = time.time()
        font = build_font(drawings, "Drawn Check")
        t_font = time.time() - t
        t = time.time()
        written = {d.glyph for d in drawings if d.kind != "latin"}
        cov = font_coverage(font.ttf, written)
        t_cov = time.time() - t
        (out / f"drawn-{label.replace(' ', '').replace('+', '-')}.ttf").write_bytes(font.ttf)
        print(f"{label}: {len(ids)} cells, strokes->outlines {t_outline:.2f} s, build_font {t_font:.2f} s, "
              f"coverage {cov:.4f} ({t_cov:.2f} s), {len(font.glyphs)} glyphs, TTF {len(font.ttf) // 1024} KB, peak {peak_mb()} MB")
    (out / "drawn-specimen.png").write_bytes(png(render_lines(font.ttf, SAMPLE, px_per_em=64)))


if __name__ == "__main__":
    main()
