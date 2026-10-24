// Runs backend/app unchanged in Pyodide, off the main thread so the page
// stays responsive. Messages in: {type: "run", photo: Uint8Array} and
// {type: "coverage"}. Messages out: progress, results and timings.

import { loadPyodide } from "./vendor/pyodide/pyodide.mjs";

const t0 = performance.now();
const timings = {};
let last = t0;
function lap(name) {
  const now = performance.now();
  timings[name] = Math.round(now - last);
  last = now;
  postMessage({ type: "progress", step: name, ms: timings[name] });
}

function wasmBytes(py) {
  try {
    return py._module.HEAPU8.byteLength;
  } catch {
    return null;
  }
}

const ready = (async () => {
  globalThis.harfbuzz = await import("./vendor/harfbuzzjs/index.mjs");
  lap("harfbuzzjs");
  const py = await loadPyodide({ indexURL: new URL("./vendor/pyodide/", import.meta.url).href });
  lap("pyodide runtime");
  await py.loadPackage(["numpy", "opencv-python", "fonttools", "brotli", "pillow"]);
  lap("packages");
  const zip = await (await fetch(new URL("./dist/bundle.zip", import.meta.url))).arrayBuffer();
  py.unpackArchive(zip, "zip", { extractDir: "/kt" });
  py.runPython(`import sys; sys.path[:0] = ["/kt", "/kt/backend"]`);
  lap("unpack bundle");
  py.runPython("import numpy");
  lap("import numpy");
  py.runPython("import cv2");
  lap("import cv2");
  py.runPython(`
import fontTools.ttLib, fontTools.subset
# fontTools packs GSUB/GPOS with uharfbuzz's repacker when it can import
# uharfbuzz. The shim has no repacker: use fontTools' own packer instead.
import fontTools.ttLib.tables.otBase as otBase
otBase.have_uharfbuzz = False
`);
  lap("import fontTools");
  py.runPython(`
from app.glyphmap import build_layout
from app.pipeline import decode_image, process_page
from app.fontbuild import build_font
build_layout()
`);
  lap("import app + layout");
  return py;
})();

async function run(photo, profile) {
  const py = await ready;
  last = performance.now();
  py.globals.set("photo_js", photo);
  py.globals.set("want_profile", !!profile);
  const out = py.runPython(`
import io, json, time, zipfile
from pyodide.ffi import to_js
import js
from app.sessions import _readme
from app.config import OFL_PATH

profile_text = ""
t = time.time()
if want_profile:
    import cProfile, pstats
    prof = cProfile.Profile()
    r = prof.runcall(lambda: process_page(decode_image(photo_js.to_bytes())))
    s = io.StringIO()
    pstats.Stats(prof, stream=s).sort_stats("tottime").print_stats(18)
    profile_text = s.getvalue()
else:
    r = process_page(decode_image(photo_js.to_bytes()))
t_page = time.time() - t
t = time.time()
font = build_font(r.drawings, "Prototype")
t_font = time.time() - t
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("Prototype.ttf", font.ttf)
    z.writestr("OFL.txt", OFL_PATH.read_text(encoding="utf-8"))
    z.writestr("README.txt", _readme("Prototype", {}))
summary = {
    "page": r.page,
    "cells_read": sum(1 for c in r.cells if c["status"] != "missing"),
    "cells_total": len(r.cells),
    "statuses": {c["id"]: c["status"] for c in r.cells},
    "seconds": {"process_page": round(t_page, 2), "build_font": round(t_font, 2)},
    "profile": profile_text,
}
to_js({"summary": json.dumps(summary), "ttf": font.ttf, "woff2": font.woff2, "zip": buf.getvalue(), "thumb": r.thumbnail_png},
      dict_converter=js.Object.fromEntries)
`);
  lap("page 1 + Latin font");
  postMessage({ type: "result", ...out, timings, wasmBytes: wasmBytes(py), sinceStartMs: Math.round(performance.now() - t0) });
}

async function coverage() {
  // Not needed for page 1: checks that HarfBuzz through harfbuzzjs gives the
  // same answers as uharfbuzz, on the reference coverage (4,209 shapes) and
  // 300 corpus clusters.
  const py = await ready;
  const expected = await (await fetch(new URL("./dist/expected.json", import.meta.url))).text();
  py.globals.set("expected_json", expected);
  last = performance.now();
  const out = py.runPython(`
import hashlib, json, time
from app.basefont import base_shaper
from app.coverage import complete_coverage, pages_1_2_coverage
exp = json.loads(expected_json)
t = time.time()
shaped = [[(g.name, g.cluster, g.x_advance, g.x_offset, g.y_offset) for g in base_shaper().shape(s)] for s in exp["shaping_texts"]]
t_shape = time.time() - t
t = time.time()
cov = (complete_coverage(), pages_1_2_coverage())
t_cov = time.time() - t
json.dumps({
    "shaping_match": hashlib.sha256(json.dumps(shaped, ensure_ascii=False).encode()).hexdigest() == exp["shaping_sha256"],
    "shaping": shaped,
    "complete_coverage": cov[0], "pages_1_2_coverage": cov[1],
    "seconds": {"shape_300": round(t_shape, 2), "reference_coverage": round(t_cov, 2)},
})
`);
  lap("harfbuzz check");
  postMessage({ type: "coverage", summary: out, wasmBytes: wasmBytes(py) });
}

async function full() {
  // Beyond page 1: pages 1+2 through to the Bangla font and its coverage,
  // the part of the pipeline with derived conjunct parts and HarfBuzz.
  const py = await ready;
  for (const page of [1, 2]) {
    const bytes = new Uint8Array(await (await fetch(new URL(`./dist/full-p${page}.jpg`, import.meta.url))).arrayBuffer());
    py.FS.writeFile(`/tmp/full-p${page}.jpg`, bytes);
  }
  last = performance.now();
  const out = py.runPython(`
import json, time
from app.coverage import font_coverage
out, drawings = {"process_page": {}}, []
for page in (1, 2):
    t = time.time()
    r = process_page(decode_image(open(f"/tmp/full-p{page}.jpg", "rb").read()))
    out["process_page"][page] = round(time.time() - t, 2)
    drawings += r.drawings
written = {d.glyph for d in drawings if d.kind != "latin"}
t = time.time()
font = build_font(drawings, "Prototype")
out["build_font"] = round(time.time() - t, 2)
t = time.time()
out["coverage"] = font_coverage(font.ttf, written)
out["font_coverage_s"] = round(time.time() - t, 2)
out["ttf_bytes"], out["glyphs"] = len(font.ttf), len(font.glyphs)
json.dumps(out)
`);
  lap("pages 1+2 + Bangla font");
  postMessage({ type: "full", summary: out, wasmBytes: wasmBytes(py) });
}

onmessage = (e) => {
  const job = e.data.type === "run" ? run(e.data.photo, e.data.profile) : e.data.type === "full" ? full() : coverage();
  job.catch((err) => postMessage({ type: "error", message: String(err?.stack ?? err) }));
};
