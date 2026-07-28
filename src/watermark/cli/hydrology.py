from __future__ import annotations

import typer
from rich.markup import escape
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


@app.command()
def hydro(
    offline: bool = typer.Option(
        False, "--offline", help="Don't fetch live streamflow; use cached/fixture data only."
    ),
) -> None:
    """Tier-0 water balance + low-flow assimilative screen of the municipal loop."""
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    balance, _checks, findings = hydro_stage.run_baseline(settings=settings, live=True)

    flow_table = Table("node", "role", "flow (cfs)", "MGD", "receiving", "source")
    for n in balance.nodes:
        v = n.return_flow or n.inflow
        flow = f"{v.value:,.2f}" if v else "—"
        mgd = f"{v.value / 1.547:,.2f}" if v else "—"
        tag = {"document": "doc", "connector": "live", "assumption": "assume", "derived": "calc"}
        src = f"[dim]{tag.get(v.source, v.source)}[/]" if v else "—"
        flow_table.add_row(n.node.name, n.node.role, flow, mgd, n.node.receiving_water or "—", src)
    console.print(flow_table)

    console.print(
        "\n[bold]Low-flow assimilative screen[/] [dim](chronic 7Q10 + acute 1Q10 dilution)[/]"
    )
    violations = 0
    for f in findings:
        color = "green" if f.ok else "red"
        console.print(f"[{color}]{f}[/]")
        violations += 0 if f.ok else 1
    if not findings:
        console.print("[yellow]No WWTP discharge had a cited receiving-water 7Q10.[/]")
    console.print(
        f"\n{len(findings)} checks, [{'red' if violations else 'green'}]{violations} violation(s)[/]."
    )
    for w in balance.warnings:
        console.print(f"[dim]! {w}[/]")


@app.command(name="basin-screen")
def basin_screen() -> None:
    """Basin-wide low-flow assimilative screen over the ECHO Maumee POTW inventory.

    Extends the Lima-loop screen to every basin POTW, using the cited 7Q10s plus the
    derived mainstem 7Q10s (`watermark derive-low-flows`). Dischargers on ungaged tributaries
    or with no receiving water in ECHO are reported, not screened (omit, don't guess).
    """
    from watermark.hydrology.basin import check_basin_assimilative

    screen = check_basin_assimilative(settings=get_settings())
    cov = screen.coverage
    table = Table("dilution", "flag", "discharger", "receiving water", "7Q10", "src")
    for ch in screen.checks:
        color = {"violation": "red", "tight": "yellow", "ok": "green"}[ch.flag]
        table.add_row(
            f"{ch.dilution_ratio:.2f}:1",
            f"[{color}]{ch.flag}[/]",
            ch.discharger,
            ch.receiving_water,
            f"{ch.design_low_flow.value:.2f} cfs",
            ch.design_low_flow.source,
        )
    console.print(table)
    console.print(
        f"\n[bold]{cov.screened}[/] of [bold]{cov.total}[/] basin POTWs screened "
        f"([red]{cov.violations} violation[/], [yellow]{cov.tight} tight[/], "
        f"[green]{cov.ok} ok[/])."
    )
    console.print(
        f"[dim]Unscreenable (reported, not guessed): {cov.no_receiving_water} no receiving "
        f"water in ECHO, {cov.no_7q10} ungaged tributary / no 7Q10, "
        f"{cov.no_design_flow} no design flow.[/]"
    )


@app.command(name="thermal")
def thermal_cmd() -> None:
    """Screen the site's cooling heat load against its receiving reach's temperature WQS / §316(a).

    The heat-side peer of `watermark toxics`: carries each disclosed facility's condenser heat
    rejection into the receiving water at its cited design low flows (1Q10 / 7Q10 / summer 30Q10)
    and reads the fully-mixed in-stream temperature against Ohio's daily-maximum temperature
    criterion and the Great Lakes RIS tolerances. Flags where a permit-level thermal / CWA
    §316(a) analysis is warranted. Consumes the committed cooling / low-flow / criteria artifacts
    (no network).
    """
    from watermark.hydrology import thermal

    inv = thermal.build_screen(get_settings())
    m = inv.meta
    console.print(
        f"[bold]{escape(m['receiving_water'] or '—')}[/] · {escape(m['zone_rule'] or 'no zone')} · "
        f"daily-max [bold]{m['daily_max_c']}[/] degC ({escape(m['design_period'] or '—')})"
    )
    for s in inv.screens:
        # Neither `context` (heat load, no computed exceedance) nor `uncharacterized` (unscreened —
        # no receiving water / no resolvable load) is a clean bill of health, so neither reads green.
        color = {
            "critical": "red",
            "elevated": "yellow",
            "exempt": "cyan",
            "dry": "blue",
            "context": "white",
            "uncharacterized": "magenta",
        }.get(s.flag, "white")
        # The condenser rejection carries its own provenance (value + range + [calc] tag) via
        # ProvenancedValue.__str__; escape it (the tag is bracketed) and drop the redundant "~".
        reject = escape(str(s.reject_heat_mw)) if s.reject_heat_mw else "—"
        console.print(
            f"\n[{color}]{s.flag.upper()}[/] [bold]{escape(s.facility)}[/] "
            f"[dim]({s.cooling_model}, {reject} rejected)[/]"
        )
        table = Table("design flow", "cfs", "capacity (MW)", "exceedance", "% exhausts cap", "flag")
        for fs in s.flow_screens:
            # `is not None`, not truthiness: a genuine 0 metric (the no-capacity row's 0% capacity
            # fraction) is a value to show, not a blank.
            factor = (
                thermal._format_factor(fs.exceedance_factor)
                if fs.exceedance_factor is not None
                else "—"
            )
            frac = f"{fs.capacity_fraction * 100:.2g}%" if fs.capacity_fraction is not None else "—"
            fcolor = {"exceedance": "red", "no_capacity": "red", "approach": "yellow"}.get(
                fs.flag, "green"
            )
            table.add_row(
                fs.flow_label,
                f"{fs.design_flow.value:g}",
                f"{fs.thermal_capacity_mw:g}" if fs.thermal_capacity_mw is not None else "—",
                factor,
                frac,
                f"[{fcolor}]{fs.flag}[/]",
            )
        console.print(table)
        if s.blowdown_exempt_note:
            console.print(escape(s.blowdown_exempt_note), style="dim")
        console.print(escape(s.detail), style="dim")
    console.print(
        f"\n[bold]{m['facility_count']}[/] facilities, "
        f"[red]{m['critical_count']} critical[/] (heat load overwhelms the reach — a §316(a) / "
        "thermal-mixing-zone trigger). [dim]Conservative once-through-equivalent screen; "
        "the capacity ratio is robust to the heat-partition assumption.[/]"
    )


