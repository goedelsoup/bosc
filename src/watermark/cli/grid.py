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
    wrote,
)


@app.command()
def compute(
    accel_fraction_low: float | None = typer.Option(
        None, "--accel-fraction-low", help="Override low accelerator-power fraction (0..1)."
    ),
    accel_fraction_high: float | None = typer.Option(
        None, "--accel-fraction-high", help="Override high accelerator-power fraction (0..1)."
    ),
    mfu: float | None = typer.Option(
        None, "--mfu", help="Override model-FLOPS-utilization for the delivered figure (0..1)."
    ),
) -> None:
    """Derive the facility's compute / AI capacity by three independent methods."""
    from watermark.facility.compute import derive_compute_capacity
    from watermark.facility.power import derive_power_basis
    from watermark.sites import active_profile

    settings = get_settings()
    if active_profile(settings).facility is None:
        console.print(
            f"[yellow]No documented facility for site '{settings.site}' "
            "(SiteProfile.facility is None) — this command needs an identified data-center "
            "facility (the data-center dimension onboarding does not capture).[/]"
        )
        raise typer.Exit(0)
    frac = None
    if accel_fraction_low is not None and accel_fraction_high is not None:
        frac = (accel_fraction_low, accel_fraction_high)
    cap = derive_compute_capacity(settings=settings, accelerator_power_fraction=frac, mfu=mfu)

    # The three IT-load estimators (the bracket headline).
    console.print(
        "[bold]Facility IT load[/] — three independent estimators "
        "[dim](nothing here is a measured fact about the facility)[/]\n"
        f"  1. power / gensets [bold](primary)[/]: [bold]{cap.it_load_power.value:g} MW[/] "
        f"[dim](inference: N+1 from the air permit P0138965 backup)[/]\n"
        f"  2. cooling-water back-solve: {cap.it_load_water_low.value:g} MW (low, recovers #1) "
        f"… {cap.it_load_water_high.value:g} MW [dim](FM-2 upper bound; shares the WUE assumption)[/]\n"
        f"  3. footprint [dim](weakest)[/]: {cap.it_load_footprint_low.value:,.0f}"
        f"-{cap.it_load_footprint_high.value:,.0f} MW "
        f"[dim](physical envelope; land != floor area — not a likely load)[/]"
    )
    console.print(
        f"\nMethods 1 and 2-low [bold]agree to within {abs(cap.it_load_water_low.value - cap.it_load_power.value):.1f} MW[/] "
        f"(the loop closes). The power method is the operative figure; the footprint method only "
        f"shows the land could physically hold far more — [bold]power, not floor space, is the "
        f"binding constraint[/]."
    )
    console.print(
        f"\n[bold]Equivalent H100-class GPUs[/] at the central IT load: "
        f"[bold]~{cap.equivalent_h100_low.value:,.0f}-{cap.equivalent_h100_high.value:,.0f}[/] "
        f"[dim](calc; accelerator power = IT load x "
        f"{cap.accelerator_power_fraction_low.value:g}-{cap.accelerator_power_fraction_high.value:g})[/]"
    )

    # Per-chip scenarios. Accelerator type is UNDISCLOSED — these are "if X" labels.
    console.print(
        "\n[bold]If the accelerator is …[/] "
        "[dim](scenarios over the power-method IT load; peak/nameplate FLOPS)[/]"
    )
    table = Table(
        "scenario",
        "accelerators",
        "BF16 dense (EFLOP/s)",
        "FP8 dense (EFLOP/s)",
        "delivered BF16 @MFU",
    )
    for s in cap.scenarios:
        fp8 = s.fp8_dense_eflops_high.value if s.fp8_dense_eflops_high else None
        delivered = s.bf16_delivered_eflops_central
        table.add_row(
            s.spec.label,
            f"{s.count_low.value:,.0f}-{s.count_high.value:,.0f}",
            f"{s.bf16_dense_eflops_low.value:g}-{s.bf16_dense_eflops_high.value:g}",
            f"≤{fp8:g}" if fp8 is not None else "—",
            f"~{delivered.value:g}" if delivered is not None else "—",
        )
    console.print(table)
    console.print(
        f"\n[dim]Peak (nameplate) FLOPS shown; delivered derates by MFU={cap.mfu.value:g} "
        "(training). Accelerator type/count/utilization are UNDISCLOSED — every per-chip row is a "
        "labeled scenario, not a fact. IT load is air-permit-derived (P0138965); chip specs are "
        "vendored reference (data/reference/compute); fractions/MFU are stated assumptions.[/]"
    )

    # Per-data-center-profile chip-level overhead (issue #89) + rack geometry (#88).
    if cap.profiles:
        console.print(
            "\n[bold]Data-center profiles[/] — chip-level overhead by deployment "
            "[dim](the per-chip rows above use the default 1.30; H100-equivalents at central IT)[/]"
        )
        prof_table = Table(
            "profile", "cooling", "host x net = total", "all-in W (H100)", "≈H100 @ central"
        )
        for p in cap.profiles:
            prof_table.add_row(
                p.label,
                p.cooling,
                f"{p.host_overhead.value:g} x {p.network_overhead.value:g} = {p.total_overhead.value:g}",
                f"{p.reference_all_in_w.value:,.0f}",
                f"{p.equivalent_h100_central.value:,.0f}",
            )
        console.print(prof_table)
        if cap.rack_floor_area_sqft is not None:
            console.print(
                f"[dim]Rack profile: {cap.rack_floor_area_sqft.value:g} sqft/rack "
                f"({cap.rack_floor_area_sqft.citation}). All profile/rack figures are "
                "assumptions (2026-06-10 facility-design call); no deployment is disclosed.[/]"
            )

    power = derive_power_basis(settings=settings)
    assert power is not None  # guarded above: this command early-exits for a facility-less site

    # Cooling / mechanical overhead (issue #87): the IT -> total facility-draw
    # translation as a banded, provenance-tagged output.
    # N+1 genset cross-check only when the facility discloses gensets (an air permit);
    # a site-plan-grounded facility (Urbana) has no backup fleet to cross-check against.
    n_plus_1 = (
        f"\n  [dim]N+1 cross-check: the {power.backup_power.value:g} MW genset backup implies "
        f"PUE ~{power.implied_pue_from_backup.value:g} if sized to IT + mechanical — covering "
        f"the draw only at the efficient PUE end (#33)[/]"
        if power.backup_power is not None and power.implied_pue_from_backup is not None
        else "\n  [dim]No disclosed gensets — the IT load is a floor-area screening bracket; "
        "the interconnection/air-permit MW stays [open][/]"
    )
    console.print(
        f"\n[bold]Total facility draw[/] — IT load x PUE "
        f"[dim](cooling/mechanical overhead is a banded assumption)[/]\n"
        f"  [bold]{power.facility_draw.low_or_value:g}-{power.facility_draw.high_or_value:g} MW[/] "
        f"(central [bold]{power.facility_draw.value:g} MW[/]) at PUE "
        f"{power.pue.low_or_value:g}-{power.pue.high_or_value:g}; cooling up to "
        f"[bold]{power.cooling_share_high.value * 100:.0f}%[/] of facility power"
        f"{n_plus_1}"
    )

    # On-site generation cycle (issue #90): the net-efficiency "power-loss coefficient"
    # per cycle + the combined-cycle steam-water pathway.
    console.print(
        "\n[bold]On-site generation cycle[/] — net-efficiency 'power-loss coefficient' "
        "[dim](open evidence question; disclosed units are emergency backup, #33)[/]"
    )
    gen_table = Table("cycle", "net efficiency", "heat rate (MMBtu/MWh)", "steam-cycle water")
    for g in power.generation:
        steam = g.steam_cycle_water
        gen_table.add_row(
            g.label,
            f"{g.net_efficiency.value:g}",
            f"{g.heat_rate_mmbtu_per_mwh.value:g}",
            f"~{steam.value:g} MGD (additional)" if steam is not None else "—",
        )
    console.print(gen_table)
    console.print(
        "\n[dim]Net efficiency (fuel → delivered MWh) and heat rate are banded assumptions; "
        "the combined-cycle steam loop reuses water — an ADDITIONAL consumptive pathway beyond "
        "data-hall cooling (cross-ref watermark.hydrology.cooling), conditional on unproven on-site "
        "primary generation. Source: 2026-06-10 call + air permit P0138965.[/]"
    )


