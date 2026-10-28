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
from functools import lru_cache

import cv2
import numpy as np
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from . import config as C
from fontTools import subset

from .basefont import ALWAYS_KEEP_UNICODES, base_shaper, base_ttfont, headline_units, subset_font, subset_options
from .derive import derive_parts, measure_matra
from .glyphmap import HALANT, Cell, build_layout
from .guides import run_left_mm
from .outline import Raster, contour_polygons
from .partfit import refit, whole_ka_before_raphala
from .spacing import widen
from .vectorize import Drawing, contours_bbox

# Latin side bearings follow the writer's pen and each side's shape: a
# straight stem gets 0.4 of a stroke width, a curve or a point 0.2. Fitted to
# Patrick Hand's own (professional) spacing: mean error 12 units, against 31
# for a flat 60 on each side.
LATIN_SB_MIN = 0.20  # x stroke width, for a point or a curve
LATIN_SB_RANGE = 0.20  # added for a straight vertical side
LATIN_STRAIGHT_FROM = 0.2  # share of height at the edge where "straight" starts
LATIN_DEFAULT_STROKE = 60
BANGLA_RSB = -10  # headlines overlap a little so words join
BANGLA_OPEN_SIDE_BEARING = 30  # Bangla letters without a full মাত্রা, digits, ।
# A sign written next to a ghost keeps the gap the writer left, but its body
# (the ink below the মাত্রা) never reaches the neighbouring letter: at least
# this far from where the body of the writer's tightest letter can start. A
# finger often lands a sign on the faint ghost, and the writer's own letter
# isn't the ghost's shape.
SIGN_CLEARANCE = 20
# The দাঁড়ি (।) stands apart from the word it ends, like the base font's (its
# ink 184 units clear of the letter before): never on the previous letter.
DANDA = "danda-deva"
DANDA_LSB = 160
DANDA_RSB = 100
VENDOR_ID = "NONE"  # unregistered


COMMON_CLUSTERS = 200  # 99.5% of conjunct use on Bangla Wikipedia

# Which letters a font is made of: both languages in one font (the default),
# or one of them alone. A single-language font has its own family name, so
# installing it next to the combined one (or the other language's) doesn't
# replace it.
SCRIPTS = ("both", "bn", "en")
SCRIPT_SUFFIX = {"both": "", "bn": "Bangla", "en": "English"}
# English cells a Bangla-only font keeps when drawn: what Bangla text uses
# besides its own letters and the দাঁড়ি. Bangla has no comma, question mark
# or quotes of its own; Bangla text written with English digits needs them.
BANGLA_TEXT_LATIN = set(",?!'\"0123456789")
# Of the code points every font keeps, these only Bangla needs (the joiners,
# and the dotted circle a sign shows on when typed alone).
BANGLA_ONLY_KEEP = {0x200C, 0x200D, 0x25CC}


@lru_cache(maxsize=1)
def common_clusters() -> list[str]:
    from .coverage import cluster_counts

    counts = cluster_counts()
    return sorted(counts, key=lambda t: -counts[t])[:COMMON_CLUSTERS]


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


def postscript_name(family: str, suffix: str = "") -> str:
    """ASCII only, at most 63 characters. The suffix (Bangla, English) goes
    on after the name is cut to length, so the two never share one."""
    ascii_part = re.sub(r"[^A-Za-z0-9]", "", family)
    if not ascii_part:
        ascii_part = "KakerTheng" + hashlib.sha1(family.encode()).hexdigest()[:6]
    return f"{ascii_part[: 50 - len(suffix)]}{suffix}-Regular"


def script_family(family: str, script: str) -> str:
    """The name the font installs under: "<name>", "<name> Bangla" or "<name> English"."""
    return f"{family} {SCRIPT_SUFFIX[script]}".rstrip()


def drawings_for(drawings: list, script: str) -> list:
    """What goes into a font of this script: an English-only font has only
    English cells; a Bangla-only one has no English letters, only the
    punctuation and digits Bangla text uses (BANGLA_TEXT_LATIN)."""
    if script == "en":
        return [d for d in drawings if d.kind == "latin"]
    if script == "bn":
        return [d for d in drawings if d.kind != "latin" or (d.unicode is not None and chr(d.unicode) in BANGLA_TEXT_LATIN)]
    return list(drawings)


# The English punctuation a Bangla-only writer may draw: not English letters.
_BANGLA_TEXT_MARKS = set(",?!'\"")