@app.command(name="cooling-reconcile")
def cooling_reconcile_cmd(
    write: bool = typer.Option(
        False,
        "--write",
        help="Persist data/reference/oepa/cooling-reconciliation.yaml (else print only).",
    ),
    out: str | None = typer.Option(
        None, "--out", help="Write the reconciliation artifact to this path instead of the default."
    ),
) -> None:
    """Reconcile each closed-loop facility's cooling claim against its documented water (#1679).

    The A3 harness of the closed-loop cooling cycling epic (#1676). Per facility it assembles the
    water account — the pinned archetype's PREDICTED makeup/blowdown (via `cooling_models`) vs the
    DOCUMENTED makeup (A1 withdrawal) / blowdown (A2 discharge) — back-solves cycles-of-
    concentration where both are on record (an `[inference]` bracket, never a scalar), and
    classifies each into discrepancy / corroborated / reservation_conflict (a low-water claim
    contradicted by a disclosed reservation ceiling — Troy-Piqua B1, #1681) / gap. It RECOMMENDS
    re-archetyping; it never mutates `cooling_model`. Includes the Intel evaporative positive
    control, which must classify corroborated (no false discrepancy). Read-only over the registry
    + committed artifacts.
    """
    from pathlib import Path

    from watermark.hydrology import blowdown, cooling_reconcile

    settings = get_settings()
    records = cooling_reconcile.reconcile_cohort(settings=settings)
    counts = {
        o.value: sum(1 for r in records if r.outcome is o)
        for o in cooling_reconcile.ReconcileOutcome
    }
    console.print(
        f"[bold]Cooling-cycling reconciliation[/] — {len(records)} facilities "
        f"([red]{counts['discrepancy']} discrepancy[/], [green]{counts['corroborated']} "
        f"corroborated[/], [magenta]{counts['reservation_conflict']} reservation-conflict[/], "
        f"[yellow]{counts['gap']} gap[/]); documented-blowdown currency "
        f"{blowdown.OHD000001.asof} (OHD000001 lifecycle)."
    )
    color = {
        "discrepancy": "red",
        "corroborated": "green",
        "reservation_conflict": "magenta",
        "gap": "yellow",
    }
    # A4 (#1680) corroborator stance → glyph: contradicts (points to over-cycling) / corroborates /
    # silent (not on record). Secondary to the outcome — never re-archetypes on its own.
    stance_glyph = {
        "contradicts": "[red]✗ contradicts[/]",
        "corroborates": "[green]✓ corroborates[/]",
        "silent": "[dim]· silent[/]",
    }
    table = Table(
        "site",
        "facility",
        "claim",
        "outcome",
        "pred makeup",
        "documented",
        "CoC*",
        "corrob†",
        "recommend",
    )
    for r in records:
        a = r.account
        documented = a.documented_blowdown or a.documented_makeup
        # A reservation_conflict has no metered figure — show the disclosed reservation ceiling
        # instead, marked "(reserved)" so a ceiling is never read as a metered use. A disclosed gap
        # likewise shows what the claim's own source self-reported: a permitted-withdrawal CEILING
        # marked "(ceiling)" (Springfield B3, #1683 — checked first, it is the actual-vs-ceiling
        # denominator) or an ongoing draw marked "(disclosed)" (Van Wert B2, #1682) — so a self-report
        # is never read as a metered use either.
        reserved = a.reserved_makeup or a.reserved_blowdown
        if documented is not None:
            documented_cell = f"{documented.value:g} MGD"
        elif reserved is not None:
            documented_cell = f"{reserved.value:g} MGD (reserved)"
        elif a.disclosed_ceiling is not None:
            documented_cell = f"{a.disclosed_ceiling.value:g} MGD (ceiling)"
        elif a.disclosed_makeup is not None:
            documented_cell = f"{a.disclosed_makeup.value:g} MGD (disclosed)"
        else:
            documented_cell = "—"
        coc = (
            f"{a.backsolved_cycles.value:g} "
            f"({a.backsolved_cycles.low_or_value:g}-{a.backsolved_cycles.high_or_value:g})"
            if a.backsolved_cycles is not None
            else "—"
        )
        if r.outcome is cooling_reconcile.ReconcileOutcome.RESERVATION_CONFLICT:
            # Keep the site's real pin (carried on the record — "unknown" for Troy-Piqua), never
            # hardcoded, so a reservation_conflict site pinning a different archetype renders right.
            recommend = f"keep {r.kept_archetype} + records request (C2)"
        elif r.recommended_archetype is not None:
            recommend = f"→ {r.recommended_archetype}, source={r.recommended_source}"
        else:
            recommend = "records request (C2)"
        corrob = stance_glyph[r.corroborators.net_stance.value] if r.corroborators else "—"
        facility = f"{r.facility}{' [cyan](control)[/]' if r.is_control else ''}"
        table.add_row(
            r.site,
            escape(facility) if not r.is_control else facility,
            r.claimed_archetype,
            f"[{color[r.outcome.value]}]{r.outcome.value}[/]",
            f"{a.predicted_makeup.value:g}",
            documented_cell,
            coc,
            corrob,
            escape(recommend),
        )
    console.print(table)
    console.print(
        r"[dim]The harness recommends; it never mutates cooling_model (re-archetyping is a reviewed "
        r"B-review edit with the instrument cited). A back-solved CoC (CoC*) is an \[inference] "
        r"bracket. A gap is an \[open] records-request lead for C2 (#1688), never 'confirmed dry'. A "
        r"reservation-conflict (Troy-Piqua B1, #1681) is a low-water claim contradicted by a reserved "
        r"CEILING (the 'reserved' documented cell) — not a discharge/withdrawal instrument, so it "
        r"keeps the UNKNOWN pin + sharpens lead #1486, never a headline consumptive. A 'disclosed' "
        r"documented cell (Van Wert B2, #1682) is an operator SELF-REPORT (not a metered instrument): "
        r"it sharpens the gap onto the initial-fill open quantity (#1409) but keeps the \[reference] "
        r"pin, never upgraded. A 'ceiling' documented cell (Springfield B3, #1683) is a permitted "
        r"withdrawal max the claim's OWN source self-disclosed — NOT a reservation conflict (a dry "
        r"loop sits far below it) and not metered use, so it too keeps the \[reference] pin and "
        r"sharpens the gap onto the actual-vs-ceiling denominator (#1415). corrob† = the A4 "
        r"independent corroborators (air-permit cooling-tower PM + Tier II chemistry) reconciled "
        r"against the claim — SECONDARY, never the sole basis for a re-archetype. The Intel row is a "
        r"constructed positive control.[/]"
    )

    if write or out:
        document = cooling_reconcile.reconciliation_document(records)
        path = cooling_reconcile.write_reconciliation(
            document, settings=settings, out=Path(out) if out else None
        )
        wrote(path)


@app.command(name="basin-network")
def basin_network(
    write: bool = typer.Option(
        False, "--write", help="Persist data/reference/network/basin-network.yaml."
    ),
) -> None:
    """The BOSC network synthesis: the Maumee watershed points as one connected basin.

    Joins the curated basin topology (sink + shared TMDL + per-node position) with each node's
    committed economy / grid / toxics artifacts and its low-flow screen, into one upstream->
    downstream cross-site comparison. The screen is one dimension; nodes on ungaged tributaries
    or with no ECHO receiving water are reported unscreened (the data gap is itself a finding).
    Read-only over committed reference data.
    """
    from watermark.network import build_basin_network, write_basin_network

    net = build_basin_network(settings=get_settings())
    console.print(
        f"[bold]BOSC network[/] - {len(net.nodes)} watershed points draining to [bold]{net.sink}[/]"
    )
    console.print(f"[dim]shared constraint: {net.shared_constraint}[/]\n")
    table = Table(
        "node",
        "subtree",
        "-> downstream",
        "regime",
        "screen",
        # c/kWh is the EIA-861 bundled-SSO COHORT price, not an all-sector or industrial
        # rate (G3/#1644) — the header says which cohort so the column can't be read as
        # "what a campus pays here".
        "grid (holding . SSO c/kWh)",
        "jobs chg",
        "mfg/info LQ",
    )
    flagcolor = {"violation": "red", "tight": "yellow", "ok": "green"}
    for n in net.nodes:
        s = n.screen
        if s.status == "screened" and s.dilution_ratio is not None:
            screen = f"[{flagcolor.get(s.flag or '', 'white')}]{s.flag} {s.dilution_ratio:.2f}:1[/]"
        else:
            screen = f"[dim]{s.status}[/]"
        grid = n.grid.holding_company or "-"
        if n.grid.avg_price_cents_kwh is not None:
            grid += f" . {n.grid.avg_price_cents_kwh:.1f}c"
        jobs = (
            "-"
            if n.economy.employment_change_pct is None
            else f"{n.economy.employment_change_pct:+.1f}%"
        )
        mfg = "-" if n.economy.manufacturing_lq is None else f"{n.economy.manufacturing_lq:.1f}"
        info = "-" if n.economy.information_lq is None else f"{n.economy.information_lq:.1f}"
        node_label = f"{n.place}{' [cyan](DC)[/]' if n.activity.has_disclosed_facility else ''}"
        table.add_row(
            node_label,
            n.subtree,
            n.downstream,
            n.regime.replace("_", " "),
            screen,
            grid,
            jobs,
            f"{mfg}/{info}",
        )
    console.print(table)
    screened = sum(n.screen.status == "screened" for n in net.nodes)
    console.print(
        f"\n[dim]{screened}/{len(net.nodes)} nodes low-flow-screenable; the rest are unscreened "
        f"(ungaged tributary / no ECHO receiving water) - the data gap is itself a finding.[/]"
    )
    if write:
        out = write_basin_network(net, settings=get_settings())
        console.print(f"[green]wrote[/] {out}")


