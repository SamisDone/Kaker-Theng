"""How much real Bangla text the font renders without a visible hasanta.

    python -m scripts.conjunct_coverage [--plan N_CELLS] [--top K]

Uses assets/conjunct_counts.json (scripts/count_conjuncts.py on a Bangla
Wikipedia dump). A cluster counts as covered when the finished font (the
base font cut down to the planned glyphs) shapes it with no hasanta glyph
and no .notdef.

With --plan, prices the most frequent missing clusters (one whole-glyph cell,
or the parts it needs, of which derivable ones cost nothing) and picks the
best coverage per cell for N_CELLS free cells.
"""

import argparse
import json
from pathlib import Path

from app.basefont import PRESENTATION_FEATURES, base_shaper, simulated_shaper
from app.charset import CONJUNCTS, CORE_PART_CONJUNCTS, CORPUS_CONJUNCTS_PATH, PART_CONJUNCTS
from app.derive import plan_part
from app.glyphmap import HALANT, _discover_parts, _specials, build_layout

COUNTS = Path(__file__).resolve().parent.parent / "assets" / "conjunct_counts.json"
# Clusters the self-test (scripts/conjunct_selftest.py) found don't assemble
# well from derived parts. The planner leaves them out.
REJECTED = COUNTS.parent.parent / "data" / "conjunct_rejected.txt"


def rejected() -> set[str]:
    return set(REJECTED.read_text(encoding="utf-8").split()) if REJECTED.exists() else set()
CHECK = "স্থ দ্ধ ন্ধ চ্ছ ত্ম ষ্ণ ন্ট প্ত".split()


def load() -> dict[str, int]:
    return json.loads(COUNTS.read_text(encoding="utf-8"))["clusters"]


# Glyphs the user writes in their own cells (plus space etc.). Set by main().
PLAIN: set[str] = set()


def plain_glyphs(layout) -> set[str]:
    return {c.glyph for c in layout.cells if c.kind != "latin" and c.group != "part"} | _specials()


def covered(sim, text: str, halant: str) -> bool:
    """Shaped with no hasanta and no .notdef, and not half-built: either the
    font builds it exactly as the base font does, or only from glyphs the
    user writes in their own cells (প + ra-phala, a whole conjunct...)."""
    names = sim.names(text)
    if ".notdef" in names or halant in names:
        return False
    return not PLAIN or names == base_shaper().names(text) or all(n in PLAIN for n in names)


def coverage(sim, counts: dict[str, int], halant: str) -> tuple[float, set[str]]:
    ok = {t for t in counts if covered(sim, t, halant)}
    return sum(counts[t] for t in ok) / sum(counts.values()), ok


