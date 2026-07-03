"""EIA consumer-energy connector replays offline fixtures; the demand-pressure
scenario links the facility's total draw (#87) to consumer electricity prices, and an
offline cache miss raises (no silent network). Issue #91.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.connectors import OfflineError
from watermark.economics.connectors.eia import (
    EiaError,
    _latest_point,
    _series_points,
    fetch_consumer_energy,
    fetch_eia_series,
)
from watermark.economics.energy import (
    derive_demand_pressure,
    load_consumer_energy,
)
from watermark.facility.power import derive_power_basis
from watermark.hydrology.model import ProvenancedValue

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seriesid_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    """A minimal EIA /v2/seriesid response envelope around the given data rows."""
    return {"response": {"data": rows}}


def test_latest_point_reads_series_specific_value_column() -> None:
    """The /v2/seriesid rows carry a value column named after the series (price/sales/
    value), NOT a uniform ``value`` — _latest_point must read the declared column and
    take the newest period. Regression for the build-but-not-run live-shape bug (#120).
    """
    # Price series: value lives under ``price``; newest period wins regardless of order.
    price = _seriesid_payload(
        [
            {"period": 2024, "stateid": "OH", "sectorid": "RES", "price": 15.71},
            {"period": 2025, "stateid": "OH", "sectorid": "RES", "price": 16.96},
        ]
    )
    assert _latest_point(price, "price") == {"period": "2025", "value": 16.96}

    # Sales series: value under ``sales``.
    sales = _seriesid_payload([{"period": 2025, "sales": 161933.97969}])
    assert _latest_point(sales, "sales") == {"period": "2025", "value": 161933.97969}

    # Natural-gas series: this one genuinely uses ``value``.
    ng = _seriesid_payload([{"period": 2025, "value": 13.85}])
    assert _latest_point(ng, "value") == {"period": "2025", "value": 13.85}


def test_series_points_keeps_full_annual_history_sorted() -> None:
    """The connector retains the full annual series (issue #1111), oldest→newest, reading
    the series-specific value column — not just the latest point."""
    payload = _seriesid_payload(
        [
            {"period": 2025, "stateid": "OH", "price": 16.96},
            {"period": 2023, "stateid": "OH", "price": 15.71},
            {"period": 2024, "stateid": "OH", "price": 16.10},
        ]
    )
    points = _series_points(payload, "price")
    assert [p["period"] for p in points] == ["2023", "2024", "2025"]  # sorted ascending
    assert [p["value"] for p in points] == [15.71, 16.10, 16.96]
    # _latest_point is the newest point of the same series.
    assert _latest_point(payload, "price") == {"period": "2025", "value": 16.96}


def test_eia_series_retains_points_with_latest_convenience(econ_settings: Settings) -> None:
    """fetch_eia_series exposes the full annual series in ``points`` plus the latest cited
    point as ``value``/``period`` (issue #1111)."""
    price = fetch_eia_series("ELEC.PRICE.OH-RES.A", settings=econ_settings)
    assert len(price.points) > 5  # a real multi-year trend, not two points
    periods = [p.period for p in price.points]
    assert periods == sorted(periods)  # oldest→newest
    # The latest convenience mirrors the newest point and stays fully provenanced.
    assert price.period == price.points[-1].period
    assert price.value.value == price.points[-1].value
    assert price.value.verified and price.value.unit == "cents/kWh"


def test_eia_series_resorts_untrusted_cache_order(econ_settings: Settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A hand-edited/external cache or fixture payload may be unordered; fetch_eia_series must
    re-sort by period so ``points`` and the latest value derive from ordering, not input trust."""
    from watermark.economics.connectors import eia

    unordered = {"points": [{"period": "2025", "value": 16.96}, {"period": "2024", "value": 16.1}]}
    monkeypatch.setattr(eia, "cached_get", lambda *a, **k: unordered)
    price = eia.fetch_eia_series("ELEC.PRICE.OH-RES.A", settings=econ_settings)
    assert [p.period for p in price.points] == ["2024", "2025"]  # re-sorted ascending
    assert price.period == "2025" and price.value.value == 16.96  # latest, not the input's last


def test_consumer_energy_price_rejects_latest_not_mirroring_points() -> None:
    """The model enforces that period/value mirror points[-1] (no headline disagreeing with the
    trend); an empty-points latest-only record stays valid for pre-#1111 committed data."""
    from watermark.economics.model import ConsumerEnergyPrice, EnergyPricePoint

    pv = ProvenancedValue.from_connector(16.96, "cents/kWh", citation="x")
    pts = [
        EnergyPricePoint(period="2024", value=16.1),
        EnergyPricePoint(period="2025", value=16.96),
    ]
    ConsumerEnergyPrice(
        series_id="ELEC.PRICE.OH-RES.A",
        label="l",
        fuel="electricity",
        period="2025",
        area="OH",
        value=pv,
        points=pts,
    )  # consistent — accepted
    with pytest.raises(ValueError, match="mirror points"):
        ConsumerEnergyPrice(
            series_id="ELEC.PRICE.OH-RES.A",
            label="l",
            fuel="electricity",
            period="2024",
            area="OH",
            value=pv,
            points=pts,  # period disagrees with points[-1]
        )


def test_latest_point_fallback_and_empty() -> None:
    """Fallback to the sole numeric column when the declared one is absent (EIA rename),
    and raise rather than silently return on an empty payload."""
    # Declared column ``price`` missing; the only numeric non-dimension field is taken.
    renamed = _seriesid_payload([{"period": 2025, "stateid": "OH", "cents_per_kwh": 16.96}])
    assert _latest_point(renamed, "price") == {"period": "2025", "value": 16.96}

    with pytest.raises(EiaError):
        _latest_point(_seriesid_payload([]), "price")


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
    costs = load_consumer_energy(Settings(data_dir=REPO_ROOT / "data"))
    assert costs is not None
    assert costs.area == "OH"
    assert costs.by_metric("electricity", "price") is not None


def test_demand_pressure_resolves_the_dataset_state_not_ohio(
    econ_settings: Settings, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """The demand-pressure series + citation follow the dataset's OWN state, not a hardcoded OH
    (#422): Fort Wayne's committed dataset is Indiana, so with a (stubbed) facility basis it must
    resolve the IN series and say "Indiana retail", never OH."""
    import yaml as _yaml

    from watermark.economics import energy
    from watermark.economics.model import ConsumerEnergyCosts

    # Reuse Lima's real power basis as a stub — the only site with a documented facility today, so
    # a non-OH site can exercise the state-resolution path without a real non-OH facility.
    basis = derive_power_basis(settings=econ_settings)
    monkeypatch.setattr(energy, "derive_power_basis", lambda **_: basis)
    fw_path = REPO_ROOT / "data" / "reference" / "eia" / "fort-wayne" / "consumer-energy.yaml"
    fw_costs = ConsumerEnergyCosts.model_validate(_yaml.safe_load(fw_path.read_text()))
    assert fw_costs.area == "IN" and fw_costs.area_name == "Indiana"

    dp = energy.derive_demand_pressure(costs=fw_costs, settings=econ_settings)
    assert "ELEC.SALES.IN-ALL.A" in dp.state_retail_sales_gwh.citation  # the IN series, not OH
    assert "Indiana retail" in dp.demand_share_pct.citation  # not "Ohio retail"
