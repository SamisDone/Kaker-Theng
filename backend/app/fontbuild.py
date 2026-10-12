"""Turn the user's drawings into a font built on the base font's tables.

GSUB/GPOS stay as they are; only outlines and advance widths change. Latin
glyphs are new (the base font has none). Everything the user didn't write is
subset away, which also prunes the GSUB rules that would produce it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from .basefont import ALWAYS_KEEP_UNICODES, base_ttfont, subset_font
from .vectorize import Drawing

LATIN_SIDE_BEARING = 60
BANGLA_RSB = -10  # headlines overlap a little so words join
VENDOR_ID = "NONE"  # unregistered


class FontNameError(ValueError):
    def __init__(self, en: str, bn: str):
        super().__init__(en)
        self.en, self.bn = en, bn


def clean_family_name(raw: str) -> str:
    name = unicodedata.normalize("NFC", " ".join((raw or "").split()))
    if not name:
        raise FontNameError("Give your font a name.", "ফন্টের একটা নাম দিন।")
    if len(name) > 40:
        raise FontNameError("Keep the name under 40 characters.", "নামটা ৪০ অক্ষরের মধ্যে রাখুন।")
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise FontNameError("The name has characters a font name can't use.", "নামে এমন চিহ্ন আছে যা ফন্টের নামে চলে না।")
    if "noto" in name.casefold():
        # "Noto" is a Google trademark (name table ID 7 of the base font).
        raise FontNameError(
            "The name can't contain “Noto”: it's a trademark of the base font's owner.",
            "নামে “Noto” রাখা যাবে না, ওটা মূল ফন্টের ট্রেডমার্ক।",
        )
    return name


def postscript_name(family: str) -> str:
    ascii_part = re.sub(r"[^A-Za-z0-9]", "", family)
    if not ascii_part:
        ascii_part = "KakerTheng" + hashlib.sha1(family.encode()).hexdigest()[:6]
    return f"{ascii_part[:50]}-Regular"


@dataclass
class BuiltFont:
    ttf: bytes
    woff2: bytes
    family: str
    glyphs: list[str]
    unicodes: list[int]


def _ttglyph(drawing: Drawing, dx: float, dy: float = 0):
    pen = TTGlyphPen(None)
    q = Cu2QuPen(pen, max_err=1.0, all_quadratic=True)
    for c in drawing.contours:
        q.moveTo((c.start[0] + dx, c.start[1] + dy))
        for seg in c.segments:
            pts = [(p[0] + dx, p[1] + dy) for p in seg[1:]]
            if seg[0] == "L":
                q.lineTo(pts[0])
            else:
                q.curveTo(*pts)
        q.closePath()
    glyph = pen.glyph()
    glyph.coordinates.toInt()
    return glyph


def _spacing(d: Drawing) -> tuple[float, int]:
    """(x shift to apply to the drawing, advance width)."""
    x_min, _, x_max, _ = d.bbox
    width = x_max - x_min
    if d.kind == "latin":
        return LATIN_SIDE_BEARING - x_min, round(width + 2 * LATIN_SIDE_BEARING)
    if d.kind == "mark":
        return -(x_min + x_max) / 2, 0
    return -x_min, round(width + BANGLA_RSB)


def _set_names(font: TTFont, family: str):
    ps = postscript_name(family)
    name = font["name"]
    original_copyright = name.getDebugName(0) or ""
    # Keep copyright (0), licence (13, 14) and feature names (256+). Drop the
    # base font's trademark (7), maker/designer/URLs (8-12): no longer theirs.
    name.names = [n for n in name.names if n.nameID in (0, 13, 14) or n.nameID >= 256]
    year = dt.date.today().year
    values = {
        0: f"{original_copyright}. Handwriting outlines {year}, made with Kaker Theng.",
        1: family,
        2: "Regular",
        3: f"1.000;{VENDOR_ID};{ps}",
        4: family,
        5: "Version 1.000",
        6: ps,
        16: family,
        17: "Regular",
    }
    for nid, text in values.items():
        name.removeNames(nameID=nid)
        name.setName(text, nid, 3, 1, 0x409)
    font["OS/2"].achVendID = VENDOR_ID
    font["head"].fontRevision = 1.0
    now = int((dt.datetime.now(dt.timezone.utc) - dt.datetime(1904, 1, 1, tzinfo=dt.timezone.utc)).total_seconds())
    font["head"].created = font["head"].modified = now


def _fix_vertical_metrics(font: TTFont):
    glyf = font["glyf"]
    y_max, y_min = 0, 0
    for g in font.getGlyphOrder():
        glyph = glyf[g]
        if glyph.numberOfContours:
            glyph.recalcBounds(glyf)
            y_max, y_min = max(y_max, glyph.yMax), min(y_min, glyph.yMin)
    os2, hhea = font["OS/2"], font["hhea"]
    os2.usWinAscent = max(os2.usWinAscent, y_max)
    os2.usWinDescent = max(os2.usWinDescent, -y_min)
    hhea.ascent = max(hhea.ascent, y_max)
    hhea.descent = min(hhea.descent, y_min)


def build_font(drawings: list[Drawing], family: str) -> BuiltFont:
    family = clean_family_name(family)
    font = base_ttfont()
    glyf, hmtx = font["glyf"], font["hmtx"]
    cmap_tables = [t for t in font["cmap"].tables if t.isUnicode()]

    order = font.getGlyphOrder()
    new = [d.glyph for d in drawings if d.glyph not in order]
    if new:
        order = order + new
        font.setGlyphOrder(order)
        glyf.glyphOrder = order

    for d in drawings:
        dx, advance = _spacing(d)
        glyph = _ttglyph(d, dx)
        glyph.recalcBounds(glyf)
        glyf[d.glyph] = glyph
        hmtx[d.glyph] = (advance, glyph.xMin if glyph.numberOfContours else 0)
        if d.unicode is not None:
            for t in cmap_tables:
                if d.unicode <= 0xFFFF or t.format in (12, 13):
                    t.cmap[d.unicode] = d.glyph

    written = {d.glyph for d in drawings}
    cmap = font.getBestCmap()
    unicodes = sorted(cp for cp, g in cmap.items() if g in written)
    subset_font(font, written, unicodes)
    _set_names(font, family)
    _fix_vertical_metrics(font)
    font["OS/2"].recalcUnicodeRanges(font)

    ttf = io.BytesIO()
    font.save(ttf)
    woff2_font = TTFont(io.BytesIO(ttf.getvalue()))
    woff2_font.flavor = "woff2"
    woff2 = io.BytesIO()
    woff2_font.save(woff2)
    kept = TTFont(io.BytesIO(ttf.getvalue()))
    return BuiltFont(
        ttf.getvalue(),
        woff2.getvalue(),
        family,
        kept.getGlyphOrder(),
        sorted(set(unicodes) | set(ALWAYS_KEEP_UNICODES) & set(kept.getBestCmap())),
    )