def has_script(drawings: list, script: str) -> bool:
    """Whether a font of this language has anything of its own to hold: a
    Bangla letter, or an English one (a comma or quotes drawn for Bangla
    text don't make an English font)."""
    if script == "bn":
        return any(d.kind != "latin" for d in drawings)
    if script == "en":
        return any(d.kind == "latin" and (d.unicode is None or chr(d.unicode) not in _BANGLA_TEXT_MARKS) for d in drawings)
    return bool(drawings)


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


def _raster(d: Drawing, res: float = 0.2) -> Raster:
    x0, y0, x1, y1 = d.bbox
    r = Raster(x0, y0, x1, y1, res, margin=0)
    r.fill(contour_polygons(d.contours))
    return r


def stroke_width(drawings: list[Drawing]) -> float:
    """The writer's typical line width (font units): twice area over
    perimeter, median over their English letters."""
    widths = []
    for d in drawings:
        if d.kind != "latin" or not d.contours:
            continue
        r = _raster(d)
        contours, _ = cv2.findContours(r.img, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        perimeter = sum(cv2.arcLength(c, True) for c in contours)
        if perimeter > 0:
            widths.append(2 * r.img.sum() / perimeter / r.res)
    return float(np.median(widths)) if widths else LATIN_DEFAULT_STROKE


def _side_straightness(d: Drawing, stroke: float) -> tuple[float, float]:
    """Share of the glyph's height with ink within one stroke width of the
    left and of the right edge: ~1 for a stem (H, l), small for o, v, A."""
    r = _raster(d)
    band = max(1, round(stroke * r.res))
    rows = r.img.shape[0]
    left = r.img[:, :band].any(axis=1).sum() / rows
    right = r.img[:, -band:].any(axis=1).sum() / rows
    return float(left), float(right)


def latin_side_bearings(d: Drawing, stroke: float) -> tuple[float, float]:
    def sb(straight: float) -> float:
        f = np.clip((straight - LATIN_STRAIGHT_FROM) / 0.5, 0, 1)
        return stroke * (LATIN_SB_MIN + LATIN_SB_RANGE * f)

    left, right = _side_straightness(d, stroke)
    return sb(left), sb(right)


def _body_extent(d: Drawing, below: float) -> tuple[float, float] | None:
    """Left and right edge of the ink under y = `below` (the মাত্রা's
    underside), font units; None if there is none."""
    r = _raster(d)
    rows = int(round((r.y1 - below) * r.res + r.m))
    cols = np.nonzero(r.img[max(rows, 0) :].any(axis=0))[0]
    if not len(cols):
        return None
    return r.x0 + (cols[0] - r.m) / r.res, r.x0 + (cols[-1] + 1 - r.m) / r.res


def body_insets(drawings: list[Drawing], cells: dict[str, Cell], matra_glyphs: set[str], matra: tuple[float, float]) -> tuple[float, float]:
    """How far the body (below the মাত্রা) of the writer's letters with a
    মাত্রা stays in from the ink's left and right edges, at the tightest:
    signs beside a ghost are kept clear of the body, not of the মাত্রা."""
    left, right = [], []
    for d in drawings:
        cell = cells.get(d.glyph)
        if d.positioned or d.kind == "latin" or not cell or cell.ghost_glyphs or d.glyph not in matra_glyphs or not d.contours:
            continue
        body = _body_extent(d, matra[0] - matra[1] / 2)
        if body:
            left.append(body[0] - d.bbox[0])
            right.append(d.bbox[2] - body[1])
    return (max(0.0, min(left)), max(0.0, min(right))) if left else (0.0, 0.0)


def _placement(
    d: Drawing,
    cell: Cell | None,
    noto: TTFont,
    matra_glyphs: set[str],
    stroke: float = LATIN_DEFAULT_STROKE,
    matra: tuple[float, float] | None = None,
    insets: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float, int]:
    """(dx, dy, advance) that put a drawing into its final glyph coordinates."""
    if d.positioned:
        return 0, 0, d.advance or 0
    x_min, y_min, x_max, y_max = d.bbox
    width = x_max - x_min
    if d.kind == "latin":
        lsb, rsb = latin_side_bearings(d, stroke)
        return lsb - x_min, 0, round(width + lsb + rsb)
    ng = noto["glyf"][d.glyph]
    if d.glyph == DANDA:
        return DANDA_LSB - x_min, 0, round(width + DANDA_LSB + DANDA_RSB)
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
        centre, thick = matra or (headline_units(), 60.0)
        body = _body_extent(d, centre - thick / 2)
        if cell.target_x < min(g.x for g in cell.ghost_glyphs):
            # Before the letter (ি ে ৈ): the next letter's ink starts where the
            # ghost's ink started. ি's hook reaches over it, as written.
            advance = ghost_left - x_min
            if advance <= 0.25 * width:
                # Not written before the ghost after all: plain spacing.
                return -x_min, -cell.target_y, round(width + rsb)
            if body:
                # The next letter's body starts at least insets[0] past its
                # origin (its মাত্রা may reach further left).
                advance = max(advance, body[1] - x_min + SIGN_CLEARANCE - insets[0])
            return -x_min, -cell.target_y, round(advance)
        # After the letter (া ী ৗ ং ঃ ্য): the previous letter's ink ends
        # -BANGLA_RSB past our origin, so put the origin there.
        dx = -(ghost_right + BANGLA_RSB)
        if body:
            # ...and the body starts clear of it. ী's hook may still reach back
            # over the previous মাত্রা, as written.
            dx = max(dx, -BANGLA_RSB - insets[1] + SIGN_CLEARANCE - body[0])
        return dx, -cell.target_y, max(0, round(x_max + dx + rsb))
    if d.glyph in matra_glyphs:
        # Letters with a মাত্রা: no gap on the left, a slight overlap on the
        # right, so headlines join inside a word.
        return -x_min, 0, round(width + BANGLA_RSB)
    return BANGLA_OPEN_SIDE_BEARING - x_min, 0, round(width + 2 * BANGLA_OPEN_SIDE_BEARING)


# An anchor in the lowest share of a letter's height is where a mark goes
# under it (ু ূ ৃ, ra-phala, হসন্ত): it follows the bottom of the writer's
# letter, which may reach lower or stay higher than the base font's.
BOTTOM_ANCHOR = 0.25


def _anchor_maps(noto: TTFont, boxes: dict[str, tuple]) -> dict[str, tuple[float, ...]]:
    """Per glyph, from base-font box to user box: x -> new_x0 + (x - old_x0)
    * k; a bottom anchor (y below old_bottom_line) moves by dy_bottom."""
    maps = {}
    glyf = noto["glyf"]
    for name, (x0, y0, x1, _) in boxes.items():
        g = glyf[name] if name in glyf.glyphs else None
        if g is None or not g.numberOfContours or g.xMax <= g.xMin or x1 <= x0:
            continue
        maps[name] = (g.xMin, x0, (x1 - x0) / (g.xMax - g.xMin), g.yMin + BOTTOM_ANCHOR * (g.yMax - g.yMin), y0 - g.yMin)
    return maps


def _remap_anchors(font: TTFont, maps: dict[str, tuple[float, ...]]):
    """Move every GPOS anchor on a replaced glyph along with its new outline.

    The base font's anchors fit its own letter widths; the user's letters are
    narrower or wider. Anchors that point at outline points (format 2) are
    turned into plain coordinates, since those points no longer exist. A
    letter's bottom anchors also move with its bottom (BOTTOM_ANCHOR)."""
    if "GPOS" not in font:
        return

    def fix(anchor, glyph, base=False):
        if anchor is None or glyph not in maps:
            return
        old_x0, new_x0, k, bottom_line, dy_bottom = maps[glyph]
        anchor.XCoordinate = round(new_x0 + (anchor.XCoordinate - old_x0) * k)
        if base and anchor.YCoordinate < bottom_line:
            anchor.YCoordinate = round(anchor.YCoordinate + dy_bottom)
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
                        fix(a, g, base=True)
            elif t == 6:
                for g, rec in zip(st.Mark2Coverage.glyphs, st.Mark2Array.Mark2Record):
                    for a in rec.Mark2Anchor:
                        fix(a, g)
            elif t == 5:
                for g, lig in zip(st.LigatureCoverage.glyphs, st.LigatureArray.LigatureAttach):
                    for comp in lig.ComponentRecord:
                        for a in comp.LigatureAnchor:
                            fix(a, g, base=True)


def _set_names(font: TTFont, family: str, script: str = "both"):
    """Names for the family as the user called it, plus the script's suffix
    in every name an app or the system tells fonts apart by (1, 3, 4, 6, 16)."""
    ps = postscript_name(family, SCRIPT_SUFFIX[script])
    family = script_family(family, script)
    name = font["name"]
    original_copyright = name.getDebugName(0) or ""
    # Keep copyright (0), licence (13, 14) and feature names (256+, while the
    # layout tables that point at them are there). Drop the base font's
    # trademark (7), maker/designer/URLs (8-12): no longer theirs.
    layout = "GSUB" in font or "GPOS" in font
    name.names = [n for n in name.names if n.nameID in (0, 13, 14) or (layout and n.nameID >= 256)]
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


def build_font(drawings: list[Drawing], family: str, script: str = "both") -> BuiltFont:
    """The font from these drawings. `script` "bn" or "en" makes a font of
    that language alone (drawings_for), with its own family name. An
    English-only font is a plain Latin font: no Bengali glyph, and none of
    the base font's layout tables, which only ever shape Bangla."""
    if script not in SCRIPTS:
        raise ValueError(f"script must be one of {SCRIPTS}")
    family = clean_family_name(family)
    drawings = drawings_for(drawings, script)
    layout = build_layout()
    noto = base_shaper().tt  # untouched copy, for the base font's boxes and metrics
    cells = {c.glyph: c for c in layout.cells}
    matra_glyphs = set(layout.matra_glyphs)

    # Parts the user didn't write, made from letters they did. With no Bangla
    # letter drawn there is nothing to make them from (only মাত্রা pieces at
    # the base font's height would come out).
    by_glyph = {d.glyph: d for d in drawings if d.contours}
    matra = measure_matra(by_glyph, matra_glyphs)
    derived = []
    if any(d.kind != "latin" for d in by_glyph.values()):
        derived = refit([d for d in derive_parts(layout.plans(), by_glyph, matra) if d.glyph not in by_glyph], layout.plans(), by_glyph)
    drawings = [d for d in drawings if d.contours] + derived
    stroke = stroke_width(drawings)
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

    insets = body_insets(drawings, cells, matra_glyphs, matra)
    boxes = {}
    for d in drawings:
        dx, dy, advance = _placement(d, cells.get(d.glyph), noto, matra_glyphs, stroke, matra, insets)
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
    if "t_ra-beng" not in written:
        whole_ka_before_raphala(font)
    cmap = font.getBestCmap()
    unicodes = sorted(cp for cp, g in cmap.items() if g in written)
    if script == "en":
        keep = [cp for cp in ALWAYS_KEEP_UNICODES if cp not in BANGLA_ONLY_KEEP]
        sub = subset.Subsetter(subset_options())
        sub.populate(glyphs=sorted(written | {".notdef"}), unicodes=unicodes + keep)
        sub.subset(font)
        for tag in ("GSUB", "GPOS", "GDEF"):
            if tag in font:
                del font[tag]
    else:
        keep = ALWAYS_KEEP_UNICODES
        subset_font(font, written, unicodes)
    _set_names(font, family, script)
    _fix_vertical_metrics(font)
    font["OS/2"].recalcUnicodeRanges(font)

    ttf = io.BytesIO()
    font.save(ttf)
    # Conjunct parts cut from the writer's letters keep the base font's
    # advance, which interlocks with the base font's letters, not theirs; a
    # visible হসন্ত hangs into the next letter. Shape the common clusters,
    # and widen what runs into its neighbour.
    widenable = {d.glyph for d in derived if d.kind != "mark"}
    halant = font.getBestCmap().get(ord(HALANT))
    drawn_glyphs = {d.glyph for d in drawings if not d.positioned}
    extra = widen(ttf.getvalue(), common_clusters(), matra, widenable, halant, drawn_glyphs) if script != "en" else {}
    if extra:
        widths = {g: font["hmtx"][g] for g in extra}
        for g, units in extra.items():
            font["hmtx"][g] = (widths[g][0] + units, widths[g][1])
        ttf = io.BytesIO()
        font.save(ttf)
        # Widening that didn't part the two (a mark moves along with the next
        # letter) is undone: it would only leave a gap.
        stuck = widen(ttf.getvalue(), common_clusters(), matra, widenable, halant, drawn_glyphs)
        if stuck:
            for g in stuck:
                font["hmtx"][g] = widths.get(g, font["hmtx"][g])
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
        script_family(family, script),
        kept.getGlyphOrder(),
        sorted(set(unicodes) | set(keep) & set(kept.getBestCmap())),
        [d.glyph for d in derived],
        matra,
    )
