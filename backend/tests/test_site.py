"""One service: the static site at /, the API routes still winning."""

import gzip

import brotli
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.site import SiteHeaders, mount_site, precompress

JS = "console.log('kaker theng');\n" * 200


def make_site(tmp_path):
    (tmp_path / "_next" / "static" / "chunks").mkdir(parents=True)
    (tmp_path / "kt").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>home</title>" + "<p>কাকের ঠ্যাং</p>" * 50, encoding="utf-8")
    (tmp_path / "404.html").write_text("<!doctype html><title>not here</title>", encoding="utf-8")
    (tmp_path / "_next" / "static" / "chunks" / "app.js").write_bytes(JS.encode())
    (tmp_path / "kt" / "template-p1.png").write_bytes(b"\x89PNG not really")
    precompress(tmp_path)
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    app.add_middleware(SiteHeaders)
    mount_site(app, tmp_path)
    return TestClient(app)


def test_site_and_api_share_one_origin(tmp_path):
    c = make_site(tmp_path)
    assert c.get("/api/ping").json() == {"pong": True}

    # The cron-job.org ping: same body, no headers added by the site layer.
    health = c.get("/health")
    assert health.content == b'{"ok":true}' and "x-content-type-options" not in health.headers
    assert "cache-control" not in health.headers

    home = c.get("/")
    assert home.status_code == 200 and "<title>home</title>" in home.text
    assert home.headers["cache-control"] == "no-cache"  # a new deploy shows at once
    assert home.headers["x-content-type-options"] == "nosniff"

    missing = c.get("/no/such/page/")
    assert missing.status_code == 404 and "not here" in missing.text

    png = c.get("/kt/template-p1.png")
    assert png.headers["cache-control"] == "public, max-age=3600" and "content-encoding" not in png.headers


def test_precompressed_text_matches_what_the_browser_accepts(tmp_path):
    c = make_site(tmp_path)
    url = "/_next/static/chunks/app.js"
    for accept, encoding in (("br, gzip", "br"), ("gzip", "gzip"), ("identity", None)):
        r = c.get(url, headers={"Accept-Encoding": accept})
        assert r.status_code == 200
        assert r.headers.get("content-encoding") == encoding
        assert r.headers["content-type"].startswith("text/javascript")
        assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert r.headers["vary"] == "Accept-Encoding"
        assert r.text == JS  # the test client undoes gzip; check brotli by hand below
    raw = c.get(url, headers={"Accept-Encoding": "br"})
    assert len(raw.headers["content-length"]) and int(raw.headers["content-length"]) < len(JS) / 5
    assert brotli.decompress((tmp_path / "_next/static/chunks/app.js.br").read_bytes()).decode() == JS
    assert gzip.decompress((tmp_path / "_next/static/chunks/app.js.gz").read_bytes()).decode() == JS