@app.command(name="economics")
def economics(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/economics/baseline.yaml."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture QCEW responses only; never fetch."
    ),
) -> None:
    """Pull the localized economic baseline (BLS QCEW) — employment mix + export-orientation."""
    from watermark.economics import build_baseline, write_baseline

    settings = offline_settings("econ", offline)
    baseline = build_baseline(settings=settings)
    latest = baseline.latest

    if len(baseline.trend) >= 2:
        first, last = baseline.trend[0], baseline.trend[-1]
        delta = last.total_employment.value - first.total_employment.value
        pct = (delta / first.total_employment.value * 100) if first.total_employment.value else 0.0
        console.print(
            f"[bold]{latest.area_name}[/] total covered employment "
            f"{first.total_employment.value:,.0f} ({first.year}) -> "
            f"{last.total_employment.value:,.0f} ({last.year})  "
            f"[{'green' if delta >= 0 else 'red'}]{pct:+.1f}%[/]"
        )

    if latest.avg_annual_pay is not None:
        console.print(
            f"[bold]{latest.area_name}[/] average annual pay "
            f"[green]${latest.avg_annual_pay.value:,.0f}[/] ({latest.year}, all ownerships)"
        )

    table = Table("NAICS", "sector", "jobs", "estabs", "avg pay", "location quotient")
    for s in latest.sectors:
        lq = s.location_quotient.value if s.location_quotient else None
        estabs = f"{s.establishments.value:,.0f}" if s.establishments else "—"
        pay = f"${s.avg_annual_pay.value:,.0f}" if s.avg_annual_pay else "—"
        tag = " [green](exports)[/]" if lq is not None and lq >= 1.2 else ""
        table.add_row(
            s.naics,
            s.sector_name[:38],
            f"{s.annual_avg_employment.value:,.0f}",
            estabs,
            pay,
            (f"{lq:.2f}{tag}" if lq is not None else "—"),
        )
    console.print(table)
    console.print(
        "\n[dim]BLS QCEW (keyless); avg pay = QCEW average annual pay per covered job; "
        "location quotient = county share / national share "
        "(>1 = export-oriented). Population from US Census ACS5 (live fetch needs "
        "WATERMARK_CENSUS_API_KEY; a warm cache/fixture is served keyless).[/]"
    )
    if write:
        path = write_baseline(baseline, settings=settings)
        wrote(path)


