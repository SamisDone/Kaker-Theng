"""Walk the site's screens in a headless phone browser and take screenshots.

    python -X utf8 -m scripts.draw_check <site url> <strokes.json> <screenshots dir> [page photo]

Draws the vowels and consonants by replaying synthetic strokes
(tests/synth_strokes.py) with real touch events (Chrome DevTools), at phone
size. Checks that the drawing screen never scrolls (not while drawing, not
from letter to letter), that the canvas stays right of the margin line and
on screen, that nothing in the top bar overflows, the chapter reward, the
language switch, the back button, the draft surviving a reload, redrawing
from the specimen, saving the try-it text as an image, the hidden strokes
export (long-press and ?debug=1), and the paper steps. Prints every letter's hint. Dev
only (Playwright).
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

base, strokes_path, shots = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
photo = Path(sys.argv[4]) if len(sys.argv) > 4 else None
shots.mkdir(parents=True, exist_ok=True)
STROKES = json.loads(strokes_path.read_text(encoding="utf-8"))
problems: list[str] = []


def check(ok: bool, what: str):
    print(f"  [{'ok' if ok else 'FAIL'}] {what}", flush=True)
    if not ok:
        problems.append(what)


def canvas(page):
    return page.locator(".draw-canvas canvas")


def current_cell(page) -> str:
    return canvas(page).get_attribute("aria-label").split("Drawing box for ")[1].rstrip(".")


def draw_touch(page, cdp, strokes, g):
    box = canvas(page).bounding_box()
    for stroke in strokes:
        pts = [(box["x"] + x / g["w"] * box["width"], box["y"] + y / g["h"] * box["height"]) for x, y in stroke]
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": pts[0][0], "y": pts[0][1]}]})
        for x, y in pts[1:]:
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def fits(page) -> tuple[bool, str]:
    """The drawing screen: no page scroll, canvas on screen and right of the margin line."""
    m = page.evaluate(
        """() => {
          const c = document.querySelector('.draw-canvas canvas').getBoundingClientRect();
          const margin = document.querySelector('.sheet').getBoundingClientRect().left + parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--margin-x')) + 1.5;
          const bar = document.querySelector('.topbar');
          const nextEl = document.querySelector('.button.next'), next = nextEl.getBoundingClientRect();
          const clipped = [...document.querySelectorAll('.draw-actions button, .topbar button')].filter(b => b.scrollWidth > b.clientWidth + 1).map(b => b.innerText);
          return {sh: document.documentElement.scrollHeight, ih: innerHeight, sw: document.documentElement.scrollWidth, iw: innerWidth,
                  left: c.left, right: c.right, top: c.top, bottom: c.bottom, w: c.width, margin,
                  bar: bar.scrollWidth <= bar.clientWidth, nextBottom: next.bottom, y: scrollY, clipped}
        }"""
    )
    ok = m["sh"] <= m["ih"] and m["sw"] <= m["iw"] and m["left"] >= m["margin"] and m["right"] <= m["iw"] and m["top"] >= 0 and m["nextBottom"] <= m["ih"] and m["bar"] and m["y"] == 0 and not m["clipped"]
    return ok, f"page {m['sw']}x{m['sh']} in {m['iw']}x{m['ih']}, canvas {m['w']:.0f}px at x {m['left']:.0f} (margin line {m['margin']:.0f}), next button bottom {m['nextBottom']:.0f}, top bar fits {m['bar']}, clipped buttons {m['clipped']}"


def draw_chapter(page, cdp, cells, by_text, shot_prefix=None):
    """Draw every letter of the chapter on screen; stop at the reward."""
    n = 0
    while page.locator(".draw-canvas canvas").count():
        cid = by_text[current_cell(page)]
        before = page.evaluate("[scrollX, scrollY, visualViewport.scale]")
        draw_touch(page, cdp, STROKES[cid], cells[cid]["draw"])
        after = page.evaluate("[scrollX, scrollY, visualViewport.scale]")
        if before != after:
            check(False, f"drawing {cells[cid]['text']} moved the page ({before} -> {after})")
        if shot_prefix and n == 1:
            page.screenshot(path=shots / f"{shot_prefix}.png")
        page.get_by_role("button", name="পরের →").click()
        n += 1
    return n


def hints(page, chapter_name: str) -> list[str]:
    """Every letter's hint in a chapter, by skipping through it."""
    if page.locator(".reward-body").count():  # skipped past the last one
        page.go_back()
    page.locator(".chapter-button").click()
    page.get_by_role("button", name=chapter_name).click()
    if page.get_by_role("button", name="শুরু করুন →").count():
        page.get_by_role("button", name="শুরু করুন →").click()
    out, seen = [], set()
    while page.locator(".draw-canvas canvas").count():
        letter = page.locator(".draw-letter").inner_text()
        if letter in seen:
            break
        seen.add(letter)
        out.append(f"{letter}: {page.locator('.draw-hint').inner_text()}")
        page.get_by_role("button", name="বাদ দিন").click()
    return out


