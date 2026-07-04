"""Household energy burden (#1110): % of median household income (Census B19013) spent on
residential electricity + heating (EIA). A fully [derived] metric — every input is cited,
unlike the deliberately-stylized facility price-pressure band. All offline from fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.economics.connectors.eia import fetch_consumer_energy
from watermark.economics.energy import (
    _AVG_HOUSEHOLD_KWH_YR,
    _AVG_HOUSEHOLD_MCF_YR,
    build_energy_burden,
    derive_energy_burden,
)
from watermark.economics.model import ConsumerEnergyCosts
from watermark.hydrology.model import ProvenancedValue

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_derive_energy_burden_math(econ_settings: Settings) -> None:
    costs = fetch_consumer_energy(settings=econ_settings)
    income = ProvenancedValue.from_connector(60_000.0, "USD/yr", citation="test")
    b = derive_energy_burden(costs=costs, income=income, settings=econ_settings)

    elec_price = costs.by_metric("electricity", "price").value.value  # type: ignore[union-attr]
    gas_price = costs.by_metric("natural_gas", "price").value.value  # type: ignore[union-attr]
    exp_elec = _AVG_HOUSEHOLD_KWH_YR * elec_price / 100.0
    exp_gas = _AVG_HOUSEHOLD_MCF_YR * gas_price

    assert b.electricity_annual_cost.value == pytest.approx(exp_elec, rel=1e-6)
    assert b.gas_annual_cost.value == pytest.approx(exp_gas, rel=1e-6)
    assert b.electricity_burden_pct.value == pytest.approx(exp_elec / 60_000 * 100, abs=0.02)
    assert b.gas_burden_pct.value == pytest.approx(exp_gas / 60_000 * 100, abs=0.02)
    assert b.combined_burden_pct.value == pytest.approx(
        (exp_elec + exp_gas) / 60_000 * 100, abs=0.02
    )
    # Combined is the sum of the parts (a gas-heated home at average use).
    assert b.combined_burden_pct.value == pytest.approx(
        b.electricity_burden_pct.value + b.gas_burden_pct.value, abs=0.02
    )


def test_derive_energy_burden_is_fully_derived_and_uses_the_gas_price(
    econ_settings: Settings,
) -> None:
    """Every burden figure is `[derived]` (not stylized), and the residential natural-gas
    price — fetched but previously unused — finally feeds a derivation (#1110)."""
    b = derive_energy_burden(
        costs=fetch_consumer_energy(settings=econ_settings),
        income=ProvenancedValue.from_connector(60_000.0, "USD/yr", citation="test"),
        settings=econ_settings,
    )
    for pv in (b.electricity_burden_pct, b.gas_burden_pct, b.combined_burden_pct):
        assert pv.source == "derived"
    # Both consumer prices are connector-sourced references, not assumptions.
    assert b.residential_electricity_price.verified
    assert b.residential_gas_price.verified
    # Honesty caveats: county income vs state prices; gas burden assumes a gas-heated home.
    joined = " ".join(b.caveats).lower()
    assert "county" in joined and "gas-heated" in joined


def test_derive_energy_burden_rejects_nonpositive_income(econ_settings: Settings) -> None:
    costs = fetch_consumer_energy(settings=econ_settings)
    with pytest.raises(ValueError, match="positive"):
        derive_energy_burden(
            costs=costs,
            income=ProvenancedValue.from_connector(0.0, "USD/yr", citation="x"),
            settings=econ_settings,
        )


def test_derive_energy_burden_rejects_missing_price_metric(econ_settings: Settings) -> None:
    """A consumer-energy dataset missing a residential electricity or gas price can't yield a
    burden — the derivation raises rather than fabricating one from a half-present dataset."""
    full = fetch_consumer_energy(settings=econ_settings)
    income = ProvenancedValue.from_connector(60_000.0, "USD/yr", citation="test")
    # Drop the natural-gas price series -> by_metric("natural_gas", "price") is None.
    no_gas = ConsumerEnergyCosts(
        area=full.area,
        area_name=full.area_name,
        prices=[p for p in full.prices if p.fuel != "natural_gas"],
    )
    with pytest.raises(ValueError, match="missing one"):
        derive_energy_burden(costs=no_gas, income=income, settings=econ_settings)


def test_build_energy_burden_from_committed(econ_settings: Settings) -> None:
    """`build_energy_burden` assembles from the committed baseline income + consumer-energy —
    no live pull. This is exactly what the site export reads."""
    b = build_energy_burden(settings=econ_settings)
    assert b is not None
    assert b.area == "OH" and b.area_name == "Ohio"
    assert b.median_household_income.value == pytest.approx(62001.0)
    # A plausible household energy burden (typically a few percent for a median-income home).
    assert 0.0 < b.combined_burden_pct.value < 20.0
    assert b.electricity_burden_pct.value > 0 and b.gas_burden_pct.value > 0


def test_build_energy_burden_none_without_committed_income(tmp_path: Path) -> None:
    """No committed baseline/income => no burden, so the feed is skipped and the section
    degrades rather than fabricating a figure (#781)."""
    assert build_energy_burden(settings=Settings(data_dir=tmp_path)) is None