@app.command(name="basin-route")
def basin_route(
    return_period: int = typer.Option(
        25, "--return-period", help="Design storm return period (yr)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture rainfall only; no NOAA fetch."
    ),
    write: bool = typer.Option(
        False, "--write", help="Persist data/reference/hydrology/routed-hydrograph.yaml."
    ),
) -> None:
    """Route the loop's design-storm hydrographs down the cited confluence graph (#1184).

    Generates an SCS design-storm hydrograph at each contributing subcatchment (reaches.yaml),
    routes each downstream through Muskingum-Cunge, and superposes them at confluences — so the
    outlet peak is ATTENUATED and LAGGED, not the arithmetic sum of the tributary peaks. The
    time-varying counterpart to `watermark network` (which routes steady-state low flow).
    Tier-0 screening, not a calibrated HEC-RAS model.
    """
    from watermark.hydrology import hydrograph_routing as hydrograph
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    rn, findings = hydro_stage.run_storm_network(
        return_period_yr=return_period, settings=settings, live=True
    )
    if rn is None:
        console.print(
            "[yellow]No routing inputs[/] (data/reference/hydrology/network.yaml + reaches.yaml)."
        )
        raise typer.Exit(1)

    loop = f"{rn.site} loop" if rn.site else "The loop"
    console.print(
        f"[bold]{loop} {rn.return_period_yr}-yr storm[/] "
        f"({rn.storm_depth_in:.2f} in, 24-hr) — routed down the cited confluence graph"
    )
    table = Table(
        "reach",
        "length (ft)",
        "sub-reaches",
        "Courant",
        "in peak (cfs)",
        "out peak (cfs)",
        "attenuation",
        "lag (hr)",
    )
    for r in rn.reaches:
        table.add_row(
            r.name,
            f"{r.length_ft:,.0f}",
            f"{r.subreaches}",
            f"{r.courant:.2f}",
            f"{r.inflow_peak_cfs:,.0f}",
            f"{r.outflow_peak_cfs:,.0f}",
            f"{r.attenuation_pct:g}%",
            f"{r.lag_hr:g}",
        )
    console.print(table)
    console.print(
        f"\n[bold]Outlet peak[/]: naive sum Σ[bold]{rn.summed_peak_cfs:,.0f}[/] cfs → routed "
        f"[bold]{rn.routed_peak_cfs:,.0f}[/] cfs "
        f"([green]{rn.peak_attenuation_pct:g}% attenuated[/], lagged [bold]{rn.lag_hr:g} hr[/])."
    )
    for f in findings:
        console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")
    for w in rn.warnings:
        console.print(f"[dim]! {w}[/]")
    console.print(
        "\n[dim]Tier-0 Muskingum-Cunge screening; reach geometry + subcatchments are "
        "cited/assumed (reaches.yaml), not a calibrated HEC-RAS model.[/]"
    )
    if write:
        path = hydrograph.write_routed_hydrograph(rn, settings=settings)
        console.print(f"[green]wrote[/] {path}")


@app.command(name="derive-low-flows")
def derive_low_flows(
    offline: bool = typer.Option(
        False, "--offline", help="Use cached NWIS records only; never fetch."
    ),
) -> None:
    """Regenerate the derived mainstem 7Q10 reference (USGS NWIS daily record -> LP3)."""
    from watermark.hydrology.basin import derive_basin_low_flows, write_derived_low_flows

    settings = offline_settings("hydro", offline)
    streams = derive_basin_low_flows(settings=settings)
    path = write_derived_low_flows(streams, settings=settings)
    console.print(f"[green]Wrote[/] {path} — {len(streams)} mainstem 7Q10s:")
    for name, entry in streams.items():
        console.print(
            f"  {name.title():22} {entry['seven_q10_cfs']:8.2f} cfs  "
            f"[dim]gage {entry['gage']} ({entry['complete_years']} yr)[/]"
        )


@app.command(name="dewatering-discharge")
def dewatering_discharge_cmd(
    write: bool = typer.Option(
        False, "--write", help="Regenerate the committed dewatering-discharge report YAML."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture NWIS records only; never fetch."
    ),
) -> None:
    """Screen the USGS gage record for the dewatering discharge + reservoir-recharge context.

    Compares the reach gain between the campus's bracketing gages (Ottawa @ Lima -> near Kalida)
    over the documented pumping window vs. a prior-year baseline. Gage discharge is [verified] USGS
    daily values; every reach-gain attribution is [inference]. `--write` refreshes the committed
    report the `dewatering` bundle feed reads offline.
    """
    from watermark.hydrology import dewatering_discharge as dd
    from watermark.hydrology.dewatering import DATASET_ASOF

    settings = offline_settings("hydro", offline)
    report = dd.build_discharge_report(as_of=DATASET_ASOF.isoformat(), settings=settings)
    if report is None:
        console.print("[yellow]No dewatering discharge reach configured for the active site.[/]")
        return
    sc = report.screen
    if sc is not None:
        verdict = "[green]not separable[/]" if not sc.separable else "[red]elevated[/]"
        console.print(
            f"[bold]{sc.upstream_name} -> {sc.downstream_name}[/] discharge screen: {verdict}"
        )
        console.print(
            f"  expected discharge up to {sc.expected_discharge_cfs.value:g} cfs; baseflow residual "
            f"delta {sc.baseflow_resid_delta_cfs:+g} cfs, low-flow floor delta "
            f"{sc.upstream_floor_delta_cfs:+g} cfs"
        )
        console.print(f"  [dim]{sc.note}[/]")
    rr = report.reservoir_recharge
    if rr is not None:
        console.print(
            f"[bold]{rr.gage_name}[/] recharge: median {rr.window_median_cfs:g} cfs, "
            f"{rr.window_refill_days}/{rr.window_days} days above the {rr.passby_cfs:g} cfs passby "
            f"(baseline {rr.baseline_refill_days}/{rr.baseline_days})"
        )
    if write:
        path = dd.discharge_report_path(settings)
        if path is None:
            console.print(
                "[yellow]Active site has no dewatering_discharge_relpath; not written.[/]"
            )
            return
        dd.write_discharge_report(report, path)
        console.print(f"[green]Wrote[/] {path}")


@app.command()
def storm(
    return_period: int = typer.Option(
        25, "--return-period", help="Design storm return period (yr)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture rainfall only; no NOAA fetch."
    ),
) -> None:
    """Tier-0 pre- vs post-development design-storm runoff for the campus footprint."""
    from watermark.hydrology import stormwater
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    runoff, findings = hydro_stage.run_storm(
        return_period_yr=return_period, settings=settings, live=True
    )
    # The post cover is the ASWCD-calibrated composite when the footprint is committed
    # (only ~115 of ~344 ac impervious); else the blanket near-impervious full-buildout bound.
    post_cover = (
        "campus (ASWCD-calibrated)"
        if stormwater.load_site_footprint(settings)
        else "impervious campus"
    )

    tag = {"document": "doc", "connector": "live", "assumption": "assume", "derived": "calc"}
    console.print(
        f"[bold]{runoff.name}[/]  {runoff.area.value:,.0f} ac "
        f"[dim]({tag[runoff.area.source]})[/]  "
        f"storm {runoff.storm.return_period_yr}-yr 24-hr "
        f"{runoff.storm.depth.value:.2f} in [dim]({tag[runoff.storm.depth.source]})[/]"
    )
    table = Table("case", "land cover", "CN", "Tc (hr)", "peak (cfs)", "volume (ac-ft)")
    table.add_row(
        "pre-development",
        "cropland",
        f"{runoff.pre.curve_number:.0f}",
        f"{runoff.pre.tc_hr:g}",
        f"{runoff.pre.peak_cfs:,.0f}",
        f"{runoff.pre.volume_acft:,.0f}",
    )
    table.add_row(
        "post-development",
        post_cover,
        f"{runoff.post.curve_number:.0f}",
        f"{runoff.post.tc_hr:g}",
        f"{runoff.post.peak_cfs:,.0f}",
        f"{runoff.post.volume_acft:,.0f}",
    )
    console.print(table)

    for f in findings:
        console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")
    rainfall_src = (
        "live NOAA Atlas-14"
        if runoff.storm.depth.source == "connector"
        else ("cited NOAA Atlas-14 depth (offline)")
    )
    console.print(
        f"\n[dim]Tier-0 SCS screening. HSG {('ABCD'[int(runoff.hsg.value) - 1])} and land cover "
        f"are cited assumptions; footprint is document-sourced; rainfall is {rainfall_src}. "
        f"See `watermark storm-discharge` for the 60-in outfall + Dug Run screen.[/]"
    )


