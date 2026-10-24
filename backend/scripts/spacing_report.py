"""Spacing of a built font: advances against ink, and letters that collide.

    python -X utf8 -m scripts.spacing_report <font.ttf|.woff2> <out dir> [label]

For every Bangla glyph: advance, ink box, right side bearing, and the base
font's advance. Flags a glyph whose advance equals the base font's while
its ink is a different width (the advance came from Noto, not the ink), and
a right side bearing below the মাত্রা join. Then shapes the sample words,
lists syllables whose ink overlaps outside the মাত্রা band, and renders the
words to <out dir>/words-<label>.png.
"""

import io
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

from app.basefont import base_shaper, base_ttfont, headline_units
from app.fontbuild import BANGLA_OPEN_SIDE_BEARING, BANGLA_RSB
from app.glyphmap import build_layout
from app.render import png, render_lines
from app.spacing import collisions

WORDS = ["আমি", "কলম", "বাংলা", "সকালে", "বিদ্যালয়", "কিছু", "বেশি", "দেশে", "কৈ", "নিজের", "তিনি", "পৌঁছে", "প্রতিদিন", "সূর্য", "বাংলাদেশ", "দেখি"]
LINES = ["আমি কলম বাংলা সকালে", "বিদ্যালয় কিছু বেশি দেশে", "নিজের তিনি পৌঁছে দেখি", "প্রতিদিন সূর্য বাংলাদেশ"]
JOIN = -BANGLA_RSB + 25  # a মাত্রা join plus a pen's round end
BODY = 400  # units²: a pen's round end touching, at most
CONJUNCT_WORDS = ["সন্দেশ", "বন্ধু", "শক্তি", "মন্ত্রী", "স্কুল", "ইচ্ছা", "অঞ্চল", "উদ্দেশ্য", "পদ্ধতি", "রাষ্ট্র"]


def ttf_bytes(path: Path) -> bytes:
    tt = TTFont(path)
    tt.flavor = None
    out = io.BytesIO()
    tt.save(out)
    return out.getvalue()


def glyph_table(font: bytes) -> list[str]:
    tt = TTFont(io.BytesIO(font))
    noto = base_shaper().tt
    cells = {c.glyph: c for c in build_layout().cells}
    rows, flags = [], []
    for name in tt.getGlyphOrder():
        g = tt["glyf"][name]
        if name not in noto["glyf"].glyphs or not g.numberOfContours:
            continue
        g.recalcBounds(tt["glyf"])
        adv = tt["hmtx"][name][0]
        if adv == 0:
            continue  # zero-advance marks: GPOS places them
        ng = noto["glyf"][name]
        noto_adv = noto["hmtx"][name][0]
        ink, noto_ink = g.xMax - g.xMin, (ng.xMax - ng.xMin) if ng.numberOfContours else 0
        rsb = adv - g.xMax
        cell = cells.get(name)
        what = cell.text if cell else f"({name})"
        note = []
        # A drawn letter's advance is its ink plus the bearings fontbuild
        # gives; one equal to Noto's for another reason is a coincidence.
        ink_rule = cell is not None and not cell.ghost_glyphs and rsb in (BANGLA_RSB, BANGLA_OPEN_SIDE_BEARING)
        if adv == noto_adv and abs(ink - noto_ink) > 20 and not ink_rule:
            note.append("advance from Noto")
        if rsb < -JOIN and not (cell and cell.ghost_glyphs and cell.target_x < min(gg.x for gg in cell.ghost_glyphs)):
            note.append(f"RSB {rsb} < -{JOIN}")
        rows.append(f"  {what:6} {name:24} adv {adv:5} ink {g.xMin:5}..{g.xMax:5} lsb {g.xMin:5} rsb {rsb:5}  noto adv {noto_adv:5}  {'; '.join(note)}")
        if note:
            flags.append(rows[-1])
    return rows, flags


def main():
    path, out = Path(sys.argv[1]), Path(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else path.stem
    out.mkdir(parents=True, exist_ok=True)
    font = ttf_bytes(path)
    rows, flags = glyph_table(font)
    print(f"{len(rows)} spacing glyphs; flagged {len(flags)}:")
    print("\n".join(flags) if flags else "  none")
    matra = (headline_units() - 20, 60)
    noto = io.BytesIO()
    base_ttfont().save(noto)
    print(f"neighbours whose ink overlaps under the মাত্রা band (> {BODY} units²) or by more than {JOIN} in it; Noto's own overlap there in brackets:")
    bad = 0
    for w in WORDS + CONJUNCT_WORDS:
        mine, ref = collisions(font, w, matra), collisions(noto.getvalue(), w, (headline_units() - 20, 60))
        same = [(r.left, r.right) for r in ref] == [(c.left, c.right) for c in mine]
        for i, c in enumerate(mine):
            if c.body > BODY or c.band > JOIN:
                bad += 1
                r = f"  [Noto {ref[i].body:.0f} / {ref[i].band:.0f}]" if same else ""
                print(f"  {w}: {c.left} | {c.right}  body {c.body:.0f}  band {c.band:.0f}{r}")
    print(f"  {bad} pair(s)")
    (out / f"words-{label}.png").write_bytes(png(render_lines(font, LINES, px_per_em=110)))
    (out / f"glyphs-{label}.txt").write_text("\n".join(rows), encoding="utf-8")


if __name__ == "__main__":
    main()
