"""Drive the drawing screen in a headless browser and take screenshots.

    python -X utf8 -m scripts.draw_check <site url> <strokes.json> <screenshots dir>

Draws the first letters of the drawing order by replaying synthetic strokes
(tests/synth_strokes.py) as mouse movements on the canvas, at desktop and
phone width. Dev only (Playwright).
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

base, strokes_path, shots = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
shots.mkdir(parents=True, exist_ok=True)
STROKES = json.loads(strokes_path.read_text(encoding="utf-8"))


def draw_letter(page, cell_id: str, w: float, h: float):
    canvas = page.locator(".draw-canvas canvas")
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    for stroke in STROKES[cell_id]:
        pts = [(box["x"] + x / w * box["width"], box["y"] + y / h * box["height"]) for x, y in stroke]
        page.mouse.move(*pts[0])
        page.mouse.down()
        for p in pts[1:]:
            page.mouse.move(*p, steps=2)
        page.mouse.up()


def run(name: str, viewport: dict, letters: int, scale: float = 1):
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=viewport, device_scale_factor=scale)
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(base + "/")
        page.wait_for_selector("text=কাকের ঠ্যাং")
        page.screenshot(path=shots / f"{name}-1-choice.png")
        page.get_by_role("button", name="আঁকুন · draw").click()
        page.wait_for_selector(".draw-canvas canvas")
        layout = page.evaluate("fetch('/kt/layout.json').then(r => r.json())")
        cells = {c["id"]: c for pg in layout["pages"].values() for c in pg["cells"]}
        page.locator("#draw-title").scroll_into_view_if_needed()
        page.screenshot(path=shots / f"{name}-2-empty.png")
        for i in range(letters):
            cid = page.locator(".draw-target .mono").inner_text().split(". ")[1]
            g = cells[cid]["draw"]
            draw_letter(page, cid, g["w"], g["h"])
            if not page.get_by_role("button", name="ফেরান · undo").is_enabled():
                page.screenshot(path=shots / f"{name}-fail.png")
                raise SystemExit(f"{name}: strokes on {cid} didn't register")
            if i == letters - 1:
                break
            page.get_by_role("button", name="পরের · next").click()
        # Coverage and the sample line appear once the first preview font is built.
        page.wait_for_selector("text=of real Bangla text covered", timeout=240_000)
        page.wait_for_function("[...document.fonts].some(f => f.status === 'loaded' && f.family.startsWith('KakerThengUser'))", timeout=60_000)
        page.wait_for_timeout(800)
        page.locator("#draw-title").scroll_into_view_if_needed()
        page.screenshot(path=shots / f"{name}-3-drawing.png", full_page=False)
        page.locator(".drawpad").screenshot(path=shots / f"{name}-3-drawpad.png")
        saved = page.evaluate("JSON.parse(localStorage.getItem('kaker-theng-drawn-v1'))")
        draft = saved.get("draft") or {}
        print(f"{name}: drew {letters} letters; saved locally: {len(saved['cells'])} cells + draft of {draft.get('id')} "
              f"({len(draft.get('strokes', []))} strokes), at {saved['at']}; console errors: {errors or 'none'}")
        # Closing the tab mid-letter: the draft comes back.
        page.reload()
        page.wait_for_selector(".draw-canvas canvas")
        restored = page.get_by_role("button", name="ফেরান · undo").is_enabled()
        print(f"{name}: after reload, the unfinished letter is {'back' if restored else 'LOST'}")
        # A fragment cell: jump there through the saved position, reload (also checks restoring).
        part = next(i for i in layout["draw_order"] if cells[i]["fragment"])
        saved["at"] = part
        page.evaluate("s => localStorage.setItem('kaker-theng-drawn-v1', JSON.stringify(s))", saved)
        page.reload()
        page.wait_for_selector(".draw-example")
        page.locator(".drawpad").screenshot(path=shots / f"{name}-4-fragment.png")
        print(f"{name}: after reload, on {page.locator('.draw-target .mono').inner_text()}, {page.locator('.draw-progress .mono').inner_text()}")
        browser.close()


run("desktop", {"width": 1280, "height": 900}, letters=8)
run("phone", {"width": 390, "height": 844}, letters=4, scale=2)
