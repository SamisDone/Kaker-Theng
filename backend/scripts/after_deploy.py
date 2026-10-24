"""Check a live deployment end to end. Needs only Python 3.9+, no packages.

    python backend/scripts/after_deploy.py <API URL> <SITE URL> [page photo]

    e.g. python backend/scripts/after_deploy.py https://kaker-theng-api.onrender.com https://kaker-theng.pages.dev

Waits for a sleeping free server to wake, then checks: /health, the site,
both copies of the template, CORS from the site's address, that site and
server use the same template, and one page upload all the way to the
preview font. The photo defaults to backend/tests/data/sample-page1.jpg.
"""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "data" / "sample-page1.jpg"
results: list[tuple[bool, str]] = []


def check(ok: bool, what: str):
    results.append((ok, what))
    print(f"  [{'ok' if ok else 'FAIL'}] {what}", flush=True)
    return ok


def get(url: str, headers=None, method="GET", data=None, timeout=60):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.status, dict(res.headers), res.read()


def wait_for_health(api: str) -> float:
    start = time.time()
    while time.time() - start < 180:
        try:
            status, _, body = get(f"{api}/health", timeout=30)
            if status == 200 and json.loads(body) == {"ok": True}:
                return time.time() - start
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
        time.sleep(3)
    raise SystemExit("  [FAIL] /health did not answer within 3 minutes")


def multipart(field: str, filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    api, site = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    photo = Path(sys.argv[3]) if len(sys.argv) > 3 else SAMPLE

    print(f"API  {api}\nSITE {site}\n")
    print("Waking the API (a free server can take a minute)...")
    check(True, f"/health answered after {wait_for_health(api):.0f} s")
    t = time.time()
    get(f"{api}/health")
    check(time.time() - t < 2, f"/health is quick once awake ({(time.time() - t) * 1000:.0f} ms)")

    status, _, html = get(f"{site}/")
    check(status == 200 and "কাকের ঠ্যাং".encode() in html, "the site loads")
    _, _, raw = get(f"{site}/kt/layout.json")
    site_layout = json.loads(raw)
    status, _, pdf = get(f"{site}/kt/{site_layout['template_pdf']}")
    check(status == 200 and pdf[:5] == b"%PDF-", f"template PDF from the site ({len(pdf) // 1024} KB)")
    status, _, pdf = get(f"{api}/template.pdf", timeout=120)
    check(status == 200 and pdf[:5] == b"%PDF-", f"template PDF from the API ({len(pdf) // 1024} KB)")

    _, _, raw = get(f"{api}/api/info", timeout=120)
    info = json.loads(raw)
    check(
        info["template_version"] == site_layout["template_version"] and info["layout_fingerprint"] == site_layout["fingerprint"],
        f"site and API use the same template (v{site_layout['template_version']}, layout {site_layout['fingerprint']})",
    )

    _, headers, _ = get(
        f"{api}/api/sessions",
        method="OPTIONS",
        headers={"Origin": site, "Access-Control-Request-Method": "POST"},
    )
    allowed = {k.lower(): v for k, v in headers.items()}.get("access-control-allow-origin")
    check(allowed == site, f"CORS allows {site} (got {allowed!r}; fix ALLOWED_ORIGINS on Render if not)")

    print(f"\nUploading {photo.name} ...")
    _, _, raw = get(f"{api}/api/sessions", method="POST", data=b"")
    session = json.loads(raw)["id"]
    body, ctype = multipart("photo", photo.name, photo.read_bytes())
    t = time.time()
    _, _, raw = get(f"{api}/api/sessions/{session}/pages", method="POST", data=body, headers={"Content-Type": ctype, "Origin": site}, timeout=120)
    job = json.loads(raw)
    while job["status"] not in ("done", "error"):
        time.sleep(2)
        _, _, raw = get(f"{api}/api/jobs/{job['id']}")
        job = json.loads(raw)
    if not check(job["status"] == "done", f"page read in {time.time() - t:.0f} s" if job["status"] == "done" else f"upload failed: {job.get('error')}"):
        return finish()
    meta = job["result"]["session"]
    page = str(job["result"]["page"])
    cells = meta["pages"][page]["cells"]
    read = sum(1 for c in cells if c["status"] != "missing")
    check(read > 0, f"page {page}: {read} of {len(cells)} cells read")
    status, _, font = get(f"{api}/api/sessions/{session}/files/{meta['font']}")
    check(status == 200 and font[:4] == b"wOF2", f"preview font built ({len(font) // 1024} KB)")
    finish()


def finish():
    failed = [w for ok, w in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
