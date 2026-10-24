"""Serving the website (the Next.js static export) from the API's own origin.

In production one service does both: the site at /, the API under /api,
/health and /template.pdf, so the browser never makes a cross-origin call.
Text files are compressed once when the image is built (`python -m app.site
<dir>`), never per request: the free server has a tenth of a CPU.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Text files we compress, with fixed types (mimetypes varies by machine).
COMPRESS = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
}
# Best encoding first; the file next to the original has this suffix.
ENCODINGS = (("br", ".br"), ("gzip", ".gz"))


class Site(StaticFiles):
    """StaticFiles that sends a precompressed copy when the browser accepts it."""

    def file_response(self, full_path, stat_result, scope: Scope, status_code: int = 200):
        media = COMPRESS.get(Path(full_path).suffix)
        if media is None:
            return super().file_response(full_path, stat_result, scope, status_code)
        accept = next((v.decode("latin-1") for k, v in scope["headers"] if k == b"accept-encoding"), "")
        response = None
        for encoding, suffix in ENCODINGS:
            packed = Path(f"{full_path}{suffix}")
            if encoding in accept and packed.is_file():
                response = super().file_response(packed, packed.stat(), scope, status_code)
                response.headers["content-encoding"] = encoding
                break
        if response is None:
            response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["content-type"] = media
        response.headers["vary"] = "Accept-Encoding"
        return response


class SiteHeaders:
    """Caching and safety headers for every response (they used to live in
    Cloudflare Pages' _headers file). Next.js puts a content hash in every
    file name under /_next/static/, so those can be cached for good; pages
    are revalidated each time so a new deploy shows up at once."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        path = scope.get("path", "")
        # /health stays exactly as it was: the cron-job.org ping.
        if scope["type"] != "http" or path == "/health":
            return await self.app(scope, receive, send)

        async def send_with_headers(message: Message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                extra = {
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"permissions-policy": b"geolocation=(), microphone=()",
                }
                if b"cache-control" not in names:
                    if path.startswith("/_next/static/"):
                        extra[b"cache-control"] = b"public, max-age=31536000, immutable"
                    elif path.startswith("/kt/"):
                        extra[b"cache-control"] = b"public, max-age=3600"
                    elif not path.startswith("/api/"):
                        extra[b"cache-control"] = b"no-cache"
                message["headers"] = headers + [(k, v) for k, v in extra.items() if k not in names]
            await send(message)

        await self.app(scope, receive, send_with_headers)


def mount_site(app: FastAPI, directory: Path):
    """Serve the static site at /. Call after every API route is defined:
    a mount at / only gets the requests no route matched."""
    app.mount("/", Site(directory=directory, html=True), name="site")


def precompress(directory: Path) -> tuple[int, int]:
    """Write .br and .gz next to each text file where it saves space."""
    import brotli

    before = after = 0
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix not in COMPRESS:
            continue
        data = path.read_bytes()
        br = brotli.compress(data, quality=11)
        if len(br) < 0.9 * len(data):
            Path(f"{path}.br").write_bytes(br)
            Path(f"{path}.gz").write_bytes(gzip.compress(data, 9, mtime=0))
            before, after = before + len(data), after + len(br)
    return before, after


if __name__ == "__main__":
    before, after = precompress(Path(sys.argv[1]))
    print(f"precompressed site text: {before / 1024:.0f} KB -> {after / 1024:.0f} KB with brotli")
