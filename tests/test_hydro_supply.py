"""Lima water-supply storage budget: the off-stream-reservoir intake half of the loop.

The correction these tests lock in: Lima draws from ~15 BG of upground (off-stream)
storage filled at high flow, so the campus draw is screened against reservoir DRAWDOWN,
not an instantaneous 7Q10 intake.
"""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import supply as sup
from watermark.hydrology.cooling import derive_cooling_basis


def test_supply_loads_dual_river_storage(hydro_settings: Settings) -> None:
    system = sup.load_supply(settings=hydro_settings)
    assert system is not None, "data/reference/hydrology/water-supply.yaml must be committed"
    assert len(system.reservoirs) == 5
    # Capacities sum to ~14.4 BG (the City states ~15 BG).
    assert system.total_storage_mg == pytest.approx(14413.0, abs=1.0)
    by_river = system.storage_by_river()
    assert by_river["Auglaize River"] == pytest.approx(10120.0)  # Bresler + Williams
    assert by_river["Ottawa River"] == pytest.approx(4293.0)  # Lost Creek + Metzger + Ferguson
    # Both treatment figures are document-tagged (City page / Vision 2040).
    assert system.plant_capacity.value == 30.0 and system.plant_capacity.source == "document"
    assert (
        system.current_production.value == 15.0 and system.current_production.source == "document"
    )
    # Four pump stations across two rivers.
    assert {p.river for p in system.pump_stations} == {"Auglaize River", "Ottawa River"}
    assert sum(p.count for p in system.pump_stations) == 4


def test_water_budget_drawdown_math(hydro_settings: Settings) -> None:
    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    budget = sup.compute_water_budget(system, campus_makeup_mgd=3.92, campus_consumptive_mgd=3.14)
    assert budget.gross_production_mgd == pytest.approx(18.92)  # 15 municipal + 3.92 campus
    assert budget.campus_share_pct == pytest.approx(20.7, abs=0.1)
    # Drought reserve = storage(MG) / production(MGD) = days.
    assert budget.drought_reserve_days_baseline == pytest.approx(14413.0 / 15.0, abs=0.1)
    assert budget.drought_reserve_days_buildout == pytest.approx(14413.0 / 18.92, abs=0.1)
    assert budget.drought_reserve_lost_days == pytest.approx(
        budget.drought_reserve_days_baseline - budget.drought_reserve_days_buildout, abs=0.1
    )
    assert budget.annual_refill_burden_mg == pytest.approx(3.92 * 365.0, abs=0.1)
    assert budget.plant_headroom_mgd == pytest.approx(30.0 - 18.92)
    assert not budget.exceeds_plant_capacity


def test_water_budget_flags_over_capacity(hydro_settings: Settings) -> None:
    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    budget = sup.compute_water_budget(system, campus_makeup_mgd=20.0, campus_consumptive_mgd=16.0)
    assert budget.exceeds_plant_capacity  # 15 + 20 = 35 > 30 rated
    assert any("exceeds" in w for w in budget.warnings)


def test_campus_budget_from_cooling_basis(hydro_settings: Settings) -> None:
    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    basis = derive_cooling_basis()
    budget = sup.campus_budget_from_cooling(system, basis=basis)
    # Makeup is the cooling basis makeup; consumptive is makeup x the consumptive fraction.
    assert budget.campus_makeup.value == pytest.approx(basis.makeup_demand.value)
    assert budget.campus_consumptive.value == pytest.approx(
        basis.makeup_demand.value * basis.consumptive_fraction.value, abs=0.01
    )
    # The cooling upper bound rides along as a warning; its citation still traces the disclosed
    # blowdown even after the WS-16 (#1616) WUE-ceiling cap reconciles the two methods.
    assert any("blowdown" in w for w in budget.warnings)


def test_water_budget_findings_cover_the_story(hydro_settings: Settings) -> None:
    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    budget = sup.campus_budget_from_cooling(system)
    findings = sup.water_budget_findings(budget, system)
    checks = {f.check for f in findings}
    required = {
        "supply-off-stream",
        "drought-reserve",
        "campus-production-share",
        "basin-consumptive-loss",
        "refill-adequacy",
    }
    missing = required - checks
    assert not missing, f"missing checks: {missing}; got: {checks}"
    off_stream = next((f for f in findings if f.check == "supply-off-stream"), None)
    assert off_stream is not None, f"no 'supply-off-stream' finding; checks: {checks}"
    assert "off-stream" not in off_stream.detail.lower() or "drawdown" in off_stream.detail.lower()
    # The drawdown decoupling is the headline, not a 7Q10 intake.
    assert "7Q10" in off_stream.detail or "drawdown" in off_stream.detail


def test_pipeline_run_water_budget(hydro_settings: Settings) -> None:
    from watermark.pipeline import hydrology as hydro_stage

    system, budget, findings = hydro_stage.run_water_budget(settings=hydro_settings)
    assert system is not None and budget is not None
    assert system.total_storage_mg == pytest.approx(14413.0, abs=1.0)
    assert budget.drought_reserve_lost_days > 0  # the campus shortens the drought reserve
    assert budget.campus_share_pct > 0
    assert findings  # non-empty
