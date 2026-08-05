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
from watermark.hydrology.connectors.echo import BASINS as _ECHO_BASINS

# Rendered from the registry, not retyped: `resolve_basin` already reports `sorted(BASINS)` on
# an unknown slug, and a help text that drifts from it advertises a basin the CLI will reject
# (or hides one it accepts). Registering a basin must not be a two-place edit.
_BASIN_HELP = f"Watershed slug ({' | '.join(sorted(_ECHO_BASINS))})."


@app.command(name="npdes")
def npdes(
    basin: str = typer.Option("maumee", "--basin", help=_BASIN_HELP),
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

    This is the **refresh path** (#1698): the basin's curated receiving-water overlay
    (``reference/echo/curation/<basin>-wwtp.receiving-water.yaml``) is re-applied to the
    fresh pull, so a re-pull never clobbers reviewed data. A correction that now *disagrees*
    with live ECHO (``conflict``) or whose facility has vanished (``stale``) aborts the run
    with nothing written; one ECHO has caught up with (``superseded``) just gets reported.
    """
    from watermark.hydrology.connectors import echo, echo_curation

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

    # Reconcile the curated overlay against the fresh pull BEFORE writing: a conflict or a
    # stale entry must abort with the committed inventory untouched, not half-rewritten.
    try:
        deduped, curation = echo.curate_inventory(results, basin=b, settings=settings)
    except echo_curation.CurationError as exc:
        console.print(f"[red]Curated receiving-water overlay does not reconcile.[/]\n{exc}")
        raise typer.Exit(code=1) from exc

    n_potw = sum(1 for f in deduped if f.is_potw)
    raw = sum(len(r.facilities) for r in results)
    console.print(
        f"\n[bold]{raw}[/] rows across {len(b.huc8s)} HUC-8s -> [bold]{len(deduped)}[/] facilities "
        f"after FRS dedup ([green]{n_potw} POTW[/], {len(deduped) - n_potw} non-POTW)."
    )

    if curation.applied:
        curated = Table("NPDES", "facility", "receiving water", "mode", "outcome")
        for entry in curation.applied:
            c = entry.correction
            colour = {"superseded": "yellow", "out_of_scope": "dim"}.get(entry.outcome, "green")
            curated.add_row(
                c.npdes_id, c.facility, c.receiving_water, c.mode, f"[{colour}]{entry.outcome}[/]"
            )
        console.print(f"\n[bold]Curated receiving water[/] ({curation.relpath}):")
        console.print(curated)
        for entry in curation.applied:
            if entry.outcome == "superseded":
                console.print(
                    f"[yellow]ECHO now supplies {entry.correction.npdes_id}'s receiving water "
                    f"({entry.echo_now!r}); retire that overlay entry.[/]"
                )

    paths = echo.write_inventory(results, target, basin=b, curated=(deduped, curation))
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
    outfall's reported monthly flow (vs. the permitted design flow), the overflow-outfall
    count (CSO + SSO, param 74063), any ECHO-flagged effluent exceedances, and a seasonality
    shape (warm/cool ratio) that distinguishes a temperature-driven evaporative blowdown from a
    flat, dry loop (#1678). With ``--out`` it writes a regenerable YAML; reported values are
    verbatim and exceedances are listed only where ECHO reports them.
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
    table.add_row(
        "overflow outfalls (CSO/SSO)",
        f"{summary.overflow_outfalls} ({summary.active_overflow_outfalls} active)",
    )
    table.add_row("reported exceedances", str(len(summary.exceedances)))
    if summary.seasonality is not None:
        s = summary.seasonality
        ratio = f"{s.warm_ratio}x" if s.warm_ratio is not None else "n/a"
        table.add_row(
            "seasonality (warm/cool, peak)",
            f"{ratio}, peak month {s.peak_month} (cv {s.cv})",
        )
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

    table = Table("flag", "facility", "receiving", "worst chemical exceedance (vs Ohio WQS)")
    for s in inv.screens:
        worst = toxics.worst_exceedances(s.chemical_screens, k=2)
        exc = (
            "; ".join(
                f"{chem.split(' (')[0].strip()} {ctype} {toxics.format_factor(ef)}"
                for ef, chem, ctype in worst
            )
            or "—"
        )
        rw = (s.receiving_water or "—") + (" *" if s.receiving_water_source == "assumption" else "")
        table.add_row(s.flag, s.facility[:28], rw[:20], exc[:48])
    console.print(table)
    console.print(
        f"\n[bold]{inv.meta['water_releaser_count']}[/] water dischargers, "
        f"[red]{inv.meta['critical_count']} critical[/] (a chemical exceeds its Ohio aquatic-life "
        f"criterion), [yellow]{inv.meta['exceeding_chemical_count']}[/] chemical exceedances. "
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


@app.command(name="water-withdrawal")
def water_withdrawal(
    county: str | None = typer.Option(
        None, "--county", help="Ohio county name (default: the active site's county)."
    ),
    since: int | None = typer.Option(
        None, "--since", help="Earliest annual-report year to keep (default from settings)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached WWFRP responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/ohio-water-withdrawal)."
    ),
) -> None:
    """Pull an Ohio county's Water Withdrawal Facilities registry (Ohio DNR WWFRP) -> YAML.

    Queries the DNR Division of Water Resources FeatureServer for every facility registered
    under R.C. 1521.16 (>100,000 gpd) in the county, joins each to its ground-water,
    surface-water, and water-return annual totals, and writes a per-county YAML. This is the
    makeup-side source for the cooling-water account (epic #1676): the reported withdrawal is
    the strongest single tell of how much a "closed-loop" facility actually spends.
    """
    from watermark.catalog import output_dir_for_command
    from watermark.hydrology.connectors import ohio_water_withdrawal as oww
    from watermark.sites import active_profile

    settings = offline_settings("hydro", offline)
    profile = active_profile(settings)
    if county is None:
        # The WWFRP is Ohio's registry; a non-Ohio watershed point (Fort Wayne, IN) has its
        # own state service — refuse cleanly rather than query the wrong state.
        if profile.gnis_default_state != "OH":
            raise typer.BadParameter(
                f"the WWFRP is Ohio's registry, but site '{profile.slug}' is in "
                f"{profile.gnis_default_state}. Pass --county for an Ohio county, or use that "
                "state's own withdrawal source.",
                param_hint="--county",
            )
        county = profile.county_name.split(" County")[0].strip()

    target = (
        Path(out_dir)
        if out_dir
        else (
            output_dir_for_command("water-withdrawal", settings=settings)
            or settings.reference_dir / "ohio-water-withdrawal"
        )
    )

    registry = oww.fetch_county(county, since_year=since, settings=settings)
    facilities = registry.facilities

    table = Table("reg#", "facility", "use", "cap MGD", "status", "latest yr", "MGD")
    for fac in facilities[:25]:
        years = fac.reported_years()
        latest = years[0] if years else None
        mgd = fac.mean_daily_withdrawal_mgd() if years else None
        table.add_row(
            fac.registration_number,
            (fac.name or "—")[:32],
            (fac.primary_use_type or "—")[:12],
            f"{fac.total_capacity_mgd:g}" if fac.total_capacity_mgd is not None else "—",
            fac.status or "—",
            str(latest) if latest is not None else "—",
            f"{mgd:.3f}" if mgd is not None else "—",
        )
    console.print(table)

    reporting = sum(1 for f in facilities if f.reported_years())
    active = sum(1 for f in facilities if (f.status or "").lower() == "active")
    console.print(
        f"\n[bold]{len(facilities)}[/] registered facilities in {county} County "
        f"([green]{active} active[/], {reporting} with a {registry.since_year}+ report)."
    )

    path = oww.write_registry(registry, target)
    wrote(path)
    console.print(
        "[dim]Withdrawal/return amounts are million gallons, verbatim from the WWFRP annual "
        "reports (self-reported). A registered capacity is not a reported withdrawal, and any "
        r"IT-load inversion from a withdrawal is \[inference].[/]"
    )


@app.command(name="waterwells")
def waterwells(
    county: str | None = typer.Option(
        None, "--county", help="Ohio county name (default: the active site's county)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached ODNR responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/ohio-waterwells)."
    ),
) -> None:
    """Pull an Ohio county's water-well-log census (Ohio DNR, R.C. 1521.05) -> CSV.

    Queries the DNR Division of Water Resources water-wells MapServer (layer 0) for every
    logged well in the county — use type, aquifer, total depth, static water level, reported
    test yield, casing, coordinates — and writes a flat per-county CSV. This is the
    groundwater peer of the surface-water supply model and the empirical basis for the
    aquifer-parameter / well-drawdown thread (the "area well concerns"). Owner/name/street
    columns are not ingested (private-resident PII the model does not need).
    """
    from watermark.catalog import output_dir_for_command
    from watermark.hydrology.connectors import ohio_waterwells as oww
    from watermark.sites import active_profile

    settings = offline_settings("hydro", offline)
    profile = active_profile(settings)
    if county is None:
        # Ohio's well-log service; a non-Ohio watershed point (Fort Wayne, IN) has its own
        # state service — refuse cleanly rather than query the wrong state.
        if profile.gnis_default_state != "OH":
            raise typer.BadParameter(
                f"the ODNR well-log census is Ohio's service, but site '{profile.slug}' is in "
                f"{profile.gnis_default_state}. Pass --county for an Ohio county, or use that "
                "state's own well-log source.",
                param_hint="--county",
            )
        county = profile.county_name.split(" County")[0].strip()

    target = (
        Path(out_dir)
        if out_dir
        else (
            output_dir_for_command("waterwells", settings=settings)
            or settings.reference_dir / "ohio-waterwells"
        )
    )

    inventory = oww.fetch_county(county, settings=settings)
    wells = inventory.wells

    table = Table("use", "n")
    for use, n in list(inventory.use_counts().items())[:10]:
        table.add_row(use, str(n))
    console.print(table)
    console.print(
        f"\n[bold]{len(wells)}[/] logged wells in {county} County "
        f"([green]{inventory.use_counts().get('DOMESTIC', 0)} domestic[/])."
    )

    path = oww.write_inventory(inventory, target)
    wrote(path)
    console.print(
        "[dim]Driller-reported figures are verbatim from the ODNR well-log database "
        r"(self-reported \[verified] for what the log states). There is no pumping-level "
        r"column, so a specific capacity / transmissivity / drawdown cone is \[inference].[/]"
    )


@app.command(name="enclave")
def enclave_cmd(
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Use cached/fixture register responses + cached RSEI tables only; never fetch.",
    ),
    skip_rsei: bool = typer.Option(
        False,
        "--skip-rsei",
        help="Skip the enclave RSEI reduction (it streams the ~447 MB v2312 archive).",
    ),
) -> None:
    """Pull the federal registers for the active site's enclave -> committed artifacts.

    A federal installation is invisible to the county-scoped instruments the rest of the
    platform uses: it is off the tax rolls (no CAMA parcel) and it reports TRI from whichever
    county it is addressed in, which for a straddling base is not the site's economic unit.
    This resolves it against four federal registers instead — DoD MIRTA (site boundary),
    EPA SDWIS (its own public water systems), EPA ECHO (its own NPDES discharges) and EPA
    RSEI/TRI (its own toxic-release row) — and writes reference/<slug>/federal-land.geojson,
    reference/<slug>/enclave.yaml and the enclave's one-facility RSEI reduction.

    No-op for a site with no `federal_installation` facility. Select the site with
    `watermark --site <slug> enclave` (default: WATERMARK_SITE).
    """
    from watermark import enclave as enc
    from watermark.sites import active_profile

    settings = get_settings()
    if offline:
        settings = Settings(
            site=settings.site,
            federal_offline=True,
            federal_fixtures_dir=repo_fixtures_dir("federal"),
            rsei_offline=True,
        )
    profile = active_profile(settings)
    if enc.installation_of(profile) is None:
        console.print(
            f"[yellow]Site '{settings.site}' has no federal_installation facility — nothing to "
            "pull. Register one on its SiteProfile (SiteFacility.kind=federal_installation) "
            "first.[/]"
        )
        raise typer.Exit(0)

    written = enc.regenerate(settings) if not skip_rsei else _enclave_without_rsei(settings)
    for path in written.values():
        wrote(path)

    prof = enc.load_enclave(settings)
    if prof is None:
        return
    tox = prof.toxics
    table = Table("dimension", "value")
    if prof.land is not None:
        record = f" / record {prof.land.record_acres:,}" if prof.land.record_acres else ""
        table.add_row("land", f"{prof.land.register_acres:,.0f} ac (register){record}")
    table.add_row(
        "water",
        f"{len(prof.water.systems)} public water system(s)"
        + (f", {prof.water.population_served:,} served" if prof.water.population_served else "")
        + (f"; {prof.water.supply_wells} supply wells" if prof.water.supply_wells else ""),
    )
    flow = prof.wastewater.reported_average_flow_mgd
    table.add_row(
        "wastewater",
        f"{len(prof.wastewater.discharges)} NPDES permit(s)"
        + (f", {flow:g} MGD reported avg" if flow is not None else r", flow \[open]"),
    )
    # `\[open]` — escaped so rich renders the evidence tag instead of eating it as markup.
    table.add_row("power", f"{prof.power.load_mw:g} MW" if prof.power.load_mw else r"\[open]")
    table.add_row(
        "toxics",
        (f"RSEI Score {tox.rsei.score:,.0f}" if tox.rsei else r"RSEI row \[open]")
        + (f"; NPL {tox.npl_site_id}" if tox.npl_site_id else "")
        + (f"; {tox.waste_disposal_sites} waste sites" if tox.waste_disposal_sites else ""),
    )
    console.print(table)
    if prof.land is not None and prof.land.acreage_note:
        console.print(f"\n[yellow]{prof.land.acreage_note}[/]")
    if tox.scope_disagreement:
        console.print(
            f"\n[yellow]Scope disagreement:[/] the enclave reports TRI from "
            f"{tox.tri_county_name} ({tox.tri_county_fips}); this site's toxics backdrop covers "
            f"{tox.site_rsei_county_name} ({tox.site_rsei_fips}). The county inventory does not "
            "contain the installation — out of scope by construction, not missing."
        )
    console.print(f"[dim]{tox.cercla_gap_note}[/]")


def _enclave_without_rsei(settings: Settings) -> dict[Path, Path] | dict[str, Path]:
    """`watermark enclave --skip-rsei`: the register pulls only, leaving the RSEI row as-is.

    The RSEI reduction streams the ~447 MB v2312 archive, so a boundary/water/wastewater refresh
    shouldn't have to pay for it. The previously committed enclave RSEI row is re-read (not
    dropped) so the assembled profile keeps it.
    """
    from watermark import enclave as enc
    from watermark.connectors.federal import boundary_geojson, write_boundary
    from watermark.sites import active_profile

    profile = active_profile(settings)
    inst = enc.installation_of(profile)
    assert inst is not None  # the caller gated on this
    written: dict[str, Path] = {}
    boundary = None
    if inst.register_name is not None:
        from watermark.connectors.federal import fetch_installation_boundary

        boundary = fetch_installation_boundary(
            inst.register_name, utm_epsg=profile.hydro_utm_epsg, settings=settings
        )
    if boundary is not None and profile.federal_land_relpath is not None:
        dest = settings.data_dir / profile.federal_land_relpath
        write_boundary(boundary_geojson(boundary, slug=settings.site), dest)
        written["federal-land"] = dest
    committed = enc.load_enclave_rsei(settings)
    row = committed.facilities[0] if committed and committed.facilities else None
    assembled = enc.build_enclave(settings, boundary=boundary, rsei_row=row)
    if assembled is not None:
        written["enclave"] = enc.write_enclave(assembled, enc.enclave_path(settings))
    return written
