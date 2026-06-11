"""EIA consumer-energy connector replays offline fixtures; the demand-pressure
scenario links the facility's total draw (#87) to consumer electricity prices, and an
offline cache miss raises (no silent network). Issue #91.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.config import Settings
from bosc.connectors import OfflineError
from bosc.economics.connectors.eia import fetch_consumer_energy, fetch_eia_series
from bosc.economics.energy import (
    derive_demand_pressure,
    load_consumer_energy,
)
from bosc.facility.power import derive_power_basis

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_eia_series_offline(econ_settings: Settings) -> None:
    price = fetch_eia_series("ELEC.PRICE.OH-RES.A", settings=econ_settings)
    assert price.fuel == "electricity" and price.metric == "price"
    assert price.value.unit == "cents/kWh"
    assert price.value.verified  # connector-sourced
    assert 5.0 < price.value.value < 40.0  # a sane residential ¢/kWh


def test_consumer_energy_dataset_offline(econ_settings: Settings) -> None:
    costs = fetch_consumer_energy(settings=econ_settings)
    assert costs.area == "OH"
    # All three anchor series are present and connector-sourced.
    assert costs.by_metric("electricity", "price") is not None
    assert costs.by_metric("electricity", "sales") is not None
    assert costs.by_metric("natural_gas", "price") is not None
    assert all(p.value.verified for p in costs.prices)


def test_unknown_series_raises(econ_settings: Settings) -> None:
    # An unrecognized series id is rejected up front (never a silent/empty pull).
    with pytest.raises(ValueError):
        fetch_eia_series("ELEC.PRICE.OH-IND.A", settings=econ_settings)


def test_offline_miss_raises(tmp_path: Path) -> None:
    # A known series with no cache and no fixtures dir raises, never silently fetches.
    with pytest.raises(OfflineError):
        fetch_eia_series(
            "ELEC.PRICE.OH-RES.A",
            settings=Settings(data_dir=tmp_path, econ_offline=True, econ_fixtures_dir=None),
        )


def test_demand_pressure_links_facility_draw(econ_settings: Settings) -> None:
    dp = derive_demand_pressure(settings=econ_settings)
    power = derive_power_basis(settings=econ_settings)

    # The scenario's facility draw IS the first-class PowerBasis.facility_draw (#87).
    assert dp.facility_draw_mw.value == pytest.approx(power.facility_draw.value, abs=0.1)

    # Annual consumption = draw x 8760 x load factor (GWh).
    expected_gwh = power.facility_draw.value * 8760.0 * dp.load_factor.value / 1000.0
    assert dp.annual_consumption_gwh.value == pytest.approx(expected_gwh, rel=0.01)

    # Demand share = consumption / state retail sales; a small but material % of Ohio.
    assert dp.state_retail_sales_gwh.value > dp.annual_consumption_gwh.value
    assert dp.demand_share_pct.value == pytest.approx(
        dp.annual_consumption_gwh.value / dp.state_retail_sales_gwh.value * 100.0, rel=0.01
    )
    assert 0.5 < dp.demand_share_pct.value < 5.0

    # Households-equivalent is a large, derived number.
    assert dp.households_equivalent.value > 50_000


def test_demand_pressure_band_is_stylized_and_flagged(econ_settings: Settings) -> None:
    dp = derive_demand_pressure(settings=econ_settings)
    # The price-pressure band scales with the demand share and is low-confidence.
    assert dp.price_pressure_pct_low.value < dp.price_pressure_pct_high.value
    assert dp.price_pressure_pct_low.confidence == "low"
    assert dp.price_pressure_pct_high.confidence == "low"
    # The honesty caveats are present (not a forecast; campus buys wholesale).
    joined = " ".join(dp.caveats).lower()
    assert "not a forecast" in joined and "wholesale" in joined
    # The residential price is the consumer reference, connector-sourced.
    assert dp.residential_price.verified


def test_committed_consumer_energy_loads() -> None:
    """The committed reference YAML round-trips into the model (what the scenario reads)."""
    costs = load_consumer_energy(REPO_ROOT / "data" / "reference")
    assert costs is not None
    assert costs.area == "OH"
    assert costs.by_metric("electricity", "price") is not None
