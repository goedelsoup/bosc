"""Tier-1 AERMOD dispersion: receptor concentration screen vs NAAQS + event-anchored
calibration (#1182). Hermetic — the NAAQS table + deck read committed data; the AERMOD binary
is absent so the run degrades to ``available=False`` (no fabricated concentration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.air.aermod import dispersion as d
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def air_settings() -> Settings:
    """Lima, offline, no AERMOD binary — deck + NAAQS resolve; the run degrades gracefully."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        aermod_bin="",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )


# --- NAAQS reference table ----------------------------------------------------------


def test_naaqs_table_covers_the_criteria_pollutants(air_settings: Settings) -> None:
    stds = d.load_naaqs(settings=air_settings)
    # Every standard is a positive µg/m³ limit; NOx is screened as NO2; VOC has no NAAQS.
    assert stds
    pollutants = {s.pollutant for s in stds}
    assert {"NOx", "CO", "PM10", "PM2.5", "SO2"} <= pollutants
    assert "VOC" not in pollutants  # ozone precursor — no direct NAAQS
    assert all(s.standard_ug_m3 > 0 for s in stds)
    nox_1h = d.naaqs_for("NOx", "1", settings=air_settings)
    assert nox_1h is not None
    assert nox_1h.naaqs_species == "NO2" and nox_1h.standard_ug_m3 == 188.0


def test_naaqs_for_returns_none_for_undefined_period(air_settings: Settings) -> None:
    # PM10 has only a 24-hour standard; a 1-hour lookup finds nothing.
    assert d.naaqs_for("PM10", "1", settings=air_settings) is None


# --- concentration screen -----------------------------------------------------------


def test_screen_flags_exceedance_and_computes_pct(air_settings: Settings) -> None:
    # NOx 1-hr peak 210 (over the 188 NO2 standard), annual 40 (under 100).
    screens = {
        s.averaging_period: s
        for s in d.screen_concentrations("NOx", {"1": 210.0, "ANNUAL": 40.0}, settings=air_settings)
    }
    assert screens["1"].exceeds_naaqs is True
    assert screens["1"].naaqs_ug_m3 == 188.0
    assert screens["1"].pct_of_naaqs == pytest.approx(111.7, abs=0.1)
    assert screens["ANNUAL"].exceeds_naaqs is False
    assert screens["ANNUAL"].pct_of_naaqs == pytest.approx(40.0, abs=0.1)


def test_screen_period_without_a_standard_still_reports(air_settings: Settings) -> None:
    # A 3-hour NOx average has no NAAQS: modeled peak reported, no comparison.
    screens = d.screen_concentrations("NOx", {"3": 50.0}, settings=air_settings)
    assert len(screens) == 1
    assert screens[0].naaqs_ug_m3 is None
    assert screens[0].pct_of_naaqs is None
    assert screens[0].exceeds_naaqs is False


# --- dispersion run: graceful degradation (no binary) -------------------------------


def test_run_dispersion_degrades_without_binary(air_settings: Settings) -> None:
    res = d.run_dispersion(pollutant="NOx", settings=air_settings)
    assert res is not None
    assert res.available is False  # no AERMOD binary
    assert res.screens == []  # nothing fabricated
    assert res.any_naaqs_exceeded is False
    # The deck IS real: the permit NOx load-point rate resolved to a source g/s.
    assert res.source_emission_g_s == pytest.approx(9.5481, rel=1e-4)
    assert res.stack_is_assumption is True  # Lima's stack is CBI-redacted
    assert "degraded" in res.note or "unavailable" in res.note


def test_dispersion_none_for_site_without_facility() -> None:
    # A site with no documented facility has no fleet/rates to model → None (section locks).
    # xenia is deliberately facility-less (Findlay now carries a disclosed SiteFacility, #1459 —
    # but with no air permit / genset fleet, so its dispersion would still lock).
    xenia = Settings(
        site="xenia",
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )
    assert d.run_dispersion(pollutant="NOx", settings=xenia) is None


# --- event-anchored calibration -----------------------------------------------------


def test_calibration_dispersion_is_event_anchored(air_settings: Settings) -> None:
    res = d.run_calibration_dispersion(pollutant="NOx", settings=air_settings)
    assert res is not None
    assert res.event is not None
    assert res.event.order_id == "202-26-33"
    # The order authorizes availability, not this facility's runtime — dispatch stays [open].
    assert res.event.facility_dispatch_confirmed is False
    assert res.factors_basis == "permit" and res.load_regime == "load"
    # A caveat states the anchoring + the open facility-dispatch question.
    assert any("Event-anchored" in c for c in res.caveats)
    assert any(
        "no monitored background" in c.lower() or "background" in c.lower() for c in res.caveats
    )


def test_calibration_dispersion_co_uses_short_term_periods(air_settings: Settings) -> None:
    res = d.run_calibration_dispersion(
        pollutant="CO", averaging_periods=("1", "8"), settings=air_settings
    )
    assert res is not None
    assert res.averaging_periods == ["1", "8"]
    assert res.pollutant == "CO"
