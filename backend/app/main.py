"""HTTP API, and in production the website too.

Heavy work (reading a page photo, building a download) goes through a
single-worker queue; the client polls the job. Everything is bilingual in
the error bodies: `message_bn` and `message`.

With KT_SITE_DIR set (the Docker image sets it), the static site is served
at / from the same origin, so production needs no CORS. ALLOWED_ORIGINS is
only for a site hosted elsewhere; http://localhost:3000 (next dev) is
allowed only when the API runs without the site, i.e. in development.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import sessions, strokes
from .fontbuild import FontNameError, clean_family_name
from .jobs import JobQueue, QueueFull
from .pipeline import MAX_UPLOAD_BYTES
from .site import SiteHeaders, mount_site

def _warm_up():
    """Load what the first upload would otherwise wait for (layout, base
    font, template, reference coverage). On a 0.1-CPU free server that is
    ~20 s; done here, it happens while the visitor is still printing."""
    try:
        from .coverage import complete_coverage, pages_1_2_coverage
        from .glyphmap import build_layout
        from .wordcov import complete_word_coverage, pages_1_2_word_coverage

        build_layout()
        _template_pdf()
        complete_coverage()
        pages_1_2_coverage()
        complete_word_coverage()
        pages_1_2_word_coverage()
    except Exception:  # noqa: BLE001 - a failed warm-up only costs speed
        import traceback

        traceback.print_exc()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sessions.start_sweeper()
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(title="Kaker Theng", docs_url=None, redoc_url=None, lifespan=lifespan)

SITE_DIR = os.environ.get("KT_SITE_DIR")
origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not SITE_DIR:
    origins.append("http://localhost:3000")  # next dev, during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)
app.add_middleware(SiteHeaders)

queue = JobQueue(max_waiting=int(os.environ.get("MAX_QUEUE", "5")))


def _error(status: int, code: str, en: str, bn: str, **extra) -> JSONResponse:
    return JSONResponse({"code": code, "message": en, "message_bn": bn, **extra}, status_code=status)


def _gone() -> JSONResponse:
    return _error(
        404,
        "session_gone",
        "This session has expired (they last an hour). Please upload your pages again.",
        "এই সেশনের মেয়াদ শেষ (এক ঘণ্টা থাকে)। পাতাগুলো আবার দিন।",
    )


def _busy() -> JSONResponse:
    wait_s = queue.wait_estimate()
    minutes = max(1, -(-wait_s // 60))
    bn_minutes = str(minutes).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))
    res = _error(
        503,
        "queue_full",
        f"Lots of people are making fonts right now. Please try again in about {minutes} min.",
        f"এখন অনেকে একসাথে ফন্ট বানাচ্ছেন। প্রায় {bn_minutes} মিনিট পরে আবার চেষ্টা করুন।",
        retry_after_s=wait_s,
    )
    res.headers["Retry-After"] = str(wait_s)
    return res


@app.get("/health")
def health():
    # Must stay instant: no files, OpenCV or fonts here.
    return {"ok": True}


@lru_cache(maxsize=1)
def _template_pdf() -> bytes:
    from .template import build_template_pdf

    return build_template_pdf()


@app.get("/template.pdf")
def template_pdf():
    return Response(
        _template_pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="kaker-theng-template.pdf"', "Cache-Control": "public, max-age=3600"},
    )


@app.post("/api/sessions")
def create_session():
    return {"id": sessions.create(), "expires_in": sessions.SESSION_TTL_S}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    meta = sessions.load(session_id)
    return meta if meta is not None else _gone()


def _job_view(job) -> dict:
    out = {"id": job.id, "kind": job.kind, "status": job.status, "ahead": queue.ahead(job), "eta_s": queue.eta(job)}
    if job.status == "done":
        out["result"] = job.result
    elif job.status == "error":
        out["error"] = job.error
    return out


@app.post("/api/sessions/{session_id}/pages", status_code=202)
async def upload_page(session_id: str, photo: UploadFile = File(...)):
    if sessions.load(session_id) is None:
        return _gone()
    data = await photo.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return _error(413, "too_large", "That photo is over 10 MB. Please use a smaller one.", "ছবিটা ১০ MB-র বেশি। আরেকটু ছোট ছবি দিন।")

    def work() -> dict:
        from .pipeline import decode_image, process_page

        result = process_page(decode_image(data))
        meta = sessions.save_page(session_id, result)
        return {"page": result.page, "session": meta}

    try:
        job = queue.submit("page", work)
    except QueueFull:
        return _busy()
    return _job_view(job)


MAX_DRAWN_BYTES = 4 * 1024 * 1024  # a whole template drawn is ~0.5 MB of JSON
_previews: dict[str, str] = {}  # session id -> its latest preview job


@app.put("/api/sessions/{session_id}/drawn")
async def put_drawn(session_id: str, request: Request):
    """Letters drawn in the browser, {"cells": {cell id: strokes}}. Only
    stores them (quick); POST .../preview rebuilds the font."""
    if sessions.load(session_id) is None:
        return _gone()
    body = await request.body()
    if len(body) > MAX_DRAWN_BYTES:
        return _error(413, "too_large", "That's too much drawing for one request.", "একবারে এত আঁকা পাঠানো যায় না।")
    try:
        cells = json.loads(body)["cells"]
        if not isinstance(cells, dict):
            raise ValueError
        return await run_in_threadpool(sessions.save_drawn, session_id, cells)
    except (ValueError, KeyError, TypeError, strokes.StrokeError) as err:
        return _error(400, "bad_strokes", f"That drawing couldn't be read: {err}", "আঁকাটা পড়া গেল না। আবার আঁকুন।")


@app.post("/api/sessions/{session_id}/preview", status_code=202)
def request_preview(session_id: str):
    """Rebuild the preview font and coverage from everything written. While
    one rebuild is still waiting, asking again returns that one."""
    if sessions.load(session_id) is None:
        return _gone()
    waiting = queue.get(_previews.get(session_id, ""))
    if waiting is not None and waiting.status == "queued":
        return _job_view(waiting)
    try:
        job = queue.submit("preview", lambda: {"session": sessions.rebuild(session_id)})
    except QueueFull:
        return _busy()
    _previews[session_id] = job.id
    return _job_view(job)


class DownloadRequest(BaseModel):
    name: str
    format: str


@app.post("/api/sessions/{session_id}/download", status_code=202)
def request_download(session_id: str, req: DownloadRequest):
    meta = sessions.load(session_id)
    if meta is None:
        return _gone()
    if not meta.get("pages") and not meta.get("drawn"):
        return _error(400, "no_pages", "Add a page photo or draw some letters first.", "আগে একটা পাতার ছবি দিন বা কয়েকটা অক্ষর আঁকুন।")
    if req.format not in ("ttf", "woff2"):
        raise HTTPException(400, "format must be ttf or woff2")
    try:
        family = clean_family_name(req.name)
    except FontNameError as err:
        return _error(400, "bad_name", err.en, err.bn)
    try:
        job = queue.submit("download", lambda: sessions.build_download(session_id, family, req.format))
    except QueueFull:
        return _busy()
    return _job_view(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = queue.get(job_id)
    if job is None:
        return _error(404, "job_gone", "That request has expired. Please try again.", "অনুরোধটার মেয়াদ শেষ। আবার চেষ্টা করুন।")
    return _job_view(job)


@app.get("/api/sessions/{session_id}/files/{name}")
def get_file(session_id: str, name: str):
    if sessions.load(session_id) is None:
        return _gone()
    path = sessions.file_path(session_id, name)
    if path is None:
        raise HTTPException(404)
    media = {"woff2": "font/woff2", "png": "image/png", "zip": "application/zip"}.get(name.rsplit(".", 1)[-1], "application/octet-stream")
    headers = {"Cache-Control": "no-store"}
    if name.endswith(".zip"):
        headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return FileResponse(path, media_type=media, headers=headers)


@app.get("/api/info")
def info():
    from .coverage import complete_coverage, pages_1_2_coverage

    from . import config as C
    from .glyphmap import fingerprint

    return {
        "template_version": C.TEMPLATE_VERSION,
        "layout_fingerprint": fingerprint(),
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "coverage_targets": {"pages_1_2": pages_1_2_coverage(), "all_pages": complete_coverage()},
        "busy": queue.waiting(),
    }


# Last: the site gets only what no route above matched.
if SITE_DIR:
    mount_site(app, Path(SITE_DIR))
