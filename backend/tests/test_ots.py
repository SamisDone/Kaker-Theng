"""Every font a browser is given passes OTS, the OpenType sanitizer Chrome
and Firefox run before using a font; a font it rejects fails to load
("NetworkError" in Chrome). The visitor's font at several stages of
drawing, drawn only and mixed with a page photo, as the preview WOFF2 and
the download's TTF and WOFF2; and the site's own fonts.
"""

import io
import subprocess
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.fontbuild import build_font
from app.glyphmap import build_layout
from app.strokes import drawing
from tests.synth import make_page
from tests.test_strokes import wait
from tests.trace_strokes import traced_cells

ots = pytest.importorskip("ots")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def sanitized(data: bytes, ext: str, tmp_path: Path) -> str:
    """OTS's complaint, or "" when it passes."""
    src, out = tmp_path / f"in.{ext}", tmp_path / f"out.{ext}"
    src.write_bytes(data)
    r: subprocess.CompletedProcess = ots.sanitize(str(src), str(out), capture_output=True)
    return "" if r.returncode == 0 else (r.stdout + r.stderr).decode(errors="replace")


STAGES = {
    "one vowel": lambda c: c.group == "vowel" and c.text == "অ",
    "the vowels": lambda c: c.group == "vowel",
    "page 2: letters, signs, phala": lambda c: c.page == 2,
    "every Bangla cell": lambda c: c.kind != "latin",
}


@pytest.mark.parametrize("stage", STAGES)
def test_a_drawn_font_passes_ots(stage, tmp_path):
    cells = [c for c in build_layout().cells if STAGES[stage](c)]
    strokes = traced_cells([c.id for c in cells], seed=11)
    font = build_font([drawing(c, strokes[c.id]) for c in cells if strokes.get(c.id)], "OTS Test")
    assert sanitized(font.ttf, "ttf", tmp_path) == ""
    assert sanitized(font.woff2, "woff2", tmp_path) == ""


def test_a_mixed_font_passes_ots_as_preview_and_download(tmp_path):
    # Page 1 from a photo, page 2 drawn: the preview the browser loads, and the zip.
    strokes = {k: v for k, v in traced_cells(seed=11).items() if k.startswith("p2-")}
    with TestClient(main.app) as c:
        sid = c.post("/api/sessions").json()["id"]
        photo = make_page(1, "laser").photo_jpeg
        assert wait(c, c.post(f"/api/sessions/{sid}/pages", files={"photo": ("p.jpg", photo, "image/jpeg")}).json()["id"])["status"] == "done"
        c.put(f"/api/sessions/{sid}/drawn", json={"cells": strokes})
        job = wait(c, c.post(f"/api/sessions/{sid}/preview").json()["id"])
        assert job["status"] == "done", job
        meta = job["result"]["session"]
        assert sanitized(c.get(f"/api/sessions/{sid}/files/{meta['font']}").content, "woff2", tmp_path) == ""
        job = wait(c, c.post(f"/api/sessions/{sid}/download", json={"name": "Mixed", "format": "both"}).json()["id"])
        assert job["status"] == "done", job
        z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/sessions/{sid}/files/{job['result']['file']}").content))
        fonts = [n for n in z.namelist() if n.endswith((".ttf", ".woff2"))]
        assert {n.rsplit(".", 1)[1] for n in fonts} == {"ttf", "woff2"}
        for n in fonts:
            assert sanitized(z.read(n), n.rsplit(".", 1)[1], tmp_path) == "", n


def test_the_sites_own_fonts_pass_ots(tmp_path):
    # The grey boxes for missing letters, and (once built) the site's typefaces.
    files = [FRONTEND / "public" / "kt" / "missing.woff2", *sorted((FRONTEND / "out" / "_next" / "static" / "media").glob("*.woff2"))]
    for f in files:
        assert sanitized(f.read_bytes(), "woff2", tmp_path) == "", f.name
