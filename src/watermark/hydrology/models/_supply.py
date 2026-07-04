"""Supply / storage / drought models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.models._core import ProvenancedValue


class Reservoir(BaseModel):
    """One Lima upground (off-stream) storage reservoir."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    built: int  # year completed
    capacity_mg: float  # million gallons
    surface_area_acres: float | None = None  # open-water pool area (for the evaporation sink)
    source_river: str  # the river its pump stations lift from
    citation: str | None = None


class PumpStation(BaseModel):
    """Pump stations lifting one river's water into its reservoirs (the refill side)."""

    model_config = ConfigDict(extra="forbid")

    river: str
    count: int
    gage: str | None = None  # USGS NWIS site that gauges the source river
    feeds: list[str] = []  # reservoir ids these stations fill
    citation: str | None = None


class WaterSupplySystem(BaseModel):
    """Lima's intake/storage/treatment system: dual-river -> upground reservoirs -> WTP.

    The supply half the routed network presumes. Its defining feature is *off-stream
    storage*: five upground reservoirs (~15 billion gallons) filled by pumping from the
    Auglaize and Ottawa at high flow, so withdrawal is decoupled from the instantaneous
    7Q10 — the binding low-flow constraint is reservoir drawdown, not intake depletion.
    """

    model_config = ConfigDict(extra="forbid")

    reservoirs: list[Reservoir]
    pump_stations: list[PumpStation] = []
    plant_capacity: ProvenancedValue  # rated MGD
    current_production: ProvenancedValue  # MGD currently treated for the community
    sources: list[str] = []
    caveats: list[str] = []

    @property
    def total_storage_mg(self) -> float:
        return round(sum(r.capacity_mg for r in self.reservoirs), 1)

    @property
    def total_surface_area_acres(self) -> float | None:
        """Combined open-water surface area, or ``None`` if no reservoir carries one."""
        present = [
            r.surface_area_acres for r in self.reservoirs if r.surface_area_acres is not None
        ]
        return round(sum(present), 1) if present else None

    def storage_by_river(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for r in self.reservoirs:
            out[r.source_river] = round(out.get(r.source_river, 0.0) + r.capacity_mg, 1)
        return out

    def reservoir(self, rid: str) -> Reservoir | None:
        return next((r for r in self.reservoirs if r.id == rid), None)


class WaterBudget(BaseModel):
    """A screening storage water-budget on Lima's supply: baseline vs the campus draw.

    Because the reservoirs decouple withdrawal from instantaneous low flow, the
    low-flow constraint is reservoir **drawdown**, not a 7Q10 intake. The campus is a
    treated-supply customer: its makeup adds to plant production and to reservoir
    drawdown (its returns go *downstream* to the Ottawa via the WWTPs, not back to
    storage), and its evaporative consumptive is a permanent loss to the basin. The
    headline metrics are the drought-reserve (zero-refill drawdown) days and the
    campus's share of plant production — both far harder to rebut than a 7Q10 multiple.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    scenario: str = "buildout"
    total_storage_mg: float
    municipal_production: ProvenancedValue  # MGD baseline community production
    campus_makeup: ProvenancedValue  # MGD added gross draw on storage
    campus_consumptive: ProvenancedValue  # MGD net basin loss (evaporated, never returns)
    gross_production_mgd: float  # municipal + campus makeup
    campus_share_pct: float  # campus makeup / gross production
    drought_reserve_days_baseline: float  # storage / municipal production (zero refill)
    drought_reserve_days_buildout: float  # storage / gross production (zero refill)
    drought_reserve_lost_days: float  # baseline - buildout
    annual_refill_burden_mg: float  # extra water/yr the pump stations must capture
    plant_headroom_mgd: float  # rated capacity - gross production
    warnings: list[str] = []

    @property
    def exceeds_plant_capacity(self) -> bool:
        return self.plant_headroom_mgd < 0.0


class RiverFlowStat(BaseModel):
    """Flow-duration + drought characterization of one supply river's gage record.

    The reservoirs are filled from each river only when flow is available; this is the
    refill side of the storage budget. The percentiles are *exceedance* flows (``p90``
    is the flow exceeded 90% of days — a low value), so the tail (``p95``/``p99``)
    measures how reliably the river can be pumped through a drought.
    """

    model_config = ConfigDict(extra="forbid")

    site_no: str
    site_name: str
    river: str
    period_start: str
    period_end: str
    record_days: int
    mean_cfs: float
    median_cfs: float
    min_cfs: float
    p90_cfs: float  # flow exceeded 90% of days
    p95_cfs: float
    p99_cfs: float
    passby_cfs: float  # screening minimum left in-stream (not pumped)
    pct_days_below_demand: float | None = None  # share of days below the buildout demand
    note: str = ""


class DroughtDrawdown(BaseModel):
    """One demand scenario's sequent-peak storage requirement over the historical record.

    The sequent-peak (Rippl) ``required_storage_mg`` is the maximum cumulative deficit of
    (demand - pumpable river inflow) — the active storage a reservoir must hold to deliver
    the constant demand through the worst historical drawdown. If it stays under the actual
    storage capacity the system survives that drought; the headroom is the safety margin.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    demand_mgd: float
    required_storage_mg: float
    pct_of_capacity: float  # required_storage / storage capacity
    worst_spell_start: str | None = None  # date the binding drawdown began
    worst_spell_days: int = 0
    survives: bool = True  # required_storage < capacity


class ReservoirEvaporation(BaseModel):
    """First-order open-water evaporation sink on the reservoir storage (``derived``).

    Reference ET0 (FAO-56 Penman-Monteith, from the committed NASA POWER climatology) over
    the reservoirs' combined open-water surface area (ODNR Division of Wildlife fishing-map
    acreages). A *screening* sink: ET0 is used directly as a first-order proxy for open-water
    evaporation and precipitation onto the pool is not credited, so the term is conservative —
    it can only tighten the drought bound. Folded into the sequent-peak as an added monthly
    loss on storage (subtracted from the pumpable inflow, by calendar month).
    """

    model_config = ConfigDict(extra="forbid")

    source: Literal["derived"] = "derived"
    surface_area_acres: float
    et0_method: str = "FAO-56 Penman-Monteith"
    et0_annual_mm: float  # reference ET0 depth (grass), mm/yr
    open_water_coefficient: float = 1.0  # ET0 -> open-water evaporation multiplier
    monthly_evap_mgd: dict[str, float]  # JAN..DEC
    annual_evap_mg: float  # days-weighted annual volume
    mean_evap_mgd: float  # annual_evap_mg / 365
    peak_month: str  # month of the largest evaporative loss
    peak_evap_mgd: float
    citation: str
    note: str = ""


class RefillAdequacy(BaseModel):
    """Can high-flow pumping refill Lima's reservoirs against demand, incl. the campus?

    Two questions, two answers: (1) in a normal year the rivers carry far more than demand
    (``annual_supply_multiple``), so refill is trivially adequate; (2) the binding case is a
    prolonged drought when both rivers fall below demand and the system draws down storage —
    answered by the sequent-peak :class:`DroughtDrawdown` per demand scenario. The campus
    raises demand, so it raises the storage the worst drought calls on; the residual risk is
    a drought longer/deeper than the gauged record. A *derived* screening analysis.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    period_start: str
    period_end: str
    aligned_days: int
    storage_capacity_mg: float
    combined_mean_cfs: float  # mean of (Auglaize + Ottawa) over the aligned record
    annual_demand_mg: float  # buildout gross annual demand
    annual_supply_multiple: float  # mean annual river supply / annual buildout demand
    rivers: list[RiverFlowStat]
    scenarios: list[DroughtDrawdown]
    evaporation: ReservoirEvaporation | None = None  # the reservoir-evaporation sink, if derived
    method: str
    warnings: list[str] = []
    caveats: list[str] = []

    def scenario(self, label: str) -> DroughtDrawdown | None:
        return next((s for s in self.scenarios if s.label == label), None)

    def river(self, site_no: str) -> RiverFlowStat | None:
        return next((r for r in self.rivers if r.site_no == site_no), None)
