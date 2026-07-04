"""Derive the stormwater the Cole/Beery roundabout could direct into Pike Run.

This grounds the ``waterfall-roundabout-pike-run`` network theory (``theories.yaml``),
whose injected flow had been a 0.5 cfs placeholder. The relator's theory is a roundabout
engineered to direct surface flow into Pike Run to augment its baseflow and flush sludge.
Deriving the actual runoff from the roundabout's catchment against the cited corridor
rainfall **refutes the sustained-augmentation premise**:

* **Mean-annual continuous-equivalent ~0.01 cfs** — a single roundabout's impervious
  catchment (~2.9 acres) yields a negligible average flow.
* **Zero at design low flow** — at the 7Q10 (a drought) it is not raining, so the roundabout
  directs nothing; it cannot augment Pike Run's low flow at all.
* **Storm-event peaks ~3-6 cfs** (2-yr to 100-yr) — transient surges of a few hours. *This*
  is the only flushing it can deliver: episodic, storm-driven, not a low-flow augmentation.

The drainage area is derived from document-cited Tetra Tech OPC quantities (no per-roundabout
area is stated in the corpus); the rainfall is the cited Atlas-14 corridor DDF + NASA POWER
precip; CN / Tc / runoff coefficient are stated assumptions. A *derived* screening result.
"""

from __future__ import annotations

from watermark.config import Settings, get_settings
from watermark.hydrology.climate import load_climatology
from watermark.hydrology.drainage import load_corridor_ddf
from watermark.hydrology.model import (
    HydroFinding,
    ProvenancedValue,
    RoundaboutFlow,
    RoundaboutStormPeak,
)
from watermark.hydrology.solver.runoff import simulate_runoff
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# Document-cited OPC anchors (Tetra Tech roundabouts OPC, PRR-01-bundle). No per-roundabout
# drainage area is stated in the corpus, so the impervious footprint is derived: Cole/Diller's
# subgrade-compaction area (a graded-footprint proxy) scaled to the larger Cole/Beery roundabout
# by the two roundabouts' pavement-subtotal ratio.
_DILLER_SUBGRADE_SY = 6200  # item 204E10001 "Subgrade compaction", Cole/Diller OPC pdf p.319
_DILLER_PAVEMENT_USD = 302631  # Cole/Diller PAVEMENT section subtotal (summary OPC)
_BEERY_PAVEMENT_USD = 681232  # Cole/Beery (Primary Access) PAVEMENT section subtotal (summary OPC)
_SY_TO_ACRE = 9.0 / 43560.0
_SEC_PER_YEAR = 365.0 * 86400.0
_ACRE_FT_TO_CF = 43560.0

# Stated assumptions for the runoff chain.
_DEFAULT_CN = 98.0  # asphalt/concrete impervious (TR-55)
# Tc for the small roundabout catchment is a per-site basin value on the SiteProfile
# (roundabout_tc_hr), resolved in derive_roundabout_flow — not a module constant.
_DEFAULT_RUNOFF_COEFF = 0.9  # impervious annual runoff coefficient
_DEFAULT_RETURN_PERIODS = (2, 10, 25, 50, 100)

# Fallback if the committed reference data is absent. The 24-hr storm-depth fallback is the
# active site's Atlas-14 table (SiteProfile.noaa_fallback_24h_depth_in, read in _storm_depths) —
# not a hardcoded Lima dict; the annual-precip fallback stays a single cited corridor value.
_FALLBACK_ANNUAL_PRECIP_IN = 39.2  # NASA POWER PRECTOTCORR 2.73 mm/day


def _derive_impervious_acres() -> ProvenancedValue:
    """Impervious roundabout footprint (acres), derived from the cited OPC quantities."""
    diller_ac = _DILLER_SUBGRADE_SY * _SY_TO_ACRE
    ratio = _BEERY_PAVEMENT_USD / _DILLER_PAVEMENT_USD
    beery_ac = diller_ac * ratio
    return ProvenancedValue.derived(
        round(beery_ac, 2),
        "acre",
        citation=(
            f"Cole/Diller subgrade compaction {_DILLER_SUBGRADE_SY} SY (Tetra Tech OPC item "
            f"204E10001, pdf p.319) = {diller_ac:.2f} ac, scaled by the Cole/Beery:Diller pavement "
            f"subtotal ratio {_BEERY_PAVEMENT_USD:,}:{_DILLER_PAVEMENT_USD:,} = {ratio:.2f}x "
            "(no per-roundabout drainage area is stated in the corpus)"
        ),
        confidence="low",
    )


def _annual_precip_in(settings: Settings) -> ProvenancedValue:
    clim = load_climatology(settings=settings)
    precip = clim.get("PRECTOTCORR") if clim is not None else None
    if precip is not None and precip.annual is not None:
        annual_in = precip.annual * 365.0 / 25.4  # mm/day -> in/yr
        return ProvenancedValue.from_connector(
            round(annual_in, 1),
            "in",
            citation=f"NASA POWER PRECTOTCORR {precip.annual:g} mm/day (nasa-power-climatology.yaml)",
        )
    return ProvenancedValue.assume(
        _FALLBACK_ANNUAL_PRECIP_IN, "in", why="NASA POWER annual precip (offline fallback)"
    )


def _storm_depths(settings: Settings, return_periods: tuple[int, ...]) -> dict[int, float]:
    ddf = load_corridor_ddf(settings=settings)
    fallback = active_profile(settings).noaa_fallback_24h_depth_in
    out: dict[int, float] = {}
    for rp in return_periods:
        depth = None
        if ddf is not None:
            depth = ddf.depths_in.get("24-hr", {}).get(str(rp))
        out[rp] = depth if depth is not None else fallback.get(rp, 4.25)
    return out


