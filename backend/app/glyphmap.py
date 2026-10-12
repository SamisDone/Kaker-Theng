"""Decide, by shaping, which glyph every template cell fills.

No glyph names are hardcoded. For Bangla:

1. Shape each cell with the base font, with presentation features off. That
   gives the basic Indic forms (plain matras, generic phala, reph, ligatures
   from akhn/cjct...). These are candidate targets.
2. Subset the base font down to the candidates and shape every cell again.
   Outlines don't affect shaping, so this is exactly how the user's finished
   font will behave. Context variants (ে.init, ি length variants, phala
   alternates, conjunct parts) are gone, and their rules with them.
3. A cell's target is the glyph that remains once the ghost's glyphs are
   taken away. A conjunct is kept only if it comes out as one glyph.
4. Repeat until the glyph set stops changing.

Latin glyphs don't exist in the base font; they get standard AGL names and
are added to the font later.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from fontTools.agl import UV2AGL

from . import config as C
from .basefont import PRESENTATION_FEATURES, base_shaper, simulated_shaper
from .charset import PAGES, CellSpec

SPECIAL_GLYPH_UNICODES = [0x20, 0xA0, 0x200C, 0x200D, 0x25CC]


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

    def page(self, n: int) -> list[Cell]:
        return [c for c in self.cells if c.page == n]

    def bangla_glyphs(self) -> set[str]:
        return {c.glyph for c in self.cells if c.kind != "latin"}


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


def _is_bangla_composite(spec: CellSpec) -> bool:
    return spec.ghost is not None or len(spec.text) > 1


def _candidates(specs: list[CellSpec]) -> set[str]:
    shaper = base_shaper()
    cmap = shaper.tt.getBestCmap()
    off = {f: False for f in PRESENTATION_FEATURES}
    glyphs = {cmap[cp] for cp in SPECIAL_GLYPH_UNICODES if cp in cmap}
    for spec in specs:
        if not _is_bangla_composite(spec):
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


def _resolve(spec: CellSpec, sim) -> tuple[str | None, str, list]:
    """(target glyph or None, reason, shaped run) using the simulated font."""
    run = sim.shape(spec.text)
    names = [g.name for g in run]
    if ".notdef" in names:
        return None, "shapes to .notdef", run
    if spec.ghost is None:
        if len(run) == 1:
            return run[0].name, "single glyph", run
        return None, f"not one glyph in the final font ({len(run)} glyphs)", run
    ghost = sim.names(spec.ghost)
    rest = _diff(names, ghost)
    if len(rest) == 1 and len(names) == len(ghost) + 1:
        return names[rest[0]], "ghost + one written glyph", run
    return None, f"ghost does not survive as-is ({names} vs ghost {ghost})", run


def _place(specs_with_cells: list[tuple[CellSpec, object]]) -> list[tuple[int, int]]:
    """Row/col per cell. Each group starts a new row when everything fits."""
    groups: list[list[int]] = []
    last = None
    for i, (spec, _) in enumerate(specs_with_cells):
        if spec.group != last:
            groups.append([])
            last = spec.group
        groups[-1].append(i)
    rows_needed = sum(-(-len(g) // C.COLS) for g in groups)
    pos: list[tuple[int, int]] = [(0, 0)] * len(specs_with_cells)
    if rows_needed <= C.ROWS:
        row = 0
        for g in groups:
            for k, i in enumerate(g):
                pos[i] = (row + k // C.COLS, k % C.COLS)
            row += -(-len(g) // C.COLS)
    else:
        for i in range(len(specs_with_cells)):
            pos[i] = (i // C.COLS, i % C.COLS)
    if max(r for r, _ in pos) >= C.ROWS:
        raise ValueError("too many cells for one page")
    return pos


@lru_cache(maxsize=1)
def build_layout() -> Layout:
    shaper = base_shaper()
    noto_hmtx = shaper.tt["hmtx"]
    bangla_specs = [s for p in (2, 3) for s in PAGES[p]]

    glyphs = _candidates(bangla_specs)
    for _ in range(5):
        sim = simulated_shaper(glyphs)
        resolved = {}
        claimed: dict[str, str] = {}
        for spec in bangla_specs:
            target, reason, run = _resolve(spec, sim)
            if target and target in claimed:
                reason = f"same glyph as cell {claimed[target]}"
                target = None
            if target:
                claimed[target] = spec.text
            resolved[spec] = (target, reason, run)
        new = {t for t, _, _ in resolved.values() if t}
        cmap = shaper.tt.getBestCmap()
        new |= {cmap[cp] for cp in SPECIAL_GLYPH_UNICODES if cp in cmap}
        if new == glyphs:
            break
        glyphs = new
    else:
        raise RuntimeError("glyph mapping did not converge")

    full_off = {f: False for f in PRESENTATION_FEATURES}
    cells: list[Cell] = []
    excluded: list[dict] = []
    log: list[dict] = []

    for page, specs in PAGES.items():
        kept: list[tuple[CellSpec, Cell]] = []
        for spec in specs:
            if page == 1:
                cp = ord(spec.text)
                cell = Cell(page, 0, 0, 0, spec.text, None, spec.group, UV2AGL[cp], "latin", unicode=cp)
                kept.append((spec, cell))
                log.append({"page": page, "text": spec.text, "glyph": cell.glyph, "kind": "latin", "status": "new glyph"})
                continue

            target, reason, run = resolved[spec]
            entry = {
                "page": page,
                "text": spec.text,
                "ghost": spec.ghost,
                "base_font": shaper.names(spec.text),
                "basic_forms": shaper.names(spec.text, full_off),
                "final_font": [g.name for g in run],
                "glyph": target,
                "status": reason,
            }
            log.append(entry)
            if not target:
                excluded.append(entry)
                continue

            kind = "mark" if noto_hmtx[target][0] == 0 else "base"
            entry["kind"] = kind
            cell = Cell(page, 0, 0, 0, spec.text, spec.ghost, spec.group, target, kind)
            x = 0
            ghost_left = Counter(sim.names(spec.ghost)) if spec.ghost else Counter()
            for g in run:
                gx, gy = x + g.x_offset, g.y_offset
                if g.name == target and not ghost_left[g.name]:
                    cell.target_x, cell.target_y = gx, gy
                else:
                    ghost_left[g.name] -= 1
                    cell.ghost_glyphs.append(GhostGlyph(g.name, gx, gy))
                x += g.x_advance
            cell.run_advance = x
            kept.append((spec, cell))

        for i, ((spec, cell), (row, col)) in enumerate(zip(kept, _place(kept))):
            cell.index, cell.row, cell.col = i, row, col
            cells.append(cell)

    return Layout(cells, excluded, log)


def layout_json(layout: Layout) -> str:
    return json.dumps(
        {"cells": [asdict(c) | {"id": c.id} for c in layout.cells], "excluded": layout.excluded},
        ensure_ascii=False,
        indent=1,
    )
