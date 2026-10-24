# Can the pipeline run in the browser? (Pyodide feasibility, 2026-10-24)

Short answer: **yes on a desktop. Phones are the open question, mainly memory.**
`backend/app` ran unchanged in Pyodide 314.0.7. It read page 1, built the
Latin font, and also built the pages 1+2 Bangla font with the same coverage
as the server (68.32%). The only HarfBuzz replacement needed is a 90-line
shim over harfbuzzjs.

Measured on an i5-13500H laptop (24 GB) in Playwright's Chromium 1248
(new headless mode, fresh on-disk profile), with files served from
localhost. The raw numbers are in `dist/measurements.json` after running
`measure.py`.

## 1. Dependencies

| Backend dependency | In Pyodide 314.0.7? | In the browser |
|---|---|---|
| numpy 2.5.4 | yes, **2.4.6** | works |
| opencv-python-headless 5.0 | yes, **4.11.0.86** (ArUco included) | works; every `cv2` call we make exists in 4.11 |
| fontTools 4.66.1 | yes, **4.62.1** | works (subset, cu2qu, glyf, WOFF2) |
| brotli (WOFF2) | yes, 1.2.0 | works |
| potracer 0.0.4 | not packaged, but pure Python (`py3-none-any`) | works, copied in; slow (see 3) |
| uharfbuzz 0.56 | **no** | **harfbuzzjs 1.6.3** through `uharfbuzz.py`; same results on 300 corpus clusters (names, clusters, advances, offsets) and identical coverage figures |
| reportlab 5.0 | not packaged, pure Python | only `stringWidth` is used at runtime; the prototype ships just the 36 modules it imports. A port would precompute the label widths |
| Pillow | yes, 12.2.0 | needed **only** because reportlab imports it; goes when reportlab goes |
| zopfli | no | not used by `app/` |
| fastapi, uvicorn, pydantic, starlette… | n/a | server only; not needed |

Two surprises:
- **fontTools uses uharfbuzz without our code asking.** When uharfbuzz can be
  imported, fontTools packs GSUB/GPOS with HarfBuzz's repacker. harfbuzzjs
  doesn't expose the repacker, so the browser uses fontTools' own packer
  (`otBase.have_uharfbuzz = False`). Checked in CPython: the pages 1+2 font
  comes out the same size (77,660 bytes), with the same glyphs and the same
  coverage either way, and no slower.
- **Cluster numbering.** uharfbuzz numbers clusters by code point;
  harfbuzzjs's `addText` uses UTF-16 offsets. The shim adds code points one
  at a time. The first version of the shim guessed UTF-8 offsets and was
  wrong; the corpus comparison caught it.

## 2. reportlab at runtime

Traced with every call counted on real uploads: the only runtime use is
`guides.label_box_mm` → `stringWidth` (152 calls on page 1, Helvetica label
widths). `template.py` is reached only from the server's `/template.pdf`
route, `scripts/` and `tests/synth.py`, and the static
`frontend/public/kt/kaker-theng-template-v2.pdf` replaces the route. HarfBuzz
calls at runtime: 72 on page 2 (Bangla label widths), 1,403 for the coverage
of each new font, and 4,209 for the two reference coverage figures, which
never change and can be shipped as numbers.

## 3. Prototype results

`index.html` + `worker.mjs`: Pyodide runs in a Web Worker so the page
stays responsive.

**First download** (cold cache): 29.5 MB of files, **about 21.5 MB on the
wire** with Cloudflare's brotli on js/wasm/json. Wheels and zips are already
compressed:

| On the wire | File |
|---|---|
| 10.18 MB | OpenCV 4.11 wheel |
| 2.82 MB | numpy wheel |
| 2.61 MB | Pyodide runtime wasm (9.15 MB uncompressed) |
| 2.43 MB | Python standard library |
| 1.10 MB | fontTools wheel |
| 0.99 MB | Pillow (removable) |
| 0.50 MB | sample photo (not in a real site) |
| 0.28 MB | brotli wheel |
| 0.21 MB | our code + assets + potrace + reportlab subset |
| 0.14 MB | harfbuzzjs wasm |
| ~0.25 MB | Pyodide JS, lock file, harfbuzzjs JS |

A real site would download about **20 MB** once: about 3.5 s at 50 Mbit/s,
17 s at 10 Mbit/s, 34 s at 5 Mbit/s. Repeat visits downloaded **0 bytes**
(HTTP cache).

**Time** (median of 5 cold visits, downloads instant):

| Step | Time |
|---|---|
| Pyodide runtime | 2.0 s |
| Load packages | 1.0 s |
| `import numpy` / `cv2` / `fontTools` | 0.5 / 0.03 / 1.0 s |
| Our code + layout | 0.4 s |
| **Read page 1** | **5.4 s** (CPython native: 1.4 s) |
| **Build Latin font** | **0.4 s** (CPython native: 0.2–0.3 s) |
| **Total, opening the page to having the font** | **~11 s** |