def run(name: str, viewport: dict):
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=viewport, device_scale_factor=3, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        page.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource") and errors.append(m.text))
        page.on("response", lambda r: r.status >= 400 and errors.append(f"{r.status} {r.url}"))
        page.goto(base + "/")
        page.wait_for_selector("text=কাকের ঠ্যাং")
        page.wait_for_timeout(800)
        layout = page.evaluate("fetch('/kt/layout.json').then(r => r.json())")
        cells = {c["id"]: c for pg in layout["pages"].values() for c in pg["cells"]}
        by_text = {c["text"]: c["id"] for c in cells.values()}
        page.screenshot(path=shots / f"{name}-01-start.png")
        check(page.evaluate("document.documentElement.scrollHeight <= innerHeight"), f"{name}: the start screen doesn't scroll")

        # Draw -> the vowels' card -> the first vowel, a whole letter.
        page.get_by_role("button", name="আঁকুন").click()
        page.wait_for_selector(".card-body")
        page.screenshot(path=shots / f"{name}-02-card-vowels.png")
        page.get_by_role("button", name="শুরু করুন →").click()
        page.wait_for_selector(".draw-canvas canvas")
        page.wait_for_timeout(300)
        ok, what = fits(page)
        check(ok, f"{name}: drawing screen fits: {what}")
        page.screenshot(path=shots / f"{name}-03-draw-first.png")
        first = current_cell(page)
        check(cells[by_text[first]]["group"] == "vowel" and not cells[by_text[first]]["ghost"], f"{name}: the first letter is a whole vowel ({first})")

        # The vowels, then the reward.
        n = draw_chapter(page, cdp, cells, by_text, shot_prefix=f"{name}-04-draw-full")
        page.wait_for_selector(".reward-body")
        page.wait_for_selector(".reward-number strong", timeout=240_000)
        page.wait_for_timeout(2500)  # the new font loads
        page.screenshot(path=shots / f"{name}-05-reward-vowels.png")
        print(f"  vowels: {n} letters drawn; reward says {page.locator('.reward-number strong').inner_text()}")

        # Consonants.
        page.get_by_role("button", name="চালিয়ে যান: ব্যঞ্জনবর্ণ →").click()
        page.wait_for_selector(".card-body")
        page.screenshot(path=shots / f"{name}-06-card-consonants.png")
        page.get_by_role("button", name="শুরু করুন →").click()
        page.wait_for_selector(".draw-canvas canvas")
        page.screenshot(path=shots / f"{name}-07-draw-ra.png")  # র comes first
        ok, what = fits(page)
        check(ok, f"{name}: still fits after many letters: {what}")
        n = draw_chapter(page, cdp, cells, by_text)
        page.wait_for_selector(".reward-number strong", timeout=240_000)
        page.wait_for_function("[...document.fonts].some(f => f.status === 'loaded' && f.family.startsWith('KakerThengUser'))", timeout=60_000)
        page.wait_for_timeout(2500)
        page.screenshot(path=shots / f"{name}-08-reward-consonants.png")
        print(f"  consonants: {n} letters drawn; reward says {page.locator('.reward-number strong').inner_text()}")

        # Vowel signs: card, then a sign letter.
        page.get_by_role("button", name="চালিয়ে যান: কার-চিহ্ন →").click()
        page.wait_for_selector(".card-body")
        page.screenshot(path=shots / f"{name}-09-card-signs.png")
        page.get_by_role("button", name="শুরু করুন →").click()
        page.wait_for_selector(".draw-canvas canvas")
        page.screenshot(path=shots / f"{name}-10-draw-sign.png")
        cid = by_text[current_cell(page)]
        draw_touch(page, cdp, STROKES[cid], cells[cid]["draw"])
        page.screenshot(path=shots / f"{name}-11-draw-sign-drawn.png")

        # A reload keeps the unfinished letter and the screen.
        page.reload()
        page.wait_for_selector(".draw-canvas canvas")
        check(page.get_by_role("button", name="ফেরান").is_enabled() and current_cell(page) == cells[cid]["text"], f"{name}: after a reload, the same letter with its strokes")
        page.get_by_role("button", name="পরের →").click()

        # English UI: one language only.
        page.get_by_role("button", name="EN", exact=True).click()
        page.wait_for_timeout(200)
        page.screenshot(path=shots / f"{name}-12-draw-sign-en.png")
        bangla_ui = page.evaluate("[...document.querySelectorAll('.topbar, .draw-hint, .draw-actions')].map(e => e.innerText).join(' ').replace(/বাংলা/g, '')")
        sign = page.locator(".draw-hint").inner_text()
        check(all(not ("ঀ" <= ch <= "৿") for ch in bangla_ui.replace(sign, "")), f"{name}: English UI shows no Bangla copy ({bangla_ui!r})")
        page.get_by_role("button", name="বাংলা", exact=True).click()

        # My font, then back with the phone's back button.
        page.get_by_role("button", name="আমার ফন্ট").click()
        page.wait_for_selector(".font-screen")
        page.wait_for_timeout(1500)
        page.screenshot(path=shots / f"{name}-13-font.png")
        page.screenshot(path=shots / f"{name}-13-font-full.png", full_page=True)
        page.go_back()
        page.wait_for_selector(".draw-canvas canvas")
        check(True, f"{name}: back from my font returns to the drawing")

        # Redraw from the specimen.
        page.get_by_role("button", name="আমার ফন্ট").click()
        page.locator(".glyph[aria-label^='ক:']").first.click()
        page.wait_for_selector(".draw-canvas canvas")
        check(current_cell(page) == "ক", f"{name}: tapping ক in the specimen opens it to redraw ({current_cell(page)})")

        # My font: save as image, where to use the font, the hidden export.
        page.get_by_role("button", name="আমার ফন্ট").click()
        page.wait_for_selector(".font-screen")
        check("Canva" in page.locator(".where-to-use").inner_text(), f"{name}: the download says where to use the font on a phone")
        export = page.get_by_role("button", name="আমার আঁকা অক্ষরগুলো ফাইলে দিন (JSON)")
        check(export.count() == 0, f"{name}: the strokes export is hidden")
        with page.expect_download() as dl:
            page.get_by_role("button", name="ছবি হিসেবে সেভ করুন").click()
        dl.value.save_as(shots / f"{name}-18-saved-image.png")
        check(dl.value.suggested_filename == "kaker-theng.png", f"{name}: save as image gives a PNG ({dl.value.suggested_filename})")
        # The download area: the font sheet (picture, PDF) first, the font file below.
        for button, out in (("ফন্ট শিট: ছবি", "24-font-sheet.png"), ("ফন্ট শিট: PDF", "25-font-sheet.pdf"), ("PDF হিসেবে সেভ করুন", "26-try-it.pdf")):
            with page.expect_download() as dl:
                page.get_by_role("button", name=button).click()
            dl.value.save_as(shots / f"{name}-{out}")
            check(dl.value.suggested_filename.endswith(out.rsplit(".", 1)[1]), f"{name}: {button} gives a {out.rsplit('.', 1)[1].upper()}")
        sheet_y = page.get_by_role("button", name="ফন্ট শিট: PDF").bounding_box()["y"]
        zip_button = page.get_by_role("button", name="কম্পিউটারে ইনস্টল করার জন্য (.ttf)")
        check(zip_button.bounding_box()["y"] > sheet_y, f"{name}: the .ttf zip comes after the picture and the PDF")
        page.locator(".download").scroll_into_view_if_needed()
        page.locator(".download").screenshot(path=shots / f"{name}-27-download-area.png")
        page.evaluate("document.querySelector('.tryit').scrollIntoView()")
        page.screenshot(path=shots / f"{name}-28-font-screen.png")
        page.evaluate("window.scrollTo(0, 0)")
        b = page.locator(".font-title").bounding_box()
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": b["x"] + 20, "y": b["y"] + b["height"] / 2}]})
        page.wait_for_timeout(900)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        check(export.count() == 1, f"{name}: holding the heading shows the strokes export")
        with page.expect_download() as dl:
            export.click()
        exported = json.loads(Path(dl.value.path()).read_text(encoding="utf-8"))
        check(len(exported["cells"]) >= 44 and exported["fingerprint"] == layout["fingerprint"], f"{name}: the export holds the drawn letters ({len(exported['cells'])}) and the layout")
        page.locator(".download").scroll_into_view_if_needed()
        page.screenshot(path=shots / f"{name}-19-font-tools.png")
        page.go_back()
        page.wait_for_selector(".draw-canvas canvas")

        # Every Bangla letter's hint.
        for ch in ("স্বরবর্ণ", "ব্যঞ্জনবর্ণ", "কার-চিহ্ন", "ফলা ও রেফ", "সংখ্যা"):
            print(f"  hints, {ch}: " + " | ".join(hints(page, ch)))
        if page.locator(".reward-body").count():
            page.go_back()
        page.locator(".chapter-button").click()
        page.get_by_role("button", name="যুক্তাক্ষর").click()
        page.wait_for_selector(".card-body")
        page.screenshot(path=shots / f"{name}-14-card-conjuncts.png")
        page.get_by_role("button", name="শুরু করুন →").click()
        while not cells[by_text[current_cell(page)]]["fragment"]:
            page.get_by_role("button", name="বাদ দিন").click()
        page.screenshot(path=shots / f"{name}-15-draw-fragment.png")
        page.locator(".chapter-button").click()
        page.screenshot(path=shots / f"{name}-16-chapters.png")
        page.get_by_role("button", name="English").click()
        page.wait_for_selector(".card-body")
        page.get_by_role("button", name="শুরু করুন →").click()
        page.screenshot(path=shots / f"{name}-17-draw-english.png")

        # ?debug=1 shows the export without holding anything.
        page.goto(base + "/?debug=1")
        page.evaluate("sessionStorage.setItem('kaker-theng-screen', JSON.stringify({name: 'font'}))")
        page.reload()
        page.wait_for_selector(".font-screen")
        check(page.get_by_role("button", name="আমার আঁকা অক্ষরগুলো ফাইলে দিন (JSON)").count() == 1, f"{name}: ?debug=1 shows the strokes export")

        # Paper.
        page.goto(base + "/")
        page.evaluate("sessionStorage.removeItem('kaker-theng-screen')")
        page.reload()
        page.get_by_role("button", name="কাগজে লিখুন").click()
        page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth)")
        page.screenshot(path=shots / f"{name}-20-paper-print.png")
        page.get_by_role("button", name="ছাপা হয়েছে →").click()
        page.screenshot(path=shots / f"{name}-21-paper-write.png")
        page.get_by_role("button", name="লেখা হয়েছে →").click()
        page.screenshot(path=shots / f"{name}-22-paper-photo.png")
        if photo:
            page.locator("input[type=file]").set_input_files(str(photo))
            page.wait_for_selector(".result", timeout=180_000)
            page.wait_for_timeout(800)
            page.screenshot(path=shots / f"{name}-23-paper-read.png", full_page=True)
        check(not errors, f"{name}: no console errors ({errors[:2]})")
        browser.close()


run("phone", {"width": 390, "height": 740})
run("small", {"width": 360, "height": 640})
print("\n" + ("all checks passed" if not problems else f"{len(problems)} problem(s): " + "; ".join(problems)))