def derive_roundabout_flow(
    *,
    roundabout: str = "Cole/Beery (Primary Access Entrance)",
    impervious_acres: ProvenancedValue | None = None,
    curve_number: float = _DEFAULT_CN,
    tc_hr: float | None = None,
    runoff_coefficient: float = _DEFAULT_RUNOFF_COEFF,
    return_periods: tuple[int, ...] = _DEFAULT_RETURN_PERIODS,
    settings: Settings | None = None,
) -> RoundaboutFlow:
    """Derive the roundabout's directed flow: mean-annual (sustained) + per-storm peaks.

    The mean-annual continuous-equivalent is the routed-network theory's defensible
    injection (a smeared average); the per-storm peaks are the transient flushing surges.
    The design-low-flow value is **zero** — it does not rain at the 7Q10.
    """
    settings = settings or get_settings()
    # The small roundabout catchment's Tc is a per-site basin value on the profile (not the
    # campus Tc, and not a module constant); an explicit override still wins.
    if tc_hr is None:
        tc_hr = active_profile(settings).roundabout_tc_hr
    area_pv = impervious_acres or _derive_impervious_acres()
    area = area_pv.value
    annual_precip = _annual_precip_in(settings)
    depths = _storm_depths(settings, return_periods)

    peaks: list[RoundaboutStormPeak] = []
    for rp in return_periods:
        depth = depths[rp]
        h = simulate_runoff(
            area_acres=area, curve_number=curve_number, tc_hr=tc_hr, storm_depth_in=depth
        )
        peaks.append(
            RoundaboutStormPeak(
                return_period_yr=rp,
                depth_in=depth,
                peak_cfs=h.peak_cfs,
                volume_acft=h.volume_acft,
                runoff_depth_in=h.runoff_depth_in,
            )
        )

    # Mean-annual continuous-equivalent: runoff depth x area, smeared over the year.
    runoff_depth_ft = runoff_coefficient * annual_precip.value / 12.0
    annual_acft = runoff_depth_ft * area
    mean_annual_cfs = annual_acft * _ACRE_FT_TO_CF / _SEC_PER_YEAR

    rf = RoundaboutFlow(
        roundabout=roundabout,
        impervious_acres=area_pv,
        curve_number=ProvenancedValue.assume(
            curve_number, "CN", why="asphalt/concrete impervious roundabout (TR-55)"
        ),
        tc_hr=ProvenancedValue.assume(
            tc_hr, "hr", why="time of concentration for a small roundabout catchment"
        ),
        annual_precip_in=annual_precip,
        runoff_coefficient=ProvenancedValue.assume(
            runoff_coefficient, "fraction", why="impervious annual runoff coefficient"
        ),
        mean_annual_cfs=ProvenancedValue.derived(
            round(mean_annual_cfs, 4),
            "cfs",
            citation=(
                f"{runoff_coefficient:g} x {annual_precip.value:g} in/yr over {area:g} impervious "
                "acres, as a continuous-equivalent flow"
            ),
        ),
        drought_flow_cfs=0.0,
        storm_peaks=peaks,
        method="SCS-CN design-storm hydrograph (peaks) + annual runoff-coefficient smear (mean)",
        caveats=[
            "Impervious area is DERIVED from OPC pavement quantities (no per-roundabout drainage "
            "area is stated in the corpus); the true catchment incl. shoulders/ROW may be larger.",
            "At design low flow (7Q10) the roundabout directs ZERO — it is not raining. The "
            "mean-annual figure is a smeared average, not a flow present during the drought.",
            "CN, Tc and the runoff coefficient are stated assumptions; storm peaks are transient "
            "(a few hours), not sustained flow.",
        ],
    )
    peak_10 = rf.peak(10)
    log.info(
        "hydro.roundabout",
        roundabout=roundabout,
        impervious_acres=area,
        mean_annual_cfs=rf.mean_annual_cfs.value,
        peak_10yr=peak_10.peak_cfs if peak_10 is not None else None,
    )
    return rf


def roundabout_findings(rf: RoundaboutFlow) -> list[HydroFinding]:
    """Findings: the theory's sustained-augmentation premise vs the derived flow."""
    p2 = rf.peak(2)
    p100 = rf.peak(100)
    storm_txt = (
        f"{p2.peak_cfs:g}-{p100.peak_cfs:g} cfs (2-yr to 100-yr)"
        if p2 is not None and p100 is not None
        else "a few cfs"
    )
    return [
        HydroFinding(
            subject="roundabout low-flow augmentation",
            check="roundabout-sustained-flow",
            ok=False,  # the theory's premise fails — surfaced as an adverse finding for the theory
            detail=(
                f"the {rf.impervious_acres.value:g}-acre impervious catchment yields a mean-annual "
                f"continuous-equivalent of only {rf.mean_annual_cfs.value:g} cfs, and ZERO at "
                "design low flow (no rain) — it cannot sustainably augment Pike Run's 7Q10. The "
                "0.5 cfs placeholder overstated it ~40x."
            ),
        ),
        HydroFinding(
            subject="roundabout storm-event flushing",
            check="roundabout-storm-surge",
            ok=True,
            detail=(
                f"what the roundabout CAN deliver is transient storm surges of {storm_txt} lasting "
                "a few hours — episodic flushing, not a low-flow augmentation, and carrying road-"
                "runoff pollution. The routed-network injection is the mean-annual smear, not these."
            ),
        ),
    ]
