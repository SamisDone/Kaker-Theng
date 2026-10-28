"""How much English a font writes: the English half of the progress measure.

assets/english_words.json (scripts/english_words.py) holds the 5,000 most
common English words with how often each is used, from wordfreq (CC BY-SA
4.0); together they make up about 84% of running English text. A word is
written when the font has every one of its characters. The words are
lowercase, as the list counts them; "i" (and i'm, i've ...) needs the
capital I, as English writes it. The share is of those words' uses, as the
Bangla measure is (wordcov.py).

assets/sentences_en.txt holds short everyday sentences, to show a visitor
what their font already writes.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from .config import ASSETS_DIR

WORDS_PATH = ASSETS_DIR / "english_words.json"
SENTENCES_PATH = ASSETS_DIR / "sentences_en.txt"
_I = re.compile(r"^i(?:'|$)")


def _needs(word: str) -> set[str]:
    """The characters a word needs, written as English writes it."""
    return set("I" + word[1:]) if _I.match(word) else set(word)


@lru_cache(maxsize=1)
def _words() -> tuple[list[tuple[str, frozenset[str], float]], float]:
    data = json.loads(WORDS_PATH.read_text(encoding="utf-8"))
    words = [(w, frozenset(_needs(w)), f) for w, f in zip(data["words"], data["freq"])]
    return words, sum(f for _, _, f in words)


def english_coverage(chars: set[str]) -> float:
    """Share of uses of common English words the font writes fully."""
    words, total = _words()
    return sum(f for _, needs, f in words if needs <= chars) / total


def writable_english_words(chars: set[str], limit: int = 60) -> list[str]:
    """The most common English words the font writes, most common first."""
    words, _ = _words()
    out = [("I" + w[1:] if _I.match(w) else w) for w, needs, _ in words if needs <= chars]
    return out[:limit]


@lru_cache(maxsize=1)
def _sentences() -> list[str]:
    lines = SENTENCES_PATH.read_text(encoding="utf-8").splitlines()
    return [s.strip() for s in lines if s.strip() and not s.startswith("#")]


def writable_english_sentences(chars: set[str]) -> list[str]:
    """The sentences the font writes fully, in order; one it writes but for
    its end mark (. ! ? not drawn yet) comes without it."""
    out = []
    for s in _sentences():
        if set(s) - {" "} <= chars:
            out.append(s)
        elif set(s.rstrip(".!?")) - {" "} <= chars:
            out.append(s.rstrip(".!?"))
    return out


def font_chars(cmap: dict[int, str], glyphs: set[str]) -> set[str]:
    """The characters whose glyph is one of `glyphs` (the writer's English letters)."""
    return {chr(cp) for cp, g in cmap.items() if g in glyphs}
