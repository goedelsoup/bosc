"""Lima's water-supply storage budget — the intake/storage half of the loop.

The routed network (:mod:`watermark.hydrology.network`) models the *receiving* half: WWTP
discharges into the Ottawa at design low flow. This module models the *supply* half it
presumes, and corrects a structural error in the old single-node "intake on the Ottawa
mainstem" framing.

The correction rests on one physical fact (``data/reference/hydrology/water-supply.yaml``,
sourced from the City of Lima utility page): Lima's raw water is held in **five upground
(off-stream) reservoirs (~15 billion gallons)** filled by pumping from **two rivers** —
the Auglaize (west) and the Ottawa (east) — at *high* flow. So Lima does **not** withdraw
at the 7Q10; it lives off stored water. The binding low-flow constraint is therefore
reservoir **drawdown / refill** (a storage water-budget), not instantaneous intake
depletion of a 0.2 cfs river.

The data-center campus draws *treated* municipal water like any large customer, so its
makeup demand is an added draw on the shared storage and its evaporative consumptive is a
permanent basin loss (the returns go *downstream* to the Ottawa via the WWTPs, not back to
the reservoirs). :func:`compute_water_budget` reports the drought-reserve (zero-refill
drawdown) days and the campus's share of plant production — both far harder to rebut than
a 7Q10 multiple.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.model import (
    CoolingBasis,
    HydroFinding,
    ProvenancedValue,
    PumpStation,
    Reservoir,
    WaterBudget,
    WaterSupplySystem,
)
from watermark.logging import get_logger

log = get_logger(__name__)

_DAYS_PER_YEAR = 365.0


def _supply_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "water-supply.yaml"


def load_supply(*, settings: Settings | None = None) -> WaterSupplySystem | None:
    """Load the committed Lima water-supply system, or ``None`` if the file is absent."""
    settings = settings or get_settings()
    path = _supply_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    meta = data.get("meta") or {}
    treatment = data.get("treatment") or {}
    return WaterSupplySystem(
        reservoirs=[Reservoir.model_validate(r) for r in (data.get("reservoirs") or [])],
        pump_stations=[PumpStation.model_validate(p) for p in (data.get("pump_stations") or [])],
        plant_capacity=ProvenancedValue.model_validate(treatment["plant_capacity"]),
        current_production=ProvenancedValue.model_validate(treatment["current_production"]),
        sources=meta.get("sources") or [],
        caveats=meta.get("caveats") or [],
    )


def compute_water_budget(
    supply: WaterSupplySystem,
    *,
    campus_makeup_mgd: float,
    campus_consumptive_mgd: float,
    makeup_citation: str = "campus makeup demand",
    consumptive_citation: str = "campus evaporative consumptive loss",
    municipal_production_mgd: float | None = None,
    scenario_name: str = "buildout",
) -> WaterBudget:
    """Screen the campus draw against Lima's reservoir storage (a drawdown water-budget).

    ``campus_makeup_mgd`` is the gross treated-water draw (it draws down storage; the
    returns go downstream, not back to the reservoirs). ``campus_consumptive_mgd`` is the
    evaporative net basin loss. The drought reserve is the zero-refill drawdown: total
    storage divided by daily production (MG / MGD = days) — a conservative drought buffer,
    not a prediction (the reservoirs do get *some* refill even in drought).
    """
    storage = supply.total_storage_mg
    warnings: list[str] = []

    if municipal_production_mgd is None:
        municipal = supply.current_production
        muni = municipal.value
    else:
        muni = municipal_production_mgd
        municipal = ProvenancedValue.assume(
            round(muni, 3), "MGD", why="municipal production override"
        )

    makeup = ProvenancedValue.derived(round(campus_makeup_mgd, 3), "MGD", citation=makeup_citation)
    consumptive = ProvenancedValue.derived(
        round(campus_consumptive_mgd, 3), "MGD", citation=consumptive_citation
    )

    gross = muni + campus_makeup_mgd
    reserve_base = storage / muni if muni > 0 else float("inf")
    reserve_build = storage / gross if gross > 0 else float("inf")
    capacity = supply.plant_capacity.value
    headroom = capacity - gross
    if headroom < 0:
        warnings.append(
            f"gross production {gross:.2f} MGD exceeds the {capacity:g} MGD rated plant capacity."
        )

    budget = WaterBudget(
        scenario=scenario_name,
        total_storage_mg=storage,
        municipal_production=municipal,
        campus_makeup=makeup,
        campus_consumptive=consumptive,
        gross_production_mgd=round(gross, 3),
        campus_share_pct=round(100.0 * campus_makeup_mgd / gross, 1) if gross > 0 else 0.0,
        drought_reserve_days_baseline=round(reserve_base, 1),
        drought_reserve_days_buildout=round(reserve_build, 1),
        drought_reserve_lost_days=round(reserve_base - reserve_build, 1),
        annual_refill_burden_mg=round(campus_makeup_mgd * _DAYS_PER_YEAR, 1),
        plant_headroom_mgd=round(headroom, 3),
        warnings=warnings,
    )
    log.info(
        "hydro.water_budget",
        scenario=scenario_name,
        storage_mg=storage,
        gross_mgd=budget.gross_production_mgd,
        campus_share_pct=budget.campus_share_pct,
        reserve_lost_days=budget.drought_reserve_lost_days,
    )
    return budget


def campus_budget_from_cooling(
    supply: WaterSupplySystem,
    *,
    basis: CoolingBasis | None = None,
    scenario_name: str = "buildout",
) -> WaterBudget:
    """Build the water budget from the sourced cooling basis (the default campus draw).

    Uses the central power x WUE estimate: ``makeup_demand`` as the gross treated draw and
    ``makeup x consumptive_fraction`` as the net basin loss. The high blowdown-method bound
    rides along as a warning, since the two methods disagree ~3x.
    """
    basis = basis or derive_cooling_basis()
    # Honesty guard (CLAUDE.md): a bracketed (undisclosed-method) basis has no single
    # makeup/consumptive headline, so a scalar water budget cannot be derived from it —
    # refuse rather than silently publishing the evaporative envelope.
    makeup_pv = basis.headline_makeup()
    if makeup_pv is None:
        raise ValueError(
            f"cooling basis for {basis.cooling_model.value} is bracketed (undisclosed "
            "method) — no single makeup/consumptive headline; supply an explicit scenario "
            "demand instead of deriving a water budget from the bracket envelope"
        )
    makeup = makeup_pv.value
    consumptive = round(makeup * basis.consumptive_fraction.value, 3)
    budget = compute_water_budget(
        supply,
        campus_makeup_mgd=makeup,
        campus_consumptive_mgd=consumptive,
        makeup_citation=f"cooling makeup demand ({basis.makeup_demand.citation})",
        consumptive_citation=(
            f"makeup x {basis.consumptive_fraction.value:g} consumptive fraction "
            f"({basis.consumptive_fraction.citation})"
        ),
        scenario_name=scenario_name,
    )
    ratio = basis.consumptive_high.value / consumptive if consumptive else 0.0
    budget.warnings.append(
        f"central power x WUE basis (consumptive {consumptive:g} MGD); the blowdown-method "
        f"upper bound is ~{basis.consumptive_high.value:g} MGD consumptive (~{ratio:.1f}x higher)."
    )
    return budget


def water_budget_findings(budget: WaterBudget, supply: WaterSupplySystem) -> list[HydroFinding]:
    """System-level findings from the supply storage budget."""
    by_river = supply.storage_by_river()
    river_txt = ", ".join(f"{r} {mg / 1000:.1f} BG" for r, mg in sorted(by_river.items()))
    findings: list[HydroFinding] = [
        HydroFinding(
            subject="Lima supply is off-stream storage",
            check="supply-off-stream",
            ok=True,
            detail=(
                f"{len(supply.reservoirs)} upground reservoirs, "
                f"{budget.total_storage_mg / 1000:.1f} BG total ({river_txt}); filled by pumping "
                "at high flow, so withdrawal is decoupled from the 7Q10 — the low-flow constraint "
                "is reservoir drawdown, not intake depletion."
            ),
        ),
        HydroFinding(
            subject="drought reserve (zero-refill drawdown)",
            check="drought-reserve",
            ok=True,  # informational screening metric
            detail=(
                f"the campus cuts the drought reserve from "
                f"{budget.drought_reserve_days_baseline:g} to "
                f"{budget.drought_reserve_days_buildout:g} days "
                f"(-{budget.drought_reserve_lost_days:g} days) at {budget.gross_production_mgd:g} "
                "MGD gross production with zero refill."
            ),
        ),
        HydroFinding(
            subject="campus share of plant production",
            check="campus-production-share",
            ok=not budget.exceeds_plant_capacity,
            detail=(
                f"campus makeup {budget.campus_makeup.value:g} MGD is "
                f"{budget.campus_share_pct:g}% of the {budget.gross_production_mgd:g} MGD gross "
                f"production; {budget.plant_headroom_mgd:g} MGD headroom under the rated capacity"
                + ("" if not budget.exceeds_plant_capacity else " — OVER capacity")
            ),
        ),
        HydroFinding(
            subject="net basin consumptive loss",
            check="basin-consumptive-loss",
            ok=True,
            detail=(
                f"{budget.campus_consumptive.value:g} MGD evaporated is a permanent loss to the "
                "basin — its returns (FM-2/FM-1) go downstream to the Ottawa via the WWTPs, not "
                "back to the upground reservoirs, so the full makeup draws down storage."
            ),
        ),
        HydroFinding(
            subject="refill adequacy",
            check="refill-adequacy",
            ok=True,
            detail=(
                f"the added draw is ~{budget.annual_refill_burden_mg:g} MG/yr the pump stations "
                "must capture from the Auglaize (USGS 04185750) + Ottawa (04187100) at high flow; "
                "quantifying refill adequacy against those flow records is the next increment."
            ),
        ),
    ]
    return findings
