"""HTTP API. Step 2 only serves the template; uploads come with the frontend."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI
from fastapi.responses import Response

app = FastAPI(title="Kaker Theng", docs_url=None, redoc_url=None)


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
