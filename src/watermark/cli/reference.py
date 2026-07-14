from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import (
    Settings,
    app,
    console,
    get_settings,
    offline_settings,
    repo_fixtures_dir,
    wrote,
)


@app.command(name="npdes")
def npdes(
    basin: str = typer.Option(
        "maumee", "--basin", help="Watershed slug (maumee | great-miami | little-miami | scioto)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached ECHO responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/echo)."
    ),
) -> None:
    """Pull a basin's NPDES inventory from EPA ECHO -> deduplicated YAML.

    Queries the basin's HUC-8 subbasins, deduplicates by FRS Registry ID, and writes a
    POTW-only YAML, an all-dischargers YAML, and a per-HUC count manifest. The basin is a
    registry entry in ``watermark.hydrology.connectors.echo`` (default: the Maumee).
    """
    from watermark.hydrology.connectors import echo

    try:
        b = echo.resolve_basin(basin)
    except echo.EchoError as exc:
        raise typer.BadParameter(str(exc), param_hint="--basin") from exc

    from watermark.catalog import output_dir_for_command

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    target = (
        Path(out_dir)
        if out_dir
        else (output_dir_for_command("npdes", settings=settings) or settings.reference_dir / "echo")
    )

    results = echo.fetch_basin(b, settings=settings)

    table = Table("HUC-8", "subbasin", "reported", "pulled", "POTWs")
    for res in results:
        n_potw = sum(1 for f in res.facilities if f.is_potw)
        table.add_row(
            res.huc8, res.name, str(res.reported_count), str(len(res.facilities)), str(n_potw)
        )
    console.print(table)

    deduped = echo.deduplicate(results)
    n_potw = sum(1 for f in deduped if f.is_potw)
    raw = sum(len(r.facilities) for r in results)
    console.print(
        f"\n[bold]{raw}[/] rows across {len(b.huc8s)} HUC-8s -> [bold]{len(deduped)}[/] facilities "
        f"after FRS dedup ([green]{n_potw} POTW[/], {len(deduped) - n_potw} non-POTW)."
    )

    paths = echo.write_inventory(results, target, basin=b)
    for label, path in paths.items():
        console.print(f"[green]Wrote[/] {label}: {path}")
    console.print(
        "[dim]Gaps: ECHO CWA search has no CWNS column; not every NPDES ID geocodes to a "
        "HUC (WATERS); cross-check the state discharger list for completeness.[/]"
    )


@app.command(name="dmr")
def dmr(
    npdes_id: str = typer.Argument(..., help="NPDES permit id, e.g. IN0032191."),
    start: str = typer.Option("2023-01-01", "--start", help="Window start (ISO YYYY-MM-DD)."),
    end: str = typer.Option("2023-12-31", "--end", help="Window end (ISO YYYY-MM-DD)."),
    design_flow: float | None = typer.Option(
        None, "--design-flow", help="Permitted design flow (MGD), for the % comparison."
    ),
    out: str | None = typer.Option(
        None, "--out", help="Write the parsed effluent record to this YAML path."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached ECHO responses only; never touch the network."
    ),
) -> None:
    """Pull a permit's reported effluent record (DMRs) from EPA ECHO -> actual flow vs design.

    Reads ECHO's effluent-chart service for one NPDES permit over a window: the primary
    outfall's reported monthly flow (vs. the permitted design flow), the CSO/bypass outfall
    count, and any ECHO-flagged effluent exceedances. With ``--out`` it writes a regenerable
    YAML; reported values are verbatim and exceedances are listed only where ECHO reports them.
    """
    import yaml

    from watermark.hydrology.connectors import echo_dmr

    settings = offline_settings("hydro", offline)
    try:
        chart = echo_dmr.fetch_effluent_chart(
            npdes_id, start_date=start, end_date=end, settings=settings
        )
    except echo_dmr.EchoDmrError as exc:
        raise typer.BadParameter(str(exc), param_hint="npdes_id") from exc

    summary = echo_dmr.summarize_discharge(chart, design_flow_mgd=design_flow)
    console.print(
        f"[bold]{chart.name}[/] (NPDES {chart.npdes_id}) — {chart.permit_status}, "
        f"SNC [yellow]{chart.snc_status or 'None'}[/]"
    )
    table = Table("metric", "value")
    table.add_row("window", summary.window)
    table.add_row("primary outfall", str(summary.primary_outfall))
    table.add_row("reported flow months", str(summary.n_flow_months))
    table.add_row("actual flow mean (MGD)", f"{summary.actual_flow_mean_mgd}")
    table.add_row(
        "actual flow min/max (MGD)",
        f"{summary.actual_flow_min_mgd} / {summary.actual_flow_max_mgd}",
    )
    if design_flow is not None:
        table.add_row("design flow (MGD)", f"{design_flow}")
        table.add_row("mean actual / design", f"{summary.flow_pct_of_design}%")
    table.add_row("CSO/bypass outfalls", str(summary.cso_outfalls))
    table.add_row("reported exceedances", str(len(summary.exceedances)))
    console.print(table)
    for r in summary.exceedances:
        code = f" [{r.violations[0].code}]" if r.violations else ""
        console.print(
            f"[red]exceedance[/] {r.period_end} {r.parameter_desc or r.parameter_code} "
            f"({r.stat_base or '?'}): {r.value} {r.unit} vs limit {r.limit}"
            + (f" (+{r.exceedance_pct:g}%)" if r.exceedance_pct is not None else "")
            + code
        )
    if not summary.exceedances:
        console.print("[dim]No ECHO-flagged effluent exceedance in the window.[/]")

    if out:
        doc = echo_dmr.dmr_document(chart, summary)
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
        )
        wrote(path)