@app.command(name="storm-discharge")
def storm_discharge(
    return_period: int = typer.Option(
        25, "--return-period", help="Design storm return period for the headline screen (yr)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture rainfall only; no NOAA fetch."
    ),
    write: bool = typer.Option(
        False, "--write", help="Regenerate data/reference/hydrology/bosc-stormwater-discharge.yaml."
    ),
) -> None:
    """ASWCD-calibrated campus storm discharge: composite CN, 60-in outfall, Dug Run.

    Calibrated to the SWCD-declared footprint (only ~115 of ~344 ac permanently impervious),
    so the post-development CN is an area-weighted composite, not a blanket impervious parcel.
    Screens the single 60-inch outfall's Manning full-flow capacity and reads the design-storm
    peak against Dug Run's cited 7Q10 — the receiving water the inspections call "the creek
    west of the site."
    """
    from watermark.hydrology import stormwater
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    screen, findings = hydro_stage.run_discharge_screen(
        settings=settings, live=True, design_return_period_yr=return_period
    )

    tag = {
        "document": "doc",
        "connector": "live",
        "reference": "ref",
        "assumption": "assume",
        "derived": "calc",
    }
    console.print(
        f"[bold]{screen.site}[/]\n"
        f"footprint {screen.footprint_area.value:,.0f} ac "
        f"[dim]({tag[screen.footprint_area.source]})[/]  HSG "
        f"{'ABCD'[int(screen.hsg.value) - 1]}  outfall {screen.outfall_diameter_in.value:.0f} in "
        f"[dim]({tag[screen.outfall_diameter_in.source]})[/]"
    )
    console.print(
        f"[dim]post CN[/] as-permitted [bold]{screen.post_cn_as_permitted:g}[/] "
        f"({screen.cover_breakdown}) vs pre {screen.pre_cn:g} "
        f"[dim]| full-buildout bound {screen.post_cn_full_buildout:g}[/]"
    )
    table = Table(
        "storm",
        "depth (in)",
        "pre (cfs)",
        "post (cfs)",
        "post wet AMC-III (cfs)",
        "full-buildout (cfs)",
    )
    for p in screen.peaks:
        table.add_row(
            f"{p.return_period_yr}-yr",
            f"{p.depth_in:.2f}",
            f"{p.pre_peak_cfs:,.0f}",
            f"{p.post_peak_cfs:,.0f}",
            f"{p.post_peak_wet_cfs:,.0f}" if p.post_peak_wet_cfs is not None else "-",
            f"{p.full_buildout_peak_cfs:,.0f}",
        )
    console.print(table)
    cap = Table("60-in outfall slope", "full-flow capacity (cfs)")
    for c in screen.outfall_capacity:
        cap.add_row(f"{c.slope_pct:g}%", f"{c.capacity_cfs:,.0f}")
    console.print(cap)
    console.print(f"[dim]{screen.receiving_note}[/]")
    rd = screen.routed_discharge
    if rd is not None:
        console.print(
            f"[dim]routed[/] {rd.return_period_yr}-yr outfall peak {rd.at_outfall_peak_cfs:,.0f} cfs "
            f"-> [bold]{rd.routed_peak_cfs:,.0f} cfs[/] at the {rd.receiving_water} confluence "
            f"({rd.attenuation_pct:g}% attenuated, +{rd.lag_hr:g} hr) "
            f"[dim]over {rd.reach_length_ft.value:,.0f} ft ({rd.reach_path})[/]"
        )
    for f in findings:
        console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")
    if write:
        path = stormwater.write_discharge_screen(screen, settings=settings)
        console.print(f"[green]wrote[/] {path}")
    console.print(
        "\n[dim]Tier-0 SCS screening; post cover calibrated to the ASWCD footprint. The "
        "receiving-water peak is routed (Tier-0 Muskingum-Cunge on stated reach assumptions); "
        "not a calibrated hydraulic model or a permit determination.[/]"
    )


@app.command()
def scenario(
    cooling_demand: float | None = typer.Option(
        None,
        "--cooling-demand",
        help="Override campus cooling intake (MGD). Default: sourced basis.",
    ),
    consumptive_fraction: float | None = typer.Option(
        None,
        "--consumptive-fraction",
        help="Override evaporated fraction (0..1). Default: sourced basis.",
    ),
    cooling_model: str | None = typer.Option(
        None,
        "--cooling-model",
        help=(
            "Override the cooling archetype (off | evaporative_tower | once_through | "
            "closed_loop_dry | hybrid_adiabatic | unknown). Default: the site facility's model."
        ),
    ),
    write: bool = typer.Option(False, "--write", help="Persist results under data/scenarios/."),
    offline: bool = typer.Option(False, "--offline", help="Use cached/fixture streamflow only."),
) -> None:
    """Baseline vs data-center buildout: net consumptive draw vs the receiving-water 7Q10."""
    from watermark.hydrology import cooling_models
    from watermark.hydrology import scenario as scenario_stage
    from watermark.pipeline import hydrology as hydro_stage
    from watermark.sites import CoolingModelType

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    if cooling_model is not None:
        try:
            CoolingModelType(cooling_model)
        except ValueError:
            console.print(
                f"[red]unknown cooling model {cooling_model!r}[/]; "
                f"choose one of: {', '.join(m.value for m in CoolingModelType)}"
            )
            raise typer.Exit(code=1) from None
    base, build, delta = hydro_stage.run_scenarios(
        cooling_demand_mgd=cooling_demand,
        consumptive_fraction=consumptive_fraction,
        cooling_model=cooling_model,
        settings=settings,
        live=True,
    )

    basis = build.scenario.basis
    if basis is not None:
        spec = cooling_models.get(basis.cooling_model)
        alias = f" ('{spec.alias}')" if spec.alias else ""
        console.print(
            f"[bold]Cooling model[/]: {basis.cooling_model.value}{alias} — {spec.mechanism}"
        )
        assumptions = [f"IT load {basis.it_load.value:g} MW"]
        if basis.wue is not None:
            assumptions.append(f"WUE {basis.wue.value:g} L/kWh")
        if basis.cycles_of_concentration is not None:
            assumptions.append(f"CoC {basis.cycles_of_concentration.value:g}")
        console.print(f"  [bold]Design basis[/] (sourced): {', '.join(assumptions)}")
        rng = cooling_models.consumptive_range_label(basis)
        span = basis.consumptive_low.value != basis.consumptive_high.value
        if basis.is_bracketed:
            console.print(
                f"  [bold yellow]cooling method undisclosed[/] — bracketed range "
                f"[bold]{rng}[/]; no single consumptive estimate"
            )
        else:
            console.print(
                f"  consumptive estimate{' range' if span else ''}: "
                f"[bold]{rng}[/] [dim]({basis.method})[/]"
            )

    table = Table("scenario", "cooling intake", "consumptive frac", "net basin loss (cfs)", "src")
    for r in (base, build):
        table.add_row(
            r.scenario.name,
            f"{r.scenario.cooling_demand.value:g} MGD",
            f"{r.scenario.consumptive_fraction.value:g}",
            f"{r.consumptive_loss.value:,.2f}",
            r.scenario.cooling_demand.source[:4],
        )
    console.print(table)

    rw = delta.receiving_water_name or "receiving water"
    q7 = delta.receiving_7q10_cfs
    live_flow = build.receiving_live.value if build.receiving_live else None
    console.print(
        f"\n[bold red]Buildout adds {delta.consumptive_increase_cfs:,.2f} cfs[/] of net "
        f"consumptive draw on the {rw} supply."
    )
    if delta.multiple_of_7q10 is not None:
        console.print(
            f"That is [bold]{delta.multiple_of_7q10:g}x[/] the {rw}'s cited 7Q10 "
            f"low flow ({q7:g} cfs)"
            + (f"; live flow now {live_flow:,.0f} cfs." if live_flow else ".")
        )
    # Seasonal screen: the draw against the regulatory summer-season design low flow (the cited
    # permit window, #1624). The basis rides along so a hybrid facility's draw is month-varying.
    sw = scenario_stage.evaluate_seasonal(
        build.consumptive_loss.value, settings=settings, basis=basis
    )
    if sw is not None and sw.summer_multiple is not None:
        summer_win_months = [m.month for m in sw.months if m.low_flow_basis == "30Q10 summer"]
        win = f"{summer_win_months[0]}-{summer_win_months[-1]}" if summer_win_months else "summer"
        console.print(
            f"\n[bold]Seasonal pinch[/] — in the [bold]{win}[/] regulatory summer season, the "
            f"draw is [bold red]{sw.summer_multiple:g}x[/] the cited summer 30Q10 "
            f"({sw.summer_30q10_cfs:g} cfs), vs {sw.annual_multiple:g}x the annual 7Q10. "
            f"The absolute floor is 1Q10 = {sw.one_q10_cfs:g} cfs — no flow to draw against."
        )
    console.print(
        f"\n[dim]Cooling basis derived per the site facility's cooling archetype (see "
        f"provenance tags); {rw} 7Q10 is cited from the NPDES permit fact sheet. "
        f"Tier-0 screening.[/]"
    )
    if write:
        for r in (base, build):
            path = scenario_stage.write_scenario(r, settings=settings)
            wrote(path)