@app.command(name="eia")
def eia_cmd(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/eia/consumer-energy.yaml."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture EIA responses only; never fetch."
    ),
) -> None:
    """Consumer energy costs (EIA) + the data-center demand → price-pressure sensitivity."""
    import httpx

    from watermark.connectors import OfflineError
    from watermark.economics.connectors.census import CensusError
    from watermark.economics.energy import (
        build_consumer_energy,
        derive_demand_pressure,
        derive_energy_burden,
        write_consumer_energy,
        write_demand_pressure,
    )

    settings = offline_settings("econ", offline)
    costs = build_consumer_energy(settings=settings)
    dp = None

    console.print(f"[bold]{costs.area_name} consumer energy costs[/] [dim](EIA API v2)[/]")
    table = Table("series", "metric", "period", "value")
    for p in costs.prices:
        table.add_row(p.label, p.metric, p.period, f"{p.value.value:,.2f} {p.value.unit}")
    console.print(table)

    # Household energy burden (#1110): % of median household income (Census B19013) on
    # residential electricity + heating — a fully derived consumer-impact metric. Needs the
    # income pull (keyed/offline), so it degrades to a note when income can't be resolved.
    try:
        burden = derive_energy_burden(costs=costs, settings=settings)
    except (CensusError, OfflineError, httpx.HTTPError, ValueError) as exc:
        msg = next(iter(str(exc).splitlines()), repr(exc))
        console.print(f"\n[yellow]Energy burden unavailable: {msg}[/]")
    else:
        inc = burden.median_household_income
        console.print(
            f"\n[bold]Household energy burden[/] [dim](% of median household income on energy)[/]\n"
            f"  Median household income [bold]${inc.value:,.0f}/yr[/] "
            f"[dim](Census B19013)[/]\n"
            f"  Electricity [bold]{burden.electricity_burden_pct.value:g}%[/] "
            f"([dim]${burden.electricity_annual_cost.value:,.0f}/yr[/]) + "
            f"gas [bold]{burden.gas_burden_pct.value:g}%[/] "
            f"([dim]${burden.gas_annual_cost.value:,.0f}/yr[/]) "
            f"= combined [bold]{burden.combined_burden_pct.value:g}%[/]\n"
            f"  [dim]Derived from EIA residential prices + Census income; gas burden assumes a "
            f"gas-heated home.[/]"
        )

    from watermark.sites import active_profile

    if active_profile(settings).facility is not None:
        dp = derive_demand_pressure(costs=costs, settings=settings)
        console.print(
            f"\n[bold]Data-center demand → consumer price pressure[/] "
            f"[dim](a sensitivity, not a forecast)[/]\n"
            f"  Facility draw [bold]{dp.facility_draw_mw.value:g} MW[/] x {dp.load_factor.value:g} "
            f"load factor → [bold]{dp.annual_consumption_gwh.value:,.0f} GWh/yr[/]\n"
            f"  = [bold]{dp.demand_share_pct.value:g}%[/] of {costs.area_name} retail "
            f"electricity sales "
            f"([dim]{dp.state_retail_sales_gwh.value:,.0f} GWh[/]); "
            f"≈ [bold]{dp.households_equivalent.value:,.0f}[/] {costs.area_name} homes\n"
            f"  Stylized price pressure [bold]{dp.price_pressure_pct_low.value:g}-"
            f"{dp.price_pressure_pct_high.value:g}%[/] on the "
            f"{dp.residential_price.value:g} {dp.residential_price.unit} residential price "
            f"[dim](transmission {dp.transmission_coefficient.value:g} %price/%demand)[/]"
        )
        console.print(
            "\n[dim]Demand share + households-equivalent are EIA-cited; the price-pressure band "
            "is a STYLIZED screening sensitivity (the campus buys at wholesale, not the "
            "residential rate shown). Source: EIA API v2 + the 2026-06-10 facility-design call.[/]"
        )
    else:
        console.print(
            f"\n[yellow]No documented facility for site '{settings.site}' — skipping the "
            "data-center demand → price-pressure sensitivity (it needs a facility load).[/]"
        )
    if write:
        path = write_consumer_energy(costs, settings=settings)
        wrote(path)
        if dp is not None:  # persist the sensitivity for the bundle feed + docs (#1105)
            wrote(write_demand_pressure(dp, settings=settings))


