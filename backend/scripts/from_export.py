"""Rebuild a font from strokes a visitor exported on the site, and check it.

    python -X utf8 -m scripts.from_export <kaker-theng-strokes-....json> <out dir>

The file comes from "Export my strokes" on the My font screen (shown with
?debug=1, or by holding the heading). A plain {cell id: strokes} file
works too. Writes <out dir>/export.ttf, then the spacing report: glyph
advances against ink, colliding neighbours, and the sample words as PNG.
"""

import json
import sys
from pathlib import Path

from app.fontbuild import build_font
from app.glyphmap import build_layout, fingerprint
from app.strokes import StrokeError, check_strokes, drawing
from scripts import spacing_report


def main():
    path, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    strokes = data.get("cells", data) if isinstance(data, dict) else {}
    if data.get("fingerprint") not in (None, fingerprint()):
        print(f"note: drawn on another template layout ({data['fingerprint']}); cells may not match")
    for key in ("exported", "template_version", "pen_mm", "screen", "browser", "session"):
        if key in data:
            print(f"{key}: {data[key]}")
    cells = {c.id: c for c in build_layout().cells}
    drawings, skipped = [], []
    for cid, s in strokes.items():
        if cid not in cells or not s:
            skipped.append(cid)
            continue
        try:
            drawings.append(drawing(cells[cid], check_strokes(s, cells[cid])))
        except StrokeError as err:
            skipped.append(f"{cid} ({err})")
    print(f"{len(drawings)} letters" + (f"; skipped {', '.join(skipped)}" if skipped else ""))
    font = build_font(drawings, "Export Check")
    (out / "export.ttf").write_bytes(font.ttf)
    sys.argv = [sys.argv[0], str(out / "export.ttf"), str(out), "export"]
    spacing_report.main()


if __name__ == "__main__":
    main()
