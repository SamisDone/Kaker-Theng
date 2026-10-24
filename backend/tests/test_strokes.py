"""Drawing in the browser: strokes to outlines, the order, the API."""

import math
import os
import tempfile
import time

os.environ.setdefault("KT_DATA_DIR", tempfile.mkdtemp(prefix="kt-test-"))

import pytest
from fastapi.testclient import TestClient

from app import config as C
from app import main
from app.coverage import pages_1_2_coverage
from app.draworder import draw_order
from app.glyphmap import build_layout
from app.guides import baseline_mm
from app.strokes import PEN_MM, StrokeError, check_strokes, drawing
from app.wordcov import pages_1_2_word_coverage
from tests.synth import make_page
from tests.synth_strokes import drawn_cells


def cell(text):
    return next(c for c in build_layout().cells if c.text == text)


def area(contour):
    pts = [contour.start] + [s[1] for s in contour.segments]
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def test_a_ring_is_an_outline_with_a_hole_at_the_pen_width():
    o = cell("O")
    ring = [[(11 + 4 * math.cos(t / 24 * 2 * math.pi), 10 + 5 * math.sin(t / 24 * 2 * math.pi)) for t in range(25)]]
    d = drawing(o, ring)
    assert len(d.contours) == 2
    outer, hole = sorted(d.contours, key=lambda c: abs(area(c)), reverse=True)
    assert area(outer) < 0 < area(hole)  # TrueType: outer clockwise, hole the other way
    pen = PEN_MM / C.MM_PER_UNIT
    assert abs((d.bbox[2] - d.bbox[0]) - (8 / C.MM_PER_UNIT + pen)) < 3  # 8 mm across plus the pen


def test_the_one_transform_puts_the_baseline_at_zero():
    a = cell("a")
    base = baseline_mm(a) - a.box_mm()[1]
    d = drawing(a, [[(5.0, base), (15.0, base)]])  # a line along the baseline
    pen = PEN_MM / C.MM_PER_UNIT
    assert abs(d.bbox[1] + pen / 2) < 1 and abs(d.bbox[3] - pen / 2) < 1
    assert abs(d.bbox[0] - (5 / C.MM_PER_UNIT - pen / 2)) < 1


def test_a_tap_is_a_round_dot():
    d = drawing(cell("i"), [[(11.0, 4.0)]])
    w, h = d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1]
    assert abs(w - PEN_MM / C.MM_PER_UNIT) < 2 and abs(w - h) < 2


def test_bad_strokes_are_refused():
    a = cell("a")
    with pytest.raises(StrokeError):
        check_strokes([[(50.0, 5.0)]], a)  # far outside the box
    with pytest.raises(StrokeError):
        check_strokes([[(1.0, float("nan"))]], a)
    with pytest.raises(StrokeError):
        check_strokes([[(1.0, 1.0)]] * 81, a)
    assert check_strokes([[[1, 2], [3, 4]]], a) == [[(1.0, 2.0), (3.0, 4.0)]]


def test_draw_order_most_useful_first():
    layout = {c.id: c for c in build_layout().cells}
    order = draw_order()
    assert sorted(order) == sorted(layout)
    first = [layout[i] for i in order[:10]]
    assert all(c.kind != "latin" and c.page == 2 for c in first)
    assert "কা" in [c.text for c in first] and "র" in [c.text for c in first]
    assert all(layout[i].group == "part" for i in order[-18:])  # fragment parts last
    # The hasanta is in every conjunct: early, or coverage stays at 0 for
    # dozens of letters (it did when it came last).
    assert "ক্" in [c.text for c in first[:5]]
    from app.basefont import simulated_shaper
    from app.coverage import _specials, coverage, derivable_from, plain_glyphs

    bangla = [layout[i].glyph for i in order if layout[i].kind != "latin"]
    w = set(bangla[:30])
    assert coverage(simulated_shaper(w | derivable_from(w) | _specials()), plain_glyphs(w)) > 0.4


def wait(client, job_id, timeout=180):
    t = time.time()
    while time.time() - t < timeout:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.2)
    raise TimeoutError(job_id)


def test_drawn_letters_make_the_same_font_as_paper():
    strokes = drawn_cells((1, 2))
    with TestClient(main.app) as c:
        sid = c.post("/api/sessions").json()["id"]
        r = c.put(f"/api/sessions/{sid}/drawn", json={"cells": strokes})
        assert r.status_code == 200 and len(r.json()["drawn"]) == len(strokes)
        job = wait(c, c.post(f"/api/sessions/{sid}/preview").json()["id"])
        assert job["status"] == "done", job
        meta = job["result"]["session"]
        # Drawn pages 1+2 cover exactly what written pages 1+2 do.
        assert meta["coverage"] == pytest.approx(pages_1_2_coverage(), abs=1e-9)
        assert meta["word_coverage"] == pytest.approx(pages_1_2_word_coverage(), abs=1e-9)
        assert 0.5 < meta["word_coverage"] < meta["coverage_targets"]["words_all_pages"] <= 1
        assert c.get(f"/api/sessions/{sid}/files/{meta['font']}").content[:4] == b"wOF2"
        # Drawn only, no photo: the download works (it once asked for a photo).
        job = wait(c, c.post(f"/api/sessions/{sid}/download", json={"name": "Drawn", "format": "ttf"}).json()["id"])
        assert job["status"] == "done", job

        # Mixing: a newer photo of page 1 replaces the drawn page 1 letters...
        photo = make_page(1, "laser").photo_jpeg
        job = wait(c, c.post(f"/api/sessions/{sid}/pages", files={"photo": ("p.jpg", photo, "image/jpeg")}).json()["id"])
        assert job["status"] == "done"
        from app.sessions import _dir, _drawings, load

        by_cell = {d.cell_id: d for d in _drawings(_dir(sid), load(sid))}
        a_drawn = drawing(cell("a"), strokes[cell("a").id])
        assert by_cell[cell("a").id].contours != a_drawn.contours
        # ...and drawing one again afterwards wins over the photo.
        c.put(f"/api/sessions/{sid}/drawn", json={"cells": {cell("a").id: strokes[cell("a").id]}})
        by_cell = {d.cell_id: d for d in _drawings(_dir(sid), load(sid))}
        assert by_cell[cell("a").id].contours == a_drawn.contours

        # An empty list removes a drawn letter; bad input is refused clearly.
        meta = c.put(f"/api/sessions/{sid}/drawn", json={"cells": {cell("ক").id: []}}).json()
        assert cell("ক").id not in meta["drawn"]
        bad = c.put(f"/api/sessions/{sid}/drawn", json={"cells": {"p9-99": [[[1, 1]]]}})
        assert bad.status_code == 400 and bad.json()["message_bn"]
