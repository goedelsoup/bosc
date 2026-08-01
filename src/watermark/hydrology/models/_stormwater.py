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


class ChannelFormingDischarge(BaseModel):
    """The receiving channel's bankfull / effective discharge — the erosion denominator (#1612).

    Channel stability and bank erosion are governed by the **channel-forming** (bankfull,
    effective) discharge — the moderate, frequent flow that does most of the long-term
    geomorphic work (Wolman & Miller 1960) and recurs at roughly 1-2 years — **not** by the
    7-day 10-year **low** flow. A storm peak is many hundreds of times any small stream's 7Q10
    almost by construction, which is why that ratio maps to no erosion threshold (WS-12).

    Estimated the only way the committed record supports: the **same** Tier-0 SCS chain the
    campus peaks run on, applied to the receiving tributary's own contributing subcatchment in
    ``reaches.yaml`` at the cited channel-forming-recurrence design storm. That symmetry is the
    point — numerator and denominator share the method, the rainfall distribution, the peak
    factor and the Atlas-14 point, so the method's systematic biases largely cancel in the ratio.
    They do **not** cancel in a peak-to-7Q10 ratio, whose denominator is a log-Pearson low-flow
    statistic from a different record entirely.

    Scale caveat, recorded on the object: the catchment is the tributary's own, taken at the
    mainstem confluence — the LARGEST channel-forming discharge anywhere on that tributary. The
    outfall enters somewhere above it, where the local drainage area (and so the local
    channel-forming discharge) is smaller, so a ratio against this figure is a **lower bound**
    on what the channel actually sees at the discharge point.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    receiving_water: str
    node_id: str  # the reaches.yaml catchment this estimate runs on (the tributary headwater)
    return_period_yr: int  # the cited channel-forming recurrence (tier0-parameters.yaml)
    storm_depth_in: float  # the Atlas-14 24-hr depth at that recurrence
    discharge: ProvenancedValue  # cfs — the bankfull / effective discharge surrogate
    catchment_area_acres: ProvenancedValue  # carried verbatim from reaches.yaml (its provenance)
    curve_number: ProvenancedValue
    tc_hr: ProvenancedValue
    method: str = ""


class ChannelFlowState(BaseModel):
    """Normal-depth (uniform-flow) hydraulics of one discharge in the cited reach section.

    ``shear_stress_psf`` is the reach-average boundary shear ``tau = gamma*R*S`` — the quantity that
    detaches bank and bed material, and the one a discharge ratio alone cannot express.
    """

    model_config = ConfigDict(extra="forbid")

    label: str  # what this discharge is ("bankfull (2-yr)", "25-yr post-development peak")
    discharge_cfs: float
    depth_ft: float
    top_width_ft: float
    velocity_fps: float
    shear_stress_psf: float


class ReachConveyance(BaseModel):
    """Does the receiving CHANNEL carry the campus peak — the check the pipe screen stops short of.

    The outfall-capacity screen ends at the 60-inch trunk's Manning full-flow. This is the next
    question: routed into the receiving reach's cited section, what depth, velocity and boundary
    shear does the design-storm peak run at, and how do those compare with the channel-forming
    (bankfull) flow the channel is adjusted to?

    Bankfull stage is taken **self-consistently** — the normal depth of the channel-forming
    discharge in this same section — because no surveyed cross-section exists for these reaches.
    So ``within_bank`` reduces to "the design peak is no larger than the channel-forming
    discharge"; what the block adds beyond that ratio is the *hydraulics*: the shear and velocity
    ratios are the geomorphic work the extra flow does. ``geometry_source`` says whether the
    section is the reach's own committed geometry or the Tier-0 routing default trapezoid — on
    the default the absolute depths are a screening bracket, and a surveyed section is the upgrade.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    node_id: str  # the reaches.yaml reach the outfall discharges into (first of the routed chain)
    receiving_water: str
    slope: float  # ft/ft, from reaches.yaml
    manning_n: float
    bottom_width_ft: float
    side_slope_z: float
    geometry_source: Literal["reach", "tier0_default"]
    bankfull: ChannelFlowState  # at the channel-forming discharge
    design: ChannelFlowState  # at the design-storm as-permitted post-development peak
    within_bank: bool  # design depth <= bankfull depth
    method: str = ""

    @property
    def depth_ratio(self) -> float | None:
        """Design-storm normal depth as a fraction of the bankfull-proxy depth."""
        return self.design.depth_ft / self.bankfull.depth_ft if self.bankfull.depth_ft else None

    @property
    def shear_ratio(self) -> float | None:
        """Design-storm boundary shear as a fraction of the bankfull-proxy shear."""
        bf = self.bankfull.shear_stress_psf
        return self.design.shear_stress_psf / bf if bf else None


class CampusDischargeScreen(BaseModel):
    """ASWCD-calibrated screening of the campus storm discharge to its receiving water.

    Four screening questions the Allen SWCD production lets us ask with primary data:
    (1) calibrated to the **115 ac of 344 ac** that is actually permanently impervious, how
    much does paving raise the design-storm peak (an area-weighted composite CN, not a
    blanket impervious parcel)?  (2) does the single **60-inch storm outfall** carry that
    peak (Manning full-flow, across an assumed slope range — the slope is not in the
    record)?  (3) does the receiving **channel** carry it — how does the peak stand against
    the channel-forming (bankfull / 2-yr) discharge that sets channel stability, and what
    depth / velocity / boundary shear does it run at in the cited reach section
    (``channel_forming`` + ``reach_conveyance``, WS-12 / #1612)?  (4) the outfall discharges
    to **Dug Run**, whose cited 7Q10 is only 0.78 cfs and which already carries the American
    II WWTP at a dilution violation — what is the storm peak relative to that design **low**
    flow?  ``source: derived`` screening, not a routed hydraulic model or a permit
    determination.

    **The erosion signal is (3), not (4).** ``peak_to_7q10_ratio`` divides a storm peak by a
    7-day 10-year *low*-flow statistic; the result is large for any flashy outfall on any small
    stream and maps to no geomorphic threshold. It is kept because the low-flow framing is the
    right one for *dilution* — it is not, and no longer reads as, a channel-stability finding.
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
    # The LOW-FLOW framing (dilution), not the erosion one: design-RP post peak / cited 7Q10.
    peak_to_7q10_ratio: float | None = None
    # The EROSION framing (WS-12 / #1612): the receiving channel's bankfull / effective discharge
    # and the design peak read against it, plus the normal-depth conveyance check at the cited
    # reach section. None when the receiving tributary has no committed catchment / reach chain,
    # or no design storm resolves at the channel-forming recurrence — degrade, never fabricate.
    channel_forming: ChannelFormingDischarge | None = None
    peak_to_channel_forming_ratio: float | None = None  # design-RP post peak / bankfull discharge
    reach_conveyance: ReachConveyance | None = None
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

    @property
    def channel_forming_peak(self) -> DischargePeak | None:
        """The site's own pre/post peaks at the channel-forming recurrence (WS-12 / #1612).

        The pair the channel-protection criterion is read on — a post-development peak that
        exceeds the pre-development peak at the channel-forming frequency is the mechanism by
        which urbanization enlarges a receiving channel. ``None`` until a channel-forming
        discharge resolves (the recurrence it is keyed to comes from the same cited constant).
        """
        cf = self.channel_forming
        return self.peak(cf.return_period_yr) if cf is not None else None

    def capacity_at(self, slope_pct: float) -> float | None:
        match = next((c for c in self.outfall_capacity if c.slope_pct == slope_pct), None)
        return match.capacity_cfs if match else None
