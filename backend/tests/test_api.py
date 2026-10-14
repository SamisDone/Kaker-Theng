"""The HTTP API: sessions, the queue, uploads, downloads."""

import io
import os
import tempfile
import threading
import time
import zipfile

os.environ.setdefault("KT_DATA_DIR", tempfile.mkdtemp(prefix="kt-test-"))

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.synth import make_page


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


def wait(client, job_id, timeout=180):
    seen_ahead = set()
    t = time.time()
    while time.time() - t < timeout:
        job = client.get(f"/api/jobs/{job_id}").json()
        seen_ahead.add(job["ahead"])
        if job["status"] in ("done", "error"):
            job["seen_ahead"] = seen_ahead
            return job
        time.sleep(0.2)
    raise TimeoutError(job_id)


def test_health_is_instant(client):
    t = time.time()
    assert client.get("/health").json() == {"ok": True}
    assert time.time() - t < 0.5


def test_full_flow_pages_1_and_2_then_download(client):
    sid = client.post("/api/sessions").json()["id"]
    for page in (1, 2):
        photo = make_page(page, "laser").photo_jpeg
        r = client.post(f"/api/sessions/{sid}/pages", files={"photo": ("p.jpg", photo, "image/jpeg")})
        assert r.status_code == 202
        job = wait(client, r.json()["id"])
        assert job["status"] == "done", job
        assert job["result"]["page"] == page

    meta = client.get(f"/api/sessions/{sid}").json()
    assert set(meta["pages"]) == {"1", "2"}
    # Pages 1 and 2 alone make a working font that covers most real text.
    assert meta["coverage"] > 0.6
    assert client.get(f"/api/sessions/{sid}/files/{meta['font']}").content[:4] == b"wOF2"
    assert client.get(f"/api/sessions/{sid}/files/page-2.png").headers["content-type"] == "image/png"

    r = client.post(f"/api/sessions/{sid}/download", json={"name": "আমার হাত", "format": "ttf"})
    job = wait(client, r.json()["id"])
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/sessions/{sid}/files/{job['result']['file']}").content))
    names = z.namelist()
    assert "OFL.txt" in names and "README.txt" in names and any(n.endswith(".ttf") for n in names)


def test_bad_inputs_get_clear_messages(client):
    sid = client.post("/api/sessions").json()["id"]
    big = b"\xff" * (main.MAX_UPLOAD_BYTES + 1)
    r = client.post(f"/api/sessions/{sid}/pages", files={"photo": ("p.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and r.json()["message_bn"]

    r = client.post(f"/api/sessions/{sid}/pages", files={"photo": ("p.jpg", b"not an image", "image/jpeg")})
    job = wait(client, r.json()["id"])
    assert job["status"] == "error" and job["error"]["code"] == "not_an_image"

    r = client.post(f"/api/sessions/{sid}/download", json={"name": "Noto Me", "format": "ttf"})
    assert r.status_code == 400  # no pages yet, or bad name: both explained
    assert client.get("/api/sessions/nope-nope-nope/").status_code in (404, 307)
    assert client.get("/api/sessions/doesnotexist123").json()["code"] == "session_gone"


def test_queue_reports_place_and_refuses_politely_when_full():
    q = main.JobQueue(max_waiting=2)
    gate = threading.Event()
    first = q.submit("page", lambda: gate.wait(10) and {})
    time.sleep(0.2)  # the worker picks up the first job
    second = q.submit("page", lambda: {})
    third = q.submit("page", lambda: {})
    assert q.ahead(first) == 0
    assert q.ahead(second) == 1 and q.ahead(third) == 2
    with pytest.raises(main.QueueFull):
        q.submit("page", lambda: {})
    gate.set()