@app.command(name="nasa-power")
def nasa_power_cmd(
    lon: float = typer.Option(None, "--lon", help="Longitude (default: settings.nasa_power_lon)."),
    lat: float = typer.Option(None, "--lat", help="Latitude (default: settings.nasa_power_lat)."),
    offline: bool = typer.Option(
        False, "--offline", help="Use the committed fixture only; never touch the network."
    ),
    write: bool = typer.Option(
        False, "--write", help="Persist to data/reference/hydrology/nasa-power-climatology.yaml."
    ),
) -> None:
    """Show NASA POWER climate normals (monthly + annual) for the Lima loop point.

    Pulls the POWER climatology point API (precip/temp/humidity/wind/solar). The
    annual precipitation normal feeds the hydrology water-balance context; NOAA
    Atlas-14 still supplies the design-storm depths. ``--write`` refreshes the
    committed reference the hydrology report reads.
    """
    from watermark.hydrology import climate
    from watermark.hydrology.connectors import nasa_power

    settings = get_settings()
    if offline:
        settings = Settings(
            hydro_offline=True,
            hydro_fixtures_dir=repo_fixtures_dir("hydrology"),
        )
    clim = nasa_power.fetch_climatology(lon=lon, lat=lat, settings=settings)

    elev = f" (elev {clim.elevation_m:.0f} m)" if clim.elevation_m is not None else ""
    console.print(
        f"[bold]NASA POWER[/] climatology at {clim.latitude:.4f}, {clim.longitude:.4f}{elev}"
    )
    table = Table("parameter", "units", "Jan", "Apr", "Jul", "Oct", "annual")
    for p in clim.parameters:
        table.add_row(
            p.parameter,
            p.units,
            *[f"{p.monthly.get(m, float('nan')):.2f}" for m in ("JAN", "APR", "JUL", "OCT")],
            f"{p.annual:.2f}" if p.annual is not None else "—",
        )
    console.print(table)
    ann = clim.annual_precip_mm()
    if ann is not None:
        console.print(f"\nAnnual precipitation normal: [bold]{ann:,.0f} mm/yr[/].")
        try:
            from watermark.hydrology.et import penman_monteith_et0

            et0 = penman_monteith_et0(clim)
            console.print(
                f"Reference ET0 (FAO-56 Penman-Monteith): [bold]{et0.annual_mm:,.0f} mm/yr[/] "
                f"(net of precip {ann - et0.annual_mm:+,.0f} mm/yr)."
            )
        except ValueError:
            pass

    if write:
        path = climate.write_climatology(clim, settings=get_settings())
        wrote(path)


