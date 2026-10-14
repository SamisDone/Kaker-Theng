"""Conjunct parts made from glyphs the user already wrote.

Noto builds some conjuncts from parts (half forms, below-base forms, headline
pieces). Asking people to write fragments is unfriendly, so each part is
classified once, offline, from the base font alone:

  bar    a plain piece of মাত্রা: drawn at the user's measured মাত্রা height
         and stroke thickness.
  slice  part of a letter at the same scale (a half form is the top of the
         consonant before the hasanta; some parts are a clear match to part of
         a letter in the same conjunct or of a vowel sign): cut from the user's
         letter.
  body   a below-base form: the body (no মাত্রা) of the consonant after the
         hasanta, scaled down into the part's box.
  written  nothing fits: the user writes it in its own cell.

At font build time the plan is applied to the user's drawings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

import cv2
import numpy as np

from .basefont import base_shaper, headline_units
from .outline import Raster, contour_polygons, glyph_polygons, polys_bbox

HALANT = "্"
MATCH_RES = 0.08  # px per unit for planning
BUILD_RES = 0.25  # px per unit when deriving from the user's drawings
MAX_STRETCH = 1.35  # body: horizontal / vertical scale at most this far apart


@dataclass
class DerivePlan:
    glyph: str
    method: str  # "bar" | "slice" | "body" | "written"
    source: str | None
    score: float
    offset: tuple[float, float] | None  # slice: source coords = part coords + offset
    bbox: tuple[float, float, float, float]  # the part's box in the base font
    advance: int
    context: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _noto_raster(name: str) -> Raster | None:
    tt = base_shaper().tt
    g = tt["glyf"][name]
    if not g.numberOfContours:
        return None
    r = Raster(g.xMin, g.yMin, g.xMax, g.yMax, MATCH_RES, margin=20)
    r.fill(glyph_polygons(tt.getGlyphSet(), name))
    return r


def _ink_crop(img: np.ndarray) -> tuple[np.ndarray, int, int]:
    ys, xs = np.nonzero(img)
    return img[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], int(xs.min()), int(ys.min())


def _match(part: Raster, source: Raster) -> tuple[float, tuple[float, float]] | None:
    """Best placement of the part inside the source letter, at the same scale."""
    pc, pcx, pcy = _ink_crop(part.img)
    if source.img.shape[0] < pc.shape[0] or source.img.shape[1] < pc.shape[1]:
        return None
    scores = cv2.matchTemplate(source.img.astype(np.float32), pc.astype(np.float32), cv2.TM_CCORR)
    _, _, _, (x, y) = cv2.minMaxLoc(scores)
    win = source.img[y : y + pc.shape[0], x : x + pc.shape[1]] > 0
    iou = float((win & (pc > 0)).sum() / max((win | (pc > 0)).sum(), 1))
    # Same pixel in both: part coords + offset = source coords.
    px, py = part.to_units(pcx, pcy)
    sx, sy = source.to_units(x, y)
    return iou, (sx - px, sy - py)


@lru_cache(maxsize=1)
def gsub_variants() -> dict[str, set[str]]:
    """variant glyph -> glyphs it replaces through a single substitution
    (e.g. a ra-phala drawn differently under each consonant)."""
    out: dict[str, set[str]] = {}
    gsub = base_shaper().tt["GSUB"].table
    for lookup in gsub.LookupList.Lookup:
        for st in lookup.SubTable:
            if lookup.LookupType == 7:
                st = st.ExtSubTable
            if getattr(st, "LookupType", lookup.LookupType) == 1:
                for src, dst in st.mapping.items():
                    if src != dst:
                        out.setdefault(dst, set()).add(src)
    return out


def origins(part: str, context: str) -> set[str]:
    """The input letters (cmap glyphs) a part descends from in this cluster,
    followed through every step of the base font's GSUB trace. Each step is
    aligned by its common prefix and suffix; the changed middle inherits the
    origins of what it replaced."""
    states = [names for _, names in base_shaper().trace(context)]
    if not states:
        return set()
    lineage = [{n} for n in states[0]]
    for prev, nxt in zip(states, states[1:]):
        k = 0
        while k < min(len(prev), len(nxt)) and prev[k] == nxt[k]:
            k += 1
        e = 0
        while e < min(len(prev), len(nxt)) - k and prev[-1 - e] == nxt[-1 - e]:
            e += 1
        middle = set().union(*lineage[k : len(prev) - e]) if len(prev) - e > k else set()
        lineage = lineage[:k] + [set(middle) for _ in range(len(nxt) - e - k)] + lineage[len(prev) - e :]
        if part in nxt:
            break
    found = [lineage[i] for i, n in enumerate(states[-1] if part not in nxt else nxt) if n == part] if states else []
    return set().union(*found) if found else set()


def _consonants(names: set[str]) -> set[str]:
    cmap = base_shaper().tt.getBestCmap()
    cons = {cmap[cp] for cp in range(0x0995, 0x09BA) if cp in cmap}
    return names & cons


SIGN_MIN_SHARE = 0.6  # a part cut from a vowel sign must hold most of that sign


def _source_share(part: Raster, source: Raster, offset: tuple[float, float]) -> float:
    """Share of the source's ink inside the window the part was matched to."""
    pc, pcx, pcy = _ink_crop(part.img)
    px, py = part.to_units(pcx, pcy)
    col = int(round((px + offset[0] - source.x0) * source.res + source.m))
    row = int(round((source.y1 - (py + offset[1])) * source.res + source.m))
    win = source.img[max(row, 0) : row + pc.shape[0], max(col, 0) : col + pc.shape[1]]
    return float(win.sum() / max(source.img.sum(), 1))


