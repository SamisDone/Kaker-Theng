"""Find the template page in a photo and straighten it."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

from . import config as C

CORNER_BN = {"top-left": "উপরে বাঁয়ের", "top-right": "উপরে ডানের", "bottom-right": "নিচে ডানের", "bottom-left": "নিচে বাঁয়ের"}


class ScanError(Exception):
    """A problem the user can fix by taking another photo."""

    def __init__(self, code: str, en: str, bn: str, **details):
        super().__init__(en)
        self.code, self.en, self.bn, self.details = code, en, bn, details

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.en, "message_bn": self.bn, **self.details}


@dataclass
class FoundPage:
    page: int
    gray: np.ndarray  # canonical CANON_H_PX x CANON_W_PX, uint8
    missing_corners: list[str] = field(default_factory=list)
    version: int | None = None  # None: no version marker found


def _version(ids) -> int | None:
    v = [i - C.VERSION_MARKER_BASE for i in ids if C.VERSION_MARKER_BASE <= i < 50]
    return max(v) if v else None


def _version_on_page(warped: np.ndarray) -> int | None:
    """Second chance: look for the version marker where it should be on the
    straightened page, enlarged."""
    k = C.PX_PER_MM
    x, y = C.version_marker_origin_mm()
    pad = 6
    crop = warped[max(0, round((y - pad) * k)) : round((y + C.VERSION_MARKER_MM + pad) * k), max(0, round((x - pad) * k)) : round((x + C.VERSION_MARKER_MM + pad) * k)]
    if crop.size == 0:
        return None
    return _version(_detect(cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)))


@lru_cache(maxsize=1)
def _detector() -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    params.adaptiveThreshWinSizeMax = 53
    d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, C.ARUCO_DICT))
    return cv2.aruco.ArucoDetector(d, params)


def _marker_corners_mm(corner: str) -> np.ndarray:
    """The marker's 4 corners on the page, in ArUco order (TL, TR, BR, BL)."""
    x, y = C.marker_origin_mm(corner)
    s = C.MARKER_MM
    return np.array([(x, y), (x + s, y), (x + s, y + s), (x, y + s)], np.float32)


def _detect(gray: np.ndarray) -> dict[int, np.ndarray]:
    corners, ids, _ = _detector().detectMarkers(gray)
    if ids is None:
        return {}
    return {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners)}


def find_page(image: np.ndarray, expected_page: int | None = None) -> FoundPage:
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    found = _detect(gray)
    if len(found) < 4:
        # Small or soft photos: try again a bit sharper and larger.
        big = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        more = {k: v / 1.5 for k, v in _detect(big).items()}
        if len(more) > len(found):
            found = more

    pages = {}
    for marker_id in found:
        page = marker_id // 4
        if 1 <= page <= 3:
            pages[page] = pages.get(page, 0) + 1
    if not pages:
        raise ScanError(
            "no_markers",
            "Couldn't find the template's corner squares. Make sure all four black corner squares are in the photo.",
            "পাতার চার কোণের কালো চৌকো খুঁজে পাইনি। চারটে কোণই ছবিতে রাখুন।",
        )
    if len(pages) > 1:
        raise ScanError(
            "mixed_pages",
            "This photo shows corners from more than one page. Photograph one page at a time.",
            "ছবিতে একাধিক পাতার কোণ দেখা যাচ্ছে। একবারে একটা পাতার ছবি দিন।",
        )
    page = next(iter(pages))
    if expected_page and page != expected_page:
        raise ScanError(
            "wrong_page",
            f"This is page {page}, not page {expected_page}.",
            f"এটা {page} নম্বর পাতা, {expected_page} নম্বর নয়।",
            page=page,
        )

    ids = C.marker_ids(page)
    missing = [corner for corner, mid in zip(C.CORNERS, ids) if mid not in found]
    if len(missing) > 1:
        names_en = " and ".join(missing)
        names_bn = " আর ".join(CORNER_BN[m] for m in missing)
        raise ScanError(
            "missing_corners",
            f"Couldn't see the {names_en} corner square{'s' if len(missing) > 1 else ''}. "
            "Keep the whole page in the photo, without a shadow or finger over the corners.",
            f"{names_bn} কোণের চৌকো দেখা যাচ্ছে না। পুরো পাতাটা ছবিতে রাখুন, কোণে যেন ছায়া বা আঙুল না পড়ে।",
            page=page,
            missing_corners=missing,
        )

    # Three markers (12 points) still pin the homography down well.
    src, dst = [], []
    for corner, mid in zip(C.CORNERS, ids):
        if mid in found:
            src.append(found[mid])
            dst.append(_marker_corners_mm(corner) * C.PX_PER_MM)
    src_pts, dst_pts = np.concatenate(src), np.concatenate(dst)
    h, _ = cv2.findHomography(src_pts, dst_pts, 0)
    if h is None:
        raise ScanError("bad_geometry", "The page is too bent or tilted to straighten.", "পাতাটা খুব বাঁকা বা কাত হয়ে আছে, সোজা করতে পারছি না।")
    err = np.linalg.norm(cv2.perspectiveTransform(src_pts[None], h)[0] - dst_pts, axis=1).max()
    if err > 12:
        raise ScanError(
            "bad_geometry",
            "The page looks bent. Lay it flat and take the photo from straight above.",
            "পাতাটা ভাঁজ বা বাঁকা মনে হচ্ছে। সমান জায়গায় রেখে ঠিক ওপর থেকে ছবি তুলুন।",
            page=page,
        )
    warped = cv2.warpPerspective(gray, h, (C.CANON_W_PX, C.CANON_H_PX), flags=cv2.INTER_LINEAR, borderValue=255)
    version = _version(found)
    if version is None:
        version = _version_on_page(warped)
    return FoundPage(page, warped, missing, version)