@app.command(name="rsei")
def rsei_cmd(
    fips: str = typer.Option(
        None, "--fips", help="County FIPS to reduce to (default: settings.rsei_fips, Allen=39003)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached RSEI tables only; never download."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/rsei)."
    ),
    update_map: bool = typer.Option(
        False, "--map", help="Also merge RSEI facility points into the GIS findings GeoJSON."
    ),
) -> None:
    """Reduce the EPA RSEI Public Data Set to one county's toxic-release inventory.

    Joins elements -> release -> submission -> facility (+ chemical, media) and rolls
    up each facility's population-weighted RSEI Score (cancer/non-cancer split),
    Hazard, and pounds released. The v2.3.12 archive caches under data/cache/rsei
    (~447 MB zip on first run); the committed artifact is a small per-county YAML.
    """
    import json

    from watermark import rsei

    settings = get_settings()
    if offline:
        settings = Settings(rsei_offline=True)
    # Default to the active site's per-site inventory dir (Lima = reference/rsei).
    target = Path(out_dir) if out_dir else rsei.inventory_path(settings).parent

    inv = rsei.build_inventory(settings, fips=fips)

    table = Table("#", "facility", "RSEI Score", "cancer %", "pounds", "years")
    for i, f in enumerate(inv.facilities[:15], 1):
        cpct = f"{100 * f.cancer_score / f.score:.0f}%" if f.score else "-"
        yrs = f"{f.first_year}-{f.last_year}" if f.first_year else "-"
        table.add_row(str(i), f.name[:40], f"{f.score:,.0f}", cpct, f"{f.pounds:,.0f}", yrs)
    console.print(table)
    console.print(
        f"\n[bold]{inv.meta['facility_count']}[/] {inv.county_name} facilities "
        f"([green]{inv.meta['scored_facility_count']} with a modeled Score[/])."
    )

    path = rsei.write_inventory(inv, target)
    wrote(path)
    console.print(
        "[dim]Score is EPA's modeled, population-weighted Risk-Screening Score "
        "(unitless, comparative only). Pounds are reported TRI releases.[/]"
    )

    if update_map:
        from watermark.site import gismap

        geojson = settings.data_dir / "site" / "gis-findings.geojson"
        if geojson.is_file():
            from watermark.hydrology import toxics

            fc = json.loads(geojson.read_text(encoding="utf-8"))
            fc, n = gismap.merge_rsei_layer(
                fc, inv, toxics.load_screen(settings.reference_dir), settings=settings
            )
            geojson.write_text(json.dumps(fc, indent=1), encoding="utf-8")
            console.print(f"[green]Merged[/] {n} RSEI points into {geojson}")
        else:
            console.print(f"[yellow]No GIS findings GeoJSON at {geojson}; skipped --map.[/]")


@app.command(name="toxics")
def toxics_cmd(
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/rsei)."
    ),
    update_map: bool = typer.Option(
        False, "--map", help="Also ring the flagged water dischargers on the GIS RSEI layer."
    ),
) -> None:
    """Screen the industrial RSEI water dischargers against their receiving 7Q10.

    Places each RSEI facility that releases toxics to water on its receiving stream
    (ECHO-cited, else inferred from the Ottawa River corridor), reads it against the
    cited 7Q10, and flags where the toxic load meets near-zero assimilative capacity.
    Consumes the committed RSEI + ECHO + 7Q10 artifacts (no network).
    """
    from watermark.catalog import output_dir_for_command
    from watermark.hydrology import toxics

    settings = get_settings()
    target = (
        Path(out_dir)
        if out_dir
        else (output_dir_for_command("rsei", settings=settings) or settings.reference_dir / "rsei")
    )

    inv = toxics.build_screen(settings)

    table = Table("flag", "facility", "to water (lb)", "receiving", "7Q10", "screen mg/L")
    for s in inv.screens:
        q7 = f"{s.low_flow_7q10.value:g} cfs" if s.low_flow_7q10 else "—"
        conc = f"{s.screening_concentration.value:g}" if s.screening_concentration else "—"
        rw = (s.receiving_water or "—") + (" *" if s.receiving_water_source == "assumption" else "")
        table.add_row(s.flag, s.facility[:30], f"{s.water_pounds:,.0f}", rw[:22], q7, conc)
    console.print(table)
    console.print(
        f"\n[bold]{inv.meta['water_releaser_count']}[/] water dischargers, "
        f"[red]{inv.meta['critical_count']} critical[/] (toxic load on a near-undiluted reach). "
        "[dim]* = receiving water inferred from corridor, not independently cited.[/]"
    )

    path = toxics.write_screen(inv, target)
    wrote(path)
    console.print(
        "[dim]Screening concentration is a derived order-of-magnitude value (annual "
        "reported water pounds at the 7Q10), not a measured concentration.[/]"
    )

    if update_map:
        import json

        from watermark.rsei import load_inventory
        from watermark.site import gismap

        rsei_inv = load_inventory(settings)
        geojson = settings.data_dir / "site" / "gis-findings.geojson"
        if rsei_inv is not None and geojson.is_file():
            fc = json.loads(geojson.read_text(encoding="utf-8"))
            fc, n = gismap.merge_rsei_layer(fc, rsei_inv, inv, settings=settings)
            geojson.write_text(json.dumps(fc, indent=1), encoding="utf-8")
            console.print(
                f"[green]Ringed[/] flagged dischargers across {n} RSEI points in {geojson}"
            )
        else:
            console.print("[yellow]No RSEI inventory or GIS findings GeoJSON; skipped --map.[/]")
