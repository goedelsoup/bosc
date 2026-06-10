"""Economics baseline: the QCEW connector replays offline fixtures, builds a sector
mix with location quotients, and an offline cache miss raises (no silent network).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.config import Settings
from bosc.connectors import OfflineError
from bosc.economics.baseline import build_baseline, load_baseline
from bosc.economics.connectors.census import fetch_population_series
from bosc.economics.connectors.qcew import fetch_county_industries

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_qcew_connector_offline(econ_settings: Settings) -> None:
    ie = fetch_county_industries(year=2023, fips="39003", settings=econ_settings)
    assert ie.year == 2023 and ie.fips == "39003"
    assert ie.total_employment.value > 0
    assert ie.total_employment.verified  # connector-sourced
    # Manufacturing is a real, dominant, export-oriented sector here.
    mfg = next(s for s in ie.sectors if s.naics == "31-33")
    assert mfg.location_quotient is not None and mfg.location_quotient.value > 1.5
    # Sectors are ranked by employment.
    emps = [s.annual_avg_employment.value for s in ie.sectors]
    assert emps == sorted(emps, reverse=True)


def test_census_population_offline(econ_settings: Settings) -> None:
    series = fetch_population_series(years=[2010, 2023], fips="39003", settings=econ_settings)
    assert series.fips == "39003" and series.area_name == "Allen County, Ohio"
    assert [p.year for p in series.points] == [2010, 2023]
    assert all(p.population.verified for p in series.points)  # connector-sourced
    # Allen County's population declined over the span (the documented trend).
    assert series.points[-1].population.value < series.points[0].population.value


def test_build_baseline_trend(econ_settings: Settings) -> None:
    baseline = build_baseline(years=[2018, 2023], settings=econ_settings)
    assert [t.year for t in baseline.trend] == [2018, 2023]
    assert baseline.latest.year == 2023
    assert baseline.latest.sectors
    # Population is folded in from the committed ACS5 fixtures (offline).
    assert baseline.population is not None
    assert len(baseline.population.points) == 4


def test_offline_miss_raises(econ_settings: Settings) -> None:
    with pytest.raises(OfflineError):
        fetch_county_industries(year=1999, fips="39003", settings=econ_settings)


def test_committed_baseline_loads() -> None:
    """The committed reference YAML round-trips into the model (what the site reads)."""
    baseline = load_baseline(REPO_ROOT / "data" / "reference")
    assert baseline is not None
    assert baseline.fips == "39003"
    assert baseline.latest.sectors
