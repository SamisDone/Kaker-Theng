"""The website's static copy of the layout must match the backend's."""

import json
from pathlib import Path

import pytest

from app.glyphmap import build_layout, fingerprint

ASSETS = Path(__file__).resolve().parents[2] / "frontend" / "public" / "kt" / "layout.json"


@pytest.mark.skipif(not ASSETS.exists(), reason="frontend assets not exported")
def test_frontend_layout_is_current():
    data = json.loads(ASSETS.read_text(encoding="utf-8"))
    assert data["fingerprint"] == fingerprint(), "run: python -m scripts.export_frontend_assets"
    exported = [c["id"] for p in ("1", "2", "3") for c in data["pages"][p]["cells"]]
    assert exported == [c.id for c in build_layout().cells]