def _has_headline_bar(r: Raster) -> bool:
    pc, _, _ = _ink_crop(r.img)
    return pc.mean() > 0.9 and pc.shape[0] < 110 * MATCH_RES


def plan_part(part: str, context: str, signs: list[str], user: set[str], others: set[str] = frozenset()) -> DerivePlan:
    """Try the ways to make `part` from what the user writes and check each
    on the base font itself (self_check). The first tier with a passing
    candidate wins: the conjunct's own letters (a half form from the first
    consonant, a below-base form from the last), then GSUB variants, then
    scaled bodies, then vowel signs that the part essentially is. Nothing
    passes: the user writes the part.

    `user`: glyphs the user writes. `others`: other parts (derived or
    written), usable as the source of a variant."""
    tt = base_shaper().tt
    g = tt["glyf"][part]
    bbox, advance = (g.xMin, g.yMin, g.xMax, g.yMax), tt["hmtx"][part][0]
    best_fail = None
    for tier in _candidates(part, context, signs, user, others):
        checked = [(self_check(c), c) for c in tier]
        passing = [(sc, c) for sc, c in checked if sc.passes]
        if passing:
            sc, plan = passing[0]
            plan.score = round(sc.overlap, 3)
            plan.reason += f" ({sc})"
            return plan
        for sc, c in checked:
            if best_fail is None or sc.overlap > best_fail[0].overlap:
                best_fail = (sc, c)
    if best_fail is None:
        return DerivePlan(part, "written", None, 0.0, None, bbox, advance, context, "no letter the user writes has this shape")
    sc, c = best_fail
    return DerivePlan(
        part, "written", None, round(sc.overlap, 3), None, bbox, advance, context,
        f"best try ({c.method} from {c.source or 'the মাত্রা'}) doesn't reproduce the base font's part ({sc})",
    )


