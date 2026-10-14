"""What the user writes, page by page.

A cell is `text` (what the cell stands for) and an optional `ghost` (a base
letter printed faintly so the user writes only the sign around it). Which
glyph a Bangla cell actually fills is decided by shaping, in glyphmap.py.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CellSpec:
    text: str
    ghost: str | None = None
    group: str = ""
    tall: bool = False  # extra room above and below, for deep or tall marks


ENGLISH = (
    [CellSpec(c, group="upper") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    + [CellSpec(c, group="lower") for c in "abcdefghijklmnopqrstuvwxyz"]
    + [CellSpec(c, group="digit") for c in "0123456789"]
    + [CellSpec(c, group="punct") for c in ".,;:!?'\"()-&@/"]
)

BN_VOWELS = "অ আ ই ঈ উ ঊ ঋ এ ঐ ও ঔ".split()
BN_CONSONANTS = "ক খ গ ঘ ঙ চ ছ জ ঝ ঞ ট ঠ ড ঢ ণ ত থ দ ধ ন প ফ ব ভ ম য র ল শ ষ স হ".split()
# ড় ঢ় য় all shape to their base letter + the same nukta mark, so only one
# cell is kept. য় comes first because it is by far the most common.
BN_NUKTA = [CellSpec("য়", ghost="য"), CellSpec("ড়", ghost="ড"), CellSpec("ঢ়", ghost="ঢ")]


# Signs that reach far above the মাত্রা or below the baseline get tall cells.
BN_TALL_SIGNS = ["ী", "ু", "ূ", "ৃ"]
BN_SIGNS = ["া", "ি", "ে", "ৈ", "ৗ"]
# Conjuncts that are one glyph in the final font: the user writes them whole.
CONJUNCTS = "ক্ষ ঙ্গ ত্ত ষ্ট জ্ঞ ঞ্চ ঞ্জ".split()

# Conjuncts Noto Sans Bengali assembles from parts (half forms, below-base
# forms, headline pieces). glyphmap.py finds the parts by tracing the GSUB
# lookups and gives each part its own cell, with the rest of the conjunct
# printed as a ghost.
# হ্ন is not in the original list, but once ka-beng.arm2 exists it forms
# without its headline piece and the মাত্রা breaks, so it gets its part too.
CORE_PART_CONJUNCTS = "ক্ত ন্ত ন্দ স্ত ম্ব ন্ন ল্প হ্ন".split()

# More clusters, picked by scripts/conjunct_coverage.py --plan from how often
# they occur in Bangla Wikipedia (assets/conjunct_counts.json): the best text
# coverage per template cell, plus any cluster the new parts would otherwise
# leave half-built. Almost all of their parts are made from the user's own
# letters, so they cost few or no cells.
CORPUS_CONJUNCTS_PATH = Path(__file__).resolve().parent.parent / "assets" / "corpus_conjuncts.txt"


def _corpus_conjuncts() -> tuple[list[str], list[str]]:
    """(whole-glyph conjuncts, conjuncts built from parts) from the file."""
    try:
        lines = CORPUS_CONJUNCTS_PATH.read_text(encoding="utf-8").split()
    except OSError:
        return [], []
    whole = [t.removeprefix("whole:") for t in lines if t.startswith("whole:")]
    parts = [t for t in lines if not t.startswith("whole:") and t not in CORE_PART_CONJUNCTS]
    return whole, parts


CORPUS_WHOLE, CORPUS_PARTS = _corpus_conjuncts()
PART_CONJUNCTS = CORE_PART_CONJUNCTS + CORPUS_PARTS

# Contexts searched when a part only exists as an intermediate glyph (for
# example the half form ক্ that ক্ত passes through) and we need somewhere it
# is visible so the user can write it.
CONSONANTS_FOR_CONTEXT = "ক খ গ ঘ ঙ চ ছ জ ঝ ঞ ট ঠ ড ঢ ণ ত থ দ ধ ন প ফ ব ভ ম য র ল শ ষ স হ".split()

# Page 2 holds everything ordinary text needs, so pages 1 and 2 alone make a
# working font. Page 3 (conjuncts, digits) is an optional upgrade.
BANGLA_LETTERS = (
    [CellSpec(c, group="vowel") for c in BN_VOWELS]
    + [CellSpec(c, group="consonant") for c in BN_CONSONANTS]
    + [CellSpec(c.text, c.ghost, group="nukta") for c in BN_NUKTA]
    + [CellSpec("ৎ", group="other"), CellSpec("কং", ghost="ক", group="other"), CellSpec("কঃ", ghost="ক", group="other")]
    + [CellSpec("ক" + s, ghost="ক", group="sign") for s in BN_SIGNS]
    + [CellSpec("ক্", ghost="ক", group="sign")]
    + [CellSpec("প্র", ghost="প", group="phala"), CellSpec("ক্য", ghost="ক", group="phala")]
    + [CellSpec("।", group="sign")]
    + [CellSpec("ক" + s, ghost="ক", group="tall", tall=True) for s in BN_TALL_SIGNS]
    + [CellSpec("কঁ", ghost="ক", group="tall", tall=True), CellSpec("র্ক", ghost="ক", group="tall", tall=True)]
)

BANGLA_EXTRA = (
    [CellSpec(c, group="digit") for c in "০১২৩৪৫৬৭৮৯"]
    + [CellSpec(c, group="conjunct") for c in CONJUNCTS + [t for t in CORPUS_WHOLE if t not in CONJUNCTS]]
)
OPTIONAL_PAGES = {3}

# For laying out rows: groups that share rows.
ROW_GROUP = {"phala": "sign", "part": "conjunct"}

PAGES: dict[int, list[CellSpec]] = {1: ENGLISH, 2: BANGLA_LETTERS, 3: BANGLA_EXTRA}

PAGE_TITLES = {
    1: ("ইংরেজি", "English"),
    2: ("বর্ণ, কার, ফলা", "Letters, vowel signs, phala"),
    3: ("যুক্তবর্ণ ও সংখ্যা (ঐচ্ছিক)", "Conjuncts and digits (optional)"),
}
