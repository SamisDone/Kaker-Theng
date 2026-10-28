"""A Bangla-only, English-only or combined font, and what each must be.

The three are built from the same drawing (pages 1 and 2) and each must:
pass OTS (what browsers run), carry its own family name in every record an
app or the system tells fonts apart by (1, 3, 4, 6, 16), so all three install
side by side, and hold only its own language: the English one no Bengali
glyph or layout table, the Bangla one no English letter. On Windows each is
loaded through GDI, all three at once, and each must be found by its own
name. The API offers each, and refuses a language with nothing drawn.
"""

import ctypes
import io
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient
from fontTools.ttLib import TTFont

from app import main
from app.basefont import Shaper
from app.englishcov import english_coverage, writable_english_sentences, writable_english_words
from app.fontbuild import BANGLA_TEXT_LATIN, build_font, postscript_name
from app.glyphmap import build_layout
from app.strokes import drawing
from tests.synth_strokes import drawn_cells
from tests.test_ots import sanitized
from tests.test_strokes import wait

FAMILY = "Test Hand"
NAMES = {"both": "Test Hand", "bn": "Test Hand Bangla", "en": "Test Hand English"}
BENGALI = set(range(0x0980, 0x0A00)) | {0x0964, 0x0965, 0x200C, 0x200D, 0x25CC}


@pytest.fixture(scope="module")
def strokes():
    return {k: v for k, v in drawn_cells((1, 2)).items() if v}


@pytest.fixture(scope="module")
def fonts(strokes):
    cells = {c.id: c for c in build_layout().cells}
    drawings = [drawing(cells[k], v) for k, v in strokes.items()]
    return {script: build_font(drawings, FAMILY, script) for script in NAMES}


@pytest.mark.parametrize("script", NAMES)
def test_each_font_passes_ots(fonts, script, tmp_path):
    assert sanitized(fonts[script].ttf, "ttf", tmp_path) == ""
    assert sanitized(fonts[script].woff2, "woff2", tmp_path) == ""


@pytest.mark.parametrize("script", NAMES)
def test_each_font_has_its_own_names(fonts, script):
    tt = TTFont(io.BytesIO(fonts[script].ttf))
    name = tt["name"]
    ps = {"both": "TestHand-Regular", "bn": "TestHandBangla-Regular", "en": "TestHandEnglish-Regular"}[script]
    assert name.getDebugName(1) == NAMES[script]
    assert name.getDebugName(4) == NAMES[script]
    assert name.getDebugName(16) == NAMES[script]
    assert name.getDebugName(6) == ps
    assert name.getDebugName(3).endswith(ps)
    # Every record of those IDs, on every platform, says the same.
    for rec in name.names:
        if rec.nameID in (1, 4, 16):
            assert rec.toUnicode() == NAMES[script]


def test_no_two_fonts_share_a_name(fonts):
    for nid in (1, 3, 4, 6, 16):
        values = [TTFont(io.BytesIO(f.ttf))["name"].getDebugName(nid) for f in fonts.values()]
        assert len(set(values)) == 3, (nid, values)


def test_english_font_is_plain_latin(fonts):
    tt = TTFont(io.BytesIO(fonts["en"].ttf))
    cmap = tt.getBestCmap()
    assert not set(cmap) & BENGALI
    assert all(cp < 0x80 or cp == 0xA0 for cp in cmap), sorted(hex(c) for c in cmap if c >= 0x80)
    assert not {"GSUB", "GPOS", "GDEF"} & set(tt.keys())
    assert not [g for g in tt.getGlyphOrder() if "beng" in g or "deva" in g]
    assert not [n for n in tt["name"].names if n.nameID >= 256]  # feature names had nothing left to name
    assert set("Hello, world!") - {" "} <= {chr(c) for c in cmap}
    # Only the 76 cells' glyphs, .notdef, space and no-break space.
    assert len(tt.getGlyphOrder()) == 76 + 3


def test_bangla_font_has_no_english_letters(fonts):
    tt = TTFont(io.BytesIO(fonts["bn"].ttf))
    latin = {chr(c) for c in tt.getBestCmap() if 0x21 <= c < 0x7F}
    assert latin <= BANGLA_TEXT_LATIN, latin
    assert set(",?!'\"") <= latin  # what Bangla text uses, drawn on page 1
    assert not latin & set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    assert {"GSUB", "GPOS"} <= set(tt.keys())
    # Still shapes Bangla: ি goes before its letter, প্র takes the ra-phala.
    shaper = Shaper(fonts["bn"].ttf)
    assert shaper.names("কি")[0] == shaper.names("ি")[0]
    assert "halant-beng" not in shaper.names("প্র")


def test_combined_font_has_both(fonts):
    tt = TTFont(io.BytesIO(fonts["both"].ttf))
    chars = {chr(c) for c in tt.getBestCmap()}
    assert {"A", "z", "ক", "অ", "।"} <= chars


def test_bangla_names_get_distinct_postscript_names():
    # No ASCII in the name: the hash stands in, and the suffix still differs.
    names = {postscript_name("আমার হাতের লেখা", s) for s in ("", "Bangla", "English")}
    assert len(names) == 3
    assert all(len(n) <= 63 and n.isascii() for n in names)
    assert all(len(postscript_name("X" * 40, s)) <= 63 for s in ("", "Bangla", "English"))


