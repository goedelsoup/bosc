from __future__ import annotations

from pathlib import Path

import typer

from watermark.cli._base import (
    Settings,
    app,
    console,
    get_settings,
    repo_fixtures_dir,
    wrote,
)


def _air_settings(offline: bool) -> Settings:
    """Live or fixture-backed air settings (station/year are passed to the connectors)."""
    if offline:
        return Settings(air_offline=True, air_fixtures_dir=repo_fixtures_dir("air"))
    return get_settings()


@app.command(name="aermet")
def aermet_cmd(
    surface_station: str = typer.Option(
        "", "--surface-station", help="ISD surface station 'USAF-WBAN' (default: settings/profile)."
    ),
    upperair_station: str = typer.Option(
        "", "--upperair-station", help="IGRA upper-air station id (default: settings/profile)."
    ),
    year: int = typer.Option(
        None, "--year", help="Meteorological year (default: settings.air_met_year)."
    ),
    utc_offset: int = typer.Option(
        None, "--utc-offset", help="AERMET GMT offset (hrs local→UTC); default solar-nominal."
    ),
    out: str = typer.Option("", "--out", help="Output dir (default: <cache>/air/aermet)."),
    offline: bool = typer.Option(
        False, "--offline", help="Use committed fixtures only; never touch the network."
    ),
) -> None:
    """Stage the AERMET met inputs: pull ISD surface + IGRA upper-air, emit files + runstream.

    Fetches one meteorological year of NOAA ISD surface obs (ISHD) and IGRA v2 soundings for
    the site's representative stations and writes the AERMET-ready surface/upper-air files plus
    a control runstream. The SFC/PFL products come from the AERMET binary (#1178); this stages
    the run without fabricating meteorology.
    """
    from watermark.air.connectors import aermet, igra, isd

    settings = _air_settings(offline)
    surf = isd.fetch_surface(station=surface_station or None, year=year, settings=settings)
    ua = igra.fetch_upperair(station=upperair_station or None, year=year, settings=settings)
    out_dir = Path(out) if out else settings.air_cache_dir / "aermet"
    inputs = aermet.write_aermet_inputs(
        surf, ua, out_dir=out_dir, site_label=settings.site, utc_offset=utc_offset
    )

    console.print(
        f"[bold]AERMET[/] {inputs.surface_station} (surface) + {inputs.upperair_station} "
        f"(upper air), {inputs.year}: {inputs.start_date} → {inputs.end_date}"
    )
    console.print(
        f"surface coverage {inputs.surface_coverage_fraction:.1%} · {inputs.n_soundings} soundings "
        f"· GMT offset {inputs.utc_offset} (verify)"
    )
    for path in (inputs.surface_path, inputs.upperair_path, inputs.runstream_path):
        wrote(path)


@app.command(name="aermap")
def aermap_cmd(
    center_lat: float = typer.Option(
        None, "--lat", help="Domain centre latitude (default: settings.nasa_power_lat)."
    ),
    center_lon: float = typer.Option(
        None, "--lon", help="Domain centre longitude (default: settings.nasa_power_lon)."
    ),
    utm_epsg: int = typer.Option(
        None, "--utm-epsg", help="UTM EPSG (default: settings.hydro_utm_epsg)."
    ),
    out: str = typer.Option("", "--out", help="Output dir (default: <cache>/air/aermap)."),
    offline: bool = typer.Option(
        False, "--offline", help="Use committed fixture DEM only; never touch the network."
    ),
) -> None:
    """Stage the AERMAP terrain inputs: pull the NED DEM, sample elevations, emit control file.

    Fetches a USGS 3DEP/NED DEM over the terrain domain and bilinearly samples the domain-centre
    ground elevation (the full receptor grid is #1182), writing an elevation deliverable and an
    AERMAP control runstream. AERMAP's binary (#1178) recomputes elevations + hill-height scale.
    """
    from watermark.air.connectors import aermap

    settings = _air_settings(offline)
    out_dir = Path(out) if out else settings.air_cache_dir / "aermap"
    outputs = aermap.build_aermap(
        out_dir=out_dir,
        site_label=settings.site,
        center_lat=center_lat,
        center_lon=center_lon,
        utm_epsg=utm_epsg,
        settings=settings,
    )

    console.print(
        f"[bold]AERMAP[/] terrain domain {outputs.bbox} · {outputs.dem_source} · "
        f"UTM EPSG:{outputs.utm_epsg}"
    )
    for pt in outputs.elevations:
        elev = f"{pt.elevation_m:.1f} m" if pt.elevation_m is not None else "outside domain"
        console.print(f"  {pt.id}: {elev}")
    for path in (outputs.control_path, outputs.elevations_path):
        wrote(path)