def price(text: str, glyphs: set[str], signs: list[str], halant: str) -> dict:
    """Cells needed to cover one cluster: whole glyph, or parts."""
    base = base_shaper()
    off = {f: False for f in PRESENTATION_FEATURES}
    out = {"text": text, "whole": None, "parts": [], "derivable": [], "written": [], "parts_ok": False}
    basic = base.names(text, off)
    if len(basic) == 1 and basic[0] not in glyphs:
        if simulated_shaper(glyphs | {basic[0]}).names(text) == basic:
            out["whole"] = basic[0]
    parts = _discover_parts(glyphs, [text])
    if parts and covered(simulated_shaper(glyphs | set(parts)), text, halant):
        out["parts_ok"] = True
        out["parts"] = parts
        for p in parts:
            plan = plan_part(p, text, signs, glyphs, (glyphs | set(parts)) - {p})
            (out["written"] if plan.method == "written" else out["derivable"]).append(f"{p}:{plan.method}")
    options = []
    if out["whole"]:
        options.append(("whole", 1, {out["whole"]}))
    if out["parts_ok"]:
        options.append(("parts", len(out["written"]), set(parts)))
    out["best"] = min(options, key=lambda o: o[1]) if options else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=int, default=0, help="template cells to spend; writes assets/corpus_conjuncts.txt")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--why", nargs="*", default=[], help="explain the planner's decision for these clusters")
    args = ap.parse_args()

    counts = load()
    total = sum(counts.values())
    layout = build_layout()
    PLAIN.update(plain_glyphs(layout))
    base = base_shaper()
    halant = base.tt.getBestCmap()[ord(HALANT)]
    signs = [c.glyph for c in layout.cells if c.ghost and c.kind != "latin"]
    print(f"{len(counts)} distinct clusters, {total} occurrences (Bangla Wikipedia sample)")

    glyphs = layout.bangla_glyphs() | _specials()
    sim = simulated_shaper(glyphs)
    cov, ok = coverage(sim, counts, halant)
    print(f"covered by the current layout ({len(PART_CONJUNCTS)} part conjuncts): {cov:.1%} of occurrences, {len(ok)} distinct")

    if args.plan:
        # Start from the core list only, so the plan is reproducible.
        user = {c.glyph for c in layout.cells if c.kind != "latin" and c.group != "part"} | _specials()
        glyphs = user | set(_discover_parts(user, CORE_PART_CONJUNCTS))
        sim = simulated_shaper(glyphs)
        cov, ok = coverage(sim, counts, halant)
        print(f"covered by the core list ({len(CORE_PART_CONJUNCTS)} part conjuncts): {cov:.1%}")
    print()

    missing = sorted((t for t in counts if t not in ok), key=lambda t: -counts[t])
    skip = rejected() if args.plan else set()
    pool = [t for t in missing if t not in skip]
    pool = list(dict.fromkeys(pool[: max(args.top, 120)] + [t for t in CHECK if t in missing and t not in skip]))
    priced = {t: price(t, glyphs, signs, halant) for t in pool}
    # A whole-glyph conjunct is written whole by the user, like a letter.
    PLAIN.update(p["whole"] for p in priced.values() if p["whole"])

    print(f"TOP {args.top} MISSING (share of all cluster occurrences; cells: whole glyph / parts new, derivable, to write)")
    for t in missing[: args.top] + [t for t in CHECK if t not in missing[: args.top] and t in missing]:
        p = priced[t]
        whole = "1" if p["whole"] else "-"
        parts = f"{len(p['parts'])} new, {len(p['derivable'])} derivable, {len(p['written'])} to write" if p["parts_ok"] else "no"
        best = f"{p['best'][0]} {p['best'][1]} cell(s)" if p["best"] else "can't cover"
        mark = " *" if t in CHECK else ""
        print(f"  {t:<6}{counts[t] / total:>7.2%}  whole {whole:<3} parts: {parts:<44} -> {best}{mark}")
    for t in CHECK:
        if t not in missing:
            print(f"  {t:<6}{counts.get(t, 0) / total:>7.2%}  covered *")

    if not args.plan:
        return

    # Each cluster's gain on the whole corpus; best coverage per cell first.
    # A whole-glyph cell beats written fragments at the same cost: writing a
    # familiar conjunct is easier than writing a piece of one.
    options = []
    for t, p in priced.items():
        choices = []
        if p["whole"]:
            choices.append(("whole", 1, {p["whole"]}))
        if p["parts_ok"]:
            choices.append(("parts", len(p["written"]), set(p["parts"])))
        if not choices:
            continue
        choices.sort(key=lambda c: (c[1], c[0] == "parts" and c[1] > 0))
        kind, cells, new = choices[0]
        _, now_ok = coverage(simulated_shaper(glyphs | new), counts, halant)
        options.append((t, choices, cells, sum(counts[x] for x in now_ok - ok)))
    options.sort(key=lambda o: -(o[3] / max(o[2], 0.5)))
    chosen, whole, used, new_glyphs = [], [], 0, set()

    protected = set(ok)  # clusters that must stay covered
    tolerated: dict[str, int] = {}  # negligible clusters given up

    def with_repairs(t: str, kind: str, new: set[str]):
        """Add an option plus the completions of anything it would break.
        Returns (glyphs to add, extra cells, completed clusters) or None."""
        cur, cells, repaired = set(new), 0, []
        whole_now = list(CONJUNCTS) + whole + ([t] if kind == "whole" else [])
        for _ in range(5):
            test = simulated_shaper(glyphs | new_glyphs | cur)
            if not all(len(test.names(w)) == 1 for w in whole_now):
                if t in args.why:
                    print(f"  why {t} ({kind}): breaks whole {[w for w in whole_now if len(test.names(w)) != 1]}")
                return None
            lost = sorted((x for x in protected if not covered(test, x, halant)), key=lambda x: -counts[x])
            if not lost:
                return cur, cells, repaired
            for x in lost:
                p = price(x, glyphs | new_glyphs | cur, signs, halant)
                if p["parts_ok"] and not (set(p["parts"]) & cur):
                    cur |= set(p["parts"])
                    cells += len(p["written"])
                    repaired.append(x)
                elif counts[x] / total < 0.0001:
                    tolerated[x] = counts[x]
                    protected.discard(x)
                else:
                    if t in args.why:
                        print(f"  why {t} ({kind}): would lose {x} ({' '.join(test.names(x))}), can't repair")
                    return None
        return None

    for t, choices, _, gain in options:
        if gain <= 0:
            continue
        # The preferred choice first; if it would break something, the next.
        for kind, cells, new in choices:
            result = with_repairs(t, kind, new) if used + cells <= args.plan else None
            if result is not None and used + cells + result[1] <= args.plan:
                break
            if t in args.why:
                print(f"  why {t} ({kind}): {'rejected' if result is None else 'over budget'} (used {used}, cells {cells})")
        else:
            continue
        add, extra_cells, repaired = result
        (whole if kind == "whole" else chosen).append(t)
        chosen.extend(repaired)
        used += cells + extra_cells
        new_glyphs |= add
        _, now = coverage(simulated_shaper(glyphs | new_glyphs), counts, halant)
        protected |= now

    def keeps_whole(extra: set[str]) -> bool:
        test = simulated_shaper(glyphs | new_glyphs | extra)
        return all(len(test.names(w)) == 1 for w in list(CONJUNCTS) + whole) and all(covered(test, x, halant) for x in protected)

    # New parts can make Noto's own constructions kick in elsewhere (a half
    # form now exists, so প্র asks for its ra-phala variant). Complete every
    # cluster that changed shape but isn't built the way Noto builds it.
    unresolved = {}
    for _ in range(6):
        after = simulated_shaper(glyphs | new_glyphs)
        partial = [
            t
            for t in counts
            if (n := after.names(t)) != sim.names(t) and n != base.names(t) and ".notdef" not in n and halant not in n
        ]
        # A cluster the user writes as one whole glyph is complete as written.
        whole_written = set(whole) | set(CONJUNCTS)
        partial = [t for t in sorted(partial, key=lambda t: -counts[t]) if t not in unresolved and t not in skip and t not in whole_written]
        if not partial:
            break
        for t in partial:
            p = price(t, glyphs | new_glyphs, signs, halant)
            if p["parts_ok"] and not p["written"] and keeps_whole(set(p["parts"])):
                chosen.append(t)
                new_glyphs |= set(p["parts"])
            elif p["parts"]:
                unresolved[t] = counts[t]
            # No new parts needed: an earlier completion this pass already
            # covered it. The next pass rechecks.
    after = simulated_shaper(glyphs | new_glyphs)
    cov2, ok2 = coverage(after, counts, halant)
    lost = [t for t in ok if t not in ok2]

    chosen = sorted(dict.fromkeys(chosen), key=lambda t: -counts.get(t, 0))
    whole = sorted(whole, key=lambda t: -counts.get(t, 0))
    lines = [f"whole:{t}" for t in whole] + chosen
    CORPUS_CONJUNCTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nPLAN: {len(whole)} whole-glyph cells + {len(chosen)} clusters from parts; {used} cell(s) of {args.plan}; wrote {CORPUS_CONJUNCTS_PATH.name}")
    print("  whole:", " ".join(whole))
    print("  parts:", " ".join(chosen))
    print(f"coverage {cov:.1%} -> {cov2:.1%}")
    print(f"half-built clusters left: {len(unresolved)} ({sum(unresolved.values()) / total:.2%} of occurrences) {list(unresolved)[:10]}")
    print(f"clusters that lost coverage: {lost or 'none'}")
    print(f"negligible clusters given up (< 0.01% each): {list(tolerated) or 'none'}")


if __name__ == "__main__":
    main()
