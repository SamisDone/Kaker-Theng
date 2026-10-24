"""Draw chapters on the site with touch events and download the font it makes.

    python -X utf8 -m scripts.ui_font <site url> <strokes.json> <out dir> [chapter ...]

A phone-sized headless browser (Playwright) opens the site, taps আঁকুন and
draws every letter of the given chapters (default: স্বরবর্ণ ব্যঞ্জনবর্ণ
কার-চিহ্ন ফলা ও রেফ) by replaying strokes ({cell id: strokes in cell mm})
as touch events on the canvas: the browser's own point handling, the
server's own build. Then downloads the font (zip, TTF) to <out dir>/ui.ttf
and the strokes the site sent, as the site exports them, to
<out dir>/ui-strokes.json. Dev only.
"""

import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

base, strokes_path, out = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
chapters = sys.argv[4:] or ["স্বরবর্ণ", "ব্যঞ্জনবর্ণ", "কার-চিহ্ন", "ফলা ও রেফ"]
STROKES = json.loads(strokes_path.read_text(encoding="utf-8"))
out.mkdir(parents=True, exist_ok=True)


def api(path: str, body: dict | None = None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def touch(page, cdp, strokes, g):
    box = page.locator(".draw-canvas canvas").bounding_box()
    for stroke in strokes:
        pts = [(box["x"] + x / g["w"] * box["width"], box["y"] + y / g["h"] * box["height"]) for x, y in stroke]
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": pts[0][0], "y": pts[0][1]}]})
        for x, y in pts[1:]:
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 740}, device_scale_factor=3, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    page.goto(base + "/")
    layout = page.evaluate("fetch('/kt/layout.json').then(r => r.json())")
    cells = {c["id"]: c for pg in layout["pages"].values() for c in pg["cells"]}
    by_text = {c["text"]: c["id"] for c in cells.values()}
    page.get_by_role("button", name="আঁকুন").click()
    for i, chapter in enumerate(chapters):
        if i:
            page.wait_for_selector(".reward-body")
            page.go_back()  # from the reward to the drawing, for the chapter list
            page.locator(".chapter-button").click()
            page.get_by_role("button", name=chapter).click()
        page.get_by_role("button", name="শুরু করুন →").click()
        n = 0
        while page.locator(".draw-canvas canvas").count():
            label = page.locator(".draw-canvas canvas").get_attribute("aria-label")
            cid = by_text[label.split("Drawing box for ")[1].rstrip(".")]
            touch(page, cdp, STROKES[cid], cells[cid]["draw"])
            page.get_by_role("button", name="পরের →").click()
            n += 1
        print(f"{chapter}: {n} letters", flush=True)
    page.wait_for_selector(".reward-body")
    # What the site sent, as the export gives it.
    sent = page.evaluate("JSON.parse(localStorage.getItem('kaker-theng-drawn-v1')).cells")
    (out / "ui-strokes.json").write_text(json.dumps(sent), encoding="utf-8")
    session = page.evaluate("sessionStorage.getItem('kaker-theng-session')")
    browser.close()

# The server has every letter (each "next" sent it); build the download.
job = json.loads(api(f"/api/sessions/{session}/download", {"name": "UI Test"}))
while job["status"] not in ("done", "error"):
    time.sleep(1)
    job = json.loads(api(f"/api/jobs/{job['id']}"))
z = zipfile.ZipFile(io.BytesIO(api(f"/api/sessions/{session}/files/{job['result']['file']}")))
(out / "ui.ttf").write_bytes(z.read(next(n for n in z.namelist() if n.endswith(".ttf"))))
print(f"session {session}: {len(sent)} letters sent; font -> {out / 'ui.ttf'}")
