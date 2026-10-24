"""Download what the prototype page loads into vendor/ (git-ignored):
the Pyodide runtime, the wheels it needs, and harfbuzzjs. Served from the
same origin, the way a static site on Cloudflare Pages would have to.

    python fetch_vendor.py
"""

import json
import sys
import urllib.request
from pathlib import Path

PYODIDE = "314.0.7"  # Python 3.14; released 2026-09-14
HARFBUZZJS = "1.6.3"  # released 2026-10-06
PY_BASE = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full"
HB_BASE = f"https://cdn.jsdelivr.net/npm/harfbuzzjs@{HARFBUZZJS}/dist"
CORE = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
PACKAGES = ["numpy", "opencv-python", "fonttools", "brotli", "pillow"]
HB_FILES = ["index.mjs", "harfbuzz.js", "harfbuzz.wasm"]

OUT = Path(__file__).resolve().parent / "vendor"


def get(url: str, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as res:
                data = res.read()
            dest.write_bytes(data)
            print(f"{len(data) / 2**20:8.2f} MB  {dest.relative_to(OUT)}", flush=True)
            return
        except OSError as err:
            print(f"retry {attempt + 1}: {url}: {err}", file=sys.stderr, flush=True)
    raise SystemExit(f"could not download {url}")


def main():
    for f in CORE:
        get(f"{PY_BASE}/{f}", OUT / "pyodide" / f)
    lock = json.loads((OUT / "pyodide" / "pyodide-lock.json").read_text(encoding="utf-8"))["packages"]
    needed, todo = set(), list(PACKAGES)
    while todo:
        name = todo.pop()
        if name not in needed:
            needed.add(name)
            todo += lock[name]["depends"]
    for name in sorted(needed):
        get(f"{PY_BASE}/{lock[name]['file_name']}", OUT / "pyodide" / lock[name]["file_name"])
    for f in HB_FILES:
        get(f"{HB_BASE}/{f}", OUT / "harfbuzzjs" / f)


if __name__ == "__main__":
    main()