@app.command(name="grid")
def grid_cmd(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/eia/grid-profile.yaml."
    ),
) -> None:
    """Grid foundation (#94): serving utility + BA (PJM) + campus load as a share."""
    from watermark.grid.utility import derive_grid_profile, write_grid_profile
    from watermark.sites import active_profile

    settings = get_settings()
    gp = derive_grid_profile(settings=settings)
    su, ls = gp.serving_utility, gp.load_share

    def _mark(f: object) -> str:
        return "[green]doc[/]" if getattr(f, "verified", False) else "[dim]ref[/]"

    console.print(
        f"[bold]Serving electric-service chain[/] [dim](cited, not asserted)[/]\n"
        f"  Utility: [bold]{su.utility.value}[/] ({_mark(su.utility)}, {su.utility.confidence})\n"
        f"  Balancing authority / RTO: [bold]{su.rto.value}[/] "
        f"({_mark(su.rto)}, {su.rto.confidence})\n"
        f"  Retail regulator: {su.retail_regulator.value}"
    )
    if ls is None:
        console.print(
            f"\n[yellow]No documented facility for site '{settings.site}' — grid backdrop only "
            "(no campus load to express as a share of the grid; the data-center dimension is "
            "not captured by onboarding).[/]"
        )
    else:
        console.print(
            f"\n[bold]Campus load as a share of the grid[/] "
            f"[dim](facility draw {ls.campus_load_mw.value:g} MW x {ls.load_factor.value:g} "
            f"→ {ls.annual_consumption_gwh.value:,.0f} GWh/yr)[/]"
        )
        from watermark.economics.connectors.eia import _state_name

        state_name = _state_name(active_profile(settings).eia_state)
        table = Table("denominator", "annual load (GWh)", "campus share", "basis")
        table.add_row(
            f"{su.utility.value} retail (EIA-861)",
            f"{ls.utility_retail_gwh.value:,.0f}",
            f"[bold]{ls.share_of_utility_pct.value:g}%[/]",
            "connector",
        )
        table.add_row(
            f"{su.rto.value} total load (EIA-930)",
            f"{ls.ba_load_gwh.value:,.0f}",
            f"{ls.share_of_ba_pct.value:g}%",
            "connector",
        )
        table.add_row(
            f"{state_name} retail (EIA, shared #91)",
            f"{ls.state_retail_gwh.value:,.0f}",
            f"{ls.share_of_state_pct.value:g}%",
            "connector",
        )
        console.print(table)
    console.print(
        f"\n[dim]Serving utility ({su.utility.value}) is corpus-grounded; RTO={su.rto.value} is "
        "authoritative. The load denominators are EIA connector-sourced: state retail (shared "
        "#91), per-utility retail (EIA-861), and RTO annual demand (EIA-930). "
        "Source: corpus + EIA + the 2026-06-10 call.[/]"
    )
    if write:
        path = write_grid_profile(gp, settings=settings)
        wrote(path)