@app.command(name="hydro-hypotheses")
def hydro_hypotheses(
    level: str | None = typer.Option(
        None, "--level", help="Filter to one level: macro | local | site."
    ),
    cooling_demand: float | None = typer.Option(
        None, "--cooling-demand", help="Override campus cooling intake (MGD)."
    ),
    consumptive_fraction: float | None = typer.Option(
        None, "--consumptive-fraction", help="Override evaporated fraction (0..1)."
    ),
    write: bool = typer.Option(
        False, "--write", help="Persist the comparison under data/scenarios/."
    ),
    offline: bool = typer.Option(False, "--offline", help="Use cached/fixture streamflow only."),
) -> None:
    """Compare BOSC-routing / cooling hypotheses at macro/local/site level vs the baseline."""
    import yaml

    from watermark.hydrology import hypothesis as hyp_stage

    settings = offline_settings("hydro", offline)
    hyps = hyp_stage.default_hypotheses(
        cooling_demand_mgd=cooling_demand, consumptive_fraction=consumptive_fraction
    )
    if level is not None:
        hyps = [h for h in hyps if h.level == level]
        if not hyps:
            console.print(f"[yellow]No default hypotheses at level '{level}'.[/]")
            raise typer.Exit()
    comparison = hyp_stage.run_hypotheses(hyps, settings=settings, live=True)

    table = Table(
        "hypothesis", "level", "net loss (cfs)", "x7Q10", "BOSC routes (built)", "held out"
    )
    for hr in comparison.hypotheses:
        built = ", ".join(r.via for r in hr.routing_applied) or "—"
        held = ", ".join(r.via for r in hr.excluded_theorized) or "—"
        x7 = hr.diff_vs_baseline.multiple_of_7q10
        table.add_row(
            hr.hypothesis.name,
            hr.hypothesis.level,
            f"{hr.result.consumptive_loss.value:,.2f}",
            f"{x7:g}x" if x7 is not None else "—",
            built,
            held,
        )
    console.print(table)
    for hr in comparison.hypotheses:
        for br in hr.excluded_theorized:
            console.print(
                f"[dim]{hr.hypothesis.name}: held out {br.via} → {', '.join(br.to)} "
                f"(status: {br.status}) — Shawnee II has no confirmed BOSC routing.[/]"
            )
    console.print(
        "\n[dim]`level` frames the same Lima-loop numbers against its scale (macro=Maumee "
        "basin); routing overrides re-label which forcemains are built, not the dilution math.[/]"
    )
    if write:
        out_dir = settings.scenarios_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "hypotheses.comparison.yaml"
        path.write_text(
            # mode="json" coerces enums (e.g. CoolingModelType) and other rich types to
            # YAML-safe scalars; a bare model_dump() leaves enum members that safe_dump can't
            # represent.
            yaml.safe_dump(comparison.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        wrote(path)


@app.command(name="tier1")
def tier1(
    return_period: int = typer.Option(
        25, "--return-period", help="Design storm return period (yr)."
    ),
    offline: bool = typer.Option(False, "--offline", help="Use cached/fixture rainfall only."),
    write: bool = typer.Option(
        False,
        "--write",
        help="Persist the decks + result to data/reference/hydrology/ (requires the engine).",
    ),
) -> None:
    """Tier-1 EPA SWMM: detention sizing + sanitary wet-weather surcharge."""
    from watermark.hydrology.tier1 import run_tier1, tier1_findings, write_tier1

    settings = offline_settings("hydro", offline)
    result = run_tier1(return_period_yr=return_period, settings=settings, live=True)
    if not result.available:
        console.print(f"[yellow]{result.note}[/]")
        console.print(
            "[dim]Install the engine: `uv add pyswmm` (and, on Apple Silicon, ad-hoc "
            "codesign the swmm-toolkit native libs).[/]"
        )
        raise typer.Exit()

    d = result.detention
    if d is not None:
        console.print(
            f"[bold]Stormwater detention[/] (SWMM, {return_period}-yr 24-hr storm)\n"
            f"  pre-development peak  {d.pre_peak_cfs:,.0f} cfs\n"
            f"  post-development peak {d.post_peak_cfs:,.0f} cfs [dim](undetained)[/]\n"
            f"  -> a [bold]{d.required_storage_acft:,.0f} ac-ft[/] basin "
            f"({d.basin_area_acres:g} ac, {d.orifice_diam_ft:g} ft orifice) holds the release to "
            f"{d.controlled_peak_cfs:,.0f} cfs"
        )
        inv = result.inventory
        if inv is not None and not inv.detention_shown:
            console.print(
                f"  [dim]grounded:[/] {inv.phase} {inv.sheet_id} shows piped conveyance with "
                f"[red]no on-site detention[/] — the sized basin is the absent control"
            )
    console.print(
        "\n[bold]Sanitary wet-weather surcharge[/] "
        "[dim](campus contribution vs documented wet-weather headroom)[/]"
    )
    for f in tier1_findings(result):
        if f.check in ("wet-weather-surcharge", "sso-mandate"):
            console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")
    console.print(
        "\n[dim]Tier-1 EPA SWMM. Footprint/storm/plant design flows document/connector-sourced; "
        "imperviousness, RDII R, and basin geometry are assumptions.[/]"
    )
    if write:
        path = write_tier1(result, settings=get_settings())
        console.print(
            f"[green]Wrote[/] {path} + {len(result.decks)} .inp decks "
            f"[dim]({result.engine}, continuity "
            f"{max((abs(d.continuity_error_pct) for d in result.decks), default=0.0):.2f}%)[/]"
        )


@app.command(name="storm-plan")
def storm_plan(
    refresh: bool = typer.Option(
        False, "--refresh", help="Re-parse the source drawing and rewrite the artifact."
    ),
) -> None:
    """Document-grounded drainage inventory from the campus grading & storm plan."""
    from watermark.hydrology import stormplan

    settings = get_settings()
    if refresh:
        inv = stormplan.refresh_inventory(settings=settings)
        console.print(f"[green]Refreshed[/] {settings.data_dir / stormplan._INVENTORY_REL}")
    else:
        loaded = stormplan.load_inventory(settings=settings)
        if loaded is None:
            console.print("[yellow]No inventory yet — run `watermark storm-plan --refresh`.[/]")
            raise typer.Exit()
        inv = loaded

    pipes = ", ".join(f'{s:g}"' for s in inv.pipe_sizes_in)
    eng = f"; {inv.engineer}" if inv.engineer else ""
    console.print(
        f"[bold]{inv.sheet_id}[/] {inv.discipline} [dim]({inv.phase}, {inv.status}{eng})[/]\n"
        f"  graded relief {inv.rim_min.value:.1f}-{inv.rim_max.value:.1f} ft "
        f"([bold]{inv.relief.value:.1f} ft[/]) over {inv.rim_labels} storm-structure rims "
        f"[dim](doc)[/]\n"
        f"  conveyance: {', '.join(s.lower() for s in inv.structure_types)}\n"
        f"  pipe callouts: {pipes}\n"
        f"  features: {', '.join(f.lower() for f in inv.conveyance_features)}"
    )
    for f in stormplan.storm_plan_findings(inv):
        console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")
    console.print(
        "\n[dim]Transcribed from the civil sheet; pipe connectivity/inverts are vector "
        "geometry with no schedule table, so a routable network is not fabricated.[/]"
    )


@app.command(name="hydro-report")
def hydro_report(
    write: bool = typer.Option(False, "--write", help="Write docs/HYDROLOGY.md."),
    live: bool = typer.Option(
        False, "--live", help="Use live connectors (default: offline/deterministic)."
    ),
) -> None:
    """Render (or write) the evidence-tagged hydrology dossier section."""
    from watermark.hydrology import report

    settings = offline_settings("hydro", not live)
    if write:
        path = report.write_report(settings=settings, live=live)
        wrote(path)
    else:
        console.print(report.render_report(settings=settings, live=live), markup=False)


@app.command(name="corridor")
def corridor_cmd(
    in_corridor: bool = typer.Option(
        False, "--in", help="Only features inside the corridor study area."
    ),
    update_map: bool = typer.Option(
        False, "--map", help="Merge the corridor + roadwork layers into the GIS findings GeoJSON."
    ),
) -> None:
    """Tie BOSC facilities / parcels / roadwork to the North Cole Street corridor.

    A spatial join of every watch item (facilities + force mains) and recorded parcel
    onto the frozen Periplus corridor geometry: in-study-area flag, distance to the
    nearest corridor route, the route, and station (chainage) along the roadwork
    centerline. Read-only and hermetic (committed GeoJSON only). ``--map`` writes the
    corridor study area + roadwork centerline into ``data/site/gis-findings.geojson``.
    """
    import json

    from watermark.gis.corridor import build_corridor_view

    settings = get_settings()
    view = build_corridor_view(settings=settings)

    console.print(
        f"[bold]North Cole Street corridor[/] — study area {view.study_area_acres:,.0f} ac, "
        f"road centerline {view.road_length_m:,.0f} m; "
        f"{len(view.in_corridor)}/{len(view.members)} features in the corridor."
    )
    routes = Table("role", "length (m)", "route")
    for r in view.routes:
        routes.add_row(r.role, f"{r.length_m:,.0f}" if r.length_m else "—", r.name[:48])
    console.print(routes)

    members = view.in_corridor if in_corridor else view.members
    table = Table("in", "kind", "feature", "dist→route (m)", "via", "station (m)")
    for m in members:
        station = f"{m.station_m:,.0f}" if m.station_m is not None else "—"
        table.add_row(
            "✓" if m.in_study_area else "",
            m.kind,
            m.id[:32],
            f"{m.distance_to_route_m:,.0f}",
            m.nearest_route_role,
            station,
        )
    console.print(table)
    console.print(f"[dim]source: {view.source}[/]")

    if update_map:
        from watermark.site import gismap

        geojson = settings.data_dir / "site" / "gis-findings.geojson"
        if geojson.is_file():
            fc = json.loads(geojson.read_text(encoding="utf-8"))
            fc, n = gismap.merge_corridor_layer(fc, settings=settings)
            geojson.write_text(json.dumps(fc, indent=1), encoding="utf-8")
            console.print(f"[green]Merged[/] {n} corridor/roadwork features into {geojson}")
        else:
            console.print(f"[yellow]No GIS findings GeoJSON at {geojson}; skipped --map.[/]")


@app.command(name="drainage-audit")
def drainage_audit_cmd(
    offline: bool = typer.Option(
        False, "--offline", help="Use the committed/fixture Atlas-14 data only; never fetch."
    ),
    write_ddf: bool = typer.Option(
        False, "--write-ddf", help="Regenerate the committed corridor Atlas-14 DDF reference."
    ),
) -> None:
    """Audit the OPC drainage scope against the corridor design storm + the 95% plan.

    Decomposes each Tetra Tech roundabout OPC's DRAINAGE section into sized conveyance
    vs lump-sum allocation, and reads it against the committed NOAA Atlas-14 corridor
    DDF and the 95% SPS storm plan (which shows no detention). A design-basis /
    scope-completeness audit — it does not size the roundabouts' hydraulics.
    """
    from watermark.hydrology import drainage

    settings = offline_settings("hydro", offline)

    if write_ddf:
        ddf = drainage.build_corridor_ddf(settings=settings)
        path = drainage.write_corridor_ddf(ddf, settings=settings)
        wrote(path)

    audit = drainage.build_drainage_audit(settings)

    table = Table("sub-estimate", "drainage $", "breakdown", "sized $", "lump-sum $", "sized %")
    for s in audit.scopes:
        if s.itemized:
            frac = f"{s.sized_fraction:.0%}" if s.sized_fraction is not None else "—"
            sized = (
                f"{'~' if s.sized_amount_approximate else ''}{s.sized_amount:,}"
                if s.sized_amount is not None
                else "—"
            )
            lump = (
                f"{'~' if s.lump_sum_amount_approximate else ''}{s.lump_sum_amount:,}"
                if s.lump_sum_amount is not None
                else "—"
            )
            table.add_row(
                s.name[:34],
                f"{s.drainage_subtotal:,}" if s.drainage_subtotal else "—",
                "itemized",
                sized,
                lump,
                frac,
            )
        else:
            table.add_row(
                s.name[:34],
                f"{s.drainage_subtotal:,}" if s.drainage_subtotal else "—",
                "[yellow]subtotal only[/]",
                "—",
                "—",
                "—",
            )
    console.print(table)

    if audit.ddf is not None:
        d = audit.ddf
        depths = ", ".join(f'{rp}-yr {d.depth("24-hr", rp):.2f}"' for rp in d.return_periods)
        console.print(f"\n[bold]Atlas-14 corridor design storm[/] (24-hr): {depths}")

    console.print("\n[bold]Findings[/]")
    for f in audit.findings:
        mark = "[green]ok[/]" if f.ok else "[red]gap[/]"
        console.print(f"  {mark} [{f.check}] {f.detail}")
    console.print(
        f"\n[dim]${audit.meta['program_drainage_total']:,} drainage program-wide; "
        f"{audit.meta['itemized_count']}/{audit.meta['sub_estimate_count']} estimates itemized. "
        "Scope/design-basis audit — roundabout hydraulics are not sized (no footprint area).[/]"
    )


@app.command(name="lowflow-freq")
def lowflow_freq(
    site: str = typer.Option(
        "04187100", "--site", help="USGS NWIS gage (default: Ottawa at Lima)."
    ),
    receiving_water: str = typer.Option(
        "Ottawa River", "--receiving", help="Receiving water whose cited 7Q10 to corroborate."
    ),
    start: str = typer.Option("1980-01-01", "--start", help="Record start date (ISO)."),
    end: str = typer.Option("2024-12-31", "--end", help="Record end date (ISO)."),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Use the cached/committed gage record only; never touch the network.",
    ),
    write: bool = typer.Option(
        False, "--write", help="Persist to data/reference/hydrology/low-flow-frequency.yaml."
    ),
) -> None:
    """Independently COMPUTE the 1Q10/7Q10/30Q10 from the USGS daily-discharge record.

    Reproduces the design low flows Ohio EPA cites from a fact sheet but never shows
    its work for (log-Pearson III + Weibull on climatic-year n-day minima), and reads
    each against the cited regulatory value. The computed figures are `derived` — a
    screening corroboration, not a substitute for the cited 7Q10.
    """
    from watermark.hydrology import lowflow_frequency as lf

    settings = get_settings()
    if offline:
        settings = Settings(
            data_dir=settings.data_dir,
            hydro_offline=True,
            hydro_fixtures_dir=repo_fixtures_dir("hydrology"),
        )

    lff = lf.compute_low_flow_frequency(
        site_no=site,
        receiving_water=receiving_water,
        start_date=start,
        end_date=end,
        settings=settings,
    )
    console.print(
        f"[bold]{lff.site_name}[/] (NWIS {lff.site_no}) — "
        f"{lff.period_start}..{lff.period_end}, {lff.complete_years} complete climatic years"
    )
    table = Table(
        "Statistic", "LP3 (cfs)", "Weibull (cfs)", "log-skew", "dry frac", "cited", "corroborates"
    )
    for s in lff.statistics:
        cited = f"{s.cited_cfs.value:g} ({s.cited_basis})" if s.cited_cfs else "—"
        mark = "—" if s.corroborates is None else ("[green]✓[/]" if s.corroborates else "[red]✗[/]")
        table.add_row(
            s.label,
            f"{s.lp3_cfs.value:g}",
            f"{s.weibull_cfs.value:g}",
            f"{s.log_skew:g}",
            f"{s.zero_fraction:g}",
            cited,
            mark,
        )
    console.print(table)

    hm = lff.harmonic_mean
    if hm is not None:
        cited = f"{hm.cited_cfs.value:g}" if hm.cited_cfs else "—"
        mark = (
            "—" if hm.corroborates is None else ("[green]✓[/]" if hm.corroborates else "[red]✗[/]")
        )
        console.print(
            f"[bold]Harmonic mean[/] (human-health design flow): "
            f"[bold]{hm.computed_cfs.value:g} cfs[/] over {hm.n_days} non-zero days"
            + (f" ({hm.zero_days} zero-flow days excluded)" if hm.zero_days else "")
            + f" — cited {cited} {mark}"
        )

    if write:
        path = lf.write_low_flow_frequency(lff, settings=get_settings())
        wrote(path)


@app.command(name="supply")
def supply_cmd() -> None:
    """Screen the campus draw against Lima's reservoir storage (the supply water-budget).

    The intake-side counterpart to `watermark network`. Lima's supply is five upground
    (off-stream) reservoirs (~15 BG) filled from the Auglaize + Ottawa at high flow, so
    the low-flow constraint is reservoir DRAWDOWN, not a 7Q10 intake. Reports the
    drought-reserve drawdown, the campus's share of plant production, and the net basin
    loss.
    """
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    supply, budget, findings = hydro_stage.run_water_budget(settings=settings)
    if supply is None or budget is None:
        console.print("[yellow]No supply system[/] (data/reference/hydrology/water-supply.yaml).")
        raise typer.Exit(1)

    by_river = supply.storage_by_river()
    river_txt = ", ".join(f"{r} {mg / 1000:.1f} BG" for r, mg in sorted(by_river.items()))
    console.print(
        f"[bold]Lima water supply[/] — {len(supply.reservoirs)} upground reservoirs, "
        f"[bold]{supply.total_storage_mg / 1000:.1f} BG[/] off-stream storage ({river_txt}); "
        f"treats ~{supply.current_production.value:g} MGD (rated {supply.plant_capacity.value:g})."
    )
    table = Table("reservoir", "built", "capacity (MG)", "source river")
    for r in supply.reservoirs:
        table.add_row(r.name, str(r.built), f"{r.capacity_mg:g}", r.source_river)
    console.print(table)
    console.print(
        f"Campus makeup [bold]{budget.campus_makeup.value:g} MGD[/] "
        f"([bold]{budget.campus_share_pct:g}%[/] of {budget.gross_production_mgd:g} MGD gross); "
        f"drought reserve [bold]{budget.drought_reserve_days_baseline:g}[/] -> "
        f"[bold]{budget.drought_reserve_days_buildout:g}[/] days "
        f"([red]-{budget.drought_reserve_lost_days:g}[/]); net basin loss "
        f"[bold]{budget.campus_consumptive.value:g} MGD[/]."
    )
    for f in findings:
        console.print(f"  {'·' if f.ok else '!'} {f.detail}", markup=False)
    for w in budget.warnings:
        console.print(f"  ! {w}", markup=False)


@app.command(name="refill")
def refill_cmd(
    write: bool = typer.Option(
        False, "--write", help="Regenerate the committed analysis from the live USGS record."
    ),
) -> None:
    """Can high-flow pumping refill the reservoirs against demand — incl. through drought?

    The flow-side counterpart to `watermark supply`. Reports the normal-year supply surplus and
    the sequent-peak (Rippl) storage the worst gauged drought calls on, city-only vs +campus.
    `--write` re-pulls the Auglaize + Ottawa daily records and rewrites the committed artifact.
    """
    from watermark.hydrology import refill as refill_mod
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if write:
        ra = refill_mod.compute_refill_adequacy(settings=settings)
        path = refill_mod.write_refill_adequacy(ra, settings=settings)
        wrote(path)
        findings = refill_mod.refill_findings(ra)
    else:
        loaded, findings = hydro_stage.run_refill(settings=settings)
        if loaded is None:
            console.print(
                "[yellow]No refill analysis[/] (data/reference/hydrology/refill-adequacy.yaml). "
                "Run [bold]watermark refill --write[/] to generate it."
            )
            raise typer.Exit(1)
        ra = loaded

    console.print(
        f"[bold]Reservoir refill adequacy[/] — combined mean flow "
        f"[bold]{ra.combined_mean_cfs:g} cfs[/] = [bold]{ra.annual_supply_multiple:g}x[/] demand "
        f"in a normal year; gauged {ra.period_start}..{ra.period_end} ({ra.aligned_days:,} days)."
    )
    rt = Table("river", "mean", "median", "p90", "p99", "min", "% days < demand")
    for r in ra.rivers:
        rt.add_row(
            r.river,
            f"{r.mean_cfs:g}",
            f"{r.median_cfs:g}",
            f"{r.p90_cfs:g}",
            f"{r.p99_cfs:g}",
            f"{r.min_cfs:g}",
            f"{r.pct_days_below_demand:g}%" if r.pct_days_below_demand is not None else "—",
        )
    console.print(rt)
    st = Table(
        "demand scenario", "MGD", "storage needed", "% of 14.4 BG", "worst drawdown", "survives"
    )
    for sc in ra.scenarios:
        st.add_row(
            sc.label,
            f"{sc.demand_mgd:g}",
            f"{sc.required_storage_mg:,.0f} MG",
            f"{sc.pct_of_capacity:g}%",
            f"{sc.worst_spell_days}d from {sc.worst_spell_start}",
            "[green]yes[/]" if sc.survives else "[red]NO[/]",
        )
    console.print(st)
    for f in findings:
        console.print(f"  {'·' if f.ok else '!'} {f.detail}", markup=False)
    for c in ra.caveats:
        console.print(f"  ~ {c}", markup=False)


@app.command(name="waterville-monitor")
def waterville_monitor(
    write: bool = typer.Option(
        False, "--write", help="Regenerate the committed read from the live/fixture USGS record."
    ),
) -> None:
    """Read the Maumee-at-Waterville monitor (04193500) against the Napoleon spill (#1498).

    Turbidity / DO / discharge / conductance / fPC across the event window, with a
    travel-time argument that decides whether the storm-timed spikes are the release plume
    or ordinary first-flush. `--write` re-pulls the IV record and rewrites the artifact.
    """
    from watermark.hydrology import waterville_monitor as wm
    from watermark.hydrology.waterville_monitor import monitor_findings

    settings = get_settings()
    if write:
        read = wm.compute_monitor_read(settings=settings)
        wrote(wm.write_monitor_read(read, settings=settings))
    else:
        loaded = wm.load_monitor_read(settings=settings)
        if loaded is None:
            console.print(
                "[yellow]No monitor read[/] "
                "(data/reference/hydrology/toledo/waterville-spill-monitor-read.yaml). "
                "Run [bold]watermark waterville-monitor --write[/] to generate it."
            )
            raise typer.Exit(1)
        read = loaded

    console.print(
        f"[bold]{read.site_name}[/] ({read.site_no}) — continuous monitor "
        f"[dim]{read.window_start}..{read.window_end}[/] vs the Napoleon / Huston Creek spill"
    )
    console.print(
        f"  discharge trough [bold]{read.discharge_min.value:g} cfs[/] "
        f"({read.low_flow_dilution_ratio:g}x the derived 7Q10 {read.seven_q10_cfs.value:g} cfs) → "
        f"storm peak {read.discharge_storm_peak.value:g} cfs"
    )
    st = Table("turbidity spike", "value")
    for s in read.turbidity_spikes:
        st.add_row(s.timestamp[:16], f"{s.value:g} {s.unit}")
    console.print(st)
    console.print(
        f"  reach [bold]{read.reach_river_km.value:g} km[/]; plume travel "
        f"[bold]{read.plume_travel.low:g}-{read.plume_travel.high:g} h[/] "
        f"(release {read.release_start[:10]})",
        markup=True,
    )
    for f in monitor_findings(read):
        console.print(f"  {'·' if f.ok else '!'} {f.detail}", markup=False)
    for c in read.caveats:
        console.print(f"  ~ {c}", markup=False)


@app.command(name="reaches")
def reaches(
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture NLDI responses only; never touch the network."
    ),
    write: bool = typer.Option(
        False, "--write", help="Write data/reference/hydrology/reaches/<site>.geojson."
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help="Output path (default: data/reference/hydrology/reaches/<site>.geojson).",
    ),
) -> None:
    """Navigate the real river centerlines for the reach network (NLDI/NHDPlus, #1235).

    The model reaches (network.yaml/reaches.yaml) carry topology + channel length only —
    no coordinates. This snaps the site's gage + tributary outfalls to the NHDPlus flowline
    network via USGS NLDI, stitches one centerline per reach node, and (with --write) lands
    them as committed reference GeoJSON — the geometry the ReachNetwork feed + FlowLayer viz
    (epic #1237) advect over. Nothing is invented: reaches with no NLDI geometry are skipped.
    """
    from pathlib import Path

    from watermark.hydrology import reach_geometry

    settings = offline_settings("hydro", offline)
    centerlines, warnings = reach_geometry.assemble_reach_network(settings=settings)

    if not centerlines:
        console.print("[yellow]No reach centerlines resolved.[/]")
        for w in warnings:
            console.print(f"[dim]! {w}[/]")
        raise typer.Exit(1)

    table = Table("reach", "name", "→ downstream", "km")
    for c in centerlines:
        table.add_row(c.node_id, c.name, c.downstream or "—", f"{c.length_km:.2f}")
    console.print(table)
    for w in warnings:
        console.print(f"[dim]! {w}[/]")

    if write:
        target = (
            Path(out)
            if out
            else settings.reference_dir / "hydrology" / "reaches" / f"{settings.site}.geojson"
        )
        path = reach_geometry.write_reach_network(centerlines, target)
        wrote(path)


