"""Pre- vs post-development stormwater runoff for the data-center campus.

The stormwater impact of the decision to pave the corridor: the same NOAA Atlas-14
design storm yields far more runoff off impervious ground than off the cropland it
replaces. We compute both Tier-0 SCS hydrographs and report the peak/volume increase
and the screening detention deficit — the classic "post-development must not exceed
pre-development peak" stormwater test.

Grounding: the footprint area is document-sourced (the recorded Bistrozzi parcels);
the design storm and the hydrologic soil group are connector-sourced (NOAA Atlas-14;
USDA SSURGO via SDA, the footprint's grid-sampled dominant HSG), each falling back to the
site profile's cited value offline. Land cover is a cited assumption (prior use "Neff
Farms" -> cropland). Curve numbers come from the cited TR-55 table.

Where SSURGO returns a **dual** group (``B/D`` here), which of its two letters a scenario
runs on is an explicit, provenance-tagged switch, not a first-character slice (WS-20 /
#1620): the first letter applies only where field tile is installed and maintained. Lima's
pre-development cropland is tile-drained, but construction severs or reroutes the tile it
does not maintain, so the developed ground runs the natural, undrained class — the
conservative design basis, and worth several curve-number points on a lake-plain clay.
``_resolve_hsg`` builds that resolution once into an
:class:`~watermark.hydrology.model.HsgDrainageBasis`; the per-site conditions live on
``SiteProfile.pre_drainage_condition`` / ``post_drainage_condition``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, TypedDict

import numpy as np
import yaml

from watermark.config import Settings, get_settings
from watermark.hsg import DUAL_HSG_RULE, DrainageCondition, hsg_code, is_dual_hsg, resolve_hsg
from watermark.hydrology import geo, network
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.hydrology.connectors.noaa_atlas14 import design_storm
from watermark.hydrology.connectors.ssurgo import SsurgoError, dominant_hsg
from watermark.hydrology.lowflow import low_flow_context, low_flow_for
from watermark.hydrology.model import (
    CampusDischargeScreen,
    ChannelFlowState,
    ChannelFormingDischarge,
    DesignStorm,
    DischargePeak,
    HsgDrainageBasis,
    HydroFinding,
    Hydrograph,
    NetworkNode,
    OutfallCapacity,
    ProvenancedValue,
    Reach,
    ReachConveyance,
    ReachTable,
    RoutedDischarge,
    SiteFootprint,
    StormRunoff,
)
from watermark.hydrology.solver.curve_number import cn_for, composite_cn
from watermark.hydrology.solver.parameters import (
    channel_forming_return_period,
    default_manning_n,
    round_sig,
)
from watermark.hydrology.solver.parameters import peak_factor as solver_peak_factor
from watermark.hydrology.solver.routing import (
    DEFAULT_BOTTOM_WIDTH_FT,
    DEFAULT_SIDE_SLOPE_Z,
    normal_flow,
    route,
)
from watermark.hydrology.solver.runoff import simulate_runoff
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# Per-site values (design point, dominant HSG + citation, cover taxonomy, the NOAA
# Atlas-14 offline-fallback depth table, the pre/post time-of-concentration bounds, and the
# parcels/footprint paths) come from the active site profile (watermark.sites); see
# active_profile(settings) at each use.

# Manning roughness for a concrete / smooth-HDPE storm trunk, and the assumed pipe-slope
# sensitivity band for the outfall capacity screen (the slope is NOT in the record).
_OUTFALL_MANNING_N = 0.013
_OUTFALL_SLOPES_PCT: tuple[float, ...] = (0.3, 0.5, 1.0)
_DISCHARGE_RETURN_PERIODS: tuple[int, ...] = (10, 25, 100)

# The flat/swampy end of NEH-630 Ch. 16's published SCS peak-factor range, used ONLY to state
# the peaks' terrain sensitivity in the screen's caveats (#1610) — a published reference value,
# not a claim about any site's landform. The reported peaks run on the site's resolved factor
# (`SiteProfile.uh_peak_factor`, else the cited 484); adopting this end for a site is a reviewed,
# separately-cited profile edit, not something this screen decides.
_FLAT_TERRAIN_PEAK_FACTOR = 300.0


def _parcels_path(settings: Settings) -> Path:
    return settings.data_dir / active_profile(settings).parcels_relpath


def _footprint_path(settings: Settings) -> Path:
    return settings.data_dir / active_profile(settings).footprint_relpath


def load_site_footprint(settings: Settings | None = None) -> SiteFootprint | None:
    """The document-cited ASWCD earth-disturbance footprint, or ``None`` if uncommitted."""
    settings = settings or get_settings()
    path = _footprint_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SiteFootprint.model_validate(data)


def _scenario_tc_hr(impervious_fraction: float, *, settings: Settings) -> float:
    """Time of concentration (hr) for a scenario at a given impervious fraction.

    Impervious paving raises runoff velocity and shortens travel time, so Tc falls with
    imperviousness. We linearly interpolate between the profile's pervious ``pre_tc_hr``
    (fraction 0 — prior cover) and fully-impervious ``post_tc_hr`` (fraction 1 — blanket
    buildout); the as-permitted composite lands in between at its declared impervious share.
    Screening-grade — a single-slope proxy for the NRCS velocity method, which needs flow
    lengths not in the record.
    """
    prof = active_profile(settings)
    frac = max(0.0, min(1.0, impervious_fraction))
    return prof.pre_tc_hr - (prof.pre_tc_hr - prof.post_tc_hr) * frac


def _post_cover_parts(
    total_acres: float,
    footprint: SiteFootprint,
    hsg: HsgDrainageBasis,
    *,
    settings: Settings,
) -> tuple[list[tuple[float, float]], str]:
    """The declared post-development ``(area, CN)`` cover split + a human breakdown.

    Only ``impervious_acres`` of the parcel is paved (near-impervious campus); the rest of
    the developed area is graded/landscaped pervious ground; the undeveloped remainder keeps
    its prior cropland cover. Acreages are clamped to the measured runoff footprint so the
    weights never exceed the total area. These parts feed the TR-55 weighted-runoff computation
    (each cover's CN run separately, runoff depths area-weighted — ``simulate_runoff(cn_parts=)``),
    which does not under-predict runoff the way a single composite CN does once the ~34%
    impervious footprint passes TR-55's ~30% directly-connected threshold (#1611).

    The two **developed** parts run on the post-development drainage condition — construction
    severs or reroutes the field tile under them — while the undeveloped remainder keeps the
    pre-development one along with its prior cover: it is still being farmed, and asserting that
    site work also severed the tile under ground nobody touched would be inventing a fact
    (WS-20 / #1620). On a single-group site the two conditions resolve to the same letter and
    this distinction is inert.
    """
    prof = active_profile(settings)
    imperv = max(0.0, min(footprint.impervious_acres.value, total_acres))
    developed = max(0.0, min(footprint.developed_acres.value, total_acres))
    dev_pervious = max(0.0, developed - imperv)
    remainder = max(0.0, total_acres - imperv - dev_pervious)
    post_letter, pre_letter = hsg.post_letter, hsg.pre_letter
    parts = [
        (imperv, cn_for(prof.post_cover, post_letter, settings=settings)),
        (dev_pervious, cn_for(prof.developed_pervious_cover, post_letter, settings=settings)),
        (remainder, cn_for(prof.pre_cover, pre_letter, settings=settings)),
    ]
    breakdown = (
        f"{imperv:.0f} ac impervious + {dev_pervious:.0f} ac developed-pervious + "
        f"{remainder:.0f} ac undeveloped (of {total_acres:.0f} ac)"
    )
    if hsg.dual:
        breakdown += (
            f"; developed ground on HSG {post_letter} ({hsg.post_condition}), the undeveloped "
            f"remainder on HSG {pre_letter} ({hsg.pre_condition})"
        )
    return parts, breakdown


def run_storm_scenario(
    *,
    return_period_yr: int = 25,
    settings: Settings | None = None,
    live: bool = True,
    footprint_path: Path | None = None,
) -> tuple[StormRunoff, list[HydroFinding]]:
    """Compute pre/post design-storm runoff over the campus footprint."""
    settings = settings or get_settings()
    prof = active_profile(settings)
    path = footprint_path or _parcels_path(settings)

    acres = geo.parcels_total_acres(path, settings=settings)
    area = ProvenancedValue.from_document(
        acres, "acre", citation=f"{path.name} (recorded Bistrozzi parcel footprints)"
    )
    hsg = _resolve_hsg(path, settings=settings, live=live)

    storm = _resolve_storm(return_period_yr, settings=settings, live=live)

    pre_cn = cn_for(prof.pre_cover, hsg.pre_letter, settings=settings)
    # Calibrate the post-development cover to the ASWCD-declared footprint when committed:
    # only ~115 of ~344 ac is permanently impervious, so the post runoff is the TR-55
    # weighted-runoff of the impervious/developed-pervious/undeveloped split (each cover's CN
    # run separately, runoff depths area-weighted; post_cn is the composite summary), not a
    # blanket near-impervious value over the whole parcel. Falls back to the blanket
    # near-impervious cover (the full-buildout bound) if the footprint is absent.
    footprint = load_site_footprint(settings)
    post_parts: list[tuple[float, float]] | None
    if footprint is not None:
        post_parts, _ = _post_cover_parts(acres, footprint, hsg, settings=settings)
        post_cn = composite_cn(post_parts)
        post_imperv_frac = min(footprint.impervious_acres.value, acres) / acres if acres else 0.0
    else:
        post_parts = None
        post_cn = cn_for(prof.post_cover, hsg.post_letter, settings=settings)
        post_imperv_frac = 1.0  # blanket near-impervious buildout — the shortest Tc
    depth = storm.depth.value
    # Pre-development is fully pervious (impervious fraction 0 -> the longest Tc); the post
    # scenario's shorter Tc scales with its impervious fraction, sharpening the post peak.
    pre_tc = _scenario_tc_hr(0.0, settings=settings)
    post_tc = _scenario_tc_hr(post_imperv_frac, settings=settings)
    pre = simulate_runoff(
        area_acres=acres,
        curve_number=pre_cn,
        tc_hr=pre_tc,
        storm_depth_in=depth,
        settings=settings,
    )
    if post_parts is not None:
        post = simulate_runoff(
            area_acres=acres,
            cn_parts=post_parts,
            tc_hr=post_tc,
            storm_depth_in=depth,
            settings=settings,
        )
    else:
        post = simulate_runoff(
            area_acres=acres,
            curve_number=post_cn,
            tc_hr=post_tc,
            storm_depth_in=depth,
            settings=settings,
        )

    runoff = StormRunoff(
        name="BOSC data-center campus",
        area=area,
        hsg=hsg.pre_hsg,
        hsg_drainage=hsg,
        storm=storm,
        pre=pre,
        post=post,
    )
    log.info(
        "hydro.storm",
        acres=round(acres, 1),
        hsg=hsg.group,
        pre_hsg=hsg.pre_letter,
        post_hsg=hsg.post_letter,
        pre_cn=pre_cn,
        post_cn=post_cn,
        depth_in=depth,
        peak_increase=round(runoff.peak_increase_cfs, 1),
    )
    return runoff, _storm_findings(runoff)


def _resolve_hsg(footprint_path: Path, *, settings: Settings, live: bool) -> HsgDrainageBasis:
    """The dominant HSG over the footprint, resolved per scenario's drainage condition.

    Sourced from SSURGO when live, else the site profile's cited assumption — either way the
    group is carried **verbatim** (``"B/D"``) and the drained-vs-undrained choice is made here,
    explicitly, once per scenario (WS-20 / #1620). The pre-development condition
    (``SiteProfile.pre_drainage_condition``, default ``drained``) and the post-development one
    (``post_drainage_condition``, default ``undrained``) each yield a single A-D letter for
    ``cn_for``, tagged with where the soil rating came from *and* why that condition applies.

    The two coded values are provenance-tagged ``connector`` when the rating was sourced live
    and ``assumption`` on the profile fallback; the drainage condition itself is always a
    stated modeling assumption, named in the citation, never presented as a survey finding.
    """
    prof = active_profile(settings)
    group = prof.dominant_hsg
    dual_fraction: float | None = None
    rating = ProvenancedValue.assume(0.0, "hsg_code", why=prof.hsg_citation)
    if live:
        try:
            survey = dominant_hsg(footprint_path, settings=settings)
            group = survey.dominant_hsg
            dual_fraction = survey.dual_fraction
            shares = ", ".join(f"{d.hsg} {d.fraction:.0%}" for d in survey.distribution)
            rating = ProvenancedValue.from_connector(
                0.0,
                "hsg_code",
                citation=(
                    f"SSURGO dominant HSG {group} ({shares}) over "
                    f"{survey.n_points} footprint grid points — {survey.source}"
                ),
            )
        except (HydroOfflineError, SsurgoError) as exc:
            log.info("hydro.storm.hsg_fallback", error=str(exc).splitlines()[0])

    dual = is_dual_hsg(group)

    def _resolved(condition: DrainageCondition, scenario: str) -> ProvenancedValue:
        letter = resolve_hsg(group, condition)
        why = (
            f"{scenario} runs hydrologic soil group {letter} — the {condition} letter of the "
            f"dual group {group}. {rating.citation}"
            if dual
            else f"{scenario} runs hydrologic soil group {letter} (not a dual group, so the "
            f"{condition} condition does not change it). {rating.citation}"
        )
        return rating.model_copy(update={"value": hsg_code(letter), "citation": why})

    return HsgDrainageBasis(
        group=group,
        dual=dual,
        dual_fraction=dual_fraction,
        pre_condition=prof.pre_drainage_condition,
        post_condition=prof.post_drainage_condition,
        pre_hsg=_resolved(prof.pre_drainage_condition, "Pre-development"),
        post_hsg=_resolved(prof.post_drainage_condition, "Post-development"),
        basis=f"{DUAL_HSG_RULE} {prof.drainage_condition_citation}",
    )


def _resolve_storm(return_period_yr: int, *, settings: Settings, live: bool) -> DesignStorm:
    prof = active_profile(settings)
    if live:
        try:
            return design_storm(
                lat=prof.design_lat,
                lon=prof.design_lon,
                return_period_yr=return_period_yr,
                settings=settings,
            )
        except HydroOfflineError:
            log.info("hydro.storm.offline_fallback", return_period=return_period_yr)
    # No live fetch / cache: fall back to the ACTIVE SITE's cited Atlas-14 corridor-point
    # depth, flagged. If the site has no cited depth for this return period, fail loudly
    # naming the missing (site, return-period) key rather than substituting Lima's — mirrors
    # the connector-cache "fail rather than fabricate" discipline (#1604).
    fallback = prof.noaa_fallback_24h_depth_in
    if return_period_yr not in fallback:
        raise HydroOfflineError(
            f"no offline NOAA Atlas-14 24-hr design-storm depth for site {settings.site!r} "
            f"at return period {return_period_yr}-yr "
            f"(SiteProfile.noaa_fallback_24h_depth_in has {sorted(fallback)}); run the "
            "NOAA Atlas-14 pull for this site or add the cited corridor-point depth"
        )
    depth = fallback[return_period_yr]
    return DesignStorm(
        return_period_yr=return_period_yr,
        duration_hr=24.0,
        depth=ProvenancedValue.assume(
            depth,
            "in",
            why=f"{return_period_yr}-yr 24-hr NOAA Atlas-14 depth at corridor point (offline cache)",
        ),
    )


def _storm_findings(runoff: StormRunoff) -> list[HydroFinding]:
    name = runoff.name
    rp = runoff.storm.return_period_yr
    findings = [
        HydroFinding(
            subject=name,
            check="post-vs-pre-peak",
            ok=runoff.peak_increase_cfs <= 0,
            detail=(
                f"{rp}-yr 24-hr storm ({runoff.storm.depth.value:.2f} in): peak "
                f"{runoff.pre.peak_cfs:.0f} -> {runoff.post.peak_cfs:.0f} cfs "
                f"(+{runoff.peak_increase_cfs:.0f}, CN {runoff.pre.curve_number:.0f} -> "
                f"{runoff.post.curve_number:.0f}, Tc {runoff.pre.tc_hr:g} -> "
                f"{runoff.post.tc_hr:g} hr)"
            ),
        ),
        HydroFinding(
            subject=name,
            check="detention-deficit",
            ok=runoff.volume_increase_acft <= 0,
            detail=(
                f"runoff volume {runoff.pre.volume_acft:.0f} -> {runoff.post.volume_acft:.0f} ac-ft "
                f"(+{runoff.volume_increase_acft:.0f} ac-ft to detain for pre-development control)"
            ),
        ),
    ]
    return findings


# --------------------------------------------------------------------------------------
# ASWCD-calibrated campus discharge screen (#149): composite post CN, the 60" outfall
# capacity, the receiving channel's channel-forming (bankfull) discharge + normal-depth
# conveyance — the erosion signal (WS-12 / #1612) — and the storm peak vs Dug Run's cited
# 7Q10, which is the LOW-flow / dilution framing and not a channel-stability threshold.
# --------------------------------------------------------------------------------------


def manning_full_pipe_cfs(
    diameter_ft: float, slope: float, *, n: float = _OUTFALL_MANNING_N
) -> float:
    """Full-flow capacity (cfs) of a circular pipe by Manning's equation (English units)."""
    area = math.pi * diameter_ft**2 / 4.0
    hydraulic_radius = diameter_ft / 4.0
    return float((1.49 / n) * area * hydraulic_radius ** (2.0 / 3.0) * math.sqrt(slope))


def _discharge_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "bosc-stormwater-discharge.yaml"


# Extra zero-padded tail (hr) so a routed reach's lag never clips the peak off the horizon
# (mirrors watermark.hydrology.hydrograph_routing).
_ROUTING_HEADROOM_HR = 24.0


class _ReachRouteKwargs(TypedDict, total=False):
    """The trapezoid overrides a reach may carry — a precise kwargs type so unpacking into
    ``route`` can't be confused with its ``settings`` keyword."""

    bottom_width_ft: float
    side_slope_z: float
    manning_n: float


def _reach_route_kwargs(reach: Reach) -> _ReachRouteKwargs:
    """The optional trapezoid overrides on a reach; the rest fall back to ``route``'s defaults."""
    kw: _ReachRouteKwargs = {}
    if reach.bottom_width_ft is not None:
        kw["bottom_width_ft"] = reach.bottom_width_ft.value
    if reach.side_slope_z is not None:
        kw["side_slope_z"] = reach.side_slope_z.value
    if reach.manning_n is not None:
        kw["manning_n"] = reach.manning_n.value
    return kw


def _tributary_reach_chain(
    nodes: list[NetworkNode], table: ReachTable, receiving_water: str
) -> list[tuple[NetworkNode, Reach]]:
    """The committed reach chain carrying ``receiving_water`` down to its mainstem confluence.

    Walks the cited topology from the tributary's headwater, following ``downstream`` and
    collecting each node that has a reach in ``table``, stopping once it routes through the
    confluence node (the tributary -> mainstem junction). Site-generic: it resolves the chain
    by the footprint's named receiving water, never a hardcoded Lima node id. Empty when the
    receiving water has no committed headwater/reach chain.
    """
    by_id = {n.id: n for n in nodes}
    start = next(
        (
            n
            for n in nodes
            if n.kind == "headwater"
            and n.receiving_water == receiving_water
            and n.id in table.reaches
        ),
        None,
    )
    chain: list[tuple[NetworkNode, Reach]] = []
    node: NetworkNode | None = start
    seen: set[str] = set()
    reached_confluence = False
    while node is not None and node.id not in seen:
        seen.add(node.id)
        reach = table.reaches.get(node.id)
        if reach is not None:
            chain.append((node, reach))
        if node.kind == "confluence":
            reached_confluence = True
            break  # routed the tributary into the mainstem; stop
        node = by_id.get(node.downstream) if node.downstream else None
    # Only a walk that actually reaches the mainstem confluence is routable: a broken
    # downstream edge or a cycle leaves a PARTIAL chain that must not be routed and
    # mislabeled as reaching the Ottawa confluence — return nothing so the caller skips it.
    return chain if reached_confluence else []


def _receiving_chain(
    receiving_water: str, *, settings: Settings
) -> tuple[list[tuple[NetworkNode, Reach]], ReachTable | None]:
    """The committed reach chain carrying ``receiving_water`` to its confluence, and its table.

    Resolved once per screen: the routed-discharge block (#1298) and the channel-forming /
    conveyance blocks (WS-12 / #1612) must read the *same* chain — the first reach is where the
    outfall enters and the whole chain is what the hydrograph travels. ``([], None)`` when the
    committed topology or reach table is absent.
    """
    from watermark.hydrology import hydrograph_routing  # lazy: hydrograph_routing imports us

    nodes = network.load_topology(settings=settings)
    table = hydrograph_routing.load_reaches(settings=settings)
    if not nodes or table is None:
        return [], table
    return _tributary_reach_chain(nodes, table, receiving_water), table


def _route_campus_outfall(
    post: Hydrograph,
    chain: list[tuple[NetworkNode, Reach]],
    receiving_water: str,
    design_return_period_yr: int,
    *,
    settings: Settings,
) -> RoutedDischarge | None:
    """Route the as-permitted post-development outfall hydrograph down to the confluence (#1298).

    Carries ``post`` (the at-outfall design-storm hydrograph) through the committed
    ``reaches.yaml`` receiving-tributary channel using the constant-parameter Muskingum-Cunge
    primitive, so the receiving-water peak is attenuated and lagged rather than the at-outfall
    peak. Returns ``None`` when the committed topology/reach chain is absent (the screen still
    reports at-outfall peaks). Tier-0 screening on stated reach assumptions.
    """
    if not chain:
        return None

    inflow = np.asarray(post.flows_cfs, dtype=np.float64)
    if inflow.size == 0 or float(inflow.max()) <= 0.0:
        return None
    # Route on the hydrograph's OWN step: the SCS unit-duration rule refines it below 0.1 hr for
    # a short-Tc catchment (#1610), and a mismatched routing dt would silently mis-lag the reach.
    # Read the exact carried step, never `times_hr[0]` — that is rounded for display, and the
    # rounding would propagate into the padding length, the Courant number, and the routed lag.
    dt_hr = post.dt_hr
    headroom = round(_ROUTING_HEADROOM_HR / dt_hr)
    padded = np.concatenate([inflow, np.zeros(headroom, dtype=np.float64)])
    times = np.arange(1, padded.size + 1, dtype=np.float64) * dt_hr

    outflow = padded
    total_len = 0.0
    segments: list[str] = []
    for node, reach in chain:
        outflow = route(
            outflow,
            length_ft=reach.length_ft.value,
            slope=reach.slope.value,
            dt_hr=dt_hr,
            settings=settings,  # hermetic: resolve the Manning default off the passed settings
            **_reach_route_kwargs(reach),
        )
        total_len += reach.length_ft.value
        segments.append(f"{node.id} ({reach.length_ft.value:,.0f} ft @ {reach.slope.value:g})")

    # Attenuation is physics, so compare the RAW series peaks — not the display-rounded
    # ``post.peak_cfs`` (2 sig figs), which would skew the percentage against the raw routed peak.
    at_peak = float(inflow.max())
    at_ttp = post.time_to_peak_hr
    r_idx = int(np.argmax(outflow))
    routed_peak = float(outflow[r_idx])
    routed_ttp = float(times[r_idx])
    atten = round(100.0 * (at_peak - routed_peak) / at_peak, 2) if at_peak else 0.0

    return RoutedDischarge(
        return_period_yr=design_return_period_yr,
        receiving_water=receiving_water,
        reach_path=" -> ".join(segments),
        reach_length_ft=ProvenancedValue.assume(
            round(total_len, 0),
            "ft",
            why=(
                f"total committed {receiving_water} channel length to the Ottawa confluence "
                f"(reaches.yaml: {' + '.join(segments)}); an UPPER bound on outfall->confluence "
                f"travel — the outfall's entry point on {receiving_water} is not in the record"
            ),
        ),
        # Reported peaks right-sized to 2 sig figs (Tier-0 inputs are ~2 sf), matching the
        # DischargePeak scalars; the attenuation above stays on the raw peaks.
        at_outfall_peak_cfs=round_sig(at_peak),
        at_outfall_time_to_peak_hr=round(at_ttp, 3),
        routed_peak_cfs=round_sig(routed_peak),
        routed_time_to_peak_hr=round(routed_ttp, 3),
        attenuation_pct=atten,
        lag_hr=round(routed_ttp - at_ttp, 3),
        method=(
            "Constant-parameter Muskingum-Cunge (watermark.hydrology.solver.routing) of the "
            "as-permitted post-development outfall hydrograph down the committed reaches.yaml "
            f"{receiving_water} channel to the Ottawa confluence; reach length/slope/geometry are "
            "stated Tier-0 assumptions (reaches.yaml), not a calibrated HEC-RAS model."
        ),
    )


def _channel_forming_discharge(
    chain: list[tuple[NetworkNode, Reach]],
    table: ReachTable | None,
    receiving_water: str,
    *,
    settings: Settings,
    live: bool,
) -> ChannelFormingDischarge | None:
    """The receiving channel's bankfull / effective discharge (WS-12 / #1612).

    Runs the **same** Tier-0 SCS chain the campus peaks run on over the receiving tributary's own
    committed subcatchment (``reaches.yaml``) at the cited channel-forming-recurrence design
    storm. Numerator and denominator therefore share the rainfall distribution, the peak factor
    and the Atlas-14 point, so the method's systematic biases largely cancel in the ratio — which
    they cannot do in a peak-to-7Q10 ratio.

    ``None`` — never a substituted figure — when the tributary's headwater carries no committed
    catchment, or no design storm resolves at that recurrence for this site.
    """
    if not chain or table is None:
        return None
    head = chain[0][0]
    catchment = table.catchments.get(head.id)
    if catchment is None:
        return None
    rp = channel_forming_return_period(settings=settings)
    try:
        storm = _resolve_storm(rp, settings=settings, live=live)
    except HydroOfflineError as exc:
        # A site whose Atlas-14 table has no depth at the channel-forming recurrence gets no
        # erosion denominator rather than one borrowed from another recurrence (#1604 discipline).
        log.info("hydro.storm.no_channel_forming_depth", return_period=rp, error=str(exc))
        return None
    depth = storm.depth.value
    hydrograph = simulate_runoff(
        area_acres=catchment.area_acres.value,
        curve_number=catchment.curve_number.value,
        tc_hr=catchment.tc_hr.value,
        storm_depth_in=depth,
        settings=settings,
    )
    return ChannelFormingDischarge(
        receiving_water=receiving_water,
        node_id=head.id,
        return_period_yr=rp,
        storm_depth_in=round(depth, 2),
        discharge=ProvenancedValue.derived(
            hydrograph.peak_cfs,
            "cfs",
            citation=(
                f"Bankfull / effective-discharge surrogate for {receiving_water}: the {rp}-yr "
                f"24-hr ({depth:.2f} in) SCS peak over the committed '{head.id}' subcatchment "
                f"(reaches.yaml — {catchment.area_acres.value:,.0f} ac, CN "
                f"{catchment.curve_number.value:g}, Tc {catchment.tc_hr.value:g} hr), computed by "
                "the same Tier-0 chain as the campus peaks so the two are like-for-like. The "
                "catchment is measured at the mainstem confluence — the largest channel-forming "
                "discharge on this tributary — so a ratio against it is a LOWER bound on what the "
                "channel sees where the outfall actually enters."
            ),
            confidence="low",
        ),
        catchment_area_acres=catchment.area_acres,
        curve_number=catchment.curve_number,
        tc_hr=catchment.tc_hr,
        method=(
            "Tier-0 SCS-CN unit-hydrograph peak at the cited channel-forming recurrence "
            "(tier0-parameters.yaml: bankfull recurs at ~1-2 yr on the annual-maximum series; "
            f"{rp} yr is the conservative — largest-denominator — end of that band) over the "
            "receiving tributary's committed contributing subcatchment. NOT a regional bankfull "
            "regression and NOT a surveyed bankfull cross-section: it inherits the catchment's own "
            "provenance, which for an undelineated tributary is a stated assumption."
        ),
    )


def _reach_conveyance(
    chain: list[tuple[NetworkNode, Reach]],
    channel_forming: ChannelFormingDischarge | None,
    design_peak_cfs: float,
    design_return_period_yr: int,
    receiving_water: str,
    *,
    settings: Settings,
) -> ReachConveyance | None:
    """Normal-depth conveyance of the design peak in the receiving reach's cited section (#1612).

    The check the outfall screen stops short of: past the 60-inch trunk, what depth, velocity and
    boundary shear does the peak run at in the channel it discharges into, against the
    channel-forming (bankfull) flow that channel is adjusted to? Bankfull stage is taken
    self-consistently — the normal depth of the channel-forming discharge in this same section —
    because these reaches carry no surveyed cross-section. ``None`` when no chain or no
    channel-forming discharge resolves.
    """
    if not chain or channel_forming is None:
        return None
    node, reach = chain[0]  # the reach the outfall discharges into
    geometry_source: Literal["reach", "tier0_default"] = (
        "reach"
        if reach.bottom_width_ft is not None or reach.side_slope_z is not None
        else "tier0_default"
    )
    bottom = reach.bottom_width_ft.value if reach.bottom_width_ft else DEFAULT_BOTTOM_WIDTH_FT
    side_z = reach.side_slope_z.value if reach.side_slope_z else DEFAULT_SIDE_SLOPE_Z
    n = reach.manning_n.value if reach.manning_n else default_manning_n(settings=settings)
    slope = reach.slope.value

    def _state(label: str, q: float) -> ChannelFlowState:
        flow = normal_flow(q, slope=slope, manning_n=n, bottom_width_ft=bottom, side_slope_z=side_z)
        return ChannelFlowState(
            label=label,
            discharge_cfs=round_sig(q),
            depth_ft=round(flow.depth_ft, 2),
            top_width_ft=round(flow.top_width_ft, 1),
            velocity_fps=round(flow.velocity_fps, 2),
            shear_stress_psf=round(flow.shear_stress_psf, 3),
        )

    q_bankfull = channel_forming.discharge.value
    bankfull = _state(
        f"bankfull ({channel_forming.return_period_yr}-yr channel-forming)", q_bankfull
    )
    design = _state(f"{design_return_period_yr}-yr post-development peak", design_peak_cfs)
    geometry_note = (
        f"section from reaches.yaml ({bottom:g} ft bottom, {side_z:g}:1 sides, n={n:g})"
        if geometry_source == "reach"
        else (
            f"NO committed cross-section for this reach — the Tier-0 routing default trapezoid "
            f"({bottom:g} ft bottom, {side_z:g}:1 sides, n={n:g}) stands in, so the absolute "
            "depths are a screening bracket and a surveyed section is the upgrade"
        )
    )
    return ReachConveyance(
        node_id=node.id,
        receiving_water=receiving_water,
        slope=slope,
        manning_n=n,
        bottom_width_ft=bottom,
        side_slope_z=side_z,
        geometry_source=geometry_source,
        bankfull=bankfull,
        design=design,
        within_bank=design.depth_ft <= bankfull.depth_ft,
        method=(
            f"Manning normal depth in the '{node.id}' reach at slope {slope:g} ft/ft — "
            f"{geometry_note}. Bankfull stage is taken self-consistently as the normal depth of "
            "the channel-forming discharge in this same section (no surveyed bankfull elevation "
            "exists), so the within-bank verdict reduces to the discharge ratio; what the "
            "velocity and boundary shear (tau = 62.4*R*S) add is the geomorphic work the flow "
            "does, which a discharge ratio cannot express. Uniform flow — no backwater, no bend "
            "or section variation; Tier-0 screening, not a HEC-RAS water-surface profile."
        ),
    )


def screen_campus_discharge(
    *,
    settings: Settings | None = None,
    live: bool = True,
    design_return_period_yr: int = 25,
    return_periods: tuple[int, ...] = _DISCHARGE_RETURN_PERIODS,
) -> CampusDischargeScreen:
    """Screen the campus storm discharge calibrated to the ASWCD-declared footprint.

    Computes the as-permitted composite post CN (only ``impervious_acres`` paved) alongside
    the full-buildout blanket upper bound, the pre/post/full peaks per return period, the
    60-inch outfall's Manning full-flow capacity across an assumed slope band, the receiving
    channel's bankfull / channel-forming discharge with the design peak read against it and a
    normal-depth conveyance check in the cited reach section (WS-12 / #1612), and — for the
    dilution framing only — the design-storm peak relative to Dug Run's cited 7Q10. Requires the
    committed footprint.
    """
    settings = settings or get_settings()
    footprint = load_site_footprint(settings)
    if footprint is None:
        raise FileNotFoundError(f"site footprint not committed: {_footprint_path(settings)}")

    prof = active_profile(settings)
    parcels = _parcels_path(settings)
    acres = geo.parcels_total_acres(parcels, settings=settings)
    hsg = _resolve_hsg(parcels, settings=settings, live=live)

    pre_cn = cn_for(prof.pre_cover, hsg.pre_letter, settings=settings)
    post_parts, breakdown = _post_cover_parts(acres, footprint, hsg, settings=settings)
    post_cn = composite_cn(post_parts)  # composite summary; runoff uses the parts (weighted-runoff)
    # The full-buildout bound develops the WHOLE parcel, so every acre of it — remainder
    # included — sits under the post-development drainage condition.
    full_cn = cn_for(prof.post_cover, hsg.post_letter, settings=settings)

    # Tc shortens with imperviousness: pre is pervious (fraction 0), the as-permitted post
    # runs at its declared impervious share, and the full-buildout bound is blanket-impervious
    # (fraction 1 -> the shortest Tc, the sharpest peak).
    post_imperv_frac = min(footprint.impervious_acres.value, acres) / acres if acres else 0.0
    pre_tc = _scenario_tc_hr(0.0, settings=settings)
    post_tc = _scenario_tc_hr(post_imperv_frac, settings=settings)
    full_tc = _scenario_tc_hr(1.0, settings=settings)

    # The channel-forming recurrence joins the reported set: the pre-vs-post pair AT that
    # frequency is what the channel-protection criterion is read on (WS-12 / #1612), and a screen
    # that only reported 10/25/100-yr peaks could not state it.
    channel_forming_rp = channel_forming_return_period(settings=settings)
    peaks: list[DischargePeak] = []
    design_post: Hydrograph | None = None
    design_post_flat: Hydrograph | None = None
    for rp in sorted({*return_periods, design_return_period_yr, channel_forming_rp}):
        depth = _resolve_storm(rp, settings=settings, live=live).depth.value
        pre = simulate_runoff(
            area_acres=acres,
            curve_number=pre_cn,
            tc_hr=pre_tc,
            storm_depth_in=depth,
            settings=settings,
        )
        post = simulate_runoff(
            area_acres=acres,
            cn_parts=post_parts,
            tc_hr=post_tc,
            storm_depth_in=depth,
            settings=settings,
        )
        if rp == design_return_period_yr:
            design_post = post  # the at-outfall hydrograph routed to the confluence below
            # Terrain sensitivity of the SCS peak factor (WS-10 / #1610): the headline peaks run
            # on the site's resolved factor, but NEH-630 Ch. 16's range spans ~100 to ~600.
            # Recomputed at the published flat/swampy end only to state the bracket in the
            # caveats — it never displaces the reported peak, asserts nothing about this site's
            # terrain, and leaves runoff VOLUME (the detention deficit) untouched.
            design_post_flat = simulate_runoff(
                area_acres=acres,
                cn_parts=post_parts,
                tc_hr=post_tc,
                storm_depth_in=depth,
                settings=settings,
                peak_factor=_FLAT_TERRAIN_PEAK_FACTOR,
            )
        # Conservative wet-antecedent bound: the same as-permitted cover split (and its shorter
        # post Tc) under AMC-III (ground already saturated by prior rain), which raises the peak
        # the 60-inch outfall and Dug Run's low flow have to absorb.
        post_wet = simulate_runoff(
            area_acres=acres,
            cn_parts=post_parts,
            tc_hr=post_tc,
            storm_depth_in=depth,
            amc="III",
            settings=settings,
        )
        full = simulate_runoff(
            area_acres=acres,
            curve_number=full_cn,
            tc_hr=full_tc,
            storm_depth_in=depth,
            settings=settings,
        )
        peaks.append(
            DischargePeak(
                return_period_yr=rp,
                depth_in=round(depth, 2),
                pre_peak_cfs=pre.peak_cfs,
                post_peak_cfs=post.peak_cfs,
                full_buildout_peak_cfs=full.peak_cfs,
                post_peak_wet_cfs=post_wet.peak_cfs,
            )
        )

    diam_ft = footprint.outfall_diameter_in.value / 12.0
    capacity = [
        OutfallCapacity(
            slope_pct=s, capacity_cfs=round(manning_full_pipe_cfs(diam_ft, s / 100.0), 1)
        )
        for s in _OUTFALL_SLOPES_PCT
    ]

    resolved_peak_factor = solver_peak_factor(settings=settings)
    seven_q10 = low_flow_for(footprint.receiving_water, settings=settings)
    ctx = low_flow_context(footprint.receiving_water, settings=settings)
    design_peak = next((p for p in peaks if p.return_period_yr == design_return_period_yr), None)
    ratio: float | None = None
    if seven_q10 and seven_q10.value > 0 and design_peak is not None:
        ratio = round(design_peak.post_peak_cfs / seven_q10.value)

    note = (
        f"{footprint.receiving_water}: cited 7Q10 {seven_q10.value:g} cfs"
        if seven_q10
        else f"{footprint.receiving_water}: no cited 7Q10"
    )
    if ctx.get("designated_use"):
        note += f"; {ctx['designated_use']}"
    note += (
        "; also receives the American II WWTP outfall (NPDES 2PH00006) at a cited dilution "
        "violation. The peak-to-7Q10 multiple is the LOW-FLOW framing — it says the storm "
        "arrives on a stream that at design low flow is effluent, and it belongs with the "
        "dilution finding, not with channel stability: a storm peak is hundreds of times any "
        "small stream's 7Q10 almost by construction. The erosion signal is the channel-forming "
        "(bankfull) comparison and the reach conveyance check (WS-12 / #1612) — corroborated by "
        "the 2026-06-05 'check the outlet ... not releasing sediment' inspection note."
    )

    # The committed reach chain, resolved ONCE: the routed-discharge block and the
    # channel-forming / conveyance blocks must read the same chain (its first reach is where the
    # outfall enters; the whole chain is what the hydrograph travels).
    chain, reach_table = _receiving_chain(footprint.receiving_water, settings=settings)

    # Route the at-outfall design-storm hydrograph down the receiving tributary to its Ottawa
    # confluence (#1298): the receiving-water peak reflects reach travel — attenuated + lagged —
    # not the at-outfall peak. Supplements (never softens) the at-outfall erosion signal.
    routed = (
        _route_campus_outfall(
            design_post,
            chain,
            footprint.receiving_water,
            design_return_period_yr,
            settings=settings,
        )
        if design_post is not None
        else None
    )

    # WS-12 / #1612 — the erosion denominator. Channel stability is set by the channel-forming
    # (bankfull / effective) discharge, not by the 7-day 10-year LOW flow, so the erosion signal
    # is anchored here and the conveyance check carries it into the receiving channel's section.
    channel_forming = _channel_forming_discharge(
        chain, reach_table, footprint.receiving_water, settings=settings, live=live
    )
    cf_ratio: float | None = None
    if channel_forming is not None and channel_forming.discharge.value > 0 and design_peak:
        cf_ratio = round(design_peak.post_peak_cfs / channel_forming.discharge.value, 2)
    conveyance = (
        _reach_conveyance(
            chain,
            channel_forming,
            design_peak.post_peak_cfs,
            design_return_period_yr,
            footprint.receiving_water,
            settings=settings,
        )
        if design_peak is not None
        else None
    )

    return CampusDischargeScreen(
        site=footprint.site,
        footprint_area=ProvenancedValue.from_document(
            round(acres, 1),
            "acre",
            citation=f"{parcels.name} (recorded Bistrozzi parcel footprints)",
        ),
        impervious_acres=footprint.impervious_acres,
        developed_acres=footprint.developed_acres,
        hsg=hsg.pre_hsg,
        hsg_drainage=hsg,
        pre_cn=round(pre_cn, 1),
        post_cn_as_permitted=round(post_cn, 1),
        post_cn_full_buildout=round(full_cn, 1),
        cover_breakdown=breakdown,
        peaks=peaks,
        design_return_period_yr=design_return_period_yr,
        outfall_diameter_in=footprint.outfall_diameter_in,
        manning_n=_OUTFALL_MANNING_N,
        outfall_capacity=capacity,
        receiving_water=footprint.receiving_water,
        receiving_7q10=seven_q10,
        receiving_note=note,
        peak_to_7q10_ratio=ratio,
        channel_forming=channel_forming,
        peak_to_channel_forming_ratio=cf_ratio,
        reach_conveyance=conveyance,
        detention_design_shown=footprint.detention_design_shown,
        routed_discharge=routed,
        basin_chronology_note=(
            "The 95% SPS grading sheet shows NO detention/retention storage "
            "(lma1a.storm-inventory.yaml); the ESC inspections show basins under construction "
            "by 2026-06-05 (topsoil on main-basin slopes; a temporary SW basin started) — field "
            "storage appearing after the 95% design. Undetained, the post-development peak "
            "discharges straight to the 60-inch outfall."
        ),
        method=(
            "Tier-0 SCS-CN screening over the measured parcel footprint; the dominant "
            f"hydrologic soil group {hsg.group} is resolved per scenario to HSG "
            f"{hsg.pre_letter} pre-development ({hsg.pre_condition}) and HSG {hsg.post_letter} "
            f"on developed post-development ground ({hsg.post_condition}) — an explicit "
            "drainage-condition switch, see caveats; post-development "
            "runoff uses the TR-55 weighted-runoff method (each ASWCD-declared cover's CN run "
            "separately over the impervious/developed-pervious/undeveloped split, runoff depths "
            "area-weighted; the reported post CN is the area-weighted composite summary) — "
            "compositing a single CN under-predicts runoff once the ~34% impervious footprint "
            "passes TR-55's ~30% directly-connected threshold; "
            f"time of concentration shortens with imperviousness (pre {pre_tc:g} hr -> "
            f"as-permitted {post_tc:g} hr -> full-buildout {full_tc:g} hr); "
            "peaks are AMC-II (average antecedent moisture) with a wet-antecedent (AMC-III) "
            "conservative bound on the as-permitted post peak; the design rainfall is the NRCS "
            "Type-II 24-hr distribution built at its published 6-minute resolution (NEH-630 "
            "Ch. 4 630.0407) and the unit hydrograph runs at the SCS unit duration "
            f"D <= 0.133*Tc on the peak factor {resolved_peak_factor:g}; outfall capacity = Manning "
            "full-flow (n=0.013) across an assumed slope band. "
            "The EROSION signal is anchored to the receiving channel's channel-forming (bankfull "
            f"/ {channel_forming_rp}-yr) discharge, not to the 7Q10: `channel_forming` runs this "
            "same SCS chain over the receiving tributary's committed contributing subcatchment "
            "(reaches.yaml) so numerator and denominator share the method, and `reach_conveyance` "
            "carries the design peak into that reach's cited section as Manning normal depth "
            "(depth / velocity / boundary shear vs the bankfull flow). The cited 7Q10 (OEPA NPDES "
            "fact sheet 2PH00006) is retained for the LOW-FLOW / dilution framing only. The "
            "receiving-water peak is additionally routed down the cited reach chain to the Ottawa "
            "confluence (Tier-0 Muskingum-Cunge; see routed_discharge) so it reflects reach "
            "travel, not only the at-outfall peak."
        ),
        caveats=[
            "Screening-grade — the receiving-water peak is a Tier-0 Muskingum-Cunge reach route "
            "on stated reach assumptions (reaches.yaml), not a calibrated HEC-RAS model or a "
            "permit determination; the pre/post/full peaks are at-outfall SCS-CN screening.",
            "Headline peaks are AMC-II; post_peak_wet_cfs is the AMC-III (wet-antecedent) "
            "upper bound — the storm falling on ground already saturated by prior rain.",
            "The outfall pipe slope is not in the record; capacity is bracketed across 0.3-1.0%.",
            "The peak is computed over the whole measured footprint; the tributary area to the "
            "single 60-inch trunk is not stated, so the capacity comparison is a bracket.",
            "The post cover split treats the developed-pervious remainder as graded open space "
            "and the undeveloped remainder as keeping prior cropland cover.",
            "Post-development runoff uses the TR-55 weighted-runoff method (runoff computed per "
            "cover, then area-weighted on depths). Because runoff is convex in CN, this yields "
            "more runoff volume than applying the single composite post CN — the detention-deficit "
            "understatement compositing hides. The volume gap is largest for small/frequent storms "
            "(the impervious fraction runs off while the pervious fraction still abstracts) and "
            "narrows as the design storm grows; the peak, which also depends on how the mixed cover "
            "redistributes excess in time, shifts only marginally at the design and rarer storms.",
            "The outfall's entry point on the receiving tributary is not in the record, so the "
            "routed channel length is an upper bound on travel — the routed attenuation/lag are "
            "upper bounds and the confluence peak a lower bound; reaches between the outfall and "
            "the confluence see intermediate, larger peaks (the unattenuated at-outfall peak is "
            "what the channel-forming comparison is read on, and this routing does not soften it).",
            "The peak-to-7Q10 multiple is the LOW-FLOW / dilution framing, NOT the erosion one "
            "(WS-12 / #1612). Channel stability is governed by the channel-forming (bankfull, "
            "effective) discharge — a moderate flow recurring at ~1-2 yr — while the 7Q10 is a "
            "7-day 10-year LOW flow: their ratio runs to the hundreds for any flashy outfall on "
            "any small stream and maps to no geomorphic threshold. The erosion claim now rests on "
            "`channel_forming` / `peak_to_channel_forming_ratio` and on the pre-vs-post pair at "
            "the channel-forming recurrence.",
            *_channel_forming_caveats(channel_forming, conveyance),
            _peak_factor_caveat(
                resolved_peak_factor, prof.uh_peak_factor, design_post, design_post_flat
            ),
            _drainage_condition_caveat(hsg, acres, footprint, settings=settings),
        ],
    )


def _channel_forming_caveats(
    channel_forming: ChannelFormingDischarge | None, conveyance: ReachConveyance | None
) -> list[str]:
    """What the re-anchored erosion signal rests on — and which way each assumption pushes it.

    Two things a reviewer must be handed: the denominator is not a surveyed bankfull discharge
    (it inherits the committed catchment's own provenance, which for an undelineated tributary is
    a low-confidence assumption), and the reach section it is turned into hydraulics on may be
    the Tier-0 default trapezoid rather than a survey. Both are stated with their **direction**
    where the direction is knowable, rather than as generic hedges.
    """
    if channel_forming is None:
        return [
            "No channel-forming (bankfull) discharge resolves for the receiving water — its "
            "tributary has no committed contributing subcatchment or reach chain, or no design "
            "storm at the channel-forming recurrence. The erosion signal is therefore NOT "
            "quantified here; the peak-to-7Q10 multiple is a low-flow statistic and does not "
            "stand in for it. Committing a delineated catchment for the receiving tributary is "
            "the unlock (WS-12 / #1612)."
        ]
    cf = channel_forming
    area = cf.catchment_area_acres
    out = [
        f"The erosion denominator — {cf.receiving_water}'s channel-forming discharge, "
        f"{cf.discharge.value:,.0f} cfs — is a SURROGATE, not a survey: the {cf.return_period_yr}-yr "
        f"SCS peak over the committed '{cf.node_id}' subcatchment "
        f"({area.value:,.0f} ac, source: {area.source}, confidence: {area.confidence}). It moves "
        "with that catchment, so a committed delineation (or a regional bankfull regression / a "
        "surveyed cross-section) would sharpen it. Two knowable directions: the recurrence is "
        "pinned at the CONSERVATIVE end of the published 1-2 yr bankfull band, which maximizes "
        "the denominator and so understates every ratio against it; and the catchment is taken "
        "at the mainstem confluence — the largest channel-forming discharge on this tributary — "
        "while the outfall enters somewhere above it, on a smaller local drainage area, so the "
        "reported ratio is a LOWER bound on what the channel sees at the discharge point."
    ]
    if conveyance is not None and conveyance.geometry_source == "tier0_default":
        out.append(
            f"The '{conveyance.node_id}' reach carries NO committed cross-section, so the "
            f"conveyance check runs on the Tier-0 routing default trapezoid "
            f"({conveyance.bottom_width_ft:g} ft bottom, {conveyance.side_slope_z:g}:1 sides, "
            f"n={conveyance.manning_n:g}) — the same section the Muskingum-Cunge routing uses. "
            "Its absolute depths are a screening bracket, not a stage prediction (a "
            f"{conveyance.bankfull.depth_ft:g}-ft bankfull depth on a small tributary is a sign of "
            "the section being too small for the committed catchment, not a finding about the "
            "channel). Because bankfull stage is taken self-consistently in that same section, "
            "the within-bank verdict is geometry-free; the velocity and shear are not, and a "
            "surveyed cross-section is the upgrade."
        )
    return out


def _drainage_condition_caveat(
    hsg: HsgDrainageBasis,
    acres: float,
    footprint: SiteFootprint,
    *,
    settings: Settings,
) -> str:
    """State the dual-HSG drainage switch and bracket the composite CN it produced.

    The screen picks one condition per scenario; this says which, why, and — the part a
    reviewer actually needs — what the *other* choices would have given on this footprint's
    own numbers. Both ends are recomputed with the same cover split, so the bracket is the
    switch's sensitivity alone, not a second model.
    """
    if not hsg.dual:
        exposure = (
            f" {hsg.dual_fraction:.0%} of the sampled footprint is nonetheless rated into a "
            "dual group, and that share runs a full class wetter undrained."
            if hsg.dual_fraction
            else ""
        )
        return (
            f"Hydrologic soil group {hsg.group} is a single class, so the drained/undrained "
            f"dual-group switch does not bind here: both scenarios run HSG {hsg.pre_letter}."
            + exposure
        )

    def _composite(condition: DrainageCondition) -> float:
        pinned = hsg.model_copy(update={"pre_condition": condition, "post_condition": condition})
        parts, _ = _post_cover_parts(acres, footprint, pinned, settings=settings)
        return composite_cn(parts)

    as_modeled = composite_cn(_post_cover_parts(acres, footprint, hsg, settings=settings)[0])
    return (
        f"SSURGO rates this footprint into the DUAL group {hsg.group}"
        + (f" over {hsg.dual_fraction:.0%} of the sampled points" if hsg.dual_fraction else "")
        + f", whose two letters are two drainage conditions of the same soil, not a spelling. "
        f"{DUAL_HSG_RULE} This screen runs pre-development on HSG {hsg.pre_letter} "
        f"({hsg.pre_condition}) and developed post-development ground on HSG {hsg.post_letter} "
        f"({hsg.post_condition}) — a stated modeling switch, not a survey finding. It is the "
        f"single largest soils assumption in the post CN: the same cover split gives composite "
        f"CN {_composite('drained'):.1f} if every acre stayed drained and "
        f"{_composite('undrained'):.1f} if every acre — including the undeveloped remainder, "
        f"which this screen keeps farmed and tiled — went undrained, against the "
        f"{as_modeled:.1f} reported. Whether this specific field's tile survives construction "
        "is not in the record; a drainage plan that showed it would move the number within "
        "that bracket."
    )


def _peak_factor_caveat(
    resolved: float,
    profile_factor: float | None,
    design_post: Hydrograph | None,
    design_post_flat: Hydrograph | None,
) -> str:
    """The SCS peak factor's terrain sensitivity, stated on the design storm's own numbers.

    Site-generic by construction: it names the *published* NEH-630 range and where the resolved
    factor came from, and never asserts what THIS site's terrain is. Claiming a landform (and so
    which end of the range applies) is a cited, reviewed `SiteProfile.uh_peak_factor` edit — a
    screen that asserted it for every site would be fabricating terrain for the peers.
    """
    origin = (
        f"declared for this site on `SiteProfile.uh_peak_factor` ({profile_factor:g})"
        if profile_factor is not None
        else "the cited standard-hydrograph default; no per-site factor is declared on "
        "`SiteProfile.uh_peak_factor`"
    )
    base = (
        f"Peaks run on the SCS unit-hydrograph peak factor {resolved:g} — {origin}. The factor is "
        "a TERRAIN property, not a universal constant: NEH-630 Ch. 16 spans ~100 (wetland "
        f"storage) through {_FLAT_TERRAIN_PEAK_FACTOR:g} (flat/swampy) to ~600 (steep). The "
        f"published flat end, {_FLAT_TERRAIN_PEAK_FACTOR:g}"
    )
    if design_post is not None and design_post_flat is not None and design_post.peak_cfs:
        drop = 100.0 * (1.0 - design_post_flat.peak_cfs / design_post.peak_cfs)
        base += (
            f", would put the design-storm post-development peak at "
            f"{design_post_flat.peak_cfs:,.0f} cfs instead of {design_post.peak_cfs:,.0f} "
            f"(~{drop:.0f}% lower)"
        )
    else:
        base += " would lower the peak substantially"
    return (
        base + ". Runoff VOLUME — and so the detention deficit — is unchanged by the peak factor; "
        "only the rate is. This is the published sensitivity BRACKET around the resolved factor, "
        "not a correction to it: moving a site off its resolved factor needs a calibrated or "
        "cited terrain basis for that catchment, recorded on the profile."
    )


def _erosion_findings(screen: CampusDischargeScreen) -> list[HydroFinding]:
    """The re-anchored channel-stability findings (WS-12 / #1612).

    Three, in the order a reviewer needs them:

    ``channel-protection`` — the standard threshold. Pre vs post peak **at the channel-forming
    recurrence**, off the same footprint: a post-development peak above the pre-development one
    at the frequency the channel is adjusted to is the mechanism by which urbanization enlarges
    a receiving channel. Same method, same footprint, same storm on both sides — nothing to
    argue with but the model.

    ``channel-forming-peak`` — the magnitude. The design-storm peak as a fraction of the
    receiving channel's own bankfull / effective discharge, the denominator the 7Q10 was standing
    in for. A LOWER bound (see the caveat: the denominator is taken at the tributary's
    confluence, downstream of where the outfall enters).

    ``receiving-channel-conveyance`` — the hydraulics. Normal depth, velocity and boundary shear
    at the cited reach section, against the bankfull flow — the conveyance question the 60-inch
    pipe screen stops short of.
    """
    findings: list[HydroFinding] = []
    cf = screen.channel_forming
    cfp = screen.channel_forming_peak
    if cf is not None and cfp is not None:
        bump = (
            100.0 * (cfp.post_peak_cfs - cfp.pre_peak_cfs) / cfp.pre_peak_cfs
            if cfp.pre_peak_cfs
            else 0.0
        )
        findings.append(
            HydroFinding(
                subject="campus stormwater discharge",
                check="channel-protection",
                ok=cfp.post_peak_cfs <= cfp.pre_peak_cfs,
                detail=(
                    f"{cf.return_period_yr}-yr 24-hr storm ({cfp.depth_in:.2f} in) — the "
                    f"channel-forming frequency: peak {cfp.pre_peak_cfs:,.0f} -> "
                    f"{cfp.post_peak_cfs:,.0f} cfs ({bump:+.0f}%) off the same footprint, "
                    "undetained. The channel-protection criterion is post <= pre at this "
                    "recurrence; it is the frequent flows, not the design storm, that do the "
                    "channel-forming work"
                ),
            )
        )
    dp = screen.design_peak
    if cf is not None and screen.peak_to_channel_forming_ratio is not None and dp is not None:
        findings.append(
            HydroFinding(
                subject=f"{cf.receiving_water} channel-forming discharge",
                check="channel-forming-peak",
                ok=screen.peak_to_channel_forming_ratio <= 1.0,
                detail=(
                    f"{screen.design_return_period_yr}-yr post-dev peak {dp.post_peak_cfs:,.0f} "
                    f"cfs is {screen.peak_to_channel_forming_ratio:.2f}x "
                    f"{cf.receiving_water}'s channel-forming ({cf.return_period_yr}-yr bankfull) "
                    f"discharge {cf.discharge.value:,.0f} cfs [derived, {cf.node_id} subcatchment]"
                    " — a LOWER bound: the denominator is taken at the mainstem confluence, "
                    "downstream of wherever the outfall enters"
                ),
            )
        )
    rc = screen.reach_conveyance
    if rc is not None:
        shear = rc.shear_ratio
        findings.append(
            HydroFinding(
                subject=f"{rc.receiving_water} reach {rc.node_id} (conveyance)",
                check="receiving-channel-conveyance",
                ok=rc.within_bank,
                detail=(
                    f"{rc.design.label} {rc.design.discharge_cfs:,.0f} cfs runs "
                    f"{rc.design.depth_ft:g} ft deep at {rc.design.velocity_fps:g} ft/s "
                    f"(tau {rc.design.shear_stress_psf:g} lb/ft2) vs bankfull "
                    f"{rc.bankfull.discharge_cfs:,.0f} cfs at {rc.bankfull.depth_ft:g} ft / "
                    f"{rc.bankfull.velocity_fps:g} ft/s (tau {rc.bankfull.shear_stress_psf:g})"
                    + (f" — {shear:.2f}x the bankfull boundary shear" if shear else "")
                    + (
                        "; Tier-0 default section, no committed cross-section"
                        if rc.geometry_source == "tier0_default"
                        else "; section from reaches.yaml"
                    )
                ),
            )
        )
    return findings


def discharge_findings(screen: CampusDischargeScreen) -> list[HydroFinding]:
    """Screening findings from a :class:`CampusDischargeScreen`."""
    findings: list[HydroFinding] = []
    dp = screen.design_peak
    rp = screen.design_return_period_yr
    mid = screen.capacity_at(0.5)
    lo, hi = screen.capacity_at(0.3), screen.capacity_at(1.0)
    if dp is not None and mid is not None and lo is not None and hi is not None:
        findings.append(
            HydroFinding(
                subject=f"{screen.outfall_diameter_in.value:.0f}-in storm outfall",
                check="outfall-capacity",
                ok=mid >= dp.post_peak_cfs,
                detail=(
                    f"{rp}-yr post-dev peak {dp.post_peak_cfs:,.0f} cfs vs 60-in full-flow "
                    f"capacity {mid:,.0f} cfs @ 0.5% (range {lo:,.0f}-{hi:,.0f} cfs @ 0.3-1.0%)"
                ),
            )
        )
    findings.extend(_erosion_findings(screen))
    if dp is not None and screen.peak_to_7q10_ratio is not None and screen.receiving_7q10:
        findings.append(
            HydroFinding(
                subject=screen.receiving_water,
                check="receiving-water-peak",
                # The stream this peak lands on has, at design low flow, essentially no water of
                # its own — that is the finding, and it is about DILUTION. The ratio itself is not
                # a channel-stability threshold (WS-12 / #1612): see `channel-forming-peak`.
                ok=False,
                detail=(
                    f"{rp}-yr post-dev peak {dp.post_peak_cfs:,.0f} cfs is "
                    f"~{screen.peak_to_7q10_ratio:,.0f}x {screen.receiving_water}'s cited 7Q10 "
                    f"{screen.receiving_7q10.value:g} cfs — the LOW-FLOW framing (a storm surge "
                    "onto a stream that at design low flow is effluent, not stream); the erosion "
                    "signal is the channel-forming comparison, not this ratio"
                ),
            )
        )
    rd = screen.routed_discharge
    if rd is not None:
        findings.append(
            HydroFinding(
                subject=f"{rd.receiving_water} receiving-water peak (routed)",
                check="routed-receiving-peak",
                ok=rd.attenuation_pct >= 0.0,
                detail=(
                    f"{rd.return_period_yr}-yr outfall hydrograph routed {rd.reach_length_ft.value:,.0f} "
                    f"ft down {rd.receiving_water} to the Ottawa confluence: peak "
                    f"{rd.at_outfall_peak_cfs:,.0f} cfs at the 60-in outfall -> {rd.routed_peak_cfs:,.0f} "
                    f"cfs at the confluence ({rd.attenuation_pct:g}% attenuated, lagged {rd.lag_hr:g} hr) "
                    "— Tier-0 Muskingum-Cunge, an upper bound on reach travel (reaches above the "
                    "confluence see intermediate, larger peaks)"
                ),
            )
        )
    findings.append(
        HydroFinding(
            subject="campus stormwater design",
            check="detention-design",
            ok=screen.detention_design_shown,
            detail=(
                "no detention/retention storage in the 95% SPS grading sheet; ESC inspections "
                "show basins under construction by 2026-06-05 (as-built storage post-dates design)"
            ),
        )
    )
    if dp is not None:
        findings.append(
            HydroFinding(
                subject="post-development CN (ASWCD-calibrated)",
                check="impervious-calibration",
                ok=True,
                detail=(
                    f"composite CN {screen.post_cn_as_permitted:g} ({screen.cover_breakdown}) vs "
                    f"pre {screen.pre_cn:g}; full-buildout bound CN {screen.post_cn_full_buildout:g}. "
                    f"{rp}-yr peak pre {dp.pre_peak_cfs:,.0f} -> as-permitted {dp.post_peak_cfs:,.0f} "
                    f"-> full-buildout {dp.full_buildout_peak_cfs:,.0f} cfs"
                    + (
                        f" (as-permitted wet-antecedent AMC-III bound {dp.post_peak_wet_cfs:,.0f} cfs)"
                        if dp.post_peak_wet_cfs is not None
                        else ""
                    )
                ),
            )
        )
    return findings


def write_discharge_screen(
    screen: CampusDischargeScreen, *, settings: Settings | None = None
) -> Path:
    """Write the committed discharge-screen artifact and return its path."""
    settings = settings or get_settings()
    path = _discharge_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = screen.model_dump(mode="json", exclude_none=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_discharge_screen(settings: Settings | None = None) -> CampusDischargeScreen | None:
    """Read the committed discharge-screen artifact, or ``None`` if uncommitted."""
    settings = settings or get_settings()
    path = _discharge_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CampusDischargeScreen.model_validate(data)
