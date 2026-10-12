"""Shared constants: paths and the template geometry.

The template generator and the scanner both read these, so a cell printed
at a given place is cut from exactly the same place in the scanned photo.
"""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
ASSETS_DIR = BACKEND_DIR / "assets"
BASE_FONT_PATH = ASSETS_DIR / "NotoSansBengali-Regular.ttf"
OFL_PATH = ASSETS_DIR / "OFL.txt"
LAYOUT_CACHE_PATH = ASSETS_DIR / "layout.json"  # written by scripts/make_template.py

# --- Colours -----------------------------------------------------------------
# Everything printed inside a cell is this light grey. It has to survive a
# black-and-white laser print or photocopy (which darken greys through dot
# gain) and still come out clearly lighter than pen ink, so the scanner can
# separate the two by darkness alone. 22% tint.
GUIDE_RGB = (0xC6, 0xC6, 0xC6)
INK_RGB = (0x1D, 0x21, 0x40)

# --- Page (millimetres, origin top-left, y grows downwards) -------------------
PAGE_W_MM = 210.0
PAGE_H_MM = 297.0

# Canonical warped image: A4 at 300 dpi.
CANON_W_PX = 2480
CANON_H_PX = 3508
PX_PER_MM = CANON_W_PX / PAGE_W_MM

# ArUco markers, DICT_4X4_50. Page n (1-based) uses ids 4n .. 4n+3, in the
# order top-left, top-right, bottom-right, bottom-left.
ARUCO_DICT = "DICT_4X4_50"
MARKER_MM = 16.0
MARKER_MARGIN_MM = 8.0
CORNERS = ("top-left", "top-right", "bottom-right", "bottom-left")


def marker_origin_mm(corner: str) -> tuple[float, float]:
    """Top-left corner of the marker square for a page corner."""
    far_x = PAGE_W_MM - MARKER_MARGIN_MM - MARKER_MM
    far_y = PAGE_H_MM - MARKER_MARGIN_MM - MARKER_MM
    return {
        "top-left": (MARKER_MARGIN_MM, MARKER_MARGIN_MM),
        "top-right": (far_x, MARKER_MARGIN_MM),
        "bottom-right": (far_x, far_y),
        "bottom-left": (MARKER_MARGIN_MM, far_y),
    }[corner]


def marker_ids(page: int) -> list[int]:
    return [4 * page + i for i in range(4)]


# --- Cell grid ---------------------------------------------------------------
CELL_MM = 22.0
COLS = 8
ROWS = 10
GRID_X_MM = (PAGE_W_MM - COLS * CELL_MM) / 2  # 17 mm
GRID_Y_MM = 39.0

# --- The ONE transform from cell to font units --------------------------------
# Inside every cell the baseline maps to y=0 and the printed মাত্রা / cap line
# maps to HEADLINE_UNITS. HEADLINE_UNITS is measured from the base font's ক at
# startup (centre of its headline bar), so this is only the vertical layout of
# the guides. Everything else follows from the scale.
CELL_TOP_UNITS = 1000  # highest ink we leave room for (reph, ই, ঈ ...)
CELL_BOTTOM_UNITS = -330  # lowest ink (ৃ, ্, Latin descenders)
CELL_PAD_MM = 0.8
MM_PER_UNIT = (CELL_MM - 2 * CELL_PAD_MM) / (CELL_TOP_UNITS - CELL_BOTTOM_UNITS)
BASELINE_FROM_TOP_MM = CELL_PAD_MM + CELL_TOP_UNITS * MM_PER_UNIT
LATIN_XHEIGHT_RATIO = 0.68  # dotted guide on the English page only

# Scanner: ink inside this inset from the cell border is ignored.
CELL_CUT_INSET_MM = 1.0
