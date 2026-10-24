"""The built site and the API on one local address, as Render runs them,
for tests and scripts that drive a real browser.

    with live_site() as url:
        session = drawn_session(url, strokes)
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SITE = BACKEND.parent / "frontend" / "out"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def api(url: str, path: str, body: dict | None = None, method: str | None = None) -> dict | bytes:
    req = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    return json.loads(data) if r.headers.get("content-type", "").startswith("application/json") else data


@contextmanager
def live_site(site: Path = SITE):
    port = _free_port()
    env = dict(os.environ, KT_SITE_DIR=str(site), KT_DATA_DIR=tempfile.mkdtemp(prefix="kt-live-"))
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(url + "/health", timeout=2)
                break
            except OSError:
                time.sleep(0.5)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=20)


def drawn_session(url: str, strokes: dict[str, list]) -> str:
    """A session holding these drawn letters, with its preview font built."""
    sid = api(url, "/api/sessions", {}, "POST")["id"]
    api(url, f"/api/sessions/{sid}/drawn", {"cells": strokes}, "PUT")
    job = api(url, f"/api/sessions/{sid}/preview", {}, "POST")
    while job["status"] not in ("done", "error"):
        time.sleep(0.5)
        job = api(url, f"/api/jobs/{job['id']}")
    assert job["status"] == "done", job
    return sid