def _candidates(part: str, context: str, signs: list[str], user: set[str], others: set[str]) -> list[list[DerivePlan]]:
    """Ways to derive a part, in tiers from most to least natural."""
    tt = base_shaper().tt
    cmap = tt.getBestCmap()
    g = tt["glyf"][part]
    bbox = (g.xMin, g.yMin, g.xMax, g.yMax)
    advance = tt["hmtx"][part][0]
    letters = [cmap[ord(ch)] for ch in context if ch != HALANT and ord(ch) in cmap]
    letters = list(dict.fromkeys(n for n in letters if n in user))
    # Follow the part back to the letters it came from. A part fused from two
    # consonants (the below-base ত্র in ন্ত্র) can't be cut from either one.
    origin = origins(part, context)
    fused = len(_consonants(origin)) >= 2
    if origin:
        letters = [n for n in letters if n in origin]

    def plan(method, source=None, offset=None, reason=""):
        return DerivePlan(part, method, source, 0.0, offset, bbox, advance, context, reason)

    pr = _noto_raster(part)
    if pr is None:
        return []
    variants = [plan("variant", src, reason=f"{src} fitted to its box (GSUB variant)") for src in sorted(gsub_variants().get(part, set()) & (set(user) | set(others)))]
    if fused:
        return [variants] if variants else []

    def slices(sources, why, whole_source=False):
        out = []
        for src in sources:
            sr = _noto_raster(src)
            m = _match(pr, sr)
            if not m:
                continue
            if whole_source and _source_share(pr, sr, m[1]) < SIGN_MIN_SHARE:
                continue  # the part is only a fragment of this sign
            out.append(plan("slice", src, m[1], f"{why} {src}"))
        return out

    # A half form (spacing, up to the মাত্রা) is the consonant before the
    # hasanta and nothing else; other parts may come from any of the cluster's
    # letters, below-base forms from the last one first.
    head_top = tt["glyf"][cmap[ord("ক")]].yMax
    if letters and advance > 0 and g.yMax >= head_top - 25 and not _has_headline_bar(pr):
        first = tt["glyf"][letters[0]]
        if (g.xMax - g.xMin) >= 0.5 * (first.xMax - first.xMin):  # a half form, not a stem
            return [slices(letters[:1], "half form: top of")]
    ordered = letters if advance > 0 else list(reversed(letters))
    tiers = [
        [plan("bar", reason="a bar at the user's মাত্রা")] if _has_headline_bar(pr) else [],
        slices(ordered, "cut from"),
        variants,
        [plan("body", src, reason=f"body of {src}, scaled") for src in ordered] if advance == 0 else [],
        slices([s for s in signs if s in user and s not in letters], "cut from the sign", whole_source=True),
    ]
    return [t for t in tiers if t]


# --- Checking a plan on the base font itself -------------------------------------
# If the "user" wrote exactly the base font's letters, a good derivation gives
# back the base font's own part. A low match means the method doesn't work for
# that part, whatever the handwriting.

MIN_OVERLAP = 0.65  # min(precision, recall) against the base font's part
MAX_BLOB = 0.10  # largest missing or extra piece, as a share of the part


@dataclass
class Check:
    overlap: float
    blob: float

    @property
    def passes(self) -> bool:
        return self.overlap >= MIN_OVERLAP and self.blob <= MAX_BLOB

    def __str__(self) -> str:
        return f"self-check overlap {self.overlap:.2f}, largest miss {self.blob:.0%}"


def _noto_drawing(name: str):
    from .vectorize import Contour, Drawing

    polys = glyph_polygons(base_shaper().tt.getGlyphSet(), name)
    contours = [Contour(tuple(p[0]), [("L", tuple(q)) for q in p[1:]]) for p in polys]
    return Drawing("noto", name, "base", None, contours, polys_bbox(polys) if polys else (0, 0, 0, 0))