@app.command(name="interchange")
def interchange_cmd(
    ba: str = typer.Option("PJM", "--ba", help="Balancing authority / RTO code (EIA-930)."),
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/eia/ba-interchange.yaml."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture EIA-930 responses only; never fetch."
    ),
) -> None:
    """Interchange layer (#95): EIA-930 BA imports/exports vs the campus load."""
    from watermark.grid.interchange import (
        derive_interchange_comparison,
        fetch_ba_interchange,
        load_ba_interchange,
        write_ba_interchange,
    )

    settings = get_settings()
    # Offline reads the committed reference slice (the regenerable artifact); a live
    # pull (default) hits EIA-930 and refreshes it.
    bai = load_ba_interchange(settings.reference_dir) if offline else None
    if bai is None:
        if offline:
            console.print("[yellow]No committed ba-interchange.yaml; run a live pull first.[/]")
            raise typer.Exit(1)
        bai = fetch_ba_interchange(ba=ba, settings=settings)
    cmp = derive_interchange_comparison(interchange=bai, settings=settings)

    console.print(
        f"[bold]{bai.ba} interchange[/] [dim](EIA-930, {bai.period_start}..{bai.period_end}, "
        f"{bai.hours} h; + exports / - imports)[/]\n"
        f"  demand mean [bold]{bai.demand_mean_mw.value:,.0f} MW[/] "
        f"(peak {bai.demand_peak_mw.value:,.0f}); net generation "
        f"[bold]{bai.net_generation_mean_mw.value:,.0f} MW[/]\n"
        f"  net interchange mean [bold]{bai.total_interchange_mean_mw.value:,.0f} MW[/] "
        f"(range {bai.interchange_min_mw.value:,.0f}..{bai.interchange_max_mw.value:,.0f}); "
        f"net-import hours {bai.net_import_hours_fraction.value * 100:.0f}%"
    )
    peak_gap = cmp.peak_import_need_mw.value
    console.print(
        f"\n[bold]Campus load vs the interchange[/] "
        f"[dim](facility draw {cmp.campus_load_mw.value:g} MW)[/]\n"
        f"  coincident-peak gap [bold]{peak_gap:,.0f} MW[/] "
        f"(peak demand {cmp.ba_demand_peak_mw.value:,.0f} - mean net generation "
        f"{cmp.ba_net_generation_mean_mw.value:,.0f}) → "
        f"[bold]{'import/peaking-dependent at peak' if cmp.import_dependent_at_peak else 'covers its own peak on average'}[/]\n"
        f"  campus is {cmp.campus_share_of_demand_pct.value:g}% of {bai.ba} mean demand, "
        f"{cmp.campus_share_of_peak_demand_pct.value:g}% of the peak, "
        f"~{cmp.campus_vs_interchange_pct.value:g}% of the mean net-interchange swing"
    )
    console.print(f"\n[dim]{cmp.interpretation}[/]")
    if write and not offline:  # offline reads the committed slice; only a live pull rewrites it
        path = write_ba_interchange(bai, settings=settings)
        wrote(path)


@app.command(name="pjm")
def pjm_cmd(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/pjm/pjm-market.yaml."
    ),
) -> None:
    """RTO / wholesale market (#96): PJM LMP + RPM capacity + large-load queue vs the campus."""
    from watermark.grid.market import (
        _market_reference,
        derive_pjm_market_scenario,
        write_pjm_market,
    )

    settings = get_settings()
    sc = derive_pjm_market_scenario(settings=settings)

    console.print(
        f"[bold]{sc.rto} wholesale market[/] "
        f"[dim](LMP {sc.lmp_zone}, {sc.zonal_lmp_usd_mwh.source}; RPM/queue transcribed, verify)[/]\n"
        f"  zonal LMP [bold]${sc.zonal_lmp_usd_mwh.value:g}/MWh[/] "
        f"(energy + congestion + losses); RPM clearing "
        f"[bold]${sc.rpm_clearing_usd_mw_day.value:g}/MW-day[/] (2025/2026 BRA); "
        f"large-load queue [bold]~{sc.large_load_queue_gw.value:g} GW[/]"
    )
    console.print(
        f"\n[bold]Campus footprint in PJM[/] "
        f"[dim](facility draw {sc.campus_load_mw.value:g} MW x {sc.load_factor.value:g} "
        f"-> {sc.annual_consumption_gwh.value:,.0f} GWh/yr)[/]"
    )
    table = Table("price signal", "rate", "campus footprint")
    table.add_row(
        "Energy (zonal LMP)",
        f"${sc.zonal_lmp_usd_mwh.value:g}/MWh",
        f"[bold]~${sc.annual_energy_cost_musd.value:,.0f}M/yr[/]",
    )
    table.add_row(
        "Capacity (RPM clearing)",
        f"${sc.rpm_clearing_usd_mw_day.value:g}/MW-day",
        f"[bold]~${sc.annual_capacity_cost_musd.value:,.0f}M/yr[/]",
    )
    table.add_row(
        "Large-load queue",
        f"~{sc.large_load_queue_gw.value:g} GW",
        f"campus ~{sc.campus_share_of_queue_pct.value:g}% of queue",
    )
    console.print(table)
    console.print(f"\n[dim]{sc.interpretation}[/]")
    console.print(
        "\n[dim]Screening view, not a settlement/dispatch model: LMP varies by node/hour; the "
        "RPM clearing price is not the campus's contracted rate; the queue figure is "
        "order-of-magnitude. Zonal LMP is connector-sourced (PJM Data Miner 2); RPM/queue "
        "transcribed, verify.[/]"
    )
    if write:
        path = write_pjm_market(_market_reference(settings), settings=settings)
        wrote(path)


