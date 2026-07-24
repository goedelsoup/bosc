"""LSC status-report connector — workbook parsing + offline fixture replay (hermetic)."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import lsc
from watermark.hydrology.connectors._cache import HydroOfflineError


def test_fetch_status_report_from_fixture(hydro_settings: Settings) -> None:
    report = lsc.fetch_status_report("136", settings=hydro_settings)
    assert report.ga == "136"
    assert report.source_url.endswith("/136/files/136th-ga-status-report.xlsx")
    assert "06/05/2026" in (report.as_of or "")
    assert report.bills

    hb1 = next(b for b in report.bills if b.identifier == "HB 1")
    assert hb1.bill_type == "H. B."
    assert hb1.sponsors == ["King", "Klopfenstein"]
    assert hb1.short_title == "Enact Ohio Property Protection Act"
    assert hb1.house.introduced == "1/23/2025"
    assert hb1.house.cmte_assigned == "H. PS"
    # Empty cells are genuine None, never a fabricated default.
    assert hb1.house.passed_3rd is None
    assert hb1.senate.introduced is None
    assert hb1.effective_date is None


def test_default_ga_comes_from_settings(hydro_settings: Settings) -> None:
    # hydro_settings doesn't override lsc_default_ga, so the default (136) is used,
    # which the committed fixture covers.
    report = lsc.fetch_status_report(settings=hydro_settings)
    assert report.ga == hydro_settings.lsc_default_ga == "136"


def test_offline_unknown_ga_raises(hydro_settings: Settings) -> None:
    # No fixture for the 99th GA -> offline cache miss is an actionable error.
    with pytest.raises(HydroOfflineError):
        lsc.fetch_status_report("99", settings=hydro_settings)


def test_identifier_normalization() -> None:
    assert lsc._identifier("H. B.", "1") == "HB 1"
    assert lsc._identifier("S. C. R.", "12") == "SCR 12"
    assert lsc._identifier(None, "5") == "5"


def test_ordinal_suffix() -> None:
    assert lsc._ordinal_suffix("136") == "th"
    assert lsc._ordinal_suffix("131") == "st"
    assert lsc._ordinal_suffix("132") == "nd"
    assert lsc._ordinal_suffix("133") == "rd"
    assert lsc._ordinal_suffix("113") == "th"  # the teens are all "th"


def test_header_anchors_validate_the_letter_map() -> None:
    """A row-2 header matching the expected anchors passes; a column shift is surfaced (WS-25)."""
    good = {"C": "Primary Sponsor(s)", "E": "Short Title", "R": "Note"}
    assert lsc._header_mismatches(good) == []
    # Case-insensitive substring, so wording variants still line up.
    assert lsc._header_mismatches({"C": "SPONSOR", "E": "Title", "R": "Notes"}) == []
    # A one-column shift (E now carries the House block) trips the title + sponsor anchors.
    shifted = {"C": "Short Title", "E": "House Introduced", "R": "Note"}
    mismatches = lsc._header_mismatches(shifted)
    assert any("col C" in m for m in mismatches)
    assert any("col E" in m for m in mismatches)
    assert not any("col R" in m for m in mismatches)
