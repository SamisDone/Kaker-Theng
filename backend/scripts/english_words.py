"""Write assets/english_words.json: the most common English words and how
often each is used, for the English half of the font's progress measure.

    python -X utf8 -m scripts.english_words <small_en.msgpack.gz>

The source is wordfreq 3.1.1's small English list (Robyn Speer;
wordfreq/data/small_en.msgpack.gz in its wheel). wordfreq's data is CC BY-SA
4.0, and it asks that the SUBTLEX authors (Brysbaert et al.) be credited; it
blends subtitles (OpenSubtitles 2018, SUBTLEX), news, Google Books Ngrams,
Wikipedia, web text, Twitter and Reddit. Only words of letters (and one
apostrophe, as in don't) are kept: numbers and symbols aren't words a font
writes or doesn't.

The file is "cBpack": a msgpack list whose first item is a header and whose
item i+1 holds the words used 10^(-i/100) of the time (i centibels below
once per word). msgpack is read by hand here, to need nothing installed.
"""

from __future__ import annotations

import gzip
import json
import re
import struct
import sys
from pathlib import Path

from app.config import ASSETS_DIR

OUT = ASSETS_DIR / "english_words.json"
TOP = 5000
WORD = re.compile(r"^[a-z]+(?:'[a-z]+)?$")


def unpack(data: bytes):
    """The subset of msgpack cBpack uses: maps, arrays, strings, ints."""
    pos = 0

    def read():
        nonlocal pos
        b = data[pos]
        pos += 1
        if b <= 0x7F:
            return b
        if 0x80 <= b <= 0x8F:
            return {read(): read() for _ in range(b & 0x0F)}
        if 0x90 <= b <= 0x9F:
            return [read() for _ in range(b & 0x0F)]
        if 0xA0 <= b <= 0xBF:
            return text(b & 0x1F)
        sized = {0xD9: ">B", 0xDA: ">H", 0xDB: ">I", 0xDC: ">H", 0xDD: ">I", 0xDE: ">H", 0xDF: ">I", 0xCC: ">B", 0xCD: ">H", 0xCE: ">I"}
        if b in sized:
            fmt = sized[b]
            (n,) = struct.unpack_from(fmt, data, pos)
            pos += struct.calcsize(fmt)
            if b in (0xD9, 0xDA, 0xDB):
                return text(n)
            if b in (0xDC, 0xDD):
                return [read() for _ in range(n)]
            if b in (0xDE, 0xDF):
                return {read(): read() for _ in range(n)}
            return n
        raise ValueError(f"msgpack type {b:#x} not handled")

    def text(n: int) -> str:
        nonlocal pos
        s = data[pos : pos + n].decode("utf-8")
        pos += n
        return s

    return read()


def main(src: Path):
    packed = unpack(gzip.decompress(src.read_bytes()))
    header, buckets = packed[0], packed[1:]
    assert header.get("format") == "cB", header
    words: list[tuple[str, float]] = []
    for i, bucket in enumerate(buckets):
        for w in bucket:
            w = w.replace("’", "'")
            if WORD.match(w):
                words.append((w, 10 ** (-i / 100)))
    words = words[:TOP]
    OUT.write_text(
        json.dumps(
            {
                "source": "wordfreq 3.1.1 (Robyn Speer), small English list. Data CC BY-SA 4.0; includes SUBTLEX word lists by Brysbaert et al.",
                "licence": "CC BY-SA 4.0",
                "words": [w for w, _ in words],
                "freq": [float(f"{f:.3g}") for _, f in words],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"{len(words)} words, {words[0]} .. {words[-1]}, {sum(f for _, f in words):.1%} of English text")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
