"""Event-anchored dispatch calibration (#1174 → the Tier-0 half of #1182).

Hermetic: reads the committed captured event (`data/extracted/grid/pjm-202c-emergency-2026.event.yaml`)
and the Lima permit; no network. Verifies the calibration grounds the runtime band in the
captured order's window while keeping facility-level dispatch [open] (never fabricated).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.air.calibration import (
    EventAnchoredAssumptions,
    calibrate_dispatch,
    event_anchored_runtime,
    event_anchored_scenario,
    load_captured_event,
)
from watermark.air.scenario import baseline_scenario, diff, evaluate
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def air_settings() -> Settings:
    """Lima, offline: committed event + AP-42 + permit read from real data, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )


def test_load_captured_event_reads_verified_window(air_settings: Settings) -> None:
    ev = load_captured_event(settings=air_settings)
    assert ev is not None
    # The backup-gen order (202-26-33) runs 2026-06-30T23:59 -> 2026-07-03T23:59 = 72 h.
    assert ev.order_id == "202-26-33"
    assert ev.authorized_window_hours.value == pytest.approx(72.0)
    # The window is read straight from the captured order -> a document-grounded value.
    assert ev.authorized_window_hours.source == "document"
    assert ev.authorized_window_hours.verified
    # The order authorized data-center backup generation...
    assert ev.backup_generation_authorized is True
    # ...but whether THIS facility ran is [open] — never asserted from a region-wide order.
    assert ev.facility_dispatch_confirmed is False
    assert any("facility" in c and "[open]" in c for c in ev.caveats)


def test_missing_event_degrades_to_none(air_settings: Settings) -> None:
    # A checkout without the captured event returns None (falls back to the pure #1176 band).
    assert (
        load_captured_event(event_relpath="grid/does-not-exist.event.yaml", settings=air_settings)
        is None
    )
    assert (
        calibrate_dispatch(event_relpath="grid/does-not-exist.event.yaml", settings=air_settings)
        is None
    )


def test_runtime_is_window_anchored_and_band_ordered(air_settings: Settings) -> None:
    est = calibrate_dispatch(settings=air_settings)
    assert est is not None
    # high band = full authorized window x recurrence (default 1/yr) = 72 h, and is [derived]
    # from the verified window — no longer a pure escalation-fraction assumption.
    assert est.runtime_hours_high.value == pytest.approx(72.0)
    assert est.runtime_hours_high.source == "derived"
    # low/central scale the window by the unobserved intra-window duty -> [inference].
    assert est.runtime_hours_central.source == "assumption"
    assert est.runtime_hours_low.source == "assumption"
    assert (
        est.runtime_hours_low.value
        <= est.runtime_hours_central.value
        <= est.runtime_hours_high.value
    )


def test_assumptions_scale_runtime_off_the_verified_window(air_settings: Settings) -> None:
    ev = load_captured_event(settings=air_settings)
    assert ev is not None
    window = ev.authorized_window_hours.value  # 72 h
    est = event_anchored_runtime(
        ev,
        assumptions=EventAnchoredAssumptions(
            duty_fraction_low=0.1,
            duty_fraction_central=0.5,
            duty_fraction_high=1.0,
            events_per_year=2.0,
        ),
    )
    # runtime = window x duty x events_per_year.
    assert est.runtime_hours_high.value == pytest.approx(window * 1.0 * 2.0)
    assert est.runtime_hours_central.value == pytest.approx(window * 0.5 * 2.0)
    assert est.runtime_hours_low.value == pytest.approx(window * 0.1 * 2.0)
    assert est.events_per_year.value == 2.0


def test_event_anchored_scenario_evaluates_against_caps(air_settings: Settings) -> None:
    """The headline: the captured event's full authorized window breaches the NOx cap.

    The epic's investigable question, answered against a real order. At the full authorized
    72 h window (the [derived] ceiling), the fleet at load emits ~132% of the NOx
    synthetic-minor cap — a breach. A partial (central-duty) event stays under. Both are
    [inference]/[open] on whether the facility actually ran; this dimensions the model, it
    does not assert a logged runtime.
    """
    est = calibrate_dispatch(settings=air_settings)
    assert est is not None

    high = event_anchored_scenario(est, band="high")
    # Distinct scenario name (won't clobber the pure #1176 band's artifact) and event-cited.
    assert high.name == "reliability_dispatch_event_high"
    assert high.runtime_hours.citation is not None and "202-26-33" in high.runtime_hours.citation
    high_result = evaluate(high, settings=air_settings)
    assert high_result.fleet_size > 0
    # Full 72 h authorized window at load crosses the NOx cap.
    assert "NOx" in high_result.breached_pollutants
    nox_high = next(e for e in high_result.emissions if e.pollutant == "NOx")
    assert nox_high.pct_of_cap is not None and nox_high.pct_of_cap > 100

    # A partial (central-duty) event over the same window stays compliant.
    central_result = evaluate(event_anchored_scenario(est, band="central"), settings=air_settings)
    assert central_result.any_cap_exceeded is False

    # And every event-anchored dispatch adds burden over idle baseline testing.
    base = evaluate(baseline_scenario(), settings=air_settings)
    d = diff(base, high_result)
    nox_delta = next(x for x in d.deltas if x.pollutant == "NOx")
    assert nox_delta.increase_tpy > 0
    assert "NOx" in d.caps_newly_breached
