"""Measure the prototype in Chromium (Playwright) on this machine.

    backend/.venv/Scripts/python -X utf8 prototype/pyodide/measure.py

- Cold first visits (fresh browser each, empty cache): bytes served, time to
  a finished font, and the tab's peak memory (Windows' per-process peaks).
- Repeat visits (reload, HTTP cache): the time again.
- A HarfBuzz check (harfbuzzjs through the shim vs uharfbuzz) and a profiled
  run, each in its own browser.
- The browser's font against CPython's (dist/expected.json, dist/cpython.ttf).

Files come from localhost, so download *time* here is near zero; the sizes
are reported so it can be worked out for real connections.
"""

import functools
import http.server
import io
import json
import statistics
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import brotli
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PORT = 8765
COLD_RUNS, WARM_RUNS = 5, 3
COMPRESSIBLE = (".js", ".mjs", ".wasm", ".json", ".html")  # Cloudflare would brotli these; .whl/.zip/.jpg already are
served: dict[str, int] = {}
served_lock = threading.Lock()


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript", ".wasm": "application/wasm", ".whl": "application/zip"}

    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def do_GET(self):
        super().do_GET()
        path = Path(self.translate_path(self.path))
        if self._status == 200 and path.is_file():
            with served_lock:
                served[path.relative_to(HERE).as_posix()] = served.get(path.relative_to(HERE).as_posix(), 0) + path.stat().st_size

    def send_response(self, code, message=None):
        self._status = code
        super().send_response(code, message)

    def log_message(self, *_):
        pass


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Handler, directory=str(HERE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def browser_memory() -> list[dict]:
    """Peak working set and peak private bytes of each Playwright Chromium process (MB)."""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*ms-playwright*' } | "
        "Select-Object ProcessId,PeakWorkingSetSize,PeakPageFileUsage,CommandLine | ConvertTo-Json -Compress"
    )
    raw = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
    rows = json.loads(raw) if raw else []
    rows = rows if isinstance(rows, list) else [rows]
    out = []
    for r in rows:
        cmd = r.get("CommandLine") or ""
        kind = cmd.split("--type=")[1].split()[0] if "--type=" in cmd else "browser"
        out.append({"type": kind, "peak_ws_mb": round(r["PeakWorkingSetSize"] / 1024), "peak_private_mb": round(r["PeakPageFileUsage"] / 1024)})
    return out


def renderer_peak(mem: list[dict]) -> dict:
    return max((m for m in mem if m["type"] == "renderer"), key=lambda m: m["peak_private_mb"])


def wait(page, what: str):
    out = page.evaluate(what)
    if "error" in out:
        raise SystemExit("in the browser:\n" + out["error"])
    return out


def visit(page, url):
    t = time.time()
    page.goto(url)
    run = wait(page, "window.__run")
    run["wall_s"] = round(time.time() - t, 1)
    return run


def compare_fonts(ttf: bytes, expected: dict) -> dict:
    from fontTools.ttLib import TTFont

    f = TTFont(io.BytesIO(ttf))
    glyf, hmtx = f["glyf"], f["hmtx"]
    got = {n: {"adv": hmtx[n][0], "box": [glyf[n].xMin, glyf[n].yMin, glyf[n].xMax, glyf[n].yMax] if glyf[n].numberOfContours else None,
               "contours": glyf[n].numberOfContours} for n in f.getGlyphOrder()}
    exp = expected["glyphs"]
    adv = {n: got[n]["adv"] - exp[n]["adv"] for n in exp if n in got and got[n]["adv"] != exp[n]["adv"]}
    box = {n: max(abs(a - b) for a, b in zip(got[n]["box"], exp[n]["box"])) for n in exp if n in got and got[n]["box"] and exp[n]["box"]}
    return {
        "same_glyph_set": set(got) == set(exp), "glyphs": len(got),
        "identical_glyphs": sum(1 for n in exp if got.get(n) == exp[n]),
        "advance_diffs": adv,
        "max_bbox_diff": max(box.values(), default=0),
        "contour_count_mismatches": sorted(n for n in exp if n in got and got[n]["contours"] != exp[n]["contours"]),
    }


def shaping_diff(got: list, expected: dict) -> list:
    out = []
    for text, a, b in zip(expected["shaping_texts"], got, expected["shaping"]):
        if a != b:
            out.append({"text": text, "browser": a, "cpython": b})
    return out


def med(xs):
    return round(statistics.median(xs), 1)