@app.command(name="lmp")
def lmp_cmd() -> None:
    """Zonal day-ahead LMP for the active site's PJM pricing zone (PJM Data Miner 2, #121).

    Needs WATERMARK_PJM_API_KEY for a live pull; offline (WATERMARK_ECON_OFFLINE=1) replays the committed
    fixture. A site whose PJM zone is not yet pinned (lmp_pnode_id=0) reports the placeholder.
    """
    from watermark.grid.lmp import fetch_zonal_lmp
    from watermark.sites import active_profile

    settings = get_settings()
    prof = active_profile(settings)
    if not prof.lmp_pnode_id:
        console.print(
            f"[yellow]Site {settings.site!r} has no pinned PJM pricing zone (lmp_pnode_id=0)[/] — "
            f"using the transcribed placeholder ${prof.lmp_usd_mwh:g}/MWh. Pin the zone to fetch live."
        )
        raise typer.Exit(0)
    z = fetch_zonal_lmp(pnode_id=prof.lmp_pnode_id, zone=prof.lmp_pnode_name, settings=settings)
    console.print(
        f"[bold]{z.zone} zone[/] (pnode {z.pnode_id}) day-ahead LMP "
        f"[bold]${z.mean_da_lmp_usd_mwh:g}/MWh[/] "
        f"[dim](mean of {z.n_hours} h, {z.period_start[:10]}..{z.period_end[:10]}; "
        f"PJM Data Miner 2 da_hrl_lmps)[/]"
    )


@app.command(name="ferc")
def ferc_cmd(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/ferc/ferc-seam.yaml."
    ),
) -> None:
    """FERC seam (#97): FERC<->PUCO jurisdiction + large-load/co-location dockets + Form 1."""
    from watermark.grid.ferc import derive_ferc_seam, write_ferc_seam

    settings = get_settings()
    seam = derive_ferc_seam(settings=settings)
    b = seam.boundary

    console.print(
        f"[bold]FERC<->PUCO jurisdictional seam[/] [dim](cited, not asserted)[/]\n"
        f"  [bold]FERC[/] ({b.ferc_scope.confidence}): {b.ferc_scope.value}\n"
        f"  [bold]PUCO[/] ({b.puco_scope.confidence}): {b.puco_scope.value}\n"
        f"  [bold]Campus[/] ({b.campus_arrangement.confidence}): {b.campus_arrangement.value}"
    )
    console.print(
        "\n[bold]Captured large-load / co-location dockets[/] [dim](public records; verify)[/]"
    )
    table = Table("docket", "topic", "status", "confidence")
    for d in seam.dockets:
        table.add_row(d.docket_no or "[dim](not pinned)[/]", d.topic, d.status, d.fact.confidence)
    console.print(table)
    f1 = seam.form1
    console.print(
        f"\n[bold]FERC Form 1 pointer[/] [dim]({f1.utility})[/]\n"
        f"  {f1.pointer.value}\n  [dim]{f1.pointer.citation}[/]"
    )
    console.print(
        "\n[dim]FERC = wholesale + interstate transmission + PJM market rules; the state PUC = "
        "retail. The campus is most likely state-retail (grid-served customer of its serving "
        "utility, #94) - which determines which regulator sets its price (#91). Dockets / Form 1 "
        "are public records captured as cited evidence, flagged verify.[/]"
    )
    if write:
        path = write_ferc_seam(seam, settings=settings)
        wrote(path)


