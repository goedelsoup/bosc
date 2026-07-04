"""NOAA Atlas-14 connector + the pre/post stormwater scenario (offline, hermetic)."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import noaa_atlas14
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