@app.command(name="drawdown")
def drawdown_cmd(
    material: str | None = typer.Option(
        None, "--material", help="Aquifer material to screen (default: the dominant one)."
    ),
    makeup_mgd: float | None = typer.Option(
        None,
        "--makeup-mgd",
        help="Override the hypothetical pumping stress (MGD); default = the site's cooling makeup.",
    ),
) -> None:
    """Groundwater aquifer characterization + a Theis drawdown screen (the well-drawdown thread).

    Reduces the active site's ODNR well-log census (data/reference/ohio-waterwells/) to per-material
    aquifer parameters — static water level, reported yield, a literature-K x census-thickness
    transmissivity BRACKET [inference] — then runs a Theis cone for a HYPOTHETICAL groundwater
    pumping stress (default: the campus cooling makeup, which is actually drawn from municipal
    SURFACE water). Its strongest result is the inverse: pumping a hyperscale load from the
    low-transmissivity limestone aquifer DEWATERS it — corroborating the municipal-water reality
    and bounding the residents' "area well concerns." Everything is [inference], never a headline.
    """
    from watermark.hydrology import aquifer as aq
    from watermark.hydrology import drawdown as dd

    settings = get_settings()
    params = aq.load_aquifer_parameters(settings=settings)
    if params is None:
        console.print(
            "[yellow]No well-log census for the active site — run "
            "`watermark waterwells` first (Ohio only).[/]"
        )
        raise typer.Exit(1)

    table = Table("aquifer", "wells", "conf", "static ft", "yield gpm", "T ft^2/day [inference]")
    for m in params.materials:
        swl = m.static_water_level_ft
        yld = m.test_yield_gpm
        t = m.transmissivity_ft2_day
        table.add_row(
            m.material,
            str(m.well_count),
            m.confinement,
            f"{swl.value:g}" if swl else "—",
            f"{yld.value:g}" if yld else "—",
            f"{t.low_or_value:g}-{t.high_or_value:g}" if t else "—",
        )
    console.print(table)
    console.print(
        f"[bold]{params.well_count}[/] logged wells in {params.county} "
        f"([green]{params.domestic_well_count} domestic[/])."
    )
    for f in aq.aquifer_findings(params):
        console.print(f"[{'green' if f.ok else 'yellow'}]{escape(str(f))}[/]")

    scen = dd.site_cooling_makeup_scenario(
        params, settings=settings, makeup_mgd=makeup_mgd, material=material
    )
    result = dd.load_drawdown(scenario=scen, settings=settings)
    if result is None:
        return
    verdict = "[red]DEWATERS[/]" if result.dewaters else "[green]sustainable[/]"
    s = result.drawdown_at_well_ft
    r0 = result.radius_of_influence_ft
    b = result.saturated_thickness_ft
    b_txt = f"{b:g}" if b is not None else "n/a"
    console.print(
        f"\n[bold]Drawdown screen[/] — {result.material} aquifer, hypothetical "
        f"{scen.pumping_mgd.value:g} MGD: {verdict}. Apex drawdown "
        f"{s.low_or_value:g}-{s.high_or_value:g} ft (b={b_txt} ft); "
        f"radius of influence {r0.value:g} ft; "
        f"{result.affected_domestic_wells} domestic wells within it."
    )
    for f in dd.drawdown_findings(result):
        console.print(f"[{'green' if f.ok else 'red'}]{escape(str(f))}[/]")
    console.print(
        r"[dim]Q is a HYPOTHETICAL groundwater stress \[inference] — the campus draws municipal "
        r"surface water; no withdrawal permit is on record \[open]. The cone is a screen, "
        "never a headline.[/]"
    )