def test_postscript_name_is_ascii_in_every_font_even_for_a_bangla_name(strokes):
    """nameID 6 must be printable ASCII (no spaces, at most 63) in every
    record of every variant; the family names (1, 4, 16) keep the name as typed."""
    cells = {c.id: c for c in build_layout().cells}
    drawings = [drawing(cells[k], v) for k, v in strokes.items()]
    seen = set()
    for script in NAMES:
        tt = TTFont(io.BytesIO(build_font(drawings, "আমার হাতের লেখা", script).ttf))
        records = [n.toUnicode() for n in tt["name"].names if n.nameID == 6]
        assert records
        for ps in records:
            assert ps.isascii() and ps.isprintable() and " " not in ps and len(ps) <= 63, (script, ps)
        seen.add(records[0])
        assert tt["name"].getDebugName(1) == ("আমার হাতের লেখা " + {"both": "", "bn": "Bangla", "en": "English"}[script]).rstrip()
    assert len(seen) == 3, seen


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_all_three_load_on_windows_side_by_side(fonts, tmp_path):
    """GDI, as an installed font: loaded (privately, for this process only),
    each must be found by its own family name, with all three loaded at
    once. A name Windows didn't take would come back as a substitute."""
    gdi32, user32 = ctypes.WinDLL("gdi32"), ctypes.WinDLL("user32")
    gdi32.CreateFontW.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.GetTextFaceW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    gdi32.GetGlyphIndicesW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ushort), ctypes.c_uint]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    FR_PRIVATE, GGI_MARK_NONEXISTING_GLYPHS = 0x10, 1
    paths = {}
    for script, f in fonts.items():
        paths[script] = tmp_path / f"{script}.ttf"
        paths[script].write_bytes(f.ttf)
    loaded = {s: gdi32.AddFontResourceExW(str(p), FR_PRIVATE, None) for s, p in paths.items()}
    hdc = user32.GetDC(None)
    try:
        assert all(n == 1 for n in loaded.values()), loaded
        for script, family in NAMES.items():
            font = gdi32.CreateFontW(-48, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, family)
            old = gdi32.SelectObject(hdc, font)
            face = ctypes.create_unicode_buffer(64)
            gdi32.GetTextFaceW(hdc, 64, face)
            # The font's own letter, not the substitute's: "A" is in the
            # English and combined fonts, "ক" in the Bangla one.
            probe = "ক" if script == "bn" else "A"
            index = (ctypes.c_ushort * 1)()
            gdi32.GetGlyphIndicesW(hdc, probe, 1, index, GGI_MARK_NONEXISTING_GLYPHS)
            gdi32.SelectObject(hdc, old)
            gdi32.DeleteObject(font)
            assert face.value == family, (script, face.value)
            assert index[0] != 0xFFFF, (script, probe)
    finally:
        user32.ReleaseDC(None, hdc)
        for p in paths.values():
            gdi32.RemoveFontResourceExW(str(p), FR_PRIVATE, None)


def test_the_api_offers_each_and_refuses_a_language_not_drawn(strokes):
    bangla_only = {k: v for k, v in strokes.items() if k.startswith("p2-")}
    with TestClient(main.app) as c:
        sid = c.post("/api/sessions").json()["id"]
        c.put(f"/api/sessions/{sid}/drawn", json={"cells": bangla_only})
        r = c.post(f"/api/sessions/{sid}/download", json={"name": FAMILY, "script": "en"})
        assert r.status_code == 400 and r.json()["code"] == "no_script"
        assert c.post(f"/api/sessions/{sid}/download", json={"name": FAMILY, "script": "xx"}).status_code == 400

        c.put(f"/api/sessions/{sid}/drawn", json={"cells": strokes})
        meta = wait(c, c.post(f"/api/sessions/{sid}/preview").json()["id"])["result"]["session"]
        assert meta["scripts"] == ["bn", "en"]
        assert meta["en_word_coverage"] > 0.95  # every English letter drawn
        assert meta["en_sentences"][0] == "The quick brown fox jumps over the lazy dog."
        for script, family in NAMES.items():
            job = wait(c, c.post(f"/api/sessions/{sid}/download", json={"name": FAMILY, "script": script}).json()["id"])
            assert job["status"] == "done", job
            assert job["result"]["family"] == family
            z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/sessions/{sid}/files/{job['result']['file']}").content))
            ttf = next(n for n in z.namelist() if n.endswith(".ttf"))
            assert TTFont(io.BytesIO(z.read(ttf)))["name"].getDebugName(1) == family
            assert z.read("README.txt").decode().startswith(family)


def test_english_measure():
    lower = set("abcdefghijklmnopqrstuvwxyz")
    # Lowercase alone writes almost every common word, but not "I".
    assert 0.9 < english_coverage(lower) < 1
    assert "I" not in writable_english_words(lower, 5000)
    assert "I" in writable_english_words(lower | {"I"}, 50)
    assert english_coverage(lower | {"I", "'"}) > english_coverage(lower)
    assert english_coverage(set("etaoin")) < 0.3
    assert english_coverage(set()) == 0
    # A sentence written but for its full stop comes without it.
    assert "I like to write" in writable_english_sentences(lower | {"I", " "})