def self_check(plan: "DerivePlan") -> "Check":
    """Compare the part derived from the base font's own letters with the base
    font's real part, in place."""
    if plan.method == "written":
        return Check(0.0, 1.0)
    head = float(headline_units())
    tt = base_shaper().tt
    ka = tt["glyf"][tt.getBestCmap()[ord("ক")]]
    matra = (head, 2 * (ka.yMax - head))
    if plan.method == "bar":
        contours = _bar(plan, matra)
    else:
        src = _noto_drawing(plan.source)
        if not src.contours:
            return Check(0.0, 1.0)
        contours = {"slice": _slice, "variant": _variant}.get(plan.method)
        contours = contours(plan, src) if contours else _body(plan, src, matra)
    if not contours:
        return Check(0.0, 1.0)
    x0, y0, x1, y1 = plan.bbox
    derived = Raster(x0 - 200, y0 - 200, x1 + 200, y1 + 200, 0.1)
    derived.fill(contour_polygons(contours))
    real = Raster(x0 - 200, y0 - 200, x1 + 200, y1 + 200, 0.1)
    real.fill(glyph_polygons(tt.getGlyphSet(), plan.glyph))
    a, b = derived.img > 0, real.img > 0
    return Check(overlap_score(a, b), largest_miss(a, b))


def largest_miss(a: np.ndarray, b: np.ndarray, slack: int = 2) -> float:
    """Largest connected piece of ink that one image has and the other lacks
    (after a little slack, and with thin slivers along edges opened away),
    as a share of b's ink. Catches a missing stroke that overlap hides."""
    k = np.ones((2 * slack + 1, 2 * slack + 1), np.uint8)
    o = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    worst = 0
    for x, y in ((b, a), (a, b)):
        diff = (x & ~(cv2.dilate(y.astype(np.uint8), k) > 0)).astype(np.uint8)
        diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, o)
        n, _, stats, _ = cv2.connectedComponentsWithStats(diff, connectivity=8)
        if n > 1:
            worst = max(worst, int(stats[1:, cv2.CC_STAT_AREA].max()))
    return worst / max(int(b.sum()), 1)


