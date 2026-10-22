"""Template versions: never read a page with the wrong cell map."""

import pytest

from app import config as C
from app.pipeline import decode_image, process_page
from app.scan import ScanError, find_page
from app.versions import current_fingerprints, history
from tests.synth import MODES, make_page


def test_history_matches_current_layout():
    assert history()[str(C.TEMPLATE_VERSION)] == current_fingerprints(), "run python -m scripts.make_template"


@pytest.mark.parametrize("mode", MODES)
def test_version_marker_is_read(mode):
    found = find_page(decode_image(make_page(2, mode).photo_jpeg))
    assert found.version == C.TEMPLATE_VERSION


def test_old_print_of_unchanged_page_is_still_read():
    result = process_page(decode_image(make_page(1, "laser", hide_version=True).photo_jpeg))
    assert result.page == 1


def test_old_print_of_changed_page_is_refused():
    with pytest.raises(ScanError) as err:
        process_page(decode_image(make_page(2, "laser", hide_version=True).photo_jpeg))
    assert err.value.code == "old_template"
    assert err.value.details["current_version"] == C.TEMPLATE_VERSION
