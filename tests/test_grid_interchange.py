"""Grid interchange layer (#95): the EIA-930 connector replays an offline fixture and
reduces to window aggregates, and the derived comparison situates the campus load
(first-class facility_draw, #87) against in-BA generation. Hermetic — no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.connectors import OfflineError
from watermark.facility.power import derive_power_basis
from watermark.grid.interchange import (
    _reduce_region_data,
    derive_interchange_comparison,
    fetch_ba_interchange,
    load_ba_interchange,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def econ_settings() -> Settings:
    return Settings(
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )


def test_reduce_region_data_groups_by_type() -> None:
    rows = [
        {"type": "D", "value": "100"},
        {"type": "D", "value": "200"},
        {"type": "NG", "value": "150"},
        {"type": "TI", "value": "-50"},
        {"type": "TI", "value": "50"},
        {"type": "TI", "value": None},  # skipped
        {"type": "OTHER", "value": "999"},  # ignored
    ]
    agg = _reduce_region_data(rows, "PJM", "2024-06-01", "2024-06-30")
    assert agg["hours"] == 2  # two D rows
    assert agg["demand_mean"] == 150.0 and agg["demand_peak"] == 200.0
    assert agg["netgen_mean"] == 150.0
    assert agg["ti_mean"] == 0.0 and agg["ti_min"] == -50.0 and agg["ti_max"] == 50.0
    assert agg["import_hours"] == 1  # one TI < 0


def test_ba_interchange_offline(econ_settings: Settings) -> None:
    bai = fetch_ba_interchange(ba="PJM", settings=econ_settings)
    assert bai.ba == "PJM" and bai.hours == 720
    # Connector-sourced demand / net-generation / interchange.
    assert bai.demand_mean_mw.verified and bai.demand_mean_mw.unit == "MW"
    assert bai.demand_peak_mw.value > bai.demand_mean_mw.value
    # PJM is a net exporter over the window (mean TI > 0), with some net-import hours.
    assert bai.total_interchange_mean_mw.value > 0
    assert 0.0 < bai.net_import_hours_fraction.value < 1.0
    assert bai.interchange_min_mw.value < 0 < bai.interchange_max_mw.value


def test_offline_miss_raises(tmp_path: Path) -> None:
    with pytest.raises(OfflineError):
        fetch_ba_interchange(
            ba="MISO",  # no committed fixture for this BA
            settings=Settings(data_dir=tmp_path, econ_offline=True, econ_fixtures_dir=None),
        )


def test_comparison_links_facility_draw_and_coincident_peak(econ_settings: Settings) -> None:
    cmp = derive_interchange_comparison(settings=econ_settings)
    power = derive_power_basis(settings=econ_settings)

    # The campus load IS the first-class facility_draw (#87).
    assert cmp.campus_load_mw.value == pytest.approx(power.facility_draw.value, abs=0.1)

    # C1/#1638: the circular "in-BA generation headroom" (≡ net interchange) is gone.
    assert not hasattr(cmp, "in_ba_generation_headroom_mw")
    assert not hasattr(cmp, "met_by_in_ba_generation")

    # C2/#1638: adequacy is judged at the coincident peak — PJM's window peak demand exceeds
    # its mean in-BA net generation, so it is import/peaking-dependent at peak (the peak was
    # collected but previously discarded). The gap is peak demand - mean net generation.
    assert cmp.import_dependent_at_peak is True
    assert cmp.ba_demand_peak_mw.value > cmp.ba_net_generation_mean_mw.value
    assert cmp.peak_import_need_mw.value == pytest.approx(
        cmp.ba_demand_peak_mw.value - cmp.ba_net_generation_mean_mw.value, abs=1.0
    )

    # The campus is a small share of demand but a noticeable share of the interchange swing;
    # its share of the (higher) peak demand is smaller than its share of mean demand.
    assert cmp.campus_share_of_demand_pct.value < 1.0
    assert cmp.campus_share_of_peak_demand_pct.value < cmp.campus_share_of_demand_pct.value
    assert cmp.campus_vs_interchange_pct.value > cmp.campus_share_of_demand_pct.value
    # The interpretation + screening caveats are present.
    assert "net exporter" in cmp.interpretation
    assert any("not an hourly dispatch" in c for c in cmp.caveats)


def test_committed_ba_interchange_loads() -> None:
    bai = load_ba_interchange(REPO_ROOT / "data" / "reference")
    assert bai is not None
    assert bai.ba == "PJM" and bai.demand_mean_mw.value > 0
