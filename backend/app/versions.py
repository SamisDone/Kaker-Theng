"""Which printed template a photo came from, and whether we can still read it.

Every page carries a version marker. assets/template_versions.json records,
for each version, a fingerprint of each page's cell map (positions, glyphs,
ghosts). A photo is read only if its version's fingerprint for that page is
the current one: unchanged pages stay valid across versions, changed pages
of an older print are refused with a link to the current template.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from functools import lru_cache

from . import config as C
from .glyphmap import build_layout
from .scan import ScanError

HISTORY_PATH = C.ASSETS_DIR / "template_versions.json"
_FIELDS = ("id", "text", "glyph", "kind", "col", "y_mm", "h_mm", "ghost_glyphs", "target_x", "target_y", "run_advance")


def page_fingerprint(cells: list[dict]) -> str:
    """Everything about a page's cells that affects reading it."""
    rows = [[c.get(k) for k in _FIELDS] for c in cells]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def current_fingerprints() -> dict[str, str]:
    layout = build_layout()
    return {str(p): page_fingerprint([asdict(c) for c in layout.page(p)]) for p in (1, 2, 3)}


@lru_cache(maxsize=1)
def history() -> dict[str, dict[str, str]]:
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}


def readable(version: int, page: int) -> bool:
    printed = history().get(str(version), {}).get(str(page))
    return printed is not None and printed == current_fingerprints()[str(page)]


def check(version: int | None, page: int):
    """Raise a clear ScanError unless this page of this version can be read."""
    v = C.UNVERSIONED if version is None else version
    if readable(v, page):
        return
    raise ScanError(
        "old_template",
        f"This page is from an older template (v{v}); its boxes have moved since. "
        "Please print the current template and write this page again.",
        f"এই পাতাটা পুরোনো টেমপ্লেটের (v{v}), তারপর ঘরগুলো বদলেছে। নতুন টেমপ্লেট ছেপে পাতাটা আবার লিখুন।",
        page=page,
        version=v,
        current_version=C.TEMPLATE_VERSION,
    )
