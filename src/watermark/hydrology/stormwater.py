"""Pre- vs post-development stormwater runoff for the data-center campus.

The stormwater impact of the decision to pave the corridor: the same NOAA Atlas-14
design storm yields far more runoff off impervious ground than off the cropland it
replaces. We compute both Tier-0 SCS hydrographs and report the peak/volume increase
and the screening detention deficit — the classic "post-development must not exceed
pre-development peak" stormwater test.

Grounding: the footprint area is document-sourced (the recorded Bistrozzi parcels);
the design storm and the hydrologic soil group are connector-sourced (NOAA Atlas-14;
USDA SSURGO via SDA, the footprint's grid-sampled dominant HSG), each falling back to a
cited value offline (HSG -> the "C" assumption). Land cover is a cited assumption (prior
use "Neff Farms" -> cropland). Curve numbers come from the cited TR-55 table.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TypedDict

import numpy as np
import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology import geo, network
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.hydrology.connectors.noaa_atlas14 import design_storm
from watermark.hydrology.connectors.ssurgo import SsurgoError, dominant_hsg
from watermark.hydrology.lowflow import low_flow_context, low_flow_for
from watermark.hydrology.model import (
    CampusDischargeScreen,
    DesignStorm,
    DischargePeak,
    HydroFinding,
    Hydrograph,
    NetworkNode,
    OutfallCapacity,
    ProvenancedValue,
    Reach,
    ReachTable,
    RoutedDischarge,
    SiteFootprint,
    StormRunoff,
)
from watermark.hydrology.solver.curve_number import cn_for, composite_cn
from watermark.hydrology.solver.routing import route
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
    hsg_letter: str,
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
    """
    prof = active_profile(settings)
    imperv = max(0.0, min(footprint.impervious_acres.value, total_acres))
    developed = max(0.0, min(footprint.developed_acres.value, total_acres))
    dev_pervious = max(0.0, developed - imperv)
    remainder = max(0.0, total_acres - imperv - dev_pervious)
    parts = [
        (imperv, cn_for(prof.post_cover, hsg_letter, settings=settings)),
        (dev_pervious, cn_for(prof.developed_pervious_cover, hsg_letter, settings=settings)),
        (remainder, cn_for(prof.pre_cover, hsg_letter, settings=settings)),
    ]
    breakdown = (
        f"{imperv:.0f} ac impervious + {dev_pervious:.0f} ac developed-pervious + "
        f"{remainder:.0f} ac undeveloped (of {total_acres:.0f} ac)"
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
    hsg_letter, hsg = _resolve_hsg(path, settings=settings, live=live)

    storm = _resolve_storm(return_period_yr, settings=settings, live=live)

    pre_cn = cn_for(prof.pre_cover, hsg_letter, settings=settings)
    # Calibrate the post-development cover to the ASWCD-declared footprint when committed:
    # only ~115 of ~344 ac is permanently impervious, so the post runoff is the TR-55
    # weighted-runoff of the impervious/developed-pervious/undeveloped split (each cover's CN
    # run separately, runoff depths area-weighted; post_cn is the composite summary), not a
    # blanket near-impervious value over the whole parcel. Falls back to the blanket
    # near-impervious cover (the full-buildout bound) if the footprint is absent.
    footprint = load_site_footprint(settings)
    post_parts: list[tuple[float, float]] | None
    if footprint is not None:
        post_parts, _ = _post_cover_parts(acres, footprint, hsg_letter, settings=settings)
        post_cn = composite_cn(post_parts)
        post_imperv_frac = min(footprint.impervious_acres.value, acres) / acres if acres else 0.0
    else:
        post_parts = None
        post_cn = cn_for(prof.post_cover, hsg_letter, settings=settings)
        post_imperv_frac = 1.0  # blanket near-impervious buildout — the shortest Tc
    depth = storm.depth.value
    # Pre-development is fully pervious (impervious fraction 0 -> the longest Tc); the post
    # scenario's shorter Tc scales with its impervious fraction, sharpening the post peak.
    pre_tc = _scenario_tc_hr(0.0, settings=settings)
    post_tc = _scenario_tc_hr(post_imperv_frac, settings=settings)
    pre = simulate_runoff(area_acres=acres, curve_number=pre_cn, tc_hr=pre_tc, storm_depth_in=depth)
    if post_parts is not None:
        post = simulate_runoff(
            area_acres=acres, cn_parts=post_parts, tc_hr=post_tc, storm_depth_in=depth
        )
    else:
        post = simulate_runoff(
            area_acres=acres, curve_number=post_cn, tc_hr=post_tc, storm_depth_in=depth
        )

    runoff = StormRunoff(
        name="BOSC data-center campus", area=area, hsg=hsg, storm=storm, pre=pre, post=post
    )
    log.info(
        "hydro.storm",
        acres=round(acres, 1),
        pre_cn=pre_cn,
        post_cn=post_cn,
        depth_in=depth,
        peak_increase=round(runoff.peak_increase_cfs, 1),
    )
    return runoff, _storm_findings(runoff)


def _resolve_hsg(
    footprint_path: Path, *, settings: Settings, live: bool
) -> tuple[str, ProvenancedValue]:
    """Dominant HSG over the footprint from SSURGO (live), else the cited "C" assumption.

    Returns ``(letter, code)`` where ``letter`` is the single A-D group fed to ``cn_for``
    (a dual group like "B/D" resolves to its drained first letter — the tile-drained
    lake-plain / engineered-drainage case) and ``code`` is the 1-4 HSG index, provenance
    tagged ``connector`` when sourced live, ``assumption`` on the offline fallback.
    """
    if live:
        try:
            survey = dominant_hsg(footprint_path, settings=settings)
            letter = survey.hsg_letter
            shares = ", ".join(f"{d.hsg} {d.fraction:.0%}" for d in survey.distribution)
            code = ProvenancedValue.from_connector(
                float("ABCD".index(letter) + 1),
                "hsg_code",
                citation=(
                    f"SSURGO dominant HSG {survey.dominant_hsg} ({shares}) over "
                    f"{survey.n_points} footprint grid points — {survey.source}"
                ),
            )
            return letter, code
        except (HydroOfflineError, SsurgoError) as exc:
            log.info("hydro.storm.hsg_fallback", error=str(exc).splitlines()[0])
    prof = active_profile(settings)
    code = ProvenancedValue.assume(
        float("ABCD".index(prof.dominant_hsg) + 1), "hsg_code", why=prof.hsg_citation
    )
    return prof.dominant_hsg, code


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
# capacity, and the storm peak vs Dug Run's cited 7Q10.
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
_ROUTING_DT_HR = 0.1


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


def _route_campus_outfall(
    post: Hydrograph,
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
    from watermark.hydrology import hydrograph_routing  # lazy: hydrograph_routing imports us

    nodes = network.load_topology(settings=settings)
    table = hydrograph_routing.load_reaches(settings=settings)
    if not nodes or table is None:
        return None
    chain = _tributary_reach_chain(nodes, table, receiving_water)
    if not chain:
        return None

    inflow = np.asarray(post.flows_cfs, dtype=np.float64)
    if inflow.size == 0 or float(inflow.max()) <= 0.0:
        return None
    headroom = round(_ROUTING_HEADROOM_HR / _ROUTING_DT_HR)
    padded = np.concatenate([inflow, np.zeros(headroom, dtype=np.float64)])
    times = np.arange(1, padded.size + 1, dtype=np.float64) * _ROUTING_DT_HR

    outflow = padded
    total_len = 0.0
    segments: list[str] = []
    for node, reach in chain:
        outflow = route(
            outflow,
            length_ft=reach.length_ft.value,
            slope=reach.slope.value,
            dt_hr=_ROUTING_DT_HR,
            **_reach_route_kwargs(reach),
        )
        total_len += reach.length_ft.value
        segments.append(f"{node.id} ({reach.length_ft.value:,.0f} ft @ {reach.slope.value:g})")

    at_peak = post.peak_cfs
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
        at_outfall_peak_cfs=round(at_peak, 3),
        at_outfall_time_to_peak_hr=round(at_ttp, 3),
        routed_peak_cfs=round(routed_peak, 3),
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
    60-inch outfall's Manning full-flow capacity across an assumed slope band, and the
    design-storm peak relative to Dug Run's cited 7Q10. Requires the committed footprint.
    """
    settings = settings or get_settings()
    footprint = load_site_footprint(settings)
    if footprint is None:
        raise FileNotFoundError(f"site footprint not committed: {_footprint_path(settings)}")

    prof = active_profile(settings)
    parcels = _parcels_path(settings)
    acres = geo.parcels_total_acres(parcels, settings=settings)
    hsg_letter, hsg = _resolve_hsg(parcels, settings=settings, live=live)

    pre_cn = cn_for(prof.pre_cover, hsg_letter, settings=settings)
    post_parts, breakdown = _post_cover_parts(acres, footprint, hsg_letter, settings=settings)
    post_cn = composite_cn(post_parts)  # composite summary; runoff uses the parts (weighted-runoff)
    full_cn = cn_for(prof.post_cover, hsg_letter, settings=settings)

    # Tc shortens with imperviousness: pre is pervious (fraction 0), the as-permitted post
    # runs at its declared impervious share, and the full-buildout bound is blanket-impervious
    # (fraction 1 -> the shortest Tc, the sharpest peak).
    post_imperv_frac = min(footprint.impervious_acres.value, acres) / acres if acres else 0.0
    pre_tc = _scenario_tc_hr(0.0, settings=settings)
    post_tc = _scenario_tc_hr(post_imperv_frac, settings=settings)
    full_tc = _scenario_tc_hr(1.0, settings=settings)

    peaks: list[DischargePeak] = []
    design_post: Hydrograph | None = None
    for rp in sorted({*return_periods, design_return_period_yr}):
        depth = _resolve_storm(rp, settings=settings, live=live).depth.value
        pre = simulate_runoff(
            area_acres=acres, curve_number=pre_cn, tc_hr=pre_tc, storm_depth_in=depth
        )
        post = simulate_runoff(
            area_acres=acres, cn_parts=post_parts, tc_hr=post_tc, storm_depth_in=depth
        )
        if rp == design_return_period_yr:
            design_post = post  # the at-outfall hydrograph routed to the confluence below
        # Conservative wet-antecedent bound: the same as-permitted cover split (and its shorter
        # post Tc) under AMC-III (ground already saturated by prior rain), which raises the peak
        # the 60-inch outfall and Dug Run's low flow have to absorb.
        post_wet = simulate_runoff(
            area_acres=acres, cn_parts=post_parts, tc_hr=post_tc, storm_depth_in=depth, amc="III"
        )
        full = simulate_runoff(
            area_acres=acres, curve_number=full_cn, tc_hr=full_tc, storm_depth_in=depth
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
        "violation. A storm peak many times the design low flow is a channel-stability / "
        "erosion signal — corroborated by the 2026-06-05 'check the outlet ... not releasing "
        "sediment' inspection note — distinct from continuous-effluent dilution."
    )

    # Route the at-outfall design-storm hydrograph down the receiving tributary to its Ottawa
    # confluence (#1298): the receiving-water peak reflects reach travel — attenuated + lagged —
    # not the at-outfall peak. Supplements (never softens) the at-outfall peak-to-7Q10 signal.
    routed = (
        _route_campus_outfall(
            design_post, footprint.receiving_water, design_return_period_yr, settings=settings
        )
        if design_post is not None
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
        hsg=hsg,
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
            "Tier-0 SCS-CN screening over the measured parcel footprint; post-development "
            "runoff uses the TR-55 weighted-runoff method (each ASWCD-declared cover's CN run "
            "separately over the impervious/developed-pervious/undeveloped split, runoff depths "
            "area-weighted; the reported post CN is the area-weighted composite summary) — "
            "compositing a single CN under-predicts runoff once the ~34% impervious footprint "
            "passes TR-55's ~30% directly-connected threshold; "
            f"time of concentration shortens with imperviousness (pre {pre_tc:g} hr -> "
            f"as-permitted {post_tc:g} hr -> full-buildout {full_tc:g} hr); "
            "peaks are AMC-II (average antecedent moisture) with a wet-antecedent (AMC-III) "
            "conservative bound on the as-permitted post peak; outfall capacity = Manning "
            "full-flow (n=0.013) across an assumed slope band; receiving 7Q10 cited from the "
            "OEPA NPDES fact sheet (2PH00006). The receiving-water peak is additionally routed "
            "down the cited reach chain to the Ottawa confluence (Tier-0 Muskingum-Cunge; see "
            "routed_discharge) so it reflects reach travel, not only the at-outfall peak."
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
            "the confluence see intermediate, larger peaks (the at-outfall peak-to-7Q10 ratio, "
            "unattenuated, is the headline erosion signal this routing does not soften).",
        ],
    )


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
    if dp is not None and screen.peak_to_7q10_ratio is not None and screen.receiving_7q10:
        findings.append(
            HydroFinding(
                subject=screen.receiving_water,
                check="receiving-water-peak",
                ok=False,
                detail=(
                    f"{rp}-yr post-dev peak {dp.post_peak_cfs:,.0f} cfs is "
                    f"~{screen.peak_to_7q10_ratio:,.0f}x {screen.receiving_water}'s cited 7Q10 "
                    f"{screen.receiving_7q10.value:g} cfs — channel-stability / erosion signal"
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