def overlap_score(a: np.ndarray, b: np.ndarray) -> float:
    """min(precision, recall) with one pixel of slack: extra ink and missing
    ink both count, so a missing piece can't hide behind a big overlap."""
    if not a.any() or not b.any():
        return 0.0
    a_near = cv2.dilate(a.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    b_near = cv2.dilate(b.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    precision = (a & b_near).sum() / a.sum()
    recall = (b & a_near).sum() / b.sum()
    return float(min(precision, recall))


# --- Applying the plan to the user's drawings -----------------------------------


def measure_matra(drawings: dict, matra_glyphs: set[str]) -> tuple[float, float]:
    """(centre y, thickness) of the user's মাত্রা, in font units."""
    centres, thicknesses = [], []
    for name, d in drawings.items():
        if name not in matra_glyphs or not d.contours:
            continue
        polys = contour_polygons(d.contours)
        x0, y0, x1, y1 = polys_bbox(polys)
        r = Raster(x0, y0, x1, y1, BUILD_RES, margin=0)
        r.fill(polys)
        cover = r.img.mean(axis=1)
        top_rows = int(r.h * 0.45)
        rows = [i for i in range(top_rows) if cover[i] >= 0.55]
        if not rows:
            continue
        band = [rows[0]]
        for i in rows[1:]:
            if i != band[-1] + 1:
                break
            band.append(i)
        top = r.to_units(0, band[0])[1]
        bottom = r.to_units(0, band[-1] + 1)[1]
        centres.append((top + bottom) / 2)
        thicknesses.append(top - bottom)
    if len(centres) < 3:
        return float(headline_units()), 60.0
    return float(np.median(centres)), float(np.median(thicknesses))


def _bar(plan: DerivePlan, matra: tuple[float, float]):
    from .vectorize import Contour

    centre, thick = matra
    x0, _, x1, _ = plan.bbox
    lo, hi = centre - thick / 2, centre + thick / 2
    return [Contour((x0, lo), [("L", (x0, hi)), ("L", (x1, hi)), ("L", (x1, lo))])]


def _slice(plan: DerivePlan, d):
    from .vectorize import trace_bitmap

    tt = base_shaper().tt
    sg = tt["glyf"][plan.source]
    polys = contour_polygons(d.contours)
    ux0, _, ux1, _ = polys_bbox(polys)
    kx = (sg.xMax - sg.xMin) / max(ux1 - ux0, 1)
    ox, oy = plan.offset
    # User letter -> base font's horizontal frame (y stays: one transform for
    # all glyphs) -> part coordinates.
    moved = [[(sg.xMin + (x - ux0) * kx - ox, y - oy) for x, y in p] for p in polys]
    x0, y0, x1, y1 = plan.bbox
    r = Raster(x0 - 10, y0 - 10, x1 + 10, y1 + 10, BUILD_RES)
    r.fill(moved)
    return trace_bitmap(r.img > 0, r.to_units)


def _body(plan: DerivePlan, d, matra: tuple[float, float]):
    from .vectorize import Contour, trace_bitmap

    polys = contour_polygons(d.contours)
    x0, y0, x1, y1 = polys_bbox(polys)
    r = Raster(x0, y0, x1, y1, BUILD_RES)
    r.fill(polys)
    centre, thick = matra
    cut_row = int(round((r.y1 - (centre - 0.75 * thick)) * r.res + r.m))
    r.img[: max(cut_row, 0)] = 0
    if not r.img.any():
        return []
    contours = trace_bitmap(r.img > 0, r.to_units)
    pts = [p for c in contours for seg in c.segments for p in seg[1:]] + [c.start for c in contours]
    bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
    bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)
    tx0, ty0, tx1, ty1 = plan.bbox
    # Fill the part's box: below-base forms are often flatter than the letter,
    # so allow up to MAX_STRETCH more scaling across than down.
    sy = (ty1 - ty0) / max(by1 - by0, 1)
    sx = float(np.clip((tx1 - tx0) / max(bx1 - bx0, 1), sy / MAX_STRETCH, sy * MAX_STRETCH))
    cx, tcx = (bx0 + bx1) / 2, (tx0 + tx1) / 2

    def f(p):
        return (tcx + (p[0] - cx) * sx, ty0 + (p[1] - by0) * sy)

    return [Contour(f(c.start), [(seg[0], *[f(p) for p in seg[1:]]) for seg in c.segments]) for c in contours]


def _variant(plan: DerivePlan, d):
    """The source glyph fitted into the variant's box."""
    from .vectorize import Contour, contours_bbox

    bx0, by0, bx1, by1 = contours_bbox(d.contours)
    tx0, ty0, tx1, ty1 = plan.bbox
    sx = (tx1 - tx0) / max(bx1 - bx0, 1)
    sy = (ty1 - ty0) / max(by1 - by0, 1)

    def f(p):
        return (tx0 + (p[0] - bx0) * sx, ty0 + (p[1] - by0) * sy)

    return [Contour(f(c.start), [(seg[0], *[f(p) for p in seg[1:]]) for seg in c.segments]) for c in d.contours]


def derive_parts(plans: list[DerivePlan], drawings: dict, matra: tuple[float, float]) -> list:
    """Drawings for every derivable part whose source exists. A variant's
    source may itself be derived, so keep going until nothing new appears."""
    from .vectorize import Drawing

    have = dict(drawings)
    out = []
    todo = [p for p in plans if p.method != "written" and p.glyph not in have]
    while todo:
        progress = False
        for plan in list(todo):
            if plan.method == "bar":
                contours = _bar(plan, matra)
            else:
                src = have.get(plan.source)
                if not src or not src.contours:
                    continue
                if plan.method == "slice":
                    contours = _slice(plan, src)
                elif plan.method == "variant":
                    contours = _variant(plan, src)
                else:
                    contours = _body(plan, src, matra)
            todo.remove(plan)
            progress = True
            if not contours:
                continue
            kind = "mark" if plan.advance == 0 else "base"
            d = Drawing(f"derived:{plan.method}", plan.glyph, kind, None, contours, (0, 0, 0, 0), positioned=True, advance=plan.advance)
            have[plan.glyph] = d
            out.append(d)
        if not progress:
            break
    return out
