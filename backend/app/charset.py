"""What the user writes, page by page.

A cell is `text` (what the cell stands for) and an optional `ghost` (a base
letter printed faintly so the user writes only the sign around it). Which
glyph a Bangla cell actually fills is decided by shaping, in glyphmap.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CellSpec:
    text: str
    ghost: str | None = None
    group: str = ""


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

BANGLA_LETTERS = (
    [CellSpec(c, group="vowel") for c in BN_VOWELS]
    + [CellSpec(c, group="consonant") for c in BN_CONSONANTS]
    + [CellSpec(c.text, c.ghost, group="nukta") for c in BN_NUKTA]
    + [
        CellSpec("ৎ", group="other"),
        CellSpec("কং", ghost="ক", group="other"),
        CellSpec("কঃ", ghost="ক", group="other"),
        CellSpec("কঁ", ghost="ক", group="other"),
    ]
)

BN_SIGNS = ["া", "ি", "ী", "ু", "ূ", "ৃ", "ে", "ৈ", "ৗ"]
# The spec's list first. Only conjuncts that are one glyph in the final font
# get a cell (see glyphmap.py); in Noto Sans Bengali ক্ত ন্ত ন্দ স্ত ম্ব ন্ন ল্প
# are assembled from parts, so they are excluded and fall back to a visible
# hasanta. The second line holds common conjuncts that are single glyphs.
CONJUNCTS = (
    "ক্ষ ক্ত ঙ্গ ন্ত ন্দ স্ত ম্ব ন্ন ত্ত ল্প ষ্ট জ্ঞ".split()
    + "ঞ্চ ঞ্জ ঙ্ক ণ্ড ষ্ঠ ক্স ট্ট".split()
)

BANGLA_SIGNS = (
    [CellSpec("ক" + s, ghost="ক", group="sign") for s in BN_SIGNS]
    + [CellSpec("ক্", ghost="ক", group="sign")]
    + [CellSpec("।", group="digit")]
    + [CellSpec(c, group="digit") for c in "০১২৩৪৫৬৭৮৯"]
    + [
        CellSpec("র্ক", ghost="ক", group="phala"),
        CellSpec("প্র", ghost="প", group="phala"),
        CellSpec("ক্য", ghost="ক", group="phala"),
    ]
    + [CellSpec(c, group="conjunct") for c in CONJUNCTS]
)

PAGES: dict[int, list[CellSpec]] = {1: ENGLISH, 2: BANGLA_LETTERS, 3: BANGLA_SIGNS}

PAGE_TITLES = {
    1: ("ইংরেজি", "English"),
    2: ("বাংলা বর্ণ", "Bangla letters"),
    3: ("কার, ফলা, যুক্তবর্ণ, সংখ্যা", "Signs, phala, conjuncts, digits"),
}
