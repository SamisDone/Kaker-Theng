"""HTTP API.

Heavy work (reading a page photo, building a download) goes through a
single-worker queue; the client polls the job. Everything is bilingual in
the error bodies: `message_bn` and `message`.
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import sessions
from .fontbuild import FontNameError, clean_family_name
from .jobs import JobQueue, QueueFull
from .pipeline import MAX_UPLOAD_BYTES

def _warm_up():
    """Load what the first upload would otherwise wait for (layout, base
    font, template, reference coverage). On a 0.1-CPU free server that is
    ~20 s; done here, it happens while the visitor is still printing."""
    try:
        from .coverage import complete_coverage, pages_1_2_coverage
        from .glyphmap import build_layout

        build_layout()
        _template_pdf()
        complete_coverage()
        pages_1_2_coverage()
    except Exception:  # noqa: BLE001 - a failed warm-up only costs speed
        import traceback

        traceback.print_exc()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sessions.start_sweeper()
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(title="Kaker Theng", docs_url=None, redoc_url=None, lifespan=lifespan)

origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins + ["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

queue = JobQueue(max_waiting=int(os.environ.get("MAX_QUEUE", "12")))


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
    return _error(
        503,
        "queue_full",
        "Lots of people are making fonts right now. Please try again in a minute.",
        "এখন অনেকে একসাথে ফন্ট বানাচ্ছেন। এক মিনিট পরে আবার চেষ্টা করুন।",
    )


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
    out = {"id": job.id, "kind": job.kind, "status": job.status, "ahead": queue.ahead(job)}
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


class DownloadRequest(BaseModel):
    name: str
    format: str


@app.post("/api/sessions/{session_id}/download", status_code=202)
def request_download(session_id: str, req: DownloadRequest):
    meta = sessions.load(session_id)
    if meta is None:
        return _gone()
    if not meta.get("pages"):
        return _error(400, "no_pages", "Add a page photo first.", "আগে একটা পাতার ছবি দিন।")
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
