"""The site's icons and link-preview picture, from the mark.

    python -X utf8 -m scripts.make_icons [../frontend]

Reads public/favicon.svg and public/mark.svg and writes, into public/:
- favicon.ico: 16, 32 and 48 px, each drawn at its own size
- apple-touch-icon.png: 180 px, on the paper colour (favicon.svg has it)
- og.png: 1200x630, the mark on paper with "কাকের ঠ্যাং / Kaker Theng", what
  Facebook and WhatsApp show for a shared link

Chromium draws them (Playwright, as scripts/ui_check.py), so the SVG renders
as a browser renders it. The name is set in the site's own Tiro Bangla and
Spectral, taken from the built site (frontend/out): build it first.
"""

import base64
import io
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image
from playwright.sync_api import sync_playwright

FRONTEND = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "frontend")
PUBLIC = FRONTEND / "public"
MEDIA = FRONTEND / "out" / "_next" / "static" / "media"
ICO_SIZES = (16, 32, 48)
TOUCH = 180
OG = (1200, 630)
PAPER, INK, PENCIL = "#F4F0E6", "#1D2140", "#6E685D"


def site_font(family: str, text: str) -> str:
    """A data: URL of the built site's file of `family` that has every letter of `text`."""
    for f in sorted(MEDIA.glob("*.woff2")):
        tt = TTFont(f)
        cmap = tt.getBestCmap()
        if tt["name"].getDebugName(1) == family and all(ord(c) in cmap for c in text if c != " "):
            return "data:font/woff2;base64," + base64.b64encode(f.read_bytes()).decode()
    raise SystemExit(f"no {family} file with {text!r} in {MEDIA}: build the site first (cd frontend && bun run build)")


def og_html() -> str:
    mark = (PUBLIC / "mark.svg").read_text(encoding="utf-8")
    tiro = site_font("Tiro Bangla", "কাকের ঠ্যাং")
    spectral = site_font("Spectral", "Kaker Theng")
    return f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: Tiro; src: url({tiro}); }}
@font-face {{ font-family: Spectral; src: url({spectral}); }}
html, body {{ margin: 0; }}
#og {{ width: {OG[0]}px; height: {OG[1]}px; background: {PAPER}; display: flex; align-items: center; justify-content: center; gap: 56px; }}
#og svg {{ height: 400px; width: auto; flex: none; }}
#og h1 {{ font: 400 136px/1.15 Tiro; color: {INK}; margin: 0; }}
#og p {{ font: 400 64px/1.2 Spectral; color: {PENCIL}; margin: 8px 0 0 6px; }}
</style><div id="og">{mark}<div><h1>কাকের ঠ্যাং</h1><p>Kaker Theng</p></div></div>"""


def main():
    favicon = (PUBLIC / "favicon.svg").read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=1)

        def icon(size: int) -> Image.Image:
            page.set_content(f'<!doctype html><style>html,body{{margin:0}} svg{{display:block;width:{size}px;height:{size}px}}</style>{favicon}')
            return Image.open(io.BytesIO(page.locator("svg").screenshot())).convert("RGBA")

        icons = [icon(s) for s in ICO_SIZES]
        icons[-1].save(PUBLIC / "favicon.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=icons[:-1])
        icon(TOUCH).convert("RGB").save(PUBLIC / "apple-touch-icon.png", optimize=True)

        page.set_viewport_size({"width": OG[0], "height": OG[1]})
        page.set_content(og_html())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(200)
        Image.open(io.BytesIO(page.locator("#og").screenshot())).convert("RGB").save(PUBLIC / "og.png", optimize=True)
        browser.close()
    for name in ("favicon.ico", "apple-touch-icon.png", "og.png"):
        print(f"{name}: {(PUBLIC / name).stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