All 5 runs took 10.5–11.5 s. In two earlier batches on the same laptop,
some runs took 2.4× longer (page 1 in 12–13 s), with no pattern by run
order. My guess, not verified: Windows put the browser on the i5-13500H's
efficiency cores. Repeat visits take the same time apart from downloading:
the startup is mostly compiling and importing, not fetching.

Beyond page 1: **page 2 in 5.0 s, the pages 1+2 Bangla font in 2.2 s, its
coverage in 0.24 s (0.683174, identical to CPython)**. For comparison, the
free Render server takes 21 s for page 1 and 44 s for page 2.

Where reading page 1 spends its time (cProfile, which exaggerates pure-Python
code): potrace (pure Python) about half, OpenCV `morphologyEx` + `dilate` about 1.4 s (single-threaded wasm),
fontTools drawing Noto's outlines for the ghost and label masks about 1.1 s
(could be precomputed).

**Peak memory** (the tab's renderer process; Windows peak counters):

| | Peak private | Peak working set |
|---|---|---|
| blank tab | 47 MB | 84 MB |
| everything loaded, no photo yet | **512 MB** | 482 MB |
| after page 1 + Latin font | **~640 MB** (614–661) | ~545 MB |
| after pages 1+2 + Bangla font | **685 MB** | 527 MB |

The Python heap (wasm memory) peaks at 188 MB. Most of the rest is the
fixed cost of the runtime and compiled libraries (OpenCV above all), so
trimming our own code can't remove it.

**Output vs the server:** same 76/76 cells and same statuses. The fonts have
the same 87 glyphs and the same contour counts; 55 glyphs are
byte-identical, the others differ by at most 12 units in advance and 9 in
bounds (of 1000 per em). See `dist/font-compare.png`. The likely cause is
OpenCV 4.11 vs 5.0 and numpy 2.4 vs 2.5 (not investigated).

## 4. Estimate and risks

**Work for a full port: about 2 weeks of focused work** if phones cope with
the memory, **3 or more** if they don't.

1. Precompute label widths and reference coverage; drop reportlab and
   Pillow. *(½ day)*
2. Turn the harfbuzzjs shim into production code, with a test that compares
   it with uharfbuzz on the corpus. *(1 day)*
3. Worker + loader: self-host Pyodide and the wheels on Pages (largest file
   10.2 MB, under the 25 MiB limit), a download progress message, errors
   for out-of-memory and unsupported browsers. *(2–3 days)*
4. Frontend: replace `lib/api.ts` with the worker. Sessions become local
   state saved to IndexedDB after each page; the queue, polling and ETA go;
   thumbnails, preview font and zip become Blobs. *(2–3 days)*
5. Tests: align the dev venv with Pyodide's numpy/OpenCV/fontTools versions,
   plus a Playwright test that runs the worker on synthetic pages and
   compares with CPython, as `measure.py` does. *(1–2 days)*
6. Remove Render, cron-job.org and CORS; rewrite the README and the
   after-deploy check. *(½–1 day)*
7. Real-phone testing and fixes. *(1–5 days; the unknown)*

**Risks, most serious first:**

1. **Phone memory.** About 650–700 MB in one tab, 512 MB of it before any
   photo. Android Chrome on 3–4 GB phones may kill the tab ("Aw, Snap")
   during processing. Not measured on a phone. Shrinking it means a custom
   OpenCV build with only core/imgproc/imgcodecs/calib3d/objdetect (unknown
   effort, several days) or replacing OpenCV.
2. **First download of about 20 MB**, half of it OpenCV. Fine on Wi-Fi, a
   real cost on mobile data. The browser may evict it, so it can come back.
3. **Phone speed.** Not measured. A mid-range Android phone is plausibly
   2–4× slower than this laptop for wasm: roughly 10–20 s per page plus
   10–20 s to start. That's still no worse than today's server, and there's
   no queue.
4. **Leaving the tab.** If someone switches to the camera app while a page
   is processing, Android may freeze or kill the tab. Each finished page
   must be saved to IndexedDB so nothing is lost.
5. **Version drift.** Pyodide decides the numpy/OpenCV/fontTools versions,
   which already differ from the server's (OpenCV 4.11 vs 5.0). Outputs
   move slightly with each Pyodide upgrade, and the loader broke between
   release lines (`pyodide.asm.js` became `pyodide.asm.mjs`). Pin and
   self-host.
6. **iPhone Safari** has stricter per-tab memory limits. Untested.
7. **Upsides:** photos never leave the phone; no cold start, queue,
   512 MB server limit, Render hours or cron job; free hosting only.

**Before deciding:** open the prototype on your Android phone (`serve.py`,
same Wi-Fi). If the tab survives page 1 and the time is acceptable, the port
is worth doing. If the tab is killed, the memory work becomes the first
task, and its size is the real unknown.
