"""``watermark air`` — air-quality & backup-generation dispatch modeling (epic #1172).

Thin wrappers over :mod:`watermark.air` (Tier-0 emissions inventory + dispatch trigger +
event-anchored calibration), :mod:`watermark.air.aermod` (Tier-1 AERMOD dispersion + NAAQS
screen), and :mod:`watermark.air.connectors` (AERMET/AERMAP met + terrain staging, #1179):
parse args → ``get_settings()`` → call the library → render. Consistent with
``cli/grid.py`` / ``cli/hydrology.py``; all verbs are grouped under ``watermark air``.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table

from watermark.cli._base import (
    Settings,
    air_app,
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


def _no_facility(site: str) -> None:
    console.print(
        f"[yellow]No documented facility for site '{site}' (SiteProfile.facility is None) — "
        "air modeling needs an identified backup-generation fleet + air permit. The grid "
        "backdrop still applies; the air section locks per the readiness layer.[/]"
    )
    raise typer.Exit(0)


@air_app.command(name="aermet")
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


@air_app.command(name="aermap")
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


@air_app.command(name="scenarios")
def scenarios_cmd(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist the evaluated scenarios to data/scenarios/."
    ),
) -> None:
    """Tier-0 emissions inventory: baseline + event-anchored dispatch vs the synthetic-minor caps.

    Evaluates the readiness-testing baseline (compliant by construction) and the event-anchored
    reliability dispatch band (#1174/#1182) against the facility's federally-enforceable NSR
    caps, and reports where forced runtime would breach them.
    """
    from watermark.air import calibration as cal
    from watermark.air.scenario import (
        baseline_scenario,
        cap_breach_runtime,
        evaluate,
        write_scenario,
    )
    from watermark.sites import active_profile

    settings = get_settings()
    if active_profile(settings).facility is None:
        _no_facility(settings.site)

    results = []
    base = evaluate(baseline_scenario(), settings=settings)
    results.append(base)

    runtime = cal.calibrate_dispatch(settings=settings)
    if runtime is not None:
        ev = runtime.event
        disp = "confirmed" if ev.facility_dispatch_confirmed else escape("[open]")
        console.print(
            f"[bold]Event-anchored dispatch[/] — {ev.name}"
            + (f" (DOE Order {ev.order_id})" if ev.order_id else "")
            + f"\n  authorized window [bold]{ev.authorized_window_hours.value:g} hr[/] "
            f"[dim]({escape('[verified]')} {ev.window_start}..{ev.window_end}; facility dispatch "
            f"{disp})[/]\n"
            f"  runtime band: central [bold]{runtime.runtime_hours_central.value:g}[/] / "
            f"high [bold]{runtime.runtime_hours_high.value:g}[/] hr/yr per engine "
            f"[dim](high = full authorized window x recurrence = the {escape('[verified]')} ceiling)[/]"
        )
        for band in ("central", "high"):
            results.append(
                evaluate(cal.event_anchored_scenario(runtime, band=band), settings=settings)
            )
    else:
        console.print("[yellow]No captured dispatch event — reporting the baseline only.[/]")

    table = Table("scenario", "runtime (hr/yr)", "NOx tpy", "CO tpy", "cap check")
    for r in results:
        by = {e.pollutant: e for e in r.emissions}
        nox, co = by.get("NOx"), by.get("CO")

        def _cell(e: object) -> str:
            if e is None:
                return "—"
            pct = f" [dim]({e.pct_of_cap:g}% of cap)[/]" if e.pct_of_cap is not None else ""  # type: ignore[attr-defined]
            colour = "red" if e.exceeds_cap else "green"  # type: ignore[attr-defined]
            return f"[{colour}]{e.tpy.value:g}[/]{pct}"  # type: ignore[attr-defined]

        breach = (
            f"[red]BREACH: {', '.join(r.breached_pollutants)}[/]"
            if r.any_cap_exceeded
            else "[green]within caps[/]"
        )
        table.add_row(
            r.scenario.name, f"{r.scenario.runtime_hours.value:g}", _cell(nox), _cell(co), breach
        )
    console.print(table)

    nox_thresh = cap_breach_runtime("NOx", settings=settings)
    if nox_thresh is not None:
        console.print(
            f"\n[bold]Cap-breach threshold[/]: the fleet crosses the NOx synthetic-minor cap at "
            f"[bold]~{nox_thresh:g} hr/yr[/] per engine of forced runtime at load "
            "[dim](how much forced generation before this becomes a major NSR source)[/]"
        )
    console.print(
        "\n[dim]Caps are the facility-wide synthetic-minor NSR limits from the air permit "
        f"(document). The event window is {escape('[verified]')}; the intra-window duty + annual "
        f"recurrence are {escape('[inference]')}, and no claim asserts the fleet actually ran "
        f"(facility dispatch {escape('[open]')}).[/]"
    )

    if write:
        for r in results:
            wrote(write_scenario(r, settings=settings))


@air_app.command(name="calibrate")
def calibrate_cmd() -> None:
    """Show the event-anchored dispatch runtime band (the captured PJM §202(c) order, #1174)."""
    from watermark.air import calibration as cal
    from watermark.sites import active_profile

    settings = get_settings()
    if active_profile(settings).facility is None:
        _no_facility(settings.site)
    runtime = cal.calibrate_dispatch(settings=settings)
    if runtime is None:
        console.print("[yellow]No captured dispatch event committed for this site.[/]")
        raise typer.Exit(0)
    ev = runtime.event
    open_tag = f"[dim]{escape('[open]')}[/]" if not ev.facility_dispatch_confirmed else ""
    console.print(
        f"[bold]{ev.name}[/]" + (f" — DOE Order {ev.order_id}" if ev.order_id else "") + "\n"
        f"  authorized backup-gen window [bold]{ev.authorized_window_hours.value:g} hr[/] "
        f"[dim]({escape('[verified]')}, {ev.window_start}..{ev.window_end})[/]\n"
        f"  backup generation authorized: {ev.backup_generation_authorized}; "
        f"this facility's dispatch confirmed: {ev.facility_dispatch_confirmed} "
        f"{open_tag}"
    )
    table = Table("band", "runtime (hr/yr/engine)", "provenance")
    for label, pv in (
        ("low", runtime.runtime_hours_low),
        ("central", runtime.runtime_hours_central),
        ("high (verified ceiling)", runtime.runtime_hours_high),
    ):
        table.add_row(label, f"{pv.value:g}", pv.source)
    console.print(table)
    for c in ev.caveats + runtime.caveats:
        console.print(f"[dim]· {escape(c)}[/]")


@air_app.command(name="dispersion")
def dispersion_cmd(
    pollutant: str = typer.Option(
        "NOx", "--pollutant", help="Criteria pollutant (NOx/CO/PM10/PM2.5/SO2)."
    ),
) -> None:
    """Tier-1 AERMOD concentration screen vs NAAQS, event-anchored (#1178/#1182).

    Builds the site's single-source screening deck at the permit load-point rate and, when the
    AERMOD binary + a canned met pair are present, runs it and screens the peak concentrations
    against the NAAQS. Degrades cleanly (no fabricated concentration) when the engine is absent.
    """
    from watermark.air.aermod.dispersion import run_calibration_dispersion
    from watermark.air.aermod.model import AveragePeriod
    from watermark.air.model import POLLUTANTS
    from watermark.sites import active_profile

    settings = get_settings()
    if active_profile(settings).facility is None:
        _no_facility(settings.site)
    if pollutant not in POLLUTANTS:
        raise typer.BadParameter(f"unknown pollutant {pollutant!r}; known: {list(POLLUTANTS)}")

    periods: tuple[AveragePeriod, ...] = ("1", "8") if pollutant == "CO" else ("1", "ANNUAL")
    result = run_calibration_dispersion(
        pollutant=pollutant,
        averaging_periods=periods,
        settings=settings,
    )
    if result is None:
        console.print(f"[yellow]No wired air permit for '{settings.site}' — nothing to model.[/]")
        raise typer.Exit(0)

    console.print(
        f"[bold]AERMOD dispersion screen[/] — {settings.site} {pollutant} "
        f"[dim]({result.factors_basis} rate at {result.load_regime} load; "
        f"source {result.source_emission_g_s:g} g/s; "
        f"stack {'assumed' if result.stack_is_assumption else 'documented'})[/]"
    )
    if result.event is not None:
        console.print(
            f"  anchored to [bold]{result.event.name}[/]"
            + (f" (Order {result.event.order_id})" if result.event.order_id else "")
        )
    if not result.available:
        console.print(
            f"\n[yellow]AERMOD engine/met unavailable[/] — deck + NAAQS basis resolved, no modeled "
            f"concentration. [dim]{escape(result.note)}[/]\n"
            "[dim]Set WATERMARK_AERMOD_BIN + supply a canned AERMET met pair to run "
            "(docs/AERMOD.md).[/]"
        )
    else:
        table = Table("averaging period", "modeled peak (µg/m³)", "NAAQS", "% of NAAQS", "screen")
        for s in result.screens:
            naaqs = f"{s.naaqs_ug_m3:g} ({s.naaqs_species})" if s.naaqs_ug_m3 else "—"
            pct = f"{s.pct_of_naaqs:g}%" if s.pct_of_naaqs is not None else "—"
            verdict = "[red]OVER[/]" if s.exceeds_naaqs else "[green]under[/]"
            table.add_row(s.averaging_period, f"{s.max_conc_ug_m3:g}", naaqs, pct, verdict)
        console.print(table)
    for c in result.caveats:
        console.print(f"[dim]· {escape(c)}[/]")
