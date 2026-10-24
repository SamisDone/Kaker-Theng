# Pyodide prototype

Runs `backend/app` unchanged in the browser: reads a page 1 photo and builds
the Latin font, with no server. A feasibility check only; the results are in
[FINDINGS.md](FINDINGS.md).

From the repository root, with the backend venv:

```sh
python prototype/pyodide/fetch_vendor.py             # Pyodide 314.0.7, wheels, harfbuzzjs -> vendor/ (~29 MB)
python -X utf8 prototype/pyodide/build_bundle.py     # app + assets -> dist/bundle.zip, CPython reference
python -X utf8 prototype/pyodide/measure.py          # Chromium: size, time, memory, output vs CPython (~8 min)
python -X utf8 prototype/pyodide/measure_baseline.py # memory before any photo
python -X utf8 prototype/pyodide/compare_fonts.py    # dist/font-compare.png
python prototype/pyodide/serve.py                    # try it on a phone on the same Wi-Fi
```

| File | What it is |
|---|---|
| `index.html` | the page: sample photo or your own, a preview in the font, downloads |
| `worker.mjs` | loads Pyodide, the packages and the bundle; runs the pipeline |
| `uharfbuzz.py` | uharfbuzz's API (the parts we use) over harfbuzzjs |
| `fetch_vendor.py`, `build_bundle.py` | download / build what the page loads (`vendor/`, `dist/`, git-ignored) |
| `measure*.py`, `compare_fonts.py`, `serve.py` | measuring and trying it |

Prototype-only shortcuts a real port would replace: reportlab is shipped
(only for `stringWidth`); fontTools is told not to use HarfBuzz's repacker;
nothing is saved between visits.
