"""Drive the drawing screen in a headless browser and take screenshots.

    python -X utf8 -m scripts.draw_check <site url> <strokes.json> <screenshots dir>

Draws the first letters of the drawing order by replaying synthetic strokes
(tests/synth_strokes.py): with the mouse at desktop width, with real touch
events (Chrome DevTools) at phone width. Checks that the canvas is fully on
screen, that touch never scrolls or zooms the page, how often the preview
is rebuilt, the language tabs, the draft surviving a reload, and redrawing
from the specimen. Dev only (Playwright).
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

base, strokes_path, shots = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
shots.mkdir(parents=True, exist_ok=True)
STROKES = json.loads(strokes_path.read_text(encoding="utf-8"))
problems: list[str] = []


def check(ok: bool, what: str):
    print(f"  [{'ok' if ok else 'FAIL'}] {what}", flush=True)
    if not ok:
        problems.append(what)


def current_cell(page) -> str:
    return page.locator(".draw-canvas canvas").get_attribute("aria-label").split("Drawing box for ")[1].rstrip(".")


def to_screen(page, stroke, g):
    box = page.locator(".draw-canvas canvas").bounding_box()
    return [(box["x"] + x / g["w"] * box["width"], box["y"] + y / g["h"] * box["height"]) for x, y in stroke]


def draw_mouse(page, cell_id, g):
    for stroke in STROKES[cell_id]:
        pts = to_screen(page, stroke, g)
        page.mouse.move(*pts[0])
        page.mouse.down()
        for p in pts[1:]:
            page.mouse.move(*p, steps=2)
        page.mouse.up()


def draw_touch(page, cdp, cell_id, g):
    for stroke in STROKES[cell_id]:
        pts = to_screen(page, stroke, g)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": pts[0][0], "y": pts[0][1]}]})
        for x, y in pts[1:]:
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def run(name: str, viewport: dict, letters: int, touch: bool):
    errors, previews = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=viewport, device_scale_factor=2 if touch else 1, has_touch=touch, is_mobile=touch)
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page) if touch else None
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("request", lambda r: r.url.endswith("/preview") and previews.append(r.url))
        page.goto(base + "/")
        page.wait_for_selector("text=কাকের ঠ্যাং")
        page.screenshot(path=shots / f"{name}-1-choice.png")
        page.get_by_role("button", name="আঁকুন · draw").click()
        page.get_by_role("button", name="বাংলা আগে · Bangla first").click()
        page.wait_for_selector(".draw-canvas canvas")
        page.wait_for_timeout(500)
        layout = page.evaluate("fetch('/kt/layout.json').then(r => r.json())")
        cells = {c["id"]: c for pg in layout["pages"].values() for c in pg["cells"]}
        by_text = {c["text"]: c["id"] for c in cells.values()}

        box = page.locator(".draw-canvas canvas").bounding_box()
        vh = page.evaluate("innerHeight")
        check(box["y"] >= 0 and box["y"] + box["height"] <= vh, f"{name}: whole canvas on screen without scrolling ({box['width']:.0f}x{box['height']:.0f} px, bottom {box['y'] + box['height']:.0f} of {vh})")
        page.screenshot(path=shots / f"{name}-2-start.png")

        for i in range(letters):
            cid = by_text[current_cell(page)]
            g = cells[cid]["draw"]
            before = page.evaluate("[scrollX, scrollY, visualViewport.scale]")
            (draw_touch(page, cdp, cid, g) if touch else draw_mouse(page, cid, g))
            after = page.evaluate("[scrollX, scrollY, visualViewport.scale]")
            if touch and i == 0:
                check(before == after, f"{name}: touch drawing doesn't scroll or zoom ({before} -> {after})")
            if not page.get_by_role("button", name="ফেরান · undo").is_enabled():
                page.screenshot(path=shots / f"{name}-fail.png")
                raise SystemExit(f"{name}: strokes on {cid} didn't register")
            if i < letters - 1:
                page.get_by_role("button", name="পরের · next").click()

        if touch:
            # A deliberate flick up and a pinch on the canvas: still no scroll, no zoom.
            b = page.locator(".draw-canvas canvas").bounding_box()
            cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            before = page.evaluate("[scrollY, visualViewport.scale]")
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx, "y": cy + 80}]})
            for k in range(1, 9):
                cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx, "y": cy + 80 - 30 * k}]})
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx - 20, "y": cy, "id": 1}, {"x": cx + 20, "y": cy, "id": 2}]})
            for k in range(1, 9):
                cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx - 20 - 12 * k, "y": cy, "id": 1}, {"x": cx + 20 + 12 * k, "y": cy, "id": 2}]})
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            page.wait_for_timeout(300)
            after = page.evaluate("[scrollY, visualViewport.scale]")
            check(before == after, f"{name}: a flick and a pinch on the canvas don't scroll or zoom ({before} -> {after})")
            page.get_by_role("button", name="ফেরান · undo").click()  # take back the flick's stroke

        # Rebuilds: after every 5 letters or 3 s without drawing, not per letter.
        page.wait_for_selector("text=You can write", timeout=240_000)
        page.wait_for_function("[...document.fonts].some(f => f.status === 'loaded' && f.family.startsWith('KakerThengUser'))", timeout=60_000)
        page.wait_for_timeout(3500)
        check(len(previews) <= letters // 5 + 2, f"{name}: {len(previews)} preview rebuild(s) for {letters} letters")
        page.locator("#drawpad").scroll_into_view_if_needed()
        page.evaluate("document.getElementById('drawpad').scrollIntoView({block: 'start'})")
        page.screenshot(path=shots / f"{name}-3-drawing.png")
        page.locator(".drawpad").screenshot(path=shots / f"{name}-3-drawpad.png")

        # Closing the tab mid-letter: the draft comes back.
        page.reload()
        page.wait_for_selector(".draw-canvas canvas")
        check(page.get_by_role("button", name="ফেরান · undo").is_enabled(), f"{name}: the unfinished letter is back after a reload")

        # Language tabs.
        page.get_by_role("tab", name="English").click()
        page.wait_for_timeout(200)
        check(current_cell(page) == "e", f"{name}: the English tab starts at the most useful letter ({current_cell(page)})")
        page.screenshot(path=shots / f"{name}-4-english.png")
        page.get_by_role("tab", name="বাংলা").click()

        # Redraw from the specimen: tap a Bangla letter that was drawn.
        first = layout["draw_order"][0]
        page.locator(f".glyph[aria-label^='{cells[first]['text']}']").first.click()
        page.wait_for_timeout(400)
        check(current_cell(page) == cells[first]["text"], f"{name}: tapping {cells[first]['text']} in the specimen opens it on the canvas")
        box = page.locator(".draw-canvas canvas").bounding_box()
        check(box["y"] >= 0 and box["y"] + box["height"] <= page.evaluate("innerHeight"), f"{name}: ...with the canvas on screen")

        # A fragment cell, through the saved position.
        saved = page.evaluate("JSON.parse(localStorage.getItem('kaker-theng-drawn-v1'))")
        saved["at"] = next(i for i in layout["draw_order"] if cells[i]["fragment"])
        page.evaluate("s => localStorage.setItem('kaker-theng-drawn-v1', JSON.stringify(s))", saved)
        page.reload()
        page.wait_for_selector(".draw-example")
        page.evaluate("document.getElementById('drawpad').scrollIntoView({block: 'start'})")
        page.screenshot(path=shots / f"{name}-5-fragment.png")
        check(not errors, f"{name}: no console errors ({errors[:2]})")
        browser.close()


run("desktop", {"width": 1280, "height": 900}, letters=12, touch=False)
run("phone", {"width": 390, "height": 844}, letters=7, touch=True)
print("\n" + ("all checks passed" if not problems else f"{len(problems)} problem(s): " + "; ".join(problems)))
