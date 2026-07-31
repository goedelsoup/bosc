"""Stormwater + roundabout models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hsg import DrainageCondition, resolve_hsg
from watermark.hydrology.models._core import ProvenancedValue


class RoundaboutStormPeak(BaseModel):
    """One design-storm peak directed flow off a roundabout's impervious catchment."""

    model_config = ConfigDict(extra="forbid")

    return_period_yr: int
    depth_in: float  # Atlas-14 24-hr point depth
    peak_cfs: float
    volume_acft: float
    runoff_depth_in: float


class RoundaboutFlow(BaseModel):
    """Derived stormwater the Cole/Beery roundabout could direct into Pike Run.

    Grounds the ``waterfall-roundabout-pike-run`` theory's injected flow. The honest
    result **refutes its sustained-augmentation premise**: a single roundabout's
    impervious catchment yields a negligible mean-annual continuous flow — and **zero at
    design low flow**, when it is not raining — so it cannot augment Pike Run's 7Q10. What
    it can deliver is transient storm-event surges: episodic flushing, not a low-flow
    augmentation. Every input is document-cited (the Tetra Tech OPC quantities, the cited
    Atlas-14 depths, the NASA POWER precip) or a stated assumption (CN, Tc, runoff coeff).
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    roundabout: str
    impervious_acres: ProvenancedValue  # derived from the OPC pavement/subgrade quantities
    curve_number: ProvenancedValue
    tc_hr: ProvenancedValue
    annual_precip_in: ProvenancedValue
    runoff_coefficient: ProvenancedValue
    mean_annual_cfs: ProvenancedValue  # continuous-equivalent sustained flow
    drought_flow_cfs: float = 0.0  # at design low flow (no rain) — the routed-network reality
    storm_peaks: list[RoundaboutStormPeak]
    method: str
    caveats: list[str] = []

    def peak(self, return_period_yr: int) -> RoundaboutStormPeak | None:
        return next((p for p in self.storm_peaks if p.return_period_yr == return_period_yr), None)


class DesignStorm(BaseModel):
    """A design rainfall event (return period x duration -> depth)."""

    model_config = ConfigDict(extra="forbid")

    return_period_yr: int
    duration_hr: float
    depth: ProvenancedValue  # inches, source typically connector (NOAA Atlas-14)


class Hydrograph(BaseModel):
    """A Tier-0 runoff hydrograph (SCS unit-hydrograph convolution)."""

    model_config = ConfigDict(extra="forbid")

    times_hr: list[float]
    flows_cfs: list[float]
    peak_cfs: float
    time_to_peak_hr: float
    volume_acft: float
    runoff_depth_in: float
    curve_number: float  # the effective CN the chain ran on (AMC-adjusted when amc != "II")
    tc_hr: float = 0.0  # time of concentration the unit hydrograph ran on (impervious-shortened)
    # The EXACT step the series was computed on — the SCS unit duration, which the D <= 0.133*Tc
    # rule refines below the requested step for a short-Tc catchment (#1610). Carried explicitly
    # because ``times_hr`` is rounded for display: a caller re-deriving the step from it (to route
    # the series, or to size a padding tail) would inherit that rounding and mis-lag the reach.
    dt_hr: float = 0.1
    amc: Literal["I", "II", "III"] = "II"  # antecedent moisture condition; "III" = wet
    # How the excess rainfall was computed: "composite_cn" applies the CN equation to one
    # (area-weighted composite) CN; "weighted_runoff" is the TR-55 method — run each cover's CN
    # separately and area-weight the runoff depths, which exceeds the composite result once a
    # mixed footprint's impervious share passes ~30% (#1611). ``curve_number`` still reports the
    # composite as a summary descriptor. Optional/defaulted so pre-#1611 hydrographs still load.
    runoff_method: Literal["composite_cn", "weighted_runoff"] = "composite_cn"
    tier: Literal["tier0"] = "tier0"


class HsgDrainageBasis(BaseModel):
    """Which letter of a dual hydrologic soil group each scenario runs on (WS-20 / #1620).

    SSURGO rates a drainable, naturally-``D`` soil into a **dual** group — ``B/D``, ``C/D`` —
    where the first letter is the group where field tile is installed and maintained and the
    second is the natural, undrained condition. Which one a scenario uses is a modeling
    decision worth several curve-number points (Lima's ``B/D``: cropland CN 78 drained, 89
    undrained), so it is recorded here as an explicit, provenance-tagged pair rather than
    taken silently from the first character of the group string.

    ``pre_hsg`` / ``post_hsg`` are the resolved groups as coded values (A=1…D=4) carrying the
    citation for *why that condition* — so a reader can see both the soil survey and the
    drainage assumption that turned it into a curve number. Identical for a site whose
    dominant group is a single class: only naturally-``D`` soils are ever dual-classed.
    """

    model_config = ConfigDict(extra="forbid")

    group: str  # the verbatim dominant group ("B/D"), never pre-collapsed
    dual: bool  # True when `group` carries both conditions
    # Share of the sampled footprint in *any* dual group — how much ground the switch moves,
    # which the dominant group alone hides. None when the group came from the profile
    # assumption rather than a survey (no distribution to measure).
    dual_fraction: float | None = None
    pre_condition: DrainageCondition
    post_condition: DrainageCondition
    pre_hsg: ProvenancedValue  # hsg_code of the pre-development scenario's resolved group
    post_hsg: ProvenancedValue  # hsg_code of the post-development scenario's resolved group
    basis: str = ""  # the published dual-class rule + this site's stated drainage assumption

    @property
    def pre_letter(self) -> str:
        """The single A-D group the pre-development scenario runs on — the ``cn_for`` input."""
        return resolve_hsg(self.group, self.pre_condition)

    @property
    def post_letter(self) -> str:
        """The single A-D group the post-development scenario runs on."""
        return resolve_hsg(self.group, self.post_condition)


class StormRunoff(BaseModel):
    """Pre- vs post-development runoff for a design storm over one footprint.

    The headline stormwater impact: paving a pervious footprint raises the curve
    number, so the same storm yields a higher peak and more volume. The extra
    volume is the screening-grade detention deficit (the volume a basin must hold
    to keep post-development discharge at the pre-development rate).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    area: ProvenancedValue  # acres
    hsg: ProvenancedValue  # PRE-development resolved group as a coded value (A=1..D=4)
    # The dual-group drainage switch behind `hsg` (WS-20 / #1620): the verbatim survey group
    # and the condition each scenario runs on. Optional so pre-#1620 committed artifacts load.
    hsg_drainage: HsgDrainageBasis | None = None
    storm: DesignStorm
    pre: Hydrograph
    post: Hydrograph

    @property
    def peak_increase_cfs(self) -> float:
        return self.post.peak_cfs - self.pre.peak_cfs

    @property
    def volume_increase_acft(self) -> float:
        return self.post.volume_acft - self.pre.volume_acft


class SiteFootprint(BaseModel):
    """Document-transcribed earth-disturbance footprint of the data-center site.

    The applicant-declared parcel / developed / permanently-impervious acreages from the
    Allen County stormwater-permit application (SW1225), plus the storm outfall and the
    named receiving water — read off the Allen SWCD PRR production, sibling to the
    :class:`StormPlanInventory` (so it lives under ``data/extracted/``). It calibrates the
    Tier-0 post-development cover: only ``impervious_acres`` of the parcel is paved, so the
    post-development curve number is an *area-weighted composite*, not a blanket impervious
    value over the whole footprint.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    citation_index: str  # rel path to the producing PRR response-index
    parcel_acres: ProvenancedValue  # declared total parcel area
    developed_acres: ProvenancedValue  # declared area to be developed
    impervious_acres: ProvenancedValue  # declared permanently-impervious area
    measured_parcel_acres: ProvenancedValue  # geojson planar area (the runoff footprint)
    outfall_diameter_in: ProvenancedValue  # the load-bearing storm outfall
    receiving_water: str
    mass_grading_months: int | None = None
    detention_design_shown: bool = False  # from the 95% SPS grading sheet
    notes: list[str] = []


class OutfallCapacity(BaseModel):
    """Manning full-flow capacity of the storm outfall at one assumed pipe slope."""

    model_config = ConfigDict(extra="forbid")

    slope_pct: float
    capacity_cfs: float


class DischargePeak(BaseModel):
    """One design storm's pre / as-permitted-post / full-buildout peak off the footprint."""

    model_config = ConfigDict(extra="forbid")

    return_period_yr: int
    depth_in: float
    pre_peak_cfs: float  # prior cropland cover
    # as-permitted split (only impervious_acres paved), AMC-II, TR-55 weighted-runoff (#1611)
    post_peak_cfs: float
    full_buildout_peak_cfs: float  # blanket near-impervious upper bound (whole parcel)
    # As-permitted post peak under wet antecedent (AMC-III) — the conservative bound when
    # the design storm falls on ground already saturated by prior rain. Optional so
    # pre-#1160 committed artifacts still load.
    post_peak_wet_cfs: float | None = None


class RoutedDischarge(BaseModel):
    """Muskingum-Cunge routing of the campus outfall hydrograph to its mainstem confluence.

    The discharge screen's other peaks are *at-outfall* — the peak as it leaves the 60-inch
    trunk, with no reach travel. This routes that as-permitted post-development outfall
    hydrograph down the committed ``reaches.yaml`` receiving-tributary channel to its Ottawa
    confluence, so the receiving-water peak is **attenuated and lagged**, not the at-outfall
    peak (#1298). Tier-0 screening on stated reach assumptions — not a calibrated HEC-RAS
    model. The outfall's exact entry point on the tributary is not in the record, so the
    routed channel length is an **upper bound** on outfall->confluence travel; hence the
    attenuation / lag are upper bounds and the confluence peak a lower bound (the reaches
    *between* the outfall and the confluence see intermediate, larger peaks — the at-outfall
    peak-to-7Q10 erosion signal is the unattenuated headline this does not soften).
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    return_period_yr: int
    receiving_water: str
    reach_path: str  # the routed node chain, e.g. "dug-run-head (21,000 ft @ 0.002) -> ..."
    reach_length_ft: ProvenancedValue  # total routed channel length (assumption; reaches.yaml)
    at_outfall_peak_cfs: float
    at_outfall_time_to_peak_hr: float
    routed_peak_cfs: float  # at the mainstem confluence
    routed_time_to_peak_hr: float
    attenuation_pct: float  # (at_outfall - routed) / at_outfall
    lag_hr: float  # routed_ttp - at_outfall_ttp
    method: str = ""


class CampusDischargeScreen(BaseModel):
    """ASWCD-calibrated screening of the campus storm discharge to its receiving water.

    Three screening questions the Allen SWCD production lets us ask with primary data:
    (1) calibrated to the **115 ac of 344 ac** that is actually permanently impervious, how
    much does paving raise the design-storm peak (an area-weighted composite CN, not a
    blanket impervious parcel)?  (2) does the single **60-inch storm outfall** carry that
    peak (Manning full-flow, across an assumed slope range — the slope is not in the
    record)?  (3) the outfall discharges to **Dug Run**, whose cited 7Q10 is only 0.78 cfs
    and which already carries the American II WWTP at a dilution violation — what is the
    storm peak relative to that design low flow (a channel-stability / erosion signal,
    distinct from continuous-effluent dilution).  ``source: derived`` screening, not a
    routed hydraulic model or a permit determination.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    site: str
    footprint_area: ProvenancedValue  # acres (the measured runoff footprint)
    impervious_acres: ProvenancedValue
    developed_acres: ProvenancedValue
    hsg: ProvenancedValue  # PRE-development resolved group (A=1..D=4); see `hsg_drainage`
    hsg_drainage: HsgDrainageBasis | None = None  # the dual-group switch (WS-20 / #1620)
    pre_cn: float
    post_cn_as_permitted: float  # area-weighted composite
    post_cn_full_buildout: float  # blanket near-impervious (whole parcel)
    cover_breakdown: str
    peaks: list[DischargePeak]
    design_return_period_yr: int  # the headline return period
    outfall_diameter_in: ProvenancedValue
    manning_n: float
    outfall_capacity: list[OutfallCapacity]  # by assumed slope
    receiving_water: str
    receiving_7q10: ProvenancedValue | None = None  # cited Dug Run 7Q10
    receiving_note: str = ""
    peak_to_7q10_ratio: float | None = None  # design-RP post peak / 7Q10
    detention_design_shown: bool = False
    basin_chronology_note: str = ""
    # Routed receiving-water peak/lag for the design storm (#1298): the at-outfall peak
    # carried down the receiving tributary to its Ottawa confluence. Optional so pre-#1298
    # committed artifacts still load; None when no committed reach chain resolves.
    routed_discharge: RoutedDischarge | None = None
    method: str = ""
    caveats: list[str] = []

    def peak(self, return_period_yr: int) -> DischargePeak | None:
        return next((p for p in self.peaks if p.return_period_yr == return_period_yr), None)

    @property
    def design_peak(self) -> DischargePeak | None:
        return self.peak(self.design_return_period_yr)

    def capacity_at(self, slope_pct: float) -> float | None:
        match = next((c for c in self.outfall_capacity if c.slope_pct == slope_pct), None)
        return match.capacity_cfs if match else None
