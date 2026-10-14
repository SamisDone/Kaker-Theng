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

from . import config as C
from .basefont import ALWAYS_KEEP_UNICODES, base_shaper, base_ttfont, subset_font
from .derive import derive_parts, measure_matra
from .glyphmap import Cell, build_layout
from .guides import run_left_mm
from .vectorize import Drawing, contours_bbox

LATIN_SIDE_BEARING = 60
BANGLA_RSB = -10  # headlines overlap a little so words join
BANGLA_OPEN_SIDE_BEARING = 30  # Bangla letters without a full মাত্রা, digits, ।
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
    derived: list[str]  # parts made from the user's letters
    matra: tuple[float, float]  # measured মাত্রা centre and thickness


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


def _placement(d: Drawing, cell: Cell | None, noto: TTFont, matra_glyphs: set[str]) -> tuple[float, float, int]:
    """(dx, dy, advance) that put a drawing into its final glyph coordinates."""
    if d.positioned:
        return 0, 0, d.advance or 0
    x_min, y_min, x_max, y_max = d.bbox
    width = x_max - x_min
    if d.kind == "latin":
        return LATIN_SIDE_BEARING - x_min, 0, round(width + 2 * LATIN_SIDE_BEARING)
    ng = noto["glyf"][d.glyph]
    if d.kind == "mark":
        # Zero-advance marks: centre on the base font's mark, keep the scale.
        # GPOS then attaches it exactly where the base font would.
        return (ng.xMin + ng.xMax) / 2 - (x_min + x_max) / 2, (ng.yMin + ng.yMax) / 2 - (y_min + y_max) / 2, 0
    if cell is not None and cell.ghost_glyphs:
        # Written beside a ghost (া ি ে ং ্য ...). Keep the gap the user left
        # between their sign and the ghost's ink, and apply it to their own
        # letters, which are spaced LSB 0 / RSB BANGLA_RSB.
        glyf = noto["glyf"]
        run_left = (run_left_mm(cell) - cell.box_mm()[0]) / C.MM_PER_UNIT
        inked = [g for g in cell.ghost_glyphs if glyf[g.name].numberOfContours]
        ghost_left = run_left + min(g.x + glyf[g.name].xMin for g in inked)
        ghost_right = run_left + max(g.x + glyf[g.name].xMax for g in inked)
        rsb = BANGLA_RSB if d.glyph in matra_glyphs else BANGLA_OPEN_SIDE_BEARING
        if cell.target_x < min(g.x for g in cell.ghost_glyphs):
            # Before the letter (ি ে ৈ): the next letter's ink starts where the
            # ghost's ink started. ি's hook reaches over it, as written.
            advance = ghost_left - x_min
            if advance <= 0.25 * width:
                # Not written before the ghost after all: plain spacing.
                return -x_min, -cell.target_y, round(width + rsb)
            return -x_min, -cell.target_y, round(advance)
        # After the letter (া ী ৗ ং ঃ ্য): the previous letter's ink ends
        # -BANGLA_RSB past our origin, so put the origin there.
        dx = -(ghost_right + BANGLA_RSB)
        return dx, -cell.target_y, max(0, round(x_max + dx + rsb))
    if d.glyph in matra_glyphs:
        # Letters with a মাত্রা: no gap on the left, a slight overlap on the
        # right, so headlines join inside a word.
        return -x_min, 0, round(width + BANGLA_RSB)
    return BANGLA_OPEN_SIDE_BEARING - x_min, 0, round(width + 2 * BANGLA_OPEN_SIDE_BEARING)


def _anchor_maps(noto: TTFont, boxes: dict[str, tuple]) -> dict[str, tuple[float, float, float]]:
    """Per glyph: x -> new_x0 + (x - old_x0) * k, from base-font box to user box."""
    maps = {}
    glyf = noto["glyf"]
    for name, (x0, _, x1, _) in boxes.items():
        g = glyf[name] if name in glyf.glyphs else None
        if g is None or not g.numberOfContours or g.xMax <= g.xMin or x1 <= x0:
            continue
        maps[name] = (g.xMin, x0, (x1 - x0) / (g.xMax - g.xMin))
    return maps


def _remap_anchors(font: TTFont, maps: dict[str, tuple[float, float, float]]):
    """Move every GPOS anchor on a replaced glyph along with its new outline.

    The base font's anchors fit its own letter widths; the user's letters are
    narrower or wider. Anchors that point at outline points (format 2) are
    turned into plain coordinates, since those points no longer exist."""
    if "GPOS" not in font:
        return

    def fix(anchor, glyph):
        if anchor is None or glyph not in maps:
            return
        old_x0, new_x0, k = maps[glyph]
        anchor.XCoordinate = round(new_x0 + (anchor.XCoordinate - old_x0) * k)
        if anchor.Format == 2:
            anchor.Format = 1
            del anchor.AnchorPoint

    for lookup in font["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            if lookup.LookupType == 9:
                st = st.ExtSubTable
            t = st.LookupType
            if t in (4, 5, 6):
                cov1 = st.MarkCoverage if t in (4, 5) else st.Mark1Coverage
                arr1 = st.MarkArray if t in (4, 5) else st.Mark1Array
                for g, rec in zip(cov1.glyphs, arr1.MarkRecord):
                    fix(rec.MarkAnchor, g)
            if t == 4:
                for g, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                    for a in rec.BaseAnchor:
                        fix(a, g)
            elif t == 6:
                for g, rec in zip(st.Mark2Coverage.glyphs, st.Mark2Array.Mark2Record):
                    for a in rec.Mark2Anchor:
                        fix(a, g)
            elif t == 5:
                for g, lig in zip(st.LigatureCoverage.glyphs, st.LigatureArray.LigatureAttach):
                    for comp in lig.ComponentRecord:
                        for a in comp.LigatureAnchor:
                            fix(a, g)


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
    layout = build_layout()
    noto = base_shaper().tt  # untouched copy, for the base font's boxes and metrics
    cells = {c.glyph: c for c in layout.cells}
    matra_glyphs = set(layout.matra_glyphs)

    # Parts the user didn't write, made from letters they did.
    by_glyph = {d.glyph: d for d in drawings if d.contours}
    matra = measure_matra(by_glyph, matra_glyphs)
    derived = [d for d in derive_parts(layout.plans(), by_glyph, matra) if d.glyph not in by_glyph]
    drawings = [d for d in drawings if d.contours] + derived
    for d in derived:
        d.bbox = contours_bbox(d.contours)

    font = base_ttfont()
    glyf, hmtx = font["glyf"], font["hmtx"]
    cmap_tables = [t for t in font["cmap"].tables if t.isUnicode()]

    order = font.getGlyphOrder()
    new = [d.glyph for d in drawings if d.glyph not in order]
    if new:
        order = order + new
        font.setGlyphOrder(order)
        glyf.glyphOrder = order

    boxes = {}
    for d in drawings:
        dx, dy, advance = _placement(d, cells.get(d.glyph), noto, matra_glyphs)
        glyph = _ttglyph(d, dx, dy)
        glyph.recalcBounds(glyf)
        glyf[d.glyph] = glyph
        hmtx[d.glyph] = (max(0, advance), glyph.xMin if glyph.numberOfContours else 0)
        if glyph.numberOfContours and not d.positioned and d.kind != "latin":
            boxes[d.glyph] = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
        if d.unicode is not None:
            for t in cmap_tables:
                if d.unicode <= 0xFFFF or t.format in (12, 13):
                    t.cmap[d.unicode] = d.glyph

    _remap_anchors(font, _anchor_maps(noto, boxes))

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
        [d.glyph for d in derived],
        matra,
    )
