"""Count Bangla consonant clusters (conjuncts, reph, phala) in a Wikipedia dump.

    python -I scripts/count_conjuncts.py <bnwiki-...-pages-articles.xml.bz2> <out.json> [--words <words.json>] [--top <top_words.json>]

Reads article pages (namespace 0, no redirects) from a bz2 dump, which may
be truncated (only the first part downloaded). Writes counts per cluster.
With --words, also what each Bangla word needs to render: its characters
and its clusters, words needing the same merged (app/wordcov.py). With
--top, the most common words themselves, to show a visitor words their
font can already write (app/wordcov.py, writable_words). No app
imports, so it can run isolated on downloaded data.
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
# Not prose: templates (citation fields), references, tables, links to categories and files.
MARKUP = re.compile(r"\{\{[^{}]*\}\}|&lt;ref[^&]*?/&gt;|&lt;ref.*?&lt;/ref&gt;|\{\|.*?\|\}|\[\[[^\]|]*:[^\]]*\]\]", re.S)


def prose(text: str) -> str:
    for _ in range(4):  # templates nest
        text, n = MARKUP.subn(" ", text)
        if not n:
            break
    return text


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
    words_out = sys.argv[sys.argv.index("--words") + 1] if "--words" in sys.argv else None
    top_out = sys.argv[sys.argv.index("--top") + 1] if "--top" in sys.argv else None
    word_counts: Counter[str] = Counter()
    prose_counts: Counter[str] = Counter()
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
        tokens = re.findall("[ঀ-৿]+", text)
        words += len(tokens)
        if words_out:
            word_counts.update(tokens)
        if top_out:
            prose_counts.update(re.findall("[ঀ-৿]+", prose(text)))
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
    if words_out:
        write_words(word_counts, words, words_out)
    if top_out:
        write_top(prose_counts, top_out)


def write_words(word_counts: Counter, total: int, out: str, keep: int = 40000):
    """Words reduced to what they need: sorted characters | sorted clusters,
    words needing the same merged. Only the `keep` most common needs are
    kept (the long tail of rare letter combinations would make the file
    huge); "kept_words" says how many words they stand for."""
    needs: Counter[str] = Counter()
    for word, n in word_counts.items():
        needs["".join(sorted(set(word))) + "|" + " ".join(sorted(set(CLUSTER.findall(word))))] += n
    kept = dict(needs.most_common(keep))
    json.dump(
        {
            "source": "Bangla Wikipedia article dump (dumps.wikimedia.org/bnwiki), CC BY-SA 4.0; first part of the file",
            "words": total,
            "distinct_words": len(word_counts),
            "kept_words": sum(kept.values()),
            "needs": kept,
        },
        open(out, "w", encoding="utf-8"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    print(f"{len(word_counts)} distinct words, {len(needs)} distinct needs, kept {len(kept)} standing for {sum(kept.values()) / total:.2%} of words")


def write_top(word_counts: Counter, out: str, keep: int = 3000):
    """The `keep` most common words of two or more characters (not numbers),
    most common first, with how often each was seen."""
    top = [(w, n) for w, n in word_counts.most_common() if len(w) > 1 and not re.fullmatch("[০-৯]+", w)][:keep]
    json.dump(
        {"source": "Bangla Wikipedia article dump (dumps.wikimedia.org/bnwiki), CC BY-SA 4.0; first part of the file", "words": dict(top)},
        open(out, "w", encoding="utf-8"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    print(f"top {len(top)} words: {' '.join(w for w, _ in top[:30])}")


if __name__ == "__main__":
    main()
