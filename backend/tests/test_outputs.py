"""What a visitor takes away matches what the browser shows.

The PDF (and picture) of the try-it text and the font sheet are drawn by
the browser on a canvas. Here the real site saves "ইচ্ছা রাষ্ট্র বাংলা কিছু"
as a PDF, and its ink is compared with the browser's own rendering of the
same text, and with HarfBuzz's. A rendering of the same letters without
shaping (ি after its letter, no conjuncts) must not pass the comparison.

Needs the built site (frontend/out) and Playwright with Chromium; skipped
without them.
"""

import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from fontTools.ttLib import TTFont

from app.render import render_lines
from tests.live_site import SITE, api, drawn_session, live_site
from tests.synth_strokes import thin
from tests.trace_strokes import traced_cells

playwright = pytest.importorskip("playwright.sync_api")
pdfium = pytest.importorskip("pypdfium2")
if not (SITE / "index.html").exists():
    pytest.skip("the site isn't built (cd frontend && bun run build)", allow_module_level=True)

TEXT = "ইচ্ছা রাষ্ট্র বাংলা কিছু"
HEIGHT = 160  # px: every rendering is scaled to this ink height before comparing


def ink(img_bgr: np.ndarray) -> np.ndarray:
    """The navy ink, cropped to its box: not the rules, the red margin line,
    or the grey boxes of letters not drawn."""
    b, g, r = img_bgr[..., 0].astype(int), img_bgr[..., 1].astype(int), img_bgr[..., 2].astype(int)
    mask = (r < 120) & (g < 120) & (b < 150)
    ys, xs = np.nonzero(mask)
    crop = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    k = HEIGHT / crop.shape[0]
    return cv2.resize(crop.astype(np.uint8) * 255, (round(crop.shape[1] * k), HEIGHT), interpolation=cv2.INTER_AREA) > 96


def agreement(a: np.ndarray, b: np.ndarray) -> float:
    """How much of each one's centre line lies near the other's (within
    4 px), the smaller of the two; 1.0 is the same drawing. Centre lines,
    so stroke weight (anti-aliasing at another size) doesn't count; both
    stretched to one length, so whole-pixel advances in the browser don't
    add up to a drift."""
    w = (a.shape[1] + b.shape[1]) // 2
    a, b = (thin(cv2.resize(m.astype(np.uint8), (w, HEIGHT), interpolation=cv2.INTER_NEAREST) > 0) for m in (a, b))
    k = np.ones((9, 9), np.uint8)
    near_a, near_b = cv2.dilate(a.astype(np.uint8), k) > 0, cv2.dilate(b.astype(np.uint8), k) > 0
    return min((a & near_b).sum() / a.sum(), (b & near_a).sum() / b.sum())


def unshaped(font: bytes, text: str) -> np.ndarray:
    """Each character's own glyph, one after another, as typed: no reordering, no conjuncts."""
    tt = TTFont(io.BytesIO(font))
    cmap, hmtx = tt.getBestCmap(), tt["hmtx"]
    from app.outline import glyph_polygons

    gs, s, x = tt.getGlyphSet(), 0.2, 40
    img = np.full((260, 40 + round(sum(hmtx[cmap[ord(c)]][0] for c in text if ord(c) in cmap) * s) + 80, 3), 255, np.uint8)
    for c in text:
        name = cmap.get(ord(c))
        if not name:
            continue
        for p in glyph_polygons(gs, name):
            pts = np.array([(x + px * s, 200 - py * s) for px, py in p]) * 16
            cv2.fillPoly(img, [pts.astype(np.int32)], (0x40, 0x21, 0x1D), cv2.LINE_AA, shift=4)
        x += max(hmtx[name][0] * s, 0)
    return img


