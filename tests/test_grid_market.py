"""PJM wholesale-market layer (#96, #121): zonal LMP is connector-sourced from PJM Data
Miner 2 (replayed from a committed fixture offline); the RPM-capacity / interconnection-
queue figures remain transcribed reference values (medium confidence, flagged verify).
The campus scenario links the first-class facility_draw (#87), and the committed YAML
round-trips. Hermetic - reads committed reference data + fixtures only, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.facility.consumption import HOURS_PER_YEAR as _HOURS_PER_YEAR
from watermark.facility.consumption import LOAD_FACTOR as _LOAD_FACTOR
from watermark.facility.power import derive_power_basis
from watermark.grid.market import (
    derive_pjm_market_scenario,
    load_pjm_market,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def market_settings() -> Settings:
    """Real repo data dir + committed connector fixtures (so offline replays the PJM LMP); no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )


def test_lmp_is_connector_sourced_capacity_is_reference(market_settings: Settings) -> None:
    sc = derive_pjm_market_scenario(settings=market_settings)
    # Zonal LMP is now connector-sourced (PJM Data Miner 2 da_hrl_lmps, #121) — Lima's AEP zone,
    # replayed from the committed fixture; a real ~$46/MWh figure, not the old $35 placeholder.
    assert sc.zonal_lmp_usd_mwh.source == "connector"
    assert sc.zonal_lmp_usd_mwh.confidence == "medium"
    assert "da_hrl_lmps" in (sc.zonal_lmp_usd_mwh.citation or "")
    assert 40.0 < sc.zonal_lmp_usd_mwh.value < 55.0
    assert sc.lmp_zone == "AEP zone"
    # The RPM clearing price + large-load queue remain transcribed reference figures, flagged verify.
    assert sc.rpm_clearing_usd_mw_day.source == "reference"
    assert "verify" in (sc.rpm_clearing_usd_mw_day.citation or "").lower()
    assert sc.large_load_queue_gw.source == "reference"
    assert "verify" in (sc.large_load_queue_gw.citation or "").lower()


def test_scenario_links_facility_draw(market_settings: Settings) -> None:
    sc = derive_pjm_market_scenario(settings=market_settings)
    power = derive_power_basis(settings=market_settings)
    assert power is not None
    # The campus load IS the first-class PowerBasis.facility_draw (#87).
    assert sc.campus_load_mw.value == pytest.approx(power.facility_draw.value, abs=0.1)
    # Annual consumption follows the shared convention (draw x 8760 x 0.9). H3/#1645: the hours
    # and load factor are spelled out here rather than read back off `sc.load_factor`, so this
    # tests the convention instead of restating whatever the scenario happened to use.
    expected_gwh = power.facility_draw.value * _HOURS_PER_YEAR * _LOAD_FACTOR / 1000.0
    assert sc.annual_consumption_gwh.value == pytest.approx(expected_gwh, rel=0.01)
    assert sc.load_factor.value == pytest.approx(_LOAD_FACTOR)
    # Plausibility, not just self-consistency: a few-hundred-MW campus run near-flat lands in
    # the low thousands of GWh/yr. A unit slip (MW↔kW, GWh↔MWh) leaves this band immediately.
    assert 1_000.0 < sc.annual_consumption_gwh.value < 10_000.0


def test_annual_capacity_cost_is_draw_times_price_times_365(market_settings: Settings) -> None:
    sc = derive_pjm_market_scenario(settings=market_settings)
    power = derive_power_basis(settings=market_settings)
    assert power is not None
    draw = power.facility_draw.value  # the input, not the scenario's echo of it
    price = sc.rpm_clearing_usd_mw_day.value
    # annual_capacity_cost ($M/yr) == draw (MW) x price ($/MW-day) x 365 / 1e6.
    expected_musd = draw * price * 365.0 / 1_000_000.0
    assert sc.annual_capacity_cost_musd.value == pytest.approx(expected_musd, rel=0.01)
    assert sc.annual_capacity_cost_musd.source == "derived"
    # The striking capacity footprint is on the order of tens of $M/yr.
    assert 20.0 < sc.annual_capacity_cost_musd.value < 60.0