@app.command(name="federal")
def federal_cmd(
    write: bool = typer.Option(
        True, "--write/--no-write", help="Persist data/reference/federal/federal-energy.yaml."
    ),
) -> None:
    """Federal backdrop (#98): energy policy levers + US output vs the campus load."""
    from watermark.grid.policy import derive_federal_backdrop, write_federal_backdrop

    settings = get_settings()
    fb = derive_federal_backdrop(settings=settings)
    out = fb.output

    console.print(
        "[bold]Federal clean-energy policy levers[/] "
        "[dim](direction on cost, not a quantified offset)[/]"
    )
    table = Table("lever", "applies to", "cost direction")
    for lever in fb.policy_levers:
        applies = lever.applies_to.value
        table.add_row(
            lever.name.value,
            applies[:48] + ("..." if len(applies) > 48 else ""),
            f"[bold]{lever.cost_direction.value}[/]",
        )
    console.print(table)
    console.print(
        f"\n[bold]US federal energy output / statistics[/] [dim](transcribed; verify via EIA)[/]\n"
        f"  US net generation [bold]{out.us_net_generation_twh.value:,.0f} TWh/yr[/]; "
        f"avg retail price [bold]{out.us_avg_retail_price_cents_kwh.value:g} "
        f"{out.us_avg_retail_price_cents_kwh.unit}[/] (upward trend)\n"
        f"  Data centers [bold]{out.datacenter_use_2023_twh.value:,.0f} TWh[/] = "
        f"[bold]{out.datacenter_share_pct_2023.value:g}%[/] of US load (2023), "
        f"projected [bold]~{out.datacenter_share_pct_2028_proj.value:g}%[/] by 2028"
    )
    console.print(
        f"\n[bold]Campus vs the national backdrop[/] "
        f"[dim](facility draw {fb.campus_load_mw.value:g} MW x {fb.load_factor.value:g} "
        f"-> {fb.annual_consumption_gwh.value:,.0f} GWh/yr)[/]\n"
        f"  = [bold]{fb.share_of_us_datacenter_pct.value:g}%[/] of US data-center load, "
        f"[bold]{fb.share_of_us_generation_pct.value:g}%[/] of US total net generation"
    )
    console.print(
        "\n[dim]Policy applicability depends on the campus's undisclosed generation/procurement "
        "choices; cost direction is direction-of-cost only. Output figures are transcribed EIA "
        "national + LBNL/DOE statistics, flagged verify. The federal backdrop the consumer-cost "
        "thread (#91) reads against; nothing is a facility disclosure.[/]"
    )
    if write:
        path = write_federal_backdrop(fb, settings=settings)
        wrote(path)


@app.command(name="lei")
def lei_cmd(
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GLEIF responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/gleif)."
    ),
) -> None:
    """Resolve the corridor LEI watchlist against GLEIF -> committed records YAML.

    Each watchlist entity is fetched by its pinned, exact 20-char LEI (no fuzzy name
    match), with its reported direct/ultimate parent. Raw responses cache under
    data/cache/gleif; the curated YAML is the committed artifact.
    """
    from watermark import gleif
    from watermark.catalog import output_dir_for_command

    settings = get_settings()
    if offline:
        settings = Settings(gleif_offline=True)
    target = (
        Path(out_dir)
        if out_dir
        else (
            output_dir_for_command("gleif", settings=settings) or settings.reference_dir / "gleif"
        )
    )

    inv = gleif.resolve_watchlist(settings)

    table = Table("Legal name", "LEI", "Juris.", "Status", "Ultimate parent")
    for r in inv.records:
        up = r.ultimate_parent.name if r.ultimate_parent else "—"
        table.add_row(
            r.legal_name[:32], r.lei, r.jurisdiction or "—", r.entity_status or "—", up[:28]
        )
    console.print(table)
    console.print(
        f"\n[bold]{len(inv.records)}[/] LEIs resolved "
        f"([green]{inv.meta['with_reported_parent']} report a parent[/]), "
        f"{len(inv.leads)} unresolved lead(s)."
    )

    path = gleif.write_inventory(inv, target)
    wrote(path)