def main():
    expected = json.loads((HERE / "dist" / "expected.json").read_text(encoding="utf-8"))
    httpd = serve()
    base = f"http://127.0.0.1:{PORT}/index.html"
    report = {"cold": [], "warm": []}
    with sync_playwright() as p:
        # Full Chromium in its new headless mode (the same engine as desktop
        # Chrome), each time with a fresh on-disk profile like a real visitor.
        for i in range(COLD_RUNS):
            browser = p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="kt-chromium-"), channel="chromium")
            page = browser.new_page()
            page.set_default_timeout(600_000)
            served.clear()
            cold = visit(page, base + "?auto")
            time.sleep(1)
            mem = browser_memory()
            report["cold"].append({"timings": cold["timings"], "python_s": cold["summary"]["seconds"], "wall_s": cold["wall_s"],
                                   "wasm_mb": round((cold["wasmBytes"] or 0) / 2**20), "renderer": renderer_peak(mem),
                                   "all_processes_peak_private_mb": sum(m["peak_private_mb"] for m in mem), "served": dict(served)})
            if i == 0:
                (HERE / "dist" / "browser.ttf").write_bytes(bytes(cold["ttf"]))
                report["font_vs_cpython"] = compare_fonts(bytes(cold["ttf"]), expected)
                report["cells_vs_cpython"] = {"same_statuses": cold["summary"]["statuses"] == expected["statuses"],
                                              "browser": f"{cold['summary']['cells_read']}/{cold['summary']['cells_total']}",
                                              "cpython": f"{expected['cells_read']}/{expected['cells_total']}"}
                report["font_rendered"] = cold["fontRendered"]
                for _ in range(WARM_RUNS):
                    served.clear()
                    warm = visit(page, base + "?auto")
                    report["warm"].append({"timings": warm["timings"], "python_s": warm["summary"]["seconds"], "wall_s": warm["wall_s"],
                                           "bytes_served": sum(served.values())})
            browser.close()

        browser = p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="kt-chromium-"), channel="chromium")
        page = browser.new_page()
        page.set_default_timeout(600_000)
        page.goto(base + "?auto&check")
        wait(page, "window.__run")
        check = wait(page, "window.__check")
        report["harfbuzz_check"] = {k: v for k, v in check.items() if k != "shaping"} | {
            "expected": {"complete_coverage": expected["complete_coverage"], "pages_1_2_coverage": expected["pages_1_2_coverage"]},
            "shaping_diffs": shaping_diff(check["shaping"], expected),
        }
        report["memory_with_check"] = renderer_peak(browser_memory())
        browser.close()

        browser = p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="kt-chromium-"), channel="chromium")
        page = browser.new_page()
        page.set_default_timeout(600_000)
        prof = visit(page, base + "?auto&profile")
        report["profile"] = prof["summary"]["profile"]
        browser.close()

        browser = p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="kt-chromium-"), channel="chromium")
        page = browser.new_page()
        page.set_default_timeout(900_000)
        page.goto(base + "?full")
        full = wait(page, "window.__full")
        report["full"] = full | {"wasm_mb": round((full["wasmBytes"] or 0) / 2**20), "renderer": renderer_peak(browser_memory()),
                                 "expected": expected["full"]}
        browser.close()
    httpd.shutdown()
    report["cpython_seconds"] = expected["cpython_seconds"]
    (HERE / "dist" / "measurements.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    first = report["cold"][0]["served"]
    raw = sum(first.values())
    wire = sum(len(brotli.compress((HERE / f).read_bytes(), quality=11)) if f.endswith(COMPRESSIBLE) else n for f, n in first.items())
    print(f"first visit downloads: {raw / 2**20:.2f} MB as files, ~{wire / 2**20:.2f} MB on the wire (brotli on js/wasm/json/html)")
    for f, n in sorted(first.items(), key=lambda kv: -kv[1])[:14]:
        print(f"   {n / 2**20:6.2f} MB  {f}")
    for kind in ("cold", "warm"):
        runs = report[kind]
        steps = runs[0]["timings"].keys()
        print(f"{kind} ({len(runs)} runs), median ms per step:", {s: med([r["timings"][s] for r in runs]) for s in steps},
              "| wall s:", [r["wall_s"] for r in runs], "| python s:", [r["python_s"] for r in runs])
    print("repeat visits re-downloaded bytes:", [r["bytes_served"] for r in report["warm"]])
    print("renderer peak private MB (cold runs):", [r["renderer"]["peak_private_mb"] for r in report["cold"]],
          "| peak working set MB:", [r["renderer"]["peak_ws_mb"] for r in report["cold"]],
          "| wasm heap MB:", [r["wasm_mb"] for r in report["cold"]],
          "| all processes MB:", [r["all_processes_peak_private_mb"] for r in report["cold"]])
    print("with HarfBuzz check, renderer peak:", report["memory_with_check"])
    print("cells:", report["cells_vs_cpython"], "| font rendered:", report["font_rendered"])
    print("font vs CPython:", report["font_vs_cpython"])
    hc = report["harfbuzz_check"]
    print("harfbuzz check:", {k: hc[k] for k in ("shaping_match", "complete_coverage", "pages_1_2_coverage", "seconds", "expected")},
          f"| {len(hc['shaping_diffs'])} of {len(expected['shaping_texts'])} clusters differ")
    for d in hc["shaping_diffs"][:3]:
        print("   ", d)
    print("CPython (native) on this machine:", report["cpython_seconds"])
    f = report["full"]
    print(f"pages 1+2 in the browser: read {f['process_page']} s, Bangla font {f['build_font']} s, coverage {f['coverage']:.6f} "
          f"({f['font_coverage_s']} s), {f['glyphs']} glyphs, TTF {f['ttf_bytes']} bytes, wasm heap {f['wasm_mb']} MB, renderer peak {f['renderer']}")
    print(f"   CPython: {f['expected']}")
    print("\nprofile of reading page 1 in the browser:\n" + report["profile"])


if __name__ == "__main__":
    main()