def test_annual_energy_cost_is_consumption_times_lmp(market_settings: Settings) -> None:
    """H3/#1645: re-derive the energy cost from the *inputs*, not from the scenario's own outputs.

    The prior form multiplied ``sc.annual_consumption_gwh`` by ``sc.zonal_lmp_usd_mwh`` — both
    read back off the object under test, so it restated the code's arithmetic and would have
    passed on any consumption figure at all. Here the chain starts at the facility draw and the
    stated convention, and ends at an order-of-magnitude claim about the real world.
    """
    sc = derive_pjm_market_scenario(settings=market_settings)
    power = derive_power_basis(settings=market_settings)
    assert power is not None
    consumption_mwh = power.facility_draw.value * _HOURS_PER_YEAR * _LOAD_FACTOR
    expected_musd = consumption_mwh * sc.zonal_lmp_usd_mwh.value / 1_000_000.0
    assert sc.annual_energy_cost_musd.value == pytest.approx(expected_musd, rel=0.01)
    assert sc.annual_energy_cost_musd.source == "derived"
    # A few-thousand-GWh campus at a ~$45/MWh zonal LMP is a low-hundreds-of-$M/yr energy bill —
    # and strictly larger than the capacity charge, which is the point the scenario makes.
    assert 50.0 < sc.annual_energy_cost_musd.value < 400.0
    assert sc.annual_energy_cost_musd.value > sc.annual_capacity_cost_musd.value


def test_campus_is_small_slice_of_queue(market_settings: Settings) -> None:
    sc = derive_pjm_market_scenario(settings=market_settings)
    power = derive_power_basis(settings=market_settings)
    assert power is not None
    queue_gw = sc.large_load_queue_gw.value
    expected_pct = power.facility_draw.value / (queue_gw * 1000.0) * 100.0
    assert sc.campus_share_of_queue_pct.value == pytest.approx(expected_pct, rel=0.01)
    # One campus is a small single-digit-percent slice of a tens-of-GW pipeline.
    assert 0.0 < sc.campus_share_of_queue_pct.value < 5.0
    assert 10.0 < queue_gw < 500.0  # the denominator is a real GW-scale queue, not a stray unit


def test_caveats_present(market_settings: Settings) -> None:
    sc = derive_pjm_market_scenario(settings=market_settings)
    assert sc.caveats, "the scenario must carry screening caveats"
    joined = " ".join(sc.caveats).lower()
    assert "screening" in joined
    assert "lmp" in joined
    assert "clearing price" in joined
    assert "order-of-magnitude" in joined
    assert sc.interpretation


def test_committed_pjm_market_loads() -> None:
    """The committed reference YAML round-trips into the model."""
    ref = load_pjm_market(Settings(data_dir=REPO_ROOT / "data"))
    assert ref is not None
    assert "PJM" in ref.rto.value
    # Zonal LMP is connector-sourced (#121); RPM remains transcribed reference, flagged verify.
    assert ref.zonal_lmp_usd_mwh.source == "connector"
    assert ref.rpm_clearing_usd_mw_day.source == "reference"
    assert ref.rpm_clearing_usd_mw_day.confidence == "medium"
    assert ref.zonal_lmp_usd_mwh.value > 0.0
    assert ref.rpm_clearing_usd_mw_day.value > ref.rpm_prior_year_usd_mw_day.value


def test_market_scenario_refuses_a_facility_less_site() -> None:
    """A site with no documented facility cannot have a campus PJM market scenario —
    the connector refuses (no fabrication) rather than reusing Lima's facility."""
    # xenia is deliberately facility-less (Findlay now carries a disclosed SiteFacility, #1459).
    with pytest.raises(ValueError, match="no documented facility"):
        derive_pjm_market_scenario(settings=Settings(site="xenia"))
