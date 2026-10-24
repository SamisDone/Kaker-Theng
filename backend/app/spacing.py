"""Do neighbouring letters' inks collide? Measured on a built font.

Text is shaped with HarfBuzz. Every glyph that takes up room (an advance:
a letter, ি ে া, a conjunct or a piece of one) is drawn together with the
marks attached to it (ু ং ্ ...), and the ink two neighbours share is
measured. In and above the মাত্রা band some overlap is wanted: headlines
join (fontbuild.BANGLA_RSB), and the hooks of ি ী ৗ reach over the
neighbouring letter's মাত্রা, wherever the writer put it. Under the মাত্রা,
ink of one letter on another is a spacing bug.

fontbuild uses widen() for what it can't know from one drawing alone: a
conjunct part cut from the writer's letter keeps the base font's advance,
made to interlock with the base font's next letter, not the writer's; and
a visible হসন্ত hangs past its letter into the next.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont

from .outline import glyph_polygons

RES = 0.25  # px per font unit
BODY_LIMIT = 400  # font units²: a pen's round end touching, at most
CLEARANCE = 20  # font units left between two inks once pushed apart


@dataclass
class Collision:
    text: str  # the word
    left: str  # glyph names of the two neighbours
    right: str
    body: float  # shared ink under the মাত্রা band, font units²
    band: float  # how far the two overlap inside the band, font units (x)


class Shaped:
    """One font, ready to shape and draw text."""

    def __init__(self, font_bytes: bytes):
        tt = TTFont(io.BytesIO(font_bytes))
        self.order, self.gs = tt.getGlyphOrder(), tt.getGlyphSet()
        self.font = hb.Font(hb.Face(hb.Blob(font_bytes)))
        gdef = tt["GDEF"].table.GlyphClassDef.classDefs if "GDEF" in tt else {}
        self.marks = {g for g, c in gdef.items() if c == 3}
        self._polys: dict[str, list] = {}

    def polys(self, name: str):
        if name not in self._polys:
            self._polys[name] = [np.array(p, np.float64) for p in glyph_polygons(self.gs, name)]
        return self._polys[name]

    def groups(self, text: str):
        """[[(name, x, y)]]: each glyph with an advance, with its marks (a
        mark stays with its letter even when it has an advance: a widened
        হসন্ত)."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {})
        groups: list[list[tuple[str, int, int]]] = []
        x = 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            g = (self.order[info.codepoint], x + pos.x_offset, pos.y_offset)
            if (pos.x_advance and g[0] not in self.marks) or not groups:
                groups.append([g])
            else:
                groups[-1].append(g)
            x += pos.x_advance
        return [g for g in groups if g[0][0] not in ("space", "uni00A0")], x

    def ink_left(self, group) -> float:
        return min((gx + p[:, 0].min() for name, gx, _ in group for p in self.polys(name)), default=0.0)

    def overlaps(self, text: str, matra: tuple[float, float], res: float = RES):
        """(left group, right group, shared ink, band rows) per neighbours."""
        groups, width = self.groups(text)
        lo, hi, off = -600, 1400, 800
        h, w = round((hi - lo) * res), round((width + 1600) * res)

        def mask(glyphs) -> np.ndarray:
            img = np.zeros((h, w), np.uint8)
            polys = [
                (np.stack([(off + gx + p[:, 0]) * res, (hi - (gy + p[:, 1])) * res], 1) * 16).astype(np.int32)
                for name, gx, gy in glyphs
                for p in self.polys(name)
            ]
            if polys:
                cv2.fillPoly(img, polys, 1, cv2.LINE_8, shift=4)
            return img.astype(bool)

        centre, thick = matra
        band = np.zeros(h, bool)
        top, bottom = max(0, round((hi - centre - thick) * res)), round((hi - centre + thick) * res)
        band[top:bottom] = True
        masks = [mask(g) for g in groups]
        for i in range(len(groups) - 1):
            yield groups[i], groups[i + 1], masks[i] & masks[i + 1], band, bottom


def collisions(font_bytes: bytes, text: str, matra: tuple[float, float]) -> list[Collision]:
    """Every pair of neighbouring glyphs in `text`, with the ink they share.
    `matra` is (centre, thickness) of the writer's মাত্রা, font units."""
    out = []
    for a, b, both, band, bottom in Shaped(font_bytes).overlaps(text, matra):
        cols = np.nonzero(both[band].any(axis=0))[0]
        out.append(
            Collision(
                text,
                " ".join(n for n, _, _ in a),
                " ".join(n for n, _, _ in b),
                float(both[bottom:].sum() / RES**2),
                float((cols.max() - cols.min() + 1) / RES) if len(cols) else 0.0,
            )
        )
    return out


def widen(font_bytes: bytes, texts: list[str], matra: tuple[float, float], widenable: set[str], halant: str | None, drawn: set[str]) -> dict[str, int]:
    """Extra advance for glyphs whose ink runs into the next letter's below
    the মাত্রা: {glyph: units}. Only `widenable` glyphs (conjunct parts made
    from the writer's letters) and the হসন্ত are widened, and only before a
    letter the writer drew (`drawn`): a part followed by another part (ল্প,
    ব্ব: a .side or below-base piece) overlaps it by the base font's design.
    The writer's own letters already take their advance from their ink."""
    res = 0.1  # coarse is enough: the limit is a few pixels
    shaped = Shaped(font_bytes)
    extra: dict[str, int] = {}
    for text in texts:
        for a, b, both, _band, bottom in shaped.overlaps(text, matra, res):
            body = both[bottom:]
            if body.sum() / res**2 <= BODY_LIMIT:
                continue
            names = [n for n, _, _ in a]
            if halant in names[1:]:
                # ষ্‌ট: the হসন্ত hangs under the next letter. It is one glyph
                # for every letter, so move only as much as it hangs past
                # where the next letter's ink starts (র-ফলা reaches left of
                # ট), not the whole overlap.
                _, hx, _ = next(g for g in a if g[0] == halant)
                hang = hx + max(p[:, 0].max() for p in shaped.polys(halant)) - shaped.ink_left(b)
                if hang + CLEARANCE > 0:
                    extra[halant] = max(extra.get(halant, 0), round(hang) + CLEARANCE)
                continue
            if names[0] not in widenable or b[0][0] not in drawn:
                continue
            glyph = names[0]
            cols = np.nonzero(body.any(axis=0))[0]
            need = round((cols.max() - cols.min() + 1) / res) + CLEARANCE
            extra[glyph] = max(extra.get(glyph, 0), need)
    return extra
