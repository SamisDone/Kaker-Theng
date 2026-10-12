"""Decide, by shaping, which glyph every template cell fills.

No glyph names are hardcoded. For Bangla:

1. Shape each cell with the base font, with presentation features off. That
   gives the basic Indic forms (plain matras, generic phala, reph, ligatures
   from akhn/cjct...). These are candidate targets.
2. Subset the base font down to the candidates and shape every cell again.
   Outlines don't affect shaping, so this is exactly how the user's finished
   font will behave. Context variants (ে.init, ি length variants, phala
   alternates) are gone, and their rules with them.
3. A cell's target is the glyph that remains once the ghost's glyphs are
   taken away. A conjunct is kept only if it comes out as one glyph.
4. Conjuncts that Noto assembles from parts (PART_CONJUNCTS): the parts are
   found by tracing the GSUB lookups. Visible parts are added first; if a
   conjunct still doesn't form, the intermediate glyphs its rule chain passes
   through are added, then pruned again if not needed. Each part gets a cell
   in a context where it is visible, the rest of the run printed as ghost.
5. Repeat until the glyph set stops changing.

Latin glyphs don't exist in the base font; they get standard AGL names and
are added to the font later.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from fontTools.agl import UV2AGL

from . import config as C
from .basefont import PRESENTATION_FEATURES, ShapedGlyph, base_shaper, headline_units, simulated_shaper
from .charset import CONSONANTS_FOR_CONTEXT, PAGES, PART_CONJUNCTS, CellSpec

SPECIAL_GLYPH_UNICODES = [0x20, 0xA0, 0x200C, 0x200D, 0x25CC]
logger = logging.getLogger(__name__)
HALANT = "্"


@dataclass
class GhostGlyph:
    name: str
    x: int  # pen position in font units, relative to the start of the run
    y: int


@dataclass
class Cell:
    page: int
    index: int
    row: int
    col: int
    text: str
    ghost: str | None
    group: str
    glyph: str  # glyph this cell's handwriting replaces
    kind: str  # "latin" | "base" | "mark"
    unicode: int | None = None  # for Latin glyphs we add ourselves
    ghost_glyphs: list[GhostGlyph] = field(default_factory=list)
    target_x: int = 0  # pen origin of the written glyph within the run
    target_y: int = 0
    run_advance: int = 0

    @property
    def id(self) -> str:
        return f"p{self.page}-{self.index:02d}"

    def box_mm(self) -> tuple[float, float, float, float]:
        """x, y (top-left), w, h on the page in mm."""
        return (C.GRID_X_MM + self.col * C.CELL_MM, C.GRID_Y_MM + self.row * C.CELL_MM, C.CELL_MM, C.CELL_MM)


@dataclass
class Layout:
    cells: list[Cell]
    excluded: list[dict]
    log: list[dict]
    parts: list[dict]
    derived: list[dict] = field(default_factory=list)  # derive.DerivePlan dicts
    matra_glyphs: list[str] = field(default_factory=list)  # base-font glyphs with a মাত্রা

    def page(self, n: int) -> list[Cell]:
        return [c for c in self.cells if c.page == n]

    def bangla_glyphs(self) -> set[str]:
        """Every Bangla glyph a complete font has: written or derived."""
        written = {c.glyph for c in self.cells if c.kind != "latin"}
        return written | {d["glyph"] for d in self.derived if d["method"] != "written"}

    def plans(self):
        from .derive import DerivePlan

        return [DerivePlan(**{**d, "offset": tuple(d["offset"]) if d["offset"] else None, "bbox": tuple(d["bbox"])}) for d in self.derived]


def _diff(names: list[str], remove: list[str]) -> list[int]:
    """Indices of `names` left after removing each of `remove` once."""
    left = Counter(remove)
    out = []
    for i, n in enumerate(names):
        if left[n] > 0:
            left[n] -= 1
        else:
            out.append(i)
    return out


def _specials() -> set[str]:
    cmap = base_shaper().tt.getBestCmap()
    return {cmap[cp] for cp in SPECIAL_GLYPH_UNICODES if cp in cmap}


def _candidates(specs: list[CellSpec]) -> set[str]:
    shaper = base_shaper()
    off = {f: False for f in PRESENTATION_FEATURES}
    glyphs = _specials()
    for spec in specs:
        if spec.ghost is None and len(spec.text) == 1:
            glyphs.update(shaper.names(spec.text))
            continue
        basic = shaper.names(spec.text, off)
        if spec.ghost is None:
            if len(basic) == 1:
                glyphs.add(basic[0])
        else:
            ghost = shaper.names(spec.ghost, off)
            glyphs.update(ghost)
            glyphs.update(basic[i] for i in _diff(basic, ghost))
    return glyphs


def _resolve(spec: CellSpec, sim) -> tuple[int | None, str, list[ShapedGlyph]]:
    """(index of the written glyph in the run, reason, run) in the simulated font."""
    run = sim.shape(spec.text)
    names = [g.name for g in run]
    if ".notdef" in names:
        return None, "shapes to .notdef", run
    if spec.ghost is None:
        if len(run) == 1:
            return 0, "single glyph", run
        return None, f"not one glyph in the final font ({len(run)} glyphs)", run
    ghost = sim.names(spec.ghost)
    rest = _diff(names, ghost)
    if len(rest) == 1 and len(names) == len(ghost) + 1:
        return rest[0], "ghost + one written glyph", run
    return None, f"ghost does not survive as-is ({names} vs ghost {ghost})", run


def _forms_like_base(sim, text: str) -> bool:
    return sim.names(text) == base_shaper().names(text)


def _discover_parts(user: set[str]) -> list[str]:
    """Part glyphs needed so every PART_CONJUNCT shapes as in the base font."""
    base = base_shaper()
    parts: list[str] = []
    for text in PART_CONJUNCTS:
        for g in base.names(text):
            if g not in user and g not in parts:
                parts.append(g)
    sim = simulated_shaper(user | set(parts))
    for text in PART_CONJUNCTS:
        if _forms_like_base(sim, text):
            continue
        extra = [g for _, names in base.trace(text) for g in names if g not in user and g not in parts]
        extra = list(dict.fromkeys(extra))
        parts += extra
        sim = simulated_shaper(user | set(parts))
        # Prune intermediates this conjunct turned out not to need.
        for g in extra:
            trial = user | (set(parts) - {g})
            if _forms_like_base(simulated_shaper(trial), text):
                parts.remove(g)
        sim = simulated_shaper(user | set(parts))
    return parts


def _part_context(part: str, glyphs: set[str], sim) -> tuple[str, list[ShapedGlyph], int] | None:
    """A short text where `part` is visible in the final font."""
    texts = list(PART_CONJUNCTS)
    texts += [a + HALANT + b for a in CONSONANTS_FOR_CONTEXT for b in CONSONANTS_FOR_CONTEXT]
    texts += [a + HALANT + "‍" for a in CONSONANTS_FOR_CONTEXT]
    best = None
    for rank, text in enumerate(texts):
        run = sim.shape(text)
        names = [g.name for g in run]
        if names.count(part) != 1 or ".notdef" in names or any(n not in glyphs for n in names):
            continue
        visible_hasanta = base_shaper().tt.getBestCmap()[ord(HALANT)] in names
        score = (text not in PART_CONJUNCTS, visible_hasanta, len(names), rank)
        if best is None or score < best[0]:
            best = (score, text, run, names.index(part))
    return best[1:] if best else None


def _make_cell(page, text, ghost, group, run, target_idx, kind) -> Cell:
    cell = Cell(page, 0, 0, 0, text, ghost, group, run[target_idx].name, kind)
    x = 0
    for i, g in enumerate(run):
        gx, gy = x + g.x_offset, g.y_offset
        if i == target_idx:
            cell.target_x, cell.target_y = gx, gy
        else:
            cell.ghost_glyphs.append(GhostGlyph(g.name, gx, gy))
        x += g.x_advance
    cell.run_advance = x
    return cell


def _place(groups: list[str]) -> list[tuple[int, int]]:
    """Row/col per cell. Each group starts a new row when everything fits."""
    runs: list[list[int]] = []
    for i, g in enumerate(groups):
        if not runs or groups[runs[-1][0]] != g:
            runs.append([])
        runs[-1].append(i)
    rows_needed = sum(-(-len(r) // C.COLS) for r in runs)
    pos: list[tuple[int, int]] = [(0, 0)] * len(groups)
    if rows_needed <= C.ROWS:
        row = 0
        for r in runs:
            for k, i in enumerate(r):
                pos[i] = (row + k // C.COLS, k % C.COLS)
            row += -(-len(r) // C.COLS)
    else:
        pos = [(i // C.COLS, i % C.COLS) for i in range(len(groups))]
    if pos and max(r for r, _ in pos) >= C.ROWS:
        raise ValueError(f"too many cells for one page ({len(groups)})")
    return pos


def compute_layout() -> Layout:
    """The full shaping analysis. Slow (many simulated fonts): run offline by
    scripts/make_template.py, which caches the result in assets/layout.json."""
    shaper = base_shaper()
    noto_hmtx = shaper.tt["hmtx"]
    bangla_specs = [s for p in (2, 3) for s in PAGES[p]]

    glyphs = _candidates(bangla_specs)
    parts: list[str] = []
    for _ in range(6):
        sim = simulated_shaper(glyphs)
        resolved = {}
        claimed: dict[str, str] = {}
        for spec in bangla_specs:
            idx, reason, run = _resolve(spec, sim)
            if idx is not None and run[idx].name in claimed:
                reason, idx = f"same glyph as cell {claimed[run[idx].name]}", None
            if idx is not None:
                claimed[run[idx].name] = spec.text
            resolved[spec] = (idx, reason, run)
        user = set(claimed) | _specials()
        parts = _discover_parts(user)
        new = user | set(parts)
        if new == glyphs:
            break
        glyphs = new
    else:
        raise RuntimeError("glyph mapping did not converge")

    sim = simulated_shaper(glyphs)
    off = {f: False for f in PRESENTATION_FEATURES}

    # Which parts can be made from letters the user writes anyway?
    from .derive import plan_part

    signs = [resolved[s_][2][resolved[s_][0]].name for s_ in bangla_specs if s_.group == "sign" and resolved[s_][0] is not None]
    plans = []
    for part in parts:
        context = next((t for t in PART_CONJUNCTS if part in sim.names(t)), None)
        if context is None:
            found = _part_context(part, glyphs, sim)
            context = found[0] if found else ""
        plans.append(plan_part(part, context, signs, user))

    cells: list[Cell] = []
    excluded: list[dict] = []
    log: list[dict] = []

    def kind_of(name: str) -> str:
        return "mark" if noto_hmtx[name][0] == 0 else "base"

    for page, specs in PAGES.items():
        page_cells: list[Cell] = []
        for spec in specs:
            if page == 1:
                cp = ord(spec.text)
                page_cells.append(Cell(page, 0, 0, 0, spec.text, None, spec.group, UV2AGL[cp], "latin", unicode=cp))
                log.append({"page": page, "text": spec.text, "glyph": UV2AGL[cp], "kind": "latin", "status": "new glyph"})
                continue
            idx, reason, run = resolved[spec]
            entry = {
                "page": page,
                "text": spec.text,
                "ghost": spec.ghost,
                "base_font": shaper.names(spec.text),
                "basic_forms": shaper.names(spec.text, off),
                "final_font": [g.name for g in run],
                "glyph": run[idx].name if idx is not None else None,
                "status": reason,
            }
            log.append(entry)
            if idx is None:
                excluded.append(entry)
                continue
            entry["kind"] = kind_of(run[idx].name)
            page_cells.append(_make_cell(page, spec.text, spec.ghost, spec.group, run, idx, entry["kind"]))

        if page == 3:
            for part in parts:
                plan = next(p for p in plans if p.glyph == part)
                if plan.method != "written":
                    log.append({"page": page, "text": plan.context, "glyph": part, "kind": kind_of(part), "status": f"derived ({plan.method}): {plan.reason}"})
                    continue
                found = _part_context(part, glyphs, sim)
                entry = {"page": page, "text": None, "ghost": None, "glyph": part, "kind": kind_of(part)}
                log.append(entry)
                if not found:
                    entry["status"] = "no context where this part is visible"
                    excluded.append(entry)
                    continue
                text, run, idx = found
                ghost_names = [g.name for i, g in enumerate(run) if i != idx]
                entry |= {"text": text, "final_font": [g.name for g in run], "status": f"part, ghost {ghost_names}"}
                page_cells.append(_make_cell(page, text, None, "part", run, idx, entry["kind"]))

        for i, (cell, (row, col)) in enumerate(zip(page_cells, _place([c.group for c in page_cells]))):
            cell.index, cell.row, cell.col = i, row, col
        cells += page_cells

    return Layout(
        cells,
        excluded,
        log,
        [{"glyph": p} for p in parts],
        [p.to_dict() for p in plans],
        sorted(g for g in glyphs if _has_matra(g)),
    )


def _has_matra(name: str) -> bool:
    """Does this base-font glyph carry a মাত্রা across (most of) its width?"""
    from .outline import Raster, glyph_polygons

    tt = base_shaper().tt
    g = tt["glyf"][name]
    if not g.numberOfContours or tt["hmtx"][name][0] == 0:
        return False
    head = headline_units()
    if g.yMax < head:
        return False
    r = Raster(g.xMin, g.yMin, g.xMax, g.yMax, 0.1, margin=0)
    r.fill(glyph_polygons(tt.getGlyphSet(), name))
    rows = slice(int((g.yMax - head - 15) * 0.1), int((g.yMax - head + 15) * 0.1) + 1)
    return bool(r.img[rows].any(axis=0).mean() > 0.75)


def part_report(layout: Layout) -> list[dict]:
    """Per part: which conjuncts show it, and which fail without it (slow)."""
    glyphs = layout.bangla_glyphs() | _specials()
    sim = simulated_shaper(glyphs)
    report = []
    for part in (p["glyph"] for p in layout.parts):
        without = simulated_shaper(glyphs - {part})
        report.append(
            {
                "glyph": part,
                "visible_in": [t for t in PART_CONJUNCTS if part in sim.names(t)],
                "needed_by": [t for t in PART_CONJUNCTS if not _forms_like_base(without, t)],
            }
        )
    return report


# --- Cache ---------------------------------------------------------------------
# The layout depends only on the base font and this code, so it is computed
# offline and shipped in assets/. A stale cache is detected by fingerprint.

_SOURCES = ("charset.py", "glyphmap.py", "basefont.py", "config.py", "derive.py")


def fingerprint() -> str:
    h = hashlib.sha256(C.BASE_FONT_PATH.read_bytes())
    for name in _SOURCES:
        h.update((C.APP_DIR / name).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def layout_json(layout: Layout) -> str:
    return json.dumps(
        {
            "fingerprint": fingerprint(),
            "cells": [asdict(c) for c in layout.cells],
            "excluded": layout.excluded,
            "log": layout.log,
            "parts": layout.parts,
            "derived": layout.derived,
            "matra_glyphs": layout.matra_glyphs,
        },
        ensure_ascii=False,
        indent=1,
    )


def _from_json(data: dict) -> Layout:
    cells = []
    for c in data["cells"]:
        ghosts = [GhostGlyph(**g) for g in c.pop("ghost_glyphs")]
        cells.append(Cell(**c, ghost_glyphs=ghosts))
    return Layout(cells, data["excluded"], data["log"], data["parts"], data["derived"], data["matra_glyphs"])


def load_cached_layout() -> Layout | None:
    try:
        data = json.loads(C.LAYOUT_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("fingerprint") != fingerprint():
        return None
    return _from_json(data)


@lru_cache(maxsize=1)
def build_layout() -> Layout:
    cached = load_cached_layout()
    if cached:
        return cached
    logger.warning("assets/layout.json is missing or stale; computing the layout (slow). Run scripts/make_template.py.")
    return compute_layout()