@app.command(name="dewatering")
def dewatering_cmd(
    asof: str | None = typer.Option(
        None, "--asof", help="Analysis date (YYYY-MM-DD) for active-well duration; default: today."
    ),
) -> None:
    """The campus construction-dewatering cone of impact -- the documented 'area well concerns'.

    Models the committed wellfield (data/reference/ohio-waterwells/lima-campus-dewatering.csv): the
    developer's 44 dewatering wells that lowered the water table for site grading. Each well is a
    Cooper-Jacob cone; the field's impact is their superposition, evaluated at each nearby domestic
    census well. Wells/rates/dates are [verified] ODNR records; every drawdown is [inference]
    (literature K, unconfined screening) -- an upper bound on concurrency, never a metered figure.
    """
    from datetime import date as _date

    from watermark.hydrology import dewatering as dw

    settings = get_settings()
    if asof:
        try:
            when = _date.fromisoformat(asof)
        except ValueError:
            console.print(f"[red]Invalid --asof date {asof!r}; expected YYYY-MM-DD.[/]")
            raise typer.Exit(1) from None
    else:
        when = _date.today()
    impact = dw.load_dewatering_impact(asof=when, settings=settings)
    if impact is None:
        console.print(
            "[yellow]No dewatering wellfield committed for the active site "
            "(data/reference/ohio-waterwells/lima-campus-dewatering.csv).[/]"
        )
        raise typer.Exit(1)

    r0s = sorted(c.radius_of_influence_ft.value for c in impact.cones)
    med = r0s[len(r0s) // 2] if r0s else 0.0
    console.print(
        f"[bold]{impact.well_count}[/] construction-dewatering wells at the campus "
        f"([green]{impact.active_count} still active[/]) -- ~[bold]{impact.total_capacity_mgd} MGD[/] "
        f"combined capacity, operated {impact.operating_window}.\n"
        f"per-well cone of impact r0 (central): {r0s[0]:.0f}-{med:.0f}-{r0s[-1]:.0f} ft "
        f"(median {med / 5280:.2f} mi)."
    )

    table = Table("domestic well", "distance ft", "drawdown ft [inference]", "aquifer")
    for w in impact.impacted_wells[:15]:
        d = w.composite_drawdown_ft
        table.add_row(
            w.object_id,
            f"{w.distance_ft:.0f}",
            f"{d.value:g} ({d.low_or_value:g}-{d.high_or_value:g})",
            w.aquifer_type or "-",
        )
    console.print(table)
    for f in dw.dewatering_findings(impact):
        console.print(f"[{'green' if f.ok else 'red'}]{escape(str(f))}[/]")
    console.print(
        r"[dim]Wells/rates/dates are \[verified] ODNR records; drawdowns are \[inference] "
        "(literature K, Cooper-Jacob superposition on an unconfined aquifer). test_rate_gpm is "
        "yield capacity -- an upper bound on the sustained dewatering rate.[/]"
    )
