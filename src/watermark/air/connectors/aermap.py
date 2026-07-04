"""AERMAP input emitter — USGS NED DEM → receptor/source terrain elevations.

Composes the NED DEM pull (:mod:`.ned`) into the AERMAP file set: the receptor/source
ground elevations (bilinearly sampled from the authoritative DEM — deterministic
``[derived]`` values), a committed ``aermap-elevations.yaml`` deliverable, and a control
runstream (``aermap.inp``) staging the full AERMAP run against the GeoTIFF DEM.

Point coordinates are reprojected WGS84 → the site UTM (``hydro_utm_epsg``) with ``pyproj``
for the AERMAP ``SO``/``RE`` records. AERMAP's binary (#1178) recomputes elevations **and**
the hill-height scale from the DEM; #1179 supplies the elevations and stages the run. The
full receptor grid is #1182 — absent an explicit point list, only the domain centre is
emitted, never a fabricated grid.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict
from pyproj import CRS, Transformer

from watermark.air.connectors.ned import PointElevation, TerrainDomain, fetch_terrain, sample_points
from watermark.config import Settings, get_settings


class AermapOutputs(BaseModel):
    """The staged AERMAP input file set + the sampled terrain elevations."""

    model_config = ConfigDict(extra="forbid")

    site_label: str
    bbox: tuple[float, float, float, float]  # WGS84 DEM domain
    utm_epsg: int
    dem_path: str
    dem_source: str
    n_points: int
    elevations: list[PointElevation]
    control_path: str
    elevations_path: str


def build_aermap(
    *,
    points: list[tuple[str, float, float]] | None = None,
    out_dir: Path,
    site_label: str,
    center_lat: float | None = None,
    center_lon: float | None = None,
    utm_epsg: int | None = None,
    settings: Settings | None = None,
) -> AermapOutputs:
    """Fetch the DEM, sample the points, and write the AERMAP inputs + elevation deliverable.

    ``points`` are ``(id, lat, lon)`` receptor/source locations; when omitted the DEM domain
    centre is used (the full receptor grid is #1182). ``utm_epsg`` defaults to the site's
    ``hydro_utm_epsg`` for the AERMAP UTM ``SO``/``RE`` records.
    """
    settings = settings or get_settings()
    domain = fetch_terrain(center_lat=center_lat, center_lon=center_lon, settings=settings)
    pts = points if points is not None else [("REC1", domain.center_lat, domain.center_lon)]
    elevations = sample_points(domain, pts)
    epsg = settings.hydro_utm_epsg if utm_epsg is None else utm_epsg
    return write_aermap_inputs(
        domain, elevations, out_dir=out_dir, site_label=site_label, utm_epsg=epsg
    )


def write_aermap_inputs(
    domain: TerrainDomain,
    elevations: list[PointElevation],
    *,
    out_dir: Path,
    site_label: str,
    utm_epsg: int,
) -> AermapOutputs:
    """Write ``aermap.inp`` + ``aermap-elevations.yaml`` for the sampled points."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tf = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True) if utm_epsg else None
    xy = {
        e.id: (tf.transform(e.longitude, e.latitude) if tf else (e.longitude, e.latitude))
        for e in elevations
    }

    # ANCHORXY ties one DEM point to the same point in the user (UTM) system; anchor the
    # domain centre (reprojected once here so _control stays free of the transformer).
    anchor = (
        tf.transform(domain.center_lon, domain.center_lat)
        if tf
        else (domain.center_lon, domain.center_lat)
    )

    control_path = out_dir / "aermap.inp"
    elevations_path = out_dir / "aermap-elevations.yaml"
    control_path.write_text(
        _control(domain, elevations, xy, anchor, site_label, utm_epsg), encoding="ascii"
    )
    elevations_path.write_text(
        _elevation_doc(domain, elevations, xy, site_label, utm_epsg), encoding="utf-8"
    )

    return AermapOutputs(
        site_label=site_label,
        bbox=domain.bbox,
        utm_epsg=utm_epsg,
        dem_path=domain.dem_path,
        dem_source=domain.source,
        n_points=len(elevations),
        elevations=elevations,
        control_path=str(control_path),
        elevations_path=str(elevations_path),
    )


def _utm_zone(utm_epsg: int) -> tuple[str | None, int]:
    """``(display, number)`` UTM zone for an EPSG — handles N (326xx) and S (327xx). pyproj-derived."""
    if not utm_epsg:
        return None, 0
    zone = CRS.from_epsg(utm_epsg).utm_zone  # e.g. "17N" / "23S" / None
    return (zone, int(zone[:-1])) if zone else (None, 0)


def _control(
    domain: TerrainDomain,
    elevations: list[PointElevation],
    xy: dict[str, tuple[float, float]],
    anchor: tuple[float, float],
    site_label: str,
    utm_epsg: int,
) -> str:
    dem_name = Path(domain.dem_path).name
    zone_label, zone = _utm_zone(utm_epsg)
    ax, ay = anchor
    # Each AERMAP line carries its pathway id (CO/SO/RE/OU) — the AERMOD-family grammar, as in
    # watermark.air.aermod.inp. Coordinates are UTM metres (like the AERMOD SO/RE decks).
    src = [f"SO LOCATION  {e.id}  POINT  {xy[e.id][0]:.1f} {xy[e.id][1]:.1f}" for e in elevations]
    rec = [f"RE DISCCART  {xy[e.id][0]:.1f} {xy[e.id][1]:.1f}" for e in elevations]
    lines = [
        "** AERMAP control file - generated by `watermark aermap` (#1179)",
        f"** Site: {site_label}   DEM: {dem_name} ({domain.source})",
        f"** Coordinates are UTM zone {zone_label or '?'} (EPSG:{utm_epsg}); the DEM must be in /",
        "** reprojected to this zone for the run. AERMAP recomputes elevations and the",
        "** hill-height scale from the DEM (that is the #1178 binary's job).",
        "**",
        "CO STARTING",
        f"CO TITLEONE  {site_label} terrain (NED/3DEP)",
        "CO DATATYPE  NED",
        f"CO DATAFILE  {dem_name}",
        # ANCHORXY: DEM point (Xa Ya) tied to the same point in the user (UTM) system (Xu Yu);
        # we anchor the domain centre to itself in UTM (identity) so DEM + receptors share one frame.
        f"CO ANCHORXY  {ax:.1f} {ay:.1f} {ax:.1f} {ay:.1f} {zone} 0",
        "CO RUNORNOT  RUN",
        "CO FINISHED",
        "",
        "SO STARTING",
        *src,
        "SO FINISHED",
        "",
        "RE STARTING",
        *rec,
        "RE FINISHED",
        "",
        "OU STARTING",
        "OU RECEPTOR  aermap_receptors.rou",
        "OU SOURCE    aermap_sources.src",
        "OU FINISHED",
        "",
    ]
    return "\n".join(lines)


def _elevation_doc(
    domain: TerrainDomain,
    elevations: list[PointElevation],
    xy: dict[str, tuple[float, float]],
    site_label: str,
    utm_epsg: int,
) -> str:
    doc = {
        "meta": {
            "subject": "AERMAP receptor/source terrain elevations",
            "site": site_label,
            "dem_source": domain.source,
            "dem_bbox_wgs84": list(domain.bbox),
            "dem_path": domain.dem_path,
            "utm_epsg": utm_epsg,
            "tool": "watermark aermap",
            "method": "bilinear sample of the USGS 3DEP/NED DEM at each point",
            "tags": {"elevation_m": "[derived]", "dem": "[reference]"},
            "caveats": [
                "Elevations are a deterministic bilinear read of the DEM; the AERMAP binary "
                "(#1178) recomputes them and the hill-height scale for the modelled run.",
                "Absent an explicit point list, only the domain centre is emitted — the full "
                "receptor grid is #1182.",
            ],
        },
        "points": [
            {
                "id": e.id,
                "latitude": e.latitude,
                "longitude": e.longitude,
                "utm_x": round(xy[e.id][0], 2),
                "utm_y": round(xy[e.id][1], 2),
                "elevation_m": e.elevation_m,
            }
            for e in elevations
        ],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


__all__ = ["AermapOutputs", "build_aermap", "write_aermap_inputs"]