@app.command(name="usaspending")
def usaspending_cmd(
    offline: bool = typer.Option(
        False, "--offline", help="Use cached USASpending responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/usaspending)."
    ),
) -> None:
    """Resolve the federal-award watchlist against USASpending -> committed awards YAML.

    Each recipient is fetched by its pinned recipient_id and verified against the
    pinned UEI (no fuzzy match); the total is all-time prime-award obligations. The
    `nexus` tag marks verified corridor ties vs context/open. Raw responses cache
    under data/cache/usaspending; the curated YAML is the committed artifact.
    """
    from watermark import usaspending
    from watermark.catalog import output_dir_for_command

    settings = get_settings()
    if offline:
        settings = Settings(usaspending_offline=True)
    target = (
        Path(out_dir)
        if out_dir
        else (
            output_dir_for_command("usaspending", settings=settings)
            or settings.reference_dir / "usaspending"
        )
    )

    inv = usaspending.resolve_watchlist(settings)

    table = Table("Recipient", "UEI", "nexus", "all-time prime obligations", "parent")
    for r in sorted(inv.records, key=lambda x: -x.total_obligations):
        table.add_row(
            r.recipient_name[:32],
            r.uei,
            r.nexus,
            f"${r.total_obligations:,.0f}",
            (r.parent_name or "—")[:24],
        )
    console.print(table)
    console.print(
        f"\n[bold]{len(inv.records)}[/] recipients resolved "
        f"([green]{inv.meta['verified_nexus_count']} verified corridor nexus[/]), "
        f"{len(inv.leads)} lead(s). "
        "[dim]Amazon corridor recipient is a warehouse, not the data center; "
        "Google ties to Scioto's Project Dazzler, not the Lima campus.[/]"
    )

    path = usaspending.write_inventory(inv, target)
    wrote(path)


@app.command(name="lsc")
def lsc(
    ga: str = typer.Option(
        None, "--ga", help="General Assembly number (default: settings.lsc_default_ga, e.g. 136)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use the cached/committed workbook only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/lsc)."
    ),
) -> None:
    """Pull the Ohio LSC Status Report of Legislation for a GA -> structured YAML.

    Downloads the LSC status-report workbook, parses every measure's chamber-by-
    chamber milestones verbatim, and writes a YAML with a provenance meta block.
    """
    from watermark.hydrology.connectors import lsc as lsc_connector

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    target = Path(out_dir) if out_dir else settings.reference_dir / "lsc"

    report = lsc_connector.fetch_status_report(ga, settings=settings)

    table = Table("bill type", "count")
    for bill_type, count in lsc_connector._type_counts(report.bills).items():
        table.add_row(bill_type, str(count))
    console.print(table)
    console.print(
        f"\n[bold]{len(report.bills)}[/] measures in the {report.ga}th GA status report "
        f"([dim]as of {report.as_of or 'unknown'}[/])."
    )

    path = lsc_connector.write_status_report(report, target)
    wrote(path)


@app.command(name="orc")
def orc(
    titles: bool = typer.Option(
        False,
        "--titles",
        help="Also pull the WHOLE titles the cited sections belong to (a large crawl).",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/committed pages only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/orc)."
    ),
) -> None:
    """Pull Ohio Revised Code full text for the sections the corpus cites.

    Scans the corpus for ORC citations, resolves each to its Title/Chapter, and
    writes the cited sections' full text plus a citations manifest. With --titles,
    also pulls the entire titles those sections live in (thousands of sections).
    """
    from watermark.hydrology.connectors import orc as orc_connector

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    target = Path(out_dir) if out_dir else settings.reference_dir / "orc"

    cited = orc_connector.scan_citations(settings.extracted_dir, settings.data_dir.parent / "docs")
    console.print(f"Found [bold]{len(cited)}[/] candidate ORC citations in the corpus.")

    resolved: list[orc_connector.OrcSection] = []
    unresolved: list[str] = []
    for number in cited:
        sec = orc_connector.fetch_section(number, settings=settings)
        if sec is None or not sec.text:
            unresolved.append(number)
        else:
            resolved.append(sec)

    table = Table("Section", "Title", "Chapter", "Heading")
    for s in resolved:
        table.add_row(
            s.number,
            f"{s.title_num} {s.title_name}" if s.title_num else "—",
            s.chapter_num or "—",
            (s.heading or "")[:48],
        )
    console.print(table)
    if unresolved:
        console.print(f"[dim]Skipped (no ORC section at portal): {', '.join(unresolved)}[/]")

    orc_connector.write_citation_index(resolved, unresolved, target)
    orc_connector.write_sections(resolved, target, scope="cited")

    if titles:
        title_nums = sorted({s.title_num for s in resolved if s.title_num}, key=int)
        console.print(f"\n[bold]--titles[/]: pulling whole titles {', '.join(title_nums)} …")
        for tnum in title_nums:
            secs = orc_connector.fetch_title(tnum, settings=settings)
            path = orc_connector.write_sections(secs, target, scope=f"title-{tnum}")
            console.print(f"[green]Wrote[/] title {tnum}: {len(secs)} sections -> {path}")

    console.print(f"\n[green]Wrote[/] {len(resolved)} cited sections + manifest to {target}.")
