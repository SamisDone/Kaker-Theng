"""Drive the built website with a headless browser and take screenshots.

    python -m scripts.ui_check <frontend/out> <photos dir> <screenshots dir>

Starts the API on :8000 and a static server for the export on :3123, uploads
synthetic page photos through the real file inputs (two back to back, to see
the queue), types in the try-it box and clicks a glyph. Dev only: needs
`pip install playwright && python -m playwright install chromium`.
"""

import functools
import http.server
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT, PHOTOS, SHOTS = (Path(p) for p in sys.argv[1:4])
SHOTS.mkdir(parents=True, exist_ok=True)


def serve_static():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 3123), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    env = dict(os.environ, ALLOWED_ORIGINS="http://localhost:3123,http://127.0.0.1:3123")
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"], env=env)
    httpd = serve_static()
    try:
        time.sleep(4)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto("http://localhost:3123/")
            page.wait_for_selector("text=কাকের ঠ্যাং")
            page.wait_for_timeout(1500)
            page.screenshot(path=SHOTS / "01-start.png", full_page=True)

            inputs = page.locator("input[type=file]")
            inputs.nth(0).set_input_files(str(PHOTOS / "laser-p1.jpg"))
            page.wait_for_selector("text=cells read", timeout=120_000)

            # Two at once: page 3 waits behind page 2.
            inputs.nth(1).set_input_files(str(PHOTOS / "ballpoint-p2.jpg"))
            page.wait_for_timeout(300)
            inputs.nth(2).set_input_files(str(PHOTOS / "laser-p3.jpg"))
            try:
                page.wait_for_selector("text=ahead of you", timeout=15_000)
                page.locator(".slot").nth(2).screenshot(path=SHOTS / "02-queue.png")
            except Exception:  # noqa: BLE001 - the first job may finish too fast to see
                print("queue message not seen")
            try:
                page.wait_for_function("document.querySelectorAll('.result').length >= 3", timeout=240_000)
            except Exception:
                page.screenshot(path=SHOTS / "fail.png", full_page=True)
                for i in range(3):
                    print("slot", i + 1, "|", page.locator(".slot").nth(i).inner_text().replace("\n", " / ")[:400])
                raise
            page.wait_for_selector("text=of real Bangla text", timeout=60_000)
            page.wait_for_timeout(2500)  # font loads, title fades into the handwriting
            page.screenshot(path=SHOTS / "03-after-upload.png", full_page=True)
            page.locator(".masthead").screenshot(path=SHOTS / "04-title-in-hand.png")

            page.locator("details.examples summary").click()
            page.locator(".slot").nth(2).screenshot(path=SHOTS / "05-page3-and-examples.png")

            page.locator(".tryit textarea").fill("আমি প্রতিদিন সকালে চা খাই। কর্মী ক্ষমা চাইল।\nবিদ্যালয়ের সামনে বৃষ্টি পড়ছে।\nThe quick brown fox jumps over the lazy dog.")
            page.locator(".glyph").nth(80).click()
            page.locator("#try-title").scroll_into_view_if_needed()
            page.locator("section").nth(2).screenshot(path=SHOTS / "06-try-specimen-download.png")

            mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            mobile.goto("http://localhost:3123/")
            mobile.wait_for_timeout(2000)
            mobile.screenshot(path=SHOTS / "07-mobile.png", full_page=False)
            browser.close()
    finally:
        api.terminate()
        httpd.shutdown()


if __name__ == "__main__":
    main()
