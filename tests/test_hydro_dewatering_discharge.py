"""The dewatering discharge-signal screen + reservoir-recharge read (offline, fixtures only).

Guards the honest headline: at Lima the ~7.6 cfs dewatering discharge is NOT separable from the
Ottawa reach gain (swamped by the 222 sq mi of incremental drainage between the Lima and Kalida
gages), the committed report round-trips byte-stable from the recorded NWIS fixtures, and the
`dewatering` feed carries the screen. All gage data is replayed from `tests/fixtures/hydrology/nwis`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology import dewatering_discharge as dd
from watermark.hydrology.dewatering import DATASET_ASOF, load_dewatering_impact

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
COMMITTED_REPORT = REPO_ROOT / "data" / "reference" / "hydrology" / "dewatering-discharge.yaml"


def _settings(site: str) -> Settings:
    return Settings(
        data_dir=REPO_ROOT / "data",
        site=site,
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
    )


@pytest.fixture
def lima() -> Settings:
    return _settings("lima")


def test_discharge_screen_is_not_separable(lima: Settings) -> None:
    screen = dd.load_discharge_screen(settings=lima)
    assert screen is not None
    assert screen.upstream_gage == "04187100" and screen.downstream_gage == "04188100"
    # The honest headline: the discharge does not register in the reach.
    assert screen.outcome == "not_separable"
    assert screen.separable is False
    # The incremental drainage that swamps the signal (350 - 128 sq mi).
    assert screen.incremental_da_sqmi == pytest.approx(222.0)
    # The observed window-vs-baseline deltas are well below the expected discharge magnitude.
    expected = screen.expected_discharge_cfs.value
    assert expected > 0
    assert abs(screen.baseflow_resid_delta_cfs) < expected
    assert abs(screen.upstream_floor_delta_cfs) < expected


def test_expected_discharge_is_bracketed_zero_to_capacity(lima: Settings) -> None:
    screen = dd.load_discharge_screen(settings=lima)
    assert screen is not None
    pv = screen.expected_discharge_cfs
    # Capacity is an UPPER bound (staged installs + unknown routing) -> the low end is 0.
    assert pv.low == 0.0
    assert pv.high == pv.value
    assert pv.unit == "cfs"


def test_reservoir_recharge_reads_the_supply_gage(lima: Settings) -> None:
    recharge = dd.load_reservoir_recharge(settings=lima)
    assert recharge is not None
    assert recharge.gage == "04186500"  # Auglaize @ Fort Jennings (Lima's primary supply gage)
    assert recharge.window_days > 0
    assert 0 <= recharge.window_refill_days <= recharge.window_days
    assert recharge.passby_cfs > 0


def test_committed_report_round_trips_byte_stable(lima: Settings, tmp_path: Path) -> None:
    """A fresh OFFLINE regen (from the recorded fixtures) must reproduce the committed report."""
    report = dd.build_discharge_report(as_of=DATASET_ASOF.isoformat(), settings=lima)
    assert report is not None and report.screen is not None
    out = tmp_path / "dewatering-discharge.yaml"
    dd.write_discharge_report(report, out)
    assert out.read_text(encoding="utf-8") == COMMITTED_REPORT.read_text(encoding="utf-8")


def test_dewatering_feed_carries_the_screen(lima: Settings) -> None:
    impact = load_dewatering_impact(asof=DATASET_ASOF, settings=lima)
    assert impact is not None
    assert impact.discharge_screen is not None
    assert impact.discharge_screen.outcome == "not_separable"
    assert impact.reservoir_recharge is not None


def test_site_without_a_reach_has_no_screen() -> None:
    # Fort Wayne has no dewatering wellfield / bracketing reach -> no screen (degrades, never fakes).
    assert dd.load_discharge_screen(settings=_settings("fort-wayne")) is None
    assert dd.read_discharge_report(settings=_settings("fort-wayne")) is None
