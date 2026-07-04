"""Unit conversions — the cheapest insurance against Tier-0 mass-balance bugs."""

from __future__ import annotations

import pytest

from watermark.hydrology import units


def test_mgd_to_cfs_matches_usgs_factor() -> None:
    # 1.2 MGD (American II design flow) -> 1.857 cfs, per the Ohio EPA fact sheet.
    assert units.mgd_to_cfs(1.0) == pytest.approx(1.547, abs=1e-3)
    assert units.mgd_to_cfs(1.2) == pytest.approx(1.8564, abs=1e-3)


def test_cfs_mgd_round_trip() -> None:
    assert units.cfs_to_mgd(units.mgd_to_cfs(2.5)) == pytest.approx(2.5, rel=1e-9)


def test_acres_sqmi() -> None:
    assert units.acres_to_sqmi(640.0) == pytest.approx(1.0)
    assert units.sqmi_to_acres(1.0) == pytest.approx(640.0)


def test_acre_ft_and_acre_mm_conversions() -> None:
    # 1 acre-ft = 325,851 gal = 0.325851 MG (standard); 1 acre-inch = 27,154 gal.
    assert pytest.approx(0.325851, abs=1e-6) == units.MG_PER_ACRE_FT
    # 1 mm of depth over 1 acre = 27,154 / 25.4 gal = 0.00106906 MG.
    assert units.acre_mm_to_mg(1.0, 1.0) == pytest.approx(0.00106906, abs=1e-8)
    # Linear in both depth and area.
    assert units.acre_mm_to_mg(25.4, 1.0) == pytest.approx(0.027154, abs=1e-6)  # 1 acre-inch
    assert units.acre_mm_to_mg(2.0, 100.0) == pytest.approx(200 * units.MG_PER_ACRE_MM)
