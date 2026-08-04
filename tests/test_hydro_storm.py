"""NOAA Atlas-14 connector + the pre/post stormwater scenario (offline, hermetic)."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import noaa_atlas14
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.pipeline.hydrology import run_storm


def test_design_storm_from_fixture(hydro_settings: Settings) -> None:
    storm = noaa_atlas14.design_storm(
        lat=40.797, lon=-84.123, return_period_yr=25, settings=hydro_settings
    )
    assert storm.return_period_yr == 25
    assert storm.duration_hr == 24.0
    assert storm.depth.value == pytest.approx(4.25, abs=0.01)
    assert storm.depth.source == "connector"
    assert "Atlas-14" in (storm.depth.citation or "")


def test_design_storm_is_dated_and_rated_by_how_it_was_served(hydro_settings: Settings) -> None:
    """A replayed committed fixture may not read as a fresh HDSC pull (WS-21, #1621).

    A published precipitation-frequency estimate carries no observation timestamp of its
    own, so the retrieval time *is* the depth's date — and the depth used to carry no date
    at all. Under the offline fixtures this test runs on, the recorded pull is months old,
    which is past the connector's freshness window: still ``connector``-sourced (a fixture
    is a recorded live pull, not a fabrication) but no longer entitled to full confidence.
    """
    storm = noaa_atlas14.design_storm(
        lat=40.797, lon=-84.123, return_period_yr=25, settings=hydro_settings
    )
    assert storm.depth.asof is not None
    assert storm.depth.source == "connector" and storm.depth.verified is True
    assert storm.depth.confidence == "medium"


def test_design_storm_return_period_monotonic(hydro_settings: Settings) -> None:
    d10 = noaa_atlas14.design_storm(
        lat=40.797, lon=-84.123, return_period_yr=10, settings=hydro_settings
    )
    d100 = noaa_atlas14.design_storm(
        lat=40.797, lon=-84.123, return_period_yr=100, settings=hydro_settings
    )
    assert d100.depth.value > d10.depth.value


def test_storm_scenario_post_exceeds_pre(hydro_settings: Settings) -> None:
    runoff, findings = run_storm(return_period_yr=25, settings=hydro_settings, live=True)

    # Paving the footprint raises the curve number, peak, and volume.
    assert runoff.post.curve_number > runoff.pre.curve_number
    assert runoff.peak_increase_cfs > 0
    assert runoff.volume_increase_acft > 0

    # Impervious development shortens travel time: the post scenario runs on a shorter Tc
    # than the pervious pre scenario (#1163), so it doesn't understate the post/pre ratio.
    assert 0 < runoff.post.tc_hr < runoff.pre.tc_hr

    # The footprint is document-sourced; the storm is connector-sourced (fixture).
    assert runoff.area.source == "document"
    assert runoff.storm.depth.source == "connector"

    # Both screening findings flag (uncontrolled increase -> detention required).
    assert all(not f.ok for f in findings)
    checks = {f.check for f in findings}
    assert checks == {"post-vs-pre-peak", "detention-deficit"}


def test_storm_runoff_volume_matches_depth_over_area(hydro_settings: Settings) -> None:
    # Self-consistency invariant for the *pipeline* runoff (real parcel area, both the
    # pre- and post-development branches): the hydrograph volume must equal the runoff
    # depth spread over the footprint, `volume_acft ~= runoff_depth_in/12 * area_acres`.
    # test_hydro_solver.py locks this for one hand-built `simulate_runoff` call; this
    # locks it end-to-end through `run_storm`, so the two SCS outputs can't silently
    # diverge in the real footprint the site actually screens.
    runoff, _findings = run_storm(return_period_yr=25, settings=hydro_settings, live=True)
    area_acres = runoff.area.value
    for branch in (runoff.pre, runoff.post):
        expected_acft = branch.runoff_depth_in / 12.0 * area_acres
        assert branch.volume_acft == pytest.approx(expected_acft, rel=0.03)  # UH-tail trunc tol


def test_storm_offline_fallback_is_flagged(tmp_path: Path) -> None:
    # Empty data dir => no cache, no fixtures => cited fallback depth, tagged assumption.
    from watermark.hydrology.stormwater import _resolve_storm

    settings = Settings(data_dir=tmp_path, hydro_offline=True)
    storm = _resolve_storm(25, settings=settings, live=True)
    assert storm.depth.source == "assumption"
    assert storm.depth.value == pytest.approx(4.25, abs=0.01)
    assert "offline" in (storm.depth.citation or "")


def test_storm_offline_fallback_raises_when_site_lacks_depth(tmp_path: Path) -> None:
    # #1604: a site whose profile carries no cited Atlas-14 fallback for the requested
    # return period must FAIL LOUDLY, naming the (site, return-period) it needs — never
    # silently substitute Lima's 4.25 (a wrong-magnitude, cross-site, cross-frequency depth
    # presented as that site's design storm).
    from watermark.hydrology.stormwater import _resolve_storm

    settings = Settings(data_dir=tmp_path, hydro_offline=True, site="urbana")
    with pytest.raises(HydroOfflineError) as exc:
        _resolve_storm(100, settings=settings, live=True)
    assert "urbana" in str(exc.value)
    assert "100" in str(exc.value)


def test_duration_hours_derived_from_label() -> None:
    # #1603: hours come from the duration label unit, not a 3-entry lookup that defaulted
    # every non-{6,12,24}-hr duration to 24.0.
    d = noaa_atlas14._duration_to_hours
    assert d("24-hr") == 24.0
    assert d("6-hr") == 6.0
    assert d("3-hr") == 3.0  # regression: previously fell through to the 24.0 default
    assert d("5-min") == pytest.approx(5.0 / 60.0)
    assert d("2-day") == 48.0


def test_design_storm_carries_true_duration_hours(hydro_settings: Settings) -> None:
    # #1603: a 3-hr design storm is tagged duration_hr=3.0 (not 24.0), so the Type-II
    # builder no longer stretches a 3-hr depth across a full day.
    storm = noaa_atlas14.design_storm(
        lat=40.797, lon=-84.123, return_period_yr=25, duration="3-hr", settings=hydro_settings
    )
    assert storm.duration_hr == 3.0
    assert storm.depth.value == pytest.approx(2.75, abs=0.01)  # fixture row "3-hr", col 25-yr


def test_quantiles_grid_dimension_check() -> None:
    # #1603: reading depths by fixed grid position is only safe if the grid is the expected
    # 19x10 shape; a reordered/resized NOAA table must raise, not return the wrong cell.
    good = [[0.0] * len(noaa_atlas14._RETURN_PERIODS) for _ in noaa_atlas14._DURATIONS]
    assert noaa_atlas14._validate_grid(good) is good
    with pytest.raises(ValueError, match="quantiles grid"):
        noaa_atlas14._validate_grid([[1.0, 2.0, 3.0]])  # wrong shape
    with pytest.raises(ValueError, match="quantiles grid"):
        # right row count, one short row (a dropped return period)
        short = [[0.0] * len(noaa_atlas14._RETURN_PERIODS) for _ in noaa_atlas14._DURATIONS]
        short[9] = short[9][:-1]
        noaa_atlas14._validate_grid(short)
