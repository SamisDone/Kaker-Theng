"""Count Bangla consonant clusters (conjuncts, reph, phala) in a Wikipedia dump.

    python -I scripts/count_conjuncts.py <bnwiki-...-pages-articles.xml.bz2> <out.json>

Reads article pages (namespace 0, no redirects) from a bz2 dump, which may
be truncated (only the first part downloaded). Writes counts per cluster.
No app imports, so it can run isolated on downloaded data.
"""

import bz2
import json
import re
import sys
import unicodedata
from collections import Counter

CONS = "[ক-হড়ঢ়য়]়?"
# Consonant, then one or more (hasanta + consonant). An explicit ZWNJ after
# the hasanta means the writer wants it visible: not a conjunct.
CLUSTER = re.compile(f"(?:{CONS}্)+{CONS}")
PAGE = re.compile(r"<page>(.*?)</page>", re.S)
TEXT = re.compile(r"<text[^>]*>(.*?)</text>", re.S)


def pages(path: str):
    dec = bz2.BZ2Decompressor()
    buf = ""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            try:
                data = dec.decompress(chunk)
            except (OSError, EOFError):
                break  # truncated download: stop at the last whole block
            buf += data.decode("utf-8", "ignore")
            last = buf.rfind("</page>")
            if last < 0:
                continue
            for m in PAGE.finditer(buf, 0, last + 7):
                yield m.group(1)
            buf = buf[last + 7 :]
            if dec.eof:
                break


def main():
    src, out = sys.argv[1], sys.argv[2]
    counts: Counter[str] = Counter()
    chars: Counter[str] = Counter()
    articles = words = 0
    for page in pages(src):
        if "<ns>0</ns>" not in page or "<redirect" in page:
            continue
        m = TEXT.search(page)
        if not m:
            continue
        text = unicodedata.normalize("NFC", m.group(1))
        articles += 1
        words += len(re.findall("[ঀ-৿]+", text))
        for c in CLUSTER.findall(text):
            counts[c] += 1
        chars.update(ch for ch in text if "ঀ" <= ch <= "৿" or ch in "।॥")  # dari lives in the Devanagari block
    json.dump(
        {
            "source": "Bangla Wikipedia article dump (dumps.wikimedia.org/bnwiki), CC BY-SA 4.0; first part of the file",
            "articles": articles,
            "bangla_words": words,
            "clusters": dict(counts.most_common()),
            "characters": dict(chars.most_common()),
        },
        open(out, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=0,
    )
    print(f"{articles} articles, {words} Bangla words, {sum(counts.values())} clusters, {len(counts)} distinct")


if __name__ == "__main__":
    main()
