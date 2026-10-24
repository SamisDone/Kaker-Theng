"""How much of the tab's memory is fixed cost (Python, OpenCV, fontTools
loaded and the layout read) and how much is reading a photo?

    backend/.venv/Scripts/python -X utf8 prototype/pyodide/measure_baseline.py
"""

import tempfile

from playwright.sync_api import sync_playwright

from measure import PORT, browser_memory, renderer_peak, serve

httpd = serve()
base = f"http://127.0.0.1:{PORT}/index.html"
with sync_playwright() as p:
    for label, url, wait_for in (
        ("blank page", "about:blank", None),
        ("everything loaded, no photo yet", base, "text=import app + layout"),
    ):
        browser = p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="kt-chromium-"), channel="chromium")
        page = browser.new_page()
        page.set_default_timeout(300_000)
        page.goto(url)
        if wait_for:
            page.wait_for_selector(wait_for)
        page.wait_for_timeout(1500)
        r = renderer_peak(browser_memory())
        print(f"{label:<34} renderer peak private {r['peak_private_mb']} MB, peak working set {r['peak_ws_mb']} MB")
        browser.close()
httpd.shutdown()