@pytest.fixture(scope="module")
def saved():
    """The site's PDF of TEXT, the browser's own rendering of it, and the font."""
    strokes = traced_cells(seed=11)  # every Bangla letter, sign and conjunct, drawn
    with live_site() as url:
        sid = drawn_session(url, strokes)
        meta = api(url, f"/api/sessions/{sid}")
        font = TTFont(io.BytesIO(api(url, f"/api/sessions/{sid}/files/{meta['font']}")))
        font.flavor = None
        ttf = io.BytesIO()
        font.save(ttf)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_context(viewport={"width": 390, "height": 740}, is_mobile=True, has_touch=True, accept_downloads=True).new_page()
            page.add_init_script(f"sessionStorage.setItem('kaker-theng-session', '{sid}'); sessionStorage.setItem('kaker-theng-screen', JSON.stringify({{name: 'font'}}))")
            page.goto(url + "/")
            page.wait_for_selector(".save-image", timeout=60_000)
            page.locator(".tryit textarea").fill(TEXT)
            with page.expect_download() as dl:
                page.get_by_role("button", name="PDF হিসেবে সেভ করুন").click()
            pdf = Path(dl.value.path()).read_bytes()
            with page.expect_download() as dl:
                page.get_by_role("button", name="ফন্ট শিট: PDF").click()
            sheet = Path(dl.value.path()).read_bytes()
            pictures = {}
            for button in ("ফন্ট শিট: ছবি", "ছবি: শুধু বাংলা অক্ষর"):
                with page.expect_download() as dl:
                    page.get_by_role("button", name=button).click()
                pictures[button] = cv2.imdecode(np.frombuffer(Path(dl.value.path()).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            # The browser's own rendering: the text in a plain element, in the font.
            family = page.locator(".tryit textarea").evaluate("e => getComputedStyle(e).fontFamily")
            page.evaluate(
                """([text, family]) => {
                  const d = document.createElement('div');
                  d.id = 'reference';
                  d.textContent = text;
                  Object.assign(d.style, {position: 'fixed', left: '0', top: '0', zIndex: 9, padding: '30px', background: '#fff',
                    color: '#1d2140', font: `96px ${family}`, whiteSpace: 'nowrap', lineHeight: '1.6'});
                  document.body.appendChild(d);
                }""",
                [TEXT, family],
            )
            page.set_viewport_size({"width": 1600, "height": 740})
            shot = page.locator("#reference").screenshot()
            browser.close()
    first = pdfium.PdfDocument(pdf)[0].render(scale=200 / 72).to_numpy()[..., :3]
    return {
        "pdf": ink(np.ascontiguousarray(first)),
        "browser": ink(cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)),
        "font": ttf.getvalue(),
        "sheet": pdfium.PdfDocument(sheet),
        "full picture": pictures["ফন্ট শিট: ছবি"],
        "letters picture": pictures["ছবি: শুধু বাংলা অক্ষর"],
    }


def test_the_pdf_matches_the_browser(saved):
    assert agreement(saved["pdf"], saved["browser"]) > 0.95


def test_the_pdf_matches_harfbuzz(saved):
    # The same text shaped by HarfBuzz itself, from the same font file.
    hb = ink(render_lines(saved["font"], [TEXT], px_per_em=120))
    assert agreement(saved["pdf"], hb) > 0.95


def test_an_unshaped_rendering_does_not_pass(saved):
    # ি after ক, conjuncts in pieces: the comparison must tell.
    wrong = ink(unshaped(saved["font"], TEXT))
    assert agreement(saved["pdf"], wrong) < 0.7


def test_the_font_sheet_is_a4_pages(saved):
    doc = saved["sheet"]
    assert len(doc) >= 2  # 113 drawn letters at 8 a row
    w, h = doc[0].get_size()
    assert abs(w - 595.28) < 1 and abs(h - 841.89) < 1


def test_the_bangla_letters_picture_fits_about_two_screens(saved):
    full, letters = saved["full picture"], saved["letters picture"]
    assert full.shape[1] == letters.shape[1] == 1080
    assert letters.shape[0] <= 2 * 1920 and letters.shape[0] < full.shape[0]


def test_conjuncts_put_together_from_pieces_are_grey_on_the_sheet(saved):
    # GREY in frontend/lib/khata.ts, #8a847a: only in the conjunct cells that
    # were put together, never in the letters-only picture.
    def grey(img) -> int:
        mask = (np.abs(img.astype(int) - (0x7A, 0x84, 0x8A)).max(axis=2) < 12).astype(np.uint8)
        # Strokes are several px wide; anti-aliased edges of pencil labels are 1 px.
        return int(cv2.erode(mask, np.ones((3, 3), np.uint8)).sum())

    assert grey(saved["full picture"]) > 500  # 13 conjuncts: about 1400
    assert grey(saved["letters picture"]) < 50  # none: about 0

