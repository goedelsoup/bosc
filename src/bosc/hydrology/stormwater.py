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

from pathlib import Path

from bosc.config import Settings, get_settings
from bosc.hydrology import geo
from bosc.hydrology.connectors._cache import HydroOfflineError
from bosc.hydrology.connectors.noaa_atlas14 import design_storm
from bosc.hydrology.connectors.ssurgo import SsurgoError, dominant_hsg
from bosc.hydrology.model import (
    DesignStorm,
    HydroFinding,
    ProvenancedValue,
    StormRunoff,
)
from bosc.hydrology.solver.curve_number import cn_for
from bosc.hydrology.solver.runoff import simulate_runoff
from bosc.logging import get_logger

log = get_logger(__name__)

# Representative corridor point for the NOAA Atlas-14 point query (campus centroid).
CORRIDOR_LAT, CORRIDOR_LON = 40.797, -84.123

# Cited assumptions for the corridor (overridable).
_HSG = "C"  # Allen County / Maumee Lake Plain: poorly drained glacial till
_HSG_CITATION = "Allen County, OH dominant hydrologic soil group C (NRCS soil survey; assumption)"
_PRE_COVER = "cropland"  # documented prior use ("Neff Farms Inc")
_POST_COVER = "developed_campus"  # near-impervious data-center campus
_TC_HR = 1.0  # time of concentration (assumption, screening-grade)

# NOAA Atlas-14 24-hr depths (in) at the corridor point, by return period — the
# offline fallback when no live fetch / cache is available (clearly flagged).
_FALLBACK_24H_DEPTH_IN: dict[int, float] = {
    1: 2.11,
    2: 2.52,
    5: 3.10,
    10: 3.58,
    25: 4.25,
    50: 4.81,
    100: 5.39,
    200: 6.01,
    500: 6.88,
    1000: 7.59,
}


def _parcels_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "periplus" / "bosc-parcels.geojson"


def run_storm_scenario(
    *,
    return_period_yr: int = 25,
    settings: Settings | None = None,
    live: bool = True,
    footprint_path: Path | None = None,
) -> tuple[StormRunoff, list[HydroFinding]]:
    """Compute pre/post design-storm runoff over the campus footprint."""
    settings = settings or get_settings()
    path = footprint_path or _parcels_path(settings)

    acres = geo.parcels_total_acres(path, settings=settings)
    area = ProvenancedValue.from_document(
        acres, "acre", citation=f"{path.name} (recorded Bistrozzi parcel footprints)"
    )
    hsg_letter, hsg = _resolve_hsg(path, settings=settings, live=live)

    storm = _resolve_storm(return_period_yr, settings=settings, live=live)

    pre_cn = cn_for(_PRE_COVER, hsg_letter, settings=settings)
    post_cn = cn_for(_POST_COVER, hsg_letter, settings=settings)
    depth = storm.depth.value
    pre = simulate_runoff(area_acres=acres, curve_number=pre_cn, tc_hr=_TC_HR, storm_depth_in=depth)
    post = simulate_runoff(
        area_acres=acres, curve_number=post_cn, tc_hr=_TC_HR, storm_depth_in=depth
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
    code = ProvenancedValue.assume(float("ABCD".index(_HSG) + 1), "hsg_code", why=_HSG_CITATION)
    return _HSG, code


def _resolve_storm(return_period_yr: int, *, settings: Settings, live: bool) -> DesignStorm:
    if live:
        try:
            return design_storm(
                lat=CORRIDOR_LAT,
                lon=CORRIDOR_LON,
                return_period_yr=return_period_yr,
                settings=settings,
            )
        except HydroOfflineError:
            log.info("hydro.storm.offline_fallback", return_period=return_period_yr)
    # No live fetch / cache: fall back to the cited corridor-point depth, flagged.
    depth = _FALLBACK_24H_DEPTH_IN.get(return_period_yr, 4.25)
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
                f"{runoff.post.curve_number:.0f})"
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
