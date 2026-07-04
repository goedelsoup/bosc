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

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology import geo
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.hydrology.connectors.noaa_atlas14 import design_storm
from watermark.hydrology.connectors.ssurgo import SsurgoError, dominant_hsg
from watermark.hydrology.lowflow import low_flow_context, low_flow_for
from watermark.hydrology.model import (
    CampusDischargeScreen,
    DesignStorm,
    DischargePeak,
    HydroFinding,
    OutfallCapacity,
    ProvenancedValue,
    SiteFootprint,
    StormRunoff,
)
from watermark.hydrology.solver.curve_number import cn_for, composite_cn
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


def _composite_post_cn(
    total_acres: float,
    footprint: SiteFootprint,
    hsg_letter: str,
    *,
    settings: Settings,
) -> tuple[float, str]:
    """Area-weighted post-development CN from the declared footprint split.

    Only ``impervious_acres`` of the parcel is paved (near-impervious campus); the rest of
    the developed area is graded/landscaped pervious ground; the undeveloped remainder keeps
    its prior cropland cover. Acreages are clamped to the measured runoff footprint so the
    weights never exceed the total area. Returns the composite CN and a human breakdown.
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
    return composite_cn(parts), breakdown


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
    # only ~115 of ~344 ac is permanently impervious, so the post CN is an area-weighted
    # composite, not a blanket near-impervious value over the whole parcel. Falls back to
    # the blanket near-impervious cover (the full-buildout bound) if the footprint is absent.
    footprint = load_site_footprint(settings)
    if footprint is not None:
        post_cn, _ = _composite_post_cn(acres, footprint, hsg_letter, settings=settings)
        post_imperv_frac = min(footprint.impervious_acres.value, acres) / acres if acres else 0.0
    else:
        post_cn = cn_for(prof.post_cover, hsg_letter, settings=settings)
        post_imperv_frac = 1.0  # blanket near-impervious buildout — the shortest Tc
    depth = storm.depth.value
    # Pre-development is fully pervious (impervious fraction 0 -> the longest Tc); the post
    # scenario's shorter Tc scales with its impervious fraction, sharpening the post peak.
    pre_tc = _scenario_tc_hr(0.0, settings=settings)
    post_tc = _scenario_tc_hr(post_imperv_frac, settings=settings)
    pre = simulate_runoff(area_acres=acres, curve_number=pre_cn, tc_hr=pre_tc, storm_depth_in=depth)
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
    # No live fetch / cache: fall back to the cited corridor-point depth, flagged.
    depth = prof.noaa_fallback_24h_depth_in.get(return_period_yr, 4.25)
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
    post_cn, breakdown = _composite_post_cn(acres, footprint, hsg_letter, settings=settings)
    full_cn = cn_for(prof.post_cover, hsg_letter, settings=settings)

    # Tc shortens with imperviousness: pre is pervious (fraction 0), the as-permitted post
    # runs at its declared impervious share, and the full-buildout bound is blanket-impervious
    # (fraction 1 -> the shortest Tc, the sharpest peak).
    post_imperv_frac = min(footprint.impervious_acres.value, acres) / acres if acres else 0.0
    pre_tc = _scenario_tc_hr(0.0, settings=settings)
    post_tc = _scenario_tc_hr(post_imperv_frac, settings=settings)
    full_tc = _scenario_tc_hr(1.0, settings=settings)

    peaks: list[DischargePeak] = []
    for rp in sorted({*return_periods, design_return_period_yr}):
        depth = _resolve_storm(rp, settings=settings, live=live).depth.value
        pre = simulate_runoff(
            area_acres=acres, curve_number=pre_cn, tc_hr=pre_tc, storm_depth_in=depth
        )
        post = simulate_runoff(
            area_acres=acres, curve_number=post_cn, tc_hr=post_tc, storm_depth_in=depth
        )
        # Conservative wet-antecedent bound: the same as-permitted composite CN (and its
        # shorter post Tc) under AMC-III (ground already saturated by prior rain), which
        # raises the peak the 60-inch outfall and Dug Run's low flow have to absorb.
        post_wet = simulate_runoff(
            area_acres=acres, curve_number=post_cn, tc_hr=post_tc, storm_depth_in=depth, amc="III"
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
        basin_chronology_note=(
            "The 95% SPS grading sheet shows NO detention/retention storage "
            "(lma1a.storm-inventory.yaml); the ESC inspections show basins under construction "
            "by 2026-06-05 (topsoil on main-basin slopes; a temporary SW basin started) — field "
            "storage appearing after the 95% design. Undetained, the post-development peak "
            "discharges straight to the 60-inch outfall."
        ),
        method=(
            "Tier-0 SCS-CN screening over the measured parcel footprint; post CN = "
            "area-weighted composite from the ASWCD-declared impervious/developed split; "
            f"time of concentration shortens with imperviousness (pre {pre_tc:g} hr -> "
            f"as-permitted {post_tc:g} hr -> full-buildout {full_tc:g} hr); "
            "peaks are AMC-II (average antecedent moisture) with a wet-antecedent (AMC-III) "
            "conservative bound on the as-permitted post peak; outfall capacity = Manning "
            "full-flow (n=0.013) across an assumed slope band; receiving 7Q10 cited from the "
            "OEPA NPDES fact sheet (2PH00006)."
        ),
        caveats=[
            "Screening-grade — not a routed hydraulic model or a permit determination.",
            "Headline peaks are AMC-II; post_peak_wet_cfs is the AMC-III (wet-antecedent) "
            "upper bound — the storm falling on ground already saturated by prior rain.",
            "The outfall pipe slope is not in the record; capacity is bracketed across 0.3-1.0%.",
            "The peak is computed over the whole measured footprint; the tributary area to the "
            "single 60-inch trunk is not stated, so the capacity comparison is a bracket.",
            "The composite post CN treats the developed-pervious remainder as graded open space "
            "and the undeveloped remainder as keeping prior cropland cover.",
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
