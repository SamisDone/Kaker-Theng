"""Per-visitor work, kept in a temp folder that is deleted after an hour.

Nothing here has to survive a restart: the disk on the free server isn't
persistent. If a session is gone the visitor simply uploads again.
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from .config import OFL_PATH
from .coverage import complete_coverage, font_coverage, pages_1_2_coverage
from .fontbuild import BuiltFont, build_font, clean_family_name, postscript_name
from .pipeline import PageResult
from .vectorize import drawing_from_dict, drawing_to_dict

SESSION_TTL_S = 3600
ROOT = Path(os.environ.get("KT_DATA_DIR") or Path(tempfile.gettempdir()) / "kaker-theng")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")
PREVIEW_FAMILY = "Kaker Theng Preview"


def _dir(session_id: str) -> Path:
    if not ID_RE.match(session_id):
        raise KeyError(session_id)
    return ROOT / session_id


def create() -> str:
    session_id = secrets.token_urlsafe(12)
    d = _dir(session_id)
    d.mkdir(parents=True)
    _write_meta(d, {"created": time.time(), "pages": {}, "font_version": 0})
    return session_id


def _meta_path(d: Path) -> Path:
    return d / "meta.json"


def _write_meta(d: Path, meta: dict):
    meta["updated"] = time.time()
    tmp = d / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_meta_path(d))


def load(session_id: str) -> dict | None:
    """The session's state, or None if it doesn't exist or has expired."""
    try:
        d = _dir(session_id)
        meta = json.loads(_meta_path(d).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        return None
    if time.time() - meta.get("updated", 0) > SESSION_TTL_S:
        shutil.rmtree(d, ignore_errors=True)
        return None
    return meta


def file_path(session_id: str, name: str) -> Path | None:
    if not re.match(r"^[A-Za-z0-9_.-]{1,80}$", name) or name.startswith("."):
        return None
    try:
        p = _dir(session_id) / name
    except KeyError:
        return None
    return p if p.is_file() else None


def _drawings(d: Path, pages) -> list:
    out = []
    for page in pages:
        p = d / f"drawings-p{page}.json"
        if p.exists():
            out += [drawing_from_dict(x) for x in json.loads(p.read_text(encoding="utf-8"))]
    return out


def save_page(session_id: str, result: PageResult) -> dict:
    """Store a processed page, rebuild the preview font, measure coverage."""
    d = _dir(session_id)
    meta = load(session_id)
    if meta is None:
        raise KeyError(session_id)
    page = result.page
    (d / f"drawings-p{page}.json").write_text(json.dumps([drawing_to_dict(x) for x in result.drawings]), encoding="utf-8")
    (d / f"page-{page}.png").write_bytes(result.thumbnail_png)
    meta["pages"][str(page)] = {
        "page": page,
        "cells": result.cells,
        "missing_corners": result.missing_corners,
        "thumbnail": f"page-{page}.png",
        "processed": time.time(),
    }

    drawings = _drawings(d, sorted(int(p) for p in meta["pages"]))
    if drawings:
        font = build_font(drawings, PREVIEW_FAMILY)
        version = meta["font_version"] + 1
        for old in d.glob("preview-*.woff2"):
            old.unlink()
        (d / f"preview-{version}.woff2").write_bytes(font.woff2)
        meta["font_version"] = version
        meta["font"] = f"preview-{version}.woff2"
        written = {x.glyph for x in drawings if x.kind != "latin"}
        meta["coverage"] = font_coverage(font.ttf, written) if written else 0.0
        meta["glyphs"] = sorted(set(font.glyphs))
    meta["coverage_targets"] = {"pages_1_2": pages_1_2_coverage(), "all_pages": complete_coverage()}
    _write_meta(d, meta)
    return meta


def build_download(session_id: str, family: str, fmt: str) -> dict:
    """A zip with the font in one format, its licence, and a short README."""
    d = _dir(session_id)
    meta = load(session_id)
    if meta is None:
        raise KeyError(session_id)
    family = clean_family_name(family)
    font: BuiltFont = build_font(_drawings(d, sorted(int(p) for p in meta["pages"])), family)
    base = postscript_name(family)
    data = font.ttf if fmt == "ttf" else font.woff2
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{base}.{fmt}", data)
        z.writestr("OFL.txt", OFL_PATH.read_text(encoding="utf-8"))
        z.writestr("README.txt", _readme(family, meta))
    name = f"{base}-{fmt}.zip"
    (d / name).write_bytes(buf.getvalue())
    _write_meta(d, meta)
    return {"file": name, "family": family, "format": fmt}


def _readme(family: str, meta: dict) -> str:
    cov = meta.get("coverage")
    cov_line = f"It renders {cov:.0%} of the consonant clusters in real Bangla text correctly.\n" if cov else ""
    return (
        f"{family}\n{'=' * len(family)}\n\n"
        "A handwriting font made with Kaker Theng (kaker theng: 'crow's leg', what people\n"
        "call messy handwriting). Bangla and English.\n\n"
        f"{cov_line}"
        "Licence: SIL Open Font License 1.1 (OFL.txt). The font is built on Noto Sans\n"
        "Bengali (Copyright The Noto Project Authors): its layout tables (how Bangla letters\n"
        "combine) are kept, the outlines are this handwriting. As a Modified Version it stays\n"
        "under the OFL: you may use, share and embed it freely, but not sell it on its own,\n"
        "and any copy must carry OFL.txt. 'Noto' is a trademark of Google: don't use it in\n"
        "the font's name.\n\n"
        "Conjunct frequencies used to choose which conjuncts get template cells come from\n"
        "Bangla Wikipedia (CC BY-SA 4.0).\n"
    )


def sweep():
    """Delete expired sessions."""
    if not ROOT.exists():
        return
    now = time.time()
    for d in ROOT.iterdir():
        try:
            meta = json.loads(_meta_path(d).read_text(encoding="utf-8"))
            expired = now - meta.get("updated", 0) > SESSION_TTL_S
        except (OSError, ValueError):
            expired = now - d.stat().st_mtime > SESSION_TTL_S
        if expired:
            shutil.rmtree(d, ignore_errors=True)


def start_sweeper(every_s: int = 300):
    def loop():
        while True:
            sweep()
            time.sleep(every_s)

    threading.Thread(target=loop, name="session-sweeper", daemon=True).start()
