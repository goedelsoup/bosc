"""``bosc`` command-line interface.

Commands:
    bosc version
    bosc ingest                 # inventory source documents
    bosc reconcile <file>       # arithmetic checks over a summary extraction
    bosc ask "<question>"       # ask the research agent
    bosc extract <doc-id> ...   # run an agentic extraction (seam for your data)
    bosc site build             # stage the GitHub Pages site under web/
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from bosc import __version__
from bosc.config import Settings, get_settings
from bosc.documents import DEFAULT_DPI
from bosc.logging import configure_logging
from bosc.models import OPCSummary
from bosc.pipeline import analyze, ingest

app = typer.Typer(
    name="bosc",
    help="Project BOSC — agentic research platform.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.callback()
def _main() -> None:
    """Configure logging before any command runs."""
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"bosc {__version__}")


@app.command(name="ingest")
def ingest_cmd() -> None:
    """Inventory source documents under data/documents."""
    docs = ingest.discover()
    if not docs:
        console.print("[yellow]No source documents found.[/]")
        raise typer.Exit()
    table = Table("doc_id", "collection", "file", "size")
    for d in docs:
        table.add_row(d.doc_id, d.collection or "—", d.path.name, f"{d.size_bytes / 1e6:.1f} MB")
    console.print(table)


@app.command()
def reconcile(filename: str) -> None:
    """Run deterministic reconciliation over a *.summary.opc.yaml extraction."""
    path = get_settings().extracted_dir / filename
    if not path.exists():
        # Fall back to treating the argument as a direct (absolute/relative) path.
        path = Path(filename)
    summary = OPCSummary.from_yaml(path)
    findings = analyze.reconcile(summary)
    failures = 0
    for f in findings:
        color = "green" if f.ok else "red"
        console.print(f"[{color}]{f}[/]")
        failures += 0 if f.ok else 1
    console.print(
        f"\n{len(findings)} checks, [{'red' if failures else 'green'}]{failures} failing[/]."
    )
    if failures:
        raise typer.Exit(code=1)


@app.command()
def timeline() -> None:
    """Assemble a cross-document chronology from every committed extraction."""
    from bosc.pipeline import timeline as timeline_stage

    events = timeline_stage.build_timeline()
    if not events:
        console.print("[yellow]No dated events found. Run some extractions first.[/]")
        raise typer.Exit()

    table = Table("date", "category", "event", "source")
    for e in events:
        date = e.date or "[dim]—[/]"
        src = e.source + (f" [dim](+{len(e.also_sources)})[/]" if e.also_sources else "")
        table.add_row(date, e.category, e.title, src)
    console.print(table)
    console.print(f"\n[dim]{len(events)} events.[/]")


@app.command()
def entities() -> None:
    """Resolve parties across deeds/NPDES into an entity graph (who relates to whom)."""
    from bosc.pipeline import entities as entities_stage

    graph = entities_stage.build_entity_graph(
        enrich_parcels=True,
        enrich_lei=True,
        enrich_rsei=True,
        enrich_federal=True,
        enrich_subdivisions=True,
        enrich_relation_classes=True,
    )
    if not graph.entities:
        console.print("[yellow]No entities found. Run some extractions first.[/]")
        raise typer.Exit()

    ent_table = Table(
        "entity", "kind", "classification", "BOSC relation", "roles", "LEI/UEI", "federal $"
    )
    for ent in sorted(graph.entities.values(), key=lambda e: (e.kind, e.key)):
        roles = ", ".join(f"{r} x{n}" for r, n in ent.roles.most_common())
        signals = ", ".join(sorted(ent.signals))
        klass = ent.classification + (f" [yellow]({signals})[/]" if signals else "")
        relation = ent.relation_class or "—"
        ids = " ".join(x for x in (ent.lei, ent.uei) if x) or "—"
        fed = f"${ent.federal_obligations:,.0f}" if ent.federal_obligations is not None else "—"
        ent_table.add_row(ent.display, ent.kind, klass, relation, roles, ids, fed)
    console.print(ent_table)

    rel_table = Table("source", "relationship", "target", "when", "ref")
    for r in graph.relationships:
        src = graph.entities[r.src].display if r.src in graph.entities else r.src
        dst = graph.entities[r.dst].display if r.dst in graph.entities else r.dst
        rel_table.add_row(src, r.rel, dst, r.date or "—", r.ref or "—")
    console.print(rel_table)
    console.print(
        f"\n[dim]{len(graph.entities)} entities, {len(graph.relationships)} relationships.[/]"
    )


@app.command()
def ledger(
    offline: bool = typer.Option(
        False, "--offline", help="Use committed/fixture data only; never fetch."
    ),
) -> None:
    """Public-subsidy vs. public-benefit ledger for the data-center CRA abatement."""
    from bosc import ledger as ledger_mod
    from bosc.config import Settings

    settings = Settings(hydro_offline=True) if offline else get_settings()
    pl = ledger_mod.build_ledger(settings)
    ft = pl.foregone_tax

    console.print(
        f"[bold]CRA abatement[/]: {ft.abatement_pct:g}% / {ft.term_years}-yr real-property "
        f"exemption on a ${ft.capital_usd:,} data center for ~{pl.benefit.jobs} jobs "
        f"(~${pl.benefit.annual_payroll_usd:,}/yr payroll)."
    )
    cost = Table("public cost (abated property tax)", "low", "high")
    cost.add_row(
        "annual full tax (if not abated)",
        f"${ft.annual_full_tax_low:,}",
        f"${ft.annual_full_tax_high:,}",
    )
    cost.add_row("annual abated (75%)", f"${ft.annual_abated_low:,}", f"${ft.annual_abated_high:,}")
    cost.add_row(
        f"abated over {ft.term_years} yr", f"${ft.term_abated_low:,}", f"${ft.term_abated_high:,}"
    )
    cost.add_row(
        "per promised job",
        f"${pl.benefit.abatement_per_job_low:,}",
        f"${pl.benefit.abatement_per_job_high:,}",
    )
    console.print(cost)
    console.print(
        "[dim]Effective rate is a stated assumption (Ohio commercial band), not a cited Allen "
        "County millage — a screening range. [inference: assumption][/]"
    )

    console.print("\n[bold]Public burdens carried alongside (cross-thread)[/]")
    for b in pl.burdens:
        console.print(f"  [yellow]•[/] [{b.thread}] {b.headline}")

    console.print("\n[bold red]Withheld — the deciding figures the public can't see[/]")
    for w in pl.withheld:
        console.print(f"  [red]✗[/] {w.what} [dim]({w.why_withheld})[/]")

    console.print("\n[bold]Findings[/]")
    for f in pl.findings:
        console.print(f"  - {f}")


@app.command()
def hydro(
    offline: bool = typer.Option(
        False, "--offline", help="Don't fetch live streamflow; use cached/fixture data only."
    ),
) -> None:
    """Tier-0 water balance + low-flow assimilative screen of the municipal loop."""
    from bosc.config import Settings
    from bosc.pipeline import hydrology as hydro_stage

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

    console.print("\n[bold]Low-flow assimilative screen[/] [dim](7Q10 dilution)[/]")
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
    from bosc.config import Settings
    from bosc.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    runoff, findings = hydro_stage.run_storm(
        return_period_yr=return_period, settings=settings, live=True
    )

    tag = {"document": "doc", "connector": "live", "assumption": "assume", "derived": "calc"}
    console.print(
        f"[bold]{runoff.name}[/]  {runoff.area.value:,.0f} ac "
        f"[dim]({tag[runoff.area.source]})[/]  "
        f"storm {runoff.storm.return_period_yr}-yr 24-hr "
        f"{runoff.storm.depth.value:.2f} in [dim]({tag[runoff.storm.depth.source]})[/]"
    )
    table = Table("case", "land cover", "CN", "peak (cfs)", "volume (ac-ft)")
    table.add_row(
        "pre-development",
        "cropland",
        f"{runoff.pre.curve_number:.0f}",
        f"{runoff.pre.peak_cfs:,.0f}",
        f"{runoff.pre.volume_acft:,.0f}",
    )
    table.add_row(
        "post-development",
        "impervious campus",
        f"{runoff.post.curve_number:.0f}",
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
        f"are cited assumptions; footprint is document-sourced; rainfall is {rainfall_src}.[/]"
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
    write: bool = typer.Option(False, "--write", help="Persist results under data/scenarios/."),
    offline: bool = typer.Option(False, "--offline", help="Use cached/fixture streamflow only."),
) -> None:
    """Baseline vs data-center buildout: net consumptive draw vs the Ottawa 7Q10."""
    from bosc.config import Settings
    from bosc.hydrology import scenario as scenario_stage
    from bosc.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    base, build, delta = hydro_stage.run_scenarios(
        cooling_demand_mgd=cooling_demand,
        consumptive_fraction=consumptive_fraction,
        settings=settings,
        live=True,
    )

    basis = build.scenario.basis
    if basis is not None:
        console.print(
            f"[bold]Cooling design basis[/] (sourced): IT load {basis.it_load.value:g} MW "
            f"[dim](doc: air permit P0138965)[/], WUE {basis.wue.value:g} L/kWh, "
            f"CoC {basis.cycles_of_concentration.value:g}\n"
            f"  consumptive estimate range: [bold]{basis.consumptive_low.value:g}-"
            f"{basis.consumptive_high.value:g} MGD[/] "
            f"[dim](powerxWUE … blowdownxcycles)[/]"
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

    q7 = delta.ottawa_7q10_cfs
    live_flow = build.ottawa_live.value if build.ottawa_live else None
    console.print(
        f"\n[bold red]Buildout adds {delta.consumptive_increase_cfs:,.2f} cfs[/] of net "
        f"consumptive draw on the Ottawa/Auglaize supply."
    )
    if delta.multiple_of_7q10 is not None:
        console.print(
            f"That is [bold]{delta.multiple_of_7q10:g}x[/] the Ottawa River's cited 7Q10 "
            f"low flow ({q7:g} cfs)"
            + (f"; live flow now {live_flow:,.0f} cfs." if live_flow else ".")
        )
    # Seasonal screen: the same draw against the growing-season design low flow.
    sw = scenario_stage.evaluate_seasonal(build.consumptive_loss.value, settings=settings)
    if sw is not None and sw.summer_multiple is not None and sw.growing_season_months:
        win = f"{sw.growing_season_months[0]}-{sw.growing_season_months[-1]}"
        console.print(
            f"\n[bold]Seasonal pinch[/] — in the [bold]{win}[/] growing season "
            f"(ET > precip), the draw is [bold red]{sw.summer_multiple:g}x[/] the cited summer "
            f"30Q10 ({sw.summer_30q10_cfs:g} cfs), vs {sw.annual_multiple:g}x the annual 7Q10. "
            f"The absolute floor is 1Q10 = {sw.one_q10_cfs:g} cfs — no flow to draw against."
        )
    console.print(
        "\n[dim]Cooling basis derived from the air permit + FM-2 discharge (see provenance "
        "tags); the Ottawa 7Q10 is document-cited (Ohio EPA 2IG00001). Tier-0 screening.[/]"
    )
    if write:
        for r in (base, build):
            path = scenario_stage.write_scenario(r, settings=settings)
            console.print(f"[green]Wrote[/] {path}")


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
    from bosc.facility.compute import derive_compute_capacity

    settings = get_settings()
    frac = None
    if accel_fraction_low is not None and accel_fraction_high is not None:
        frac = (accel_fraction_low, accel_fraction_high)
    cap = derive_compute_capacity(settings=settings, accelerator_power_fraction=frac, mfu=mfu)

    # The three IT-load estimators (the bracket headline).
    console.print(
        "[bold]Facility IT load[/] — three independent estimators "
        "[dim](nothing here is a measured fact about the facility)[/]\n"
        f"  1. power / gensets [bold](primary)[/]: [bold]{cap.it_load_power.value:g} MW[/] "
        f"[dim](doc: air permit P0138965)[/]\n"
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

    from bosc.config import Settings
    from bosc.hydrology import hypothesis as hyp_stage

    settings = Settings(hydro_offline=True) if offline else get_settings()
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
            yaml.safe_dump(comparison.model_dump(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        console.print(f"[green]Wrote[/] {path}")


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
    from bosc.config import Settings
    from bosc.hydrology.tier1 import run_tier1, tier1_findings, write_tier1

    settings = Settings(hydro_offline=True) if offline else get_settings()
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
    from bosc.hydrology import stormplan

    settings = get_settings()
    if refresh:
        inv = stormplan.refresh_inventory(settings=settings)
        console.print(f"[green]Refreshed[/] {settings.data_dir / stormplan._INVENTORY_REL}")
    else:
        loaded = stormplan.load_inventory(settings=settings)
        if loaded is None:
            console.print("[yellow]No inventory yet — run `bosc storm-plan --refresh`.[/]")
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
    from bosc.config import Settings
    from bosc.hydrology import report

    settings = get_settings() if live else Settings(hydro_offline=True)
    if write:
        path = report.write_report(settings=settings, live=live)
        console.print(f"[green]Wrote[/] {path}")
    else:
        console.print(report.render_report(settings=settings, live=live), markup=False)


@app.command()
def ask(
    question: str,
    no_tools: bool = typer.Option(
        False, "--no-tools", help="Disable the BOSC data tools (answer from the prompt alone)."
    ),
) -> None:
    """Ask the Project BOSC research agent a question (streams the answer)."""
    from bosc.agent.client import AgentResult, ResearchAgent

    agent = ResearchAgent(enable_tools=not no_tools)

    def emit(chunk: str) -> None:
        console.print(chunk, end="", markup=False, highlight=False)

    async def _run() -> AgentResult:
        return await agent.converse(question, on_text=emit)

    result = asyncio.run(_run())
    console.print()  # newline after the streamed answer

    footer: list[str] = []
    if result.tools_used:
        footer.append("tools: " + ", ".join(dict.fromkeys(result.tools_used)))
    if result.num_turns:
        footer.append(f"{result.num_turns} turns")
    if result.cost_usd is not None:
        footer.append(f"${result.cost_usd:.4f}")
    if footer:
        console.print(f"[dim]({' · '.join(footer)})[/]")
    if result.is_error:
        raise typer.Exit(code=1)


@app.command()
def extract(
    doc_id: str = typer.Argument(..., help="A doc_id from `bosc ingest`."),
    page: int | None = typer.Option(None, "--page", help="0-based PDF page index."),
    pdf_page: int | None = typer.Option(
        None, "--pdf-page", help="1-based printed sheet number (= page index + 1)."
    ),
    kind: str = typer.Option(
        "opc", "--kind", help="Document kind: opc | deed | npdes | sos | epa | plan."
    ),
    profile: str = typer.Option(
        "auto", "--profile", help="OPC format profile id, or 'auto' to detect from the page."
    ),
    dpi: int = typer.Option(0, "--dpi", help="Render DPI; 0 uses the per-kind default."),
    detail: bool = typer.Option(
        False, "--detail", "-d", help="OPC: extract full line items, not just section subtotals."
    ),
    write: bool = typer.Option(False, "--write", "-w", help="Save the YAML under data/extracted."),
) -> None:
    """Extract a document: an OPC cost page (--page), or a deed/NPDES/SoS document."""
    from bosc.models import (
        DeedExtraction,
        EpaExtraction,
        NpdesExtraction,
        PlanExtraction,
        SosExtraction,
    )
    from bosc.pipeline import analyze
    from bosc.pipeline import extract as extract_stage

    docs = {d.doc_id: d for d in ingest.discover()}
    doc = docs.get(doc_id)
    if doc is None:
        console.print(f"[red]Unknown doc_id:[/] {doc_id}. Run `bosc ingest` to list ids.")
        raise typer.Exit(code=1)

    # Document-level kinds (deed, npdes) read across pages — no --page needed.
    if kind in extract_stage.DOC_EXTRACTORS:
        dpi_kw = {"dpi": dpi} if dpi > 0 else {}
        doc_extraction = extract_stage.extract_document(doc, kind=kind, **dpi_kw)
        if isinstance(doc_extraction, DeedExtraction):
            d = doc_extraction.deed
            console.print(
                f"[bold]Deed[/] {d.instrument_type or '?'} no={d.instrument_no or '?'} — "
                f"grantors={d.grantors} grantees={d.grantees} "
                f"parcels={len(d.parcel_ids)} [dim](confidence {d.confidence})[/]"
            )
            warns = d.warnings
        elif isinstance(doc_extraction, NpdesExtraction):
            p = doc_extraction.permit
            console.print(
                f"[bold]NPDES[/] {p.permit_no or '?'} — {p.facility_name or '?'} "
                f"applicant={p.applicant or '?'} receiving={p.receiving_water or '?'} "
                f"[dim](confidence {p.confidence})[/]"
            )
            warns = p.warnings
        elif isinstance(doc_extraction, SosExtraction):
            fil = doc_extraction.filing
            console.print(
                f"[bold]SoS[/] {fil.entity_name or '?'} ({fil.entity_type or '?'}) — "
                f"agent={fil.registered_agent or '?'} organizer={fil.organizer or '?'} "
                f"jurisdiction={fil.jurisdiction or '?'} [dim](confidence {fil.confidence})[/]"
            )
            warns = fil.warnings
        elif isinstance(doc_extraction, EpaExtraction):
            a = doc_extraction.action
            console.print(
                f"[bold]EPA[/] {a.program or '?'} {a.permit_no or ''} — {a.action or '?'} "
                f"applicant={a.applicant or '?'} project={a.project_name or '?'} "
                f"date={a.action_date or '?'} [dim](confidence {a.confidence})[/]"
            )
            warns = a.warnings
        elif isinstance(doc_extraction, PlanExtraction):
            pl = doc_extraction.plan
            firms = ", ".join(f"{fm.name} ({fm.discipline or '?'})" for fm in pl.prepared_by)
            console.print(
                f"[bold]Plan[/] {pl.project_name or '?'} — {pl.discipline or '?'} "
                f"{pl.phase or ''} [dim](confidence {pl.confidence})[/]\n"
                f"  features: {', '.join(pl.key_features[:8])}\n"
                f"  prepared by: {firms}"
            )
            warns = pl.warnings
        else:  # pragma: no cover - defensive
            warns = []
        for warning in warns:
            console.print(f"  [yellow]![/] {warning}")
        if write:
            console.print(f"[green]Saved[/] {extract_stage.save_doc_extraction(doc_extraction)}")
        else:
            console.print(doc_extraction.to_yaml())
        return

    if kind != "opc":
        known = ", ".join(["opc", *sorted(extract_stage.DOC_EXTRACTORS)])
        console.print(f"[red]Unknown --kind {kind!r}.[/] Known: {known}.")
        raise typer.Exit(code=2)

    if (page is None) == (pdf_page is None):
        console.print("[red]Provide exactly one of --page (0-based) or --pdf-page (1-based).[/]")
        raise typer.Exit(code=2)
    page_index = page if page is not None else pdf_page - 1  # type: ignore[operator]

    extraction = extract_stage.extract_page(
        doc, page_index, kind=kind, profile=profile, detail=detail, dpi=dpi or DEFAULT_DPI
    )
    est = extraction.estimate
    color = "green" if est.reconciles() else "yellow"
    console.print(
        f"[bold]{est.name}[/] [dim](profile: {est.profile})[/] — confidence "
        f"[{color}]{est.confidence}[/], reconciles={est.reconciles()}, "
        f"sections={len(est.sections)}, warnings={len(est.warnings)}"
    )
    for warning in est.warnings:
        console.print(f"  [yellow]![/] {warning}")

    for f in analyze.reconcile_estimate(est):
        console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")

    if write:
        path = extract_stage.save_extraction(extraction)
        console.print(f"[green]Saved[/] {path}")
    else:
        console.print(extraction.to_yaml())


@app.command(name="npdes")
def npdes(
    offline: bool = typer.Option(
        False, "--offline", help="Use cached ECHO responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/echo)."
    ),
) -> None:
    """Pull the Maumee-watershed NPDES inventory from EPA ECHO -> deduplicated YAML.

    Queries the seven Maumee HUC-8 subbasins, deduplicates by FRS Registry ID, and
    writes a POTW-only YAML, an all-dischargers YAML, and a per-HUC count manifest.
    """
    from bosc.config import Settings
    from bosc.hydrology.connectors import echo

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)
    target = Path(out_dir) if out_dir else settings.reference_dir / "echo"

    results = echo.fetch_maumee(settings=settings)

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
        f"\n[bold]{raw}[/] rows across 7 HUC-8s -> [bold]{len(deduped)}[/] facilities after "
        f"FRS dedup ([green]{n_potw} POTW[/], {len(deduped) - n_potw} non-POTW)."
    )

    paths = echo.write_inventory(results, target)
    for label, path in paths.items():
        console.print(f"[green]Wrote[/] {label}: {path}")
    console.print(
        "[dim]Gaps: ECHO CWA search has no CWNS column; not every NPDES ID geocodes to a "
        "HUC (WATERS); 4 subbasins cross into IN/MI — cross-check state lists.[/]"
    )


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
    from bosc.config import Settings
    from bosc.hydrology import climate
    from bosc.hydrology.connectors import nasa_power

    settings = get_settings()
    if offline:
        settings = Settings(
            hydro_offline=True,
            hydro_fixtures_dir=settings.data_dir.parent / "tests" / "fixtures" / "hydrology",
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
            from bosc.hydrology.et import penman_monteith_et0

            et0 = penman_monteith_et0(clim)
            console.print(
                f"Reference ET0 (FAO-56 Penman-Monteith): [bold]{et0.annual_mm:,.0f} mm/yr[/] "
                f"(net of precip {ann - et0.annual_mm:+,.0f} mm/yr)."
            )
        except ValueError:
            pass

    if write:
        path = climate.write_climatology(clim, settings=get_settings())
        console.print(f"[green]Wrote[/] {path}")


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
    Hazard, and pounds released. Bulk tables cache under data/cache/rsei (~340 MB on
    first run); the committed artifact is a small per-county YAML.
    """
    import json

    from bosc import rsei
    from bosc.config import Settings

    settings = get_settings()
    if offline:
        settings = Settings(rsei_offline=True)
    target = Path(out_dir) if out_dir else settings.reference_dir / "rsei"

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
    console.print(f"[green]Wrote[/] {path}")
    console.print(
        "[dim]Score is EPA's modeled, population-weighted Risk-Screening Score "
        "(unitless, comparative only). Pounds are reported TRI releases.[/]"
    )

    if update_map:
        from bosc.site import gismap

        geojson = settings.data_dir / "site" / "gis-findings.geojson"
        if geojson.is_file():
            from bosc.hydrology import toxics

            fc = json.loads(geojson.read_text(encoding="utf-8"))
            fc, n = gismap.merge_rsei_layer(fc, inv, toxics.load_screen(settings.reference_dir))
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
    from bosc.hydrology import toxics

    settings = get_settings()
    target = Path(out_dir) if out_dir else settings.reference_dir / "rsei"

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
    console.print(f"[green]Wrote[/] {path}")
    console.print(
        "[dim]Screening concentration is a derived order-of-magnitude value (annual "
        "reported water pounds at the 7Q10), not a measured concentration.[/]"
    )

    if update_map:
        import json

        from bosc.rsei import load_inventory
        from bosc.site import gismap

        rsei_inv = load_inventory(settings.reference_dir)
        geojson = settings.data_dir / "site" / "gis-findings.geojson"
        if rsei_inv is not None and geojson.is_file():
            fc = json.loads(geojson.read_text(encoding="utf-8"))
            fc, n = gismap.merge_rsei_layer(fc, rsei_inv, inv)
            geojson.write_text(json.dumps(fc, indent=1), encoding="utf-8")
            console.print(
                f"[green]Ringed[/] flagged dischargers across {n} RSEI points in {geojson}"
            )
        else:
            console.print("[yellow]No RSEI inventory or GIS findings GeoJSON; skipped --map.[/]")


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
    from bosc.config import Settings
    from bosc.hydrology import drainage

    settings = Settings(hydro_offline=True) if offline else get_settings()

    if write_ddf:
        ddf = drainage.build_corridor_ddf(settings=settings)
        path = drainage.write_corridor_ddf(ddf, settings=settings)
        console.print(f"[green]Wrote[/] {path}")

    audit = drainage.build_drainage_audit(settings)

    table = Table("sub-estimate", "drainage $", "breakdown", "sized $", "lump-sum $", "sized %")
    for s in audit.scopes:
        if s.itemized:
            frac = f"{s.sized_fraction:.0%}" if s.sized_fraction is not None else "—"
            table.add_row(
                s.name[:34],
                f"{s.drainage_subtotal:,}" if s.drainage_subtotal else "—",
                "itemized",
                f"{s.sized_amount:,}" if s.sized_amount is not None else "—",
                f"{s.lump_sum_amount:,}" if s.lump_sum_amount is not None else "—",
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
    from bosc.config import Settings
    from bosc.economics.baseline import build_baseline, write_baseline

    settings = Settings(econ_offline=True) if offline else get_settings()
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

    table = Table("NAICS", "sector", "jobs", "estabs", "location quotient")
    for s in latest.sectors:
        lq = s.location_quotient.value if s.location_quotient else None
        estabs = f"{s.establishments.value:,.0f}" if s.establishments else "—"
        tag = " [green](exports)[/]" if lq is not None and lq >= 1.2 else ""
        table.add_row(
            s.naics,
            s.sector_name[:38],
            f"{s.annual_avg_employment.value:,.0f}",
            estabs,
            (f"{lq:.2f}{tag}" if lq is not None else "—"),
        )
    console.print(table)
    console.print(
        "\n[dim]BLS QCEW (keyless); location quotient = county share / national share "
        "(>1 = export-oriented). Population-over-time needs BOSC_CENSUS_API_KEY.[/]"
    )
    if write:
        path = write_baseline(baseline, settings=settings)
        console.print(f"[green]Wrote[/] {path}")


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
    from bosc import gleif
    from bosc.config import Settings

    settings = get_settings()
    if offline:
        settings = Settings(gleif_offline=True)
    target = Path(out_dir) if out_dir else settings.reference_dir / "gleif"

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
    console.print(f"[green]Wrote[/] {path}")


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
    from bosc import usaspending
    from bosc.config import Settings

    settings = get_settings()
    if offline:
        settings = Settings(usaspending_offline=True)
    target = Path(out_dir) if out_dir else settings.reference_dir / "usaspending"

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
    console.print(f"[green]Wrote[/] {path}")


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
    from bosc.config import Settings
    from bosc.hydrology.connectors import lsc as lsc_connector

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
    console.print(f"[green]Wrote[/] {path}")


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
    from bosc.config import Settings
    from bosc.hydrology.connectors import orc as orc_connector

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


@app.command(name="parcels")
def parcels(
    parcel: str | None = typer.Option(None, "--parcel", help="Look up one parcel by number."),
    owner: str | None = typer.Option(None, "--owner", help="Find parcels by owner-name substring."),
    cited: bool = typer.Option(
        False, "--cited", help="Pull every parcel id cited in the corpus (deeds) -> reference YAML."
    ),
    defense: bool = typer.Option(
        False,
        "--defense",
        help="Scan parcel owners against the defense-contractor seed list -> reference YAML.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None,
        "--out",
        help="Output directory for --cited/--defense (default: data/reference/allen-gis).",
    ),
) -> None:
    """Query the Allen County GIS parcel (CAMA) layer: by number, owner, citations, or defense scan."""
    from bosc.config import Settings
    from bosc.hydrology.connectors import allen_gis

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)

    if parcel:
        p = allen_gis.fetch_parcel(parcel, settings=settings)
        if p is None:
            console.print(
                f"[yellow]No parcel[/] {parcel} ({allen_gis.normalize_parcel_id(parcel)})."
            )
            raise typer.Exit(1)
        console.print(p.model_dump())
        return

    if owner:
        results = allen_gis.parcels_by_owner(owner, settings=settings)
        table = Table("Parcel", "Owner", "Situs", "Acres", "Mkt total")
        for p in results:
            table.add_row(
                p.parcel_no or "—",
                p.owner or "—",
                p.situs_address or "—",
                f"{p.acres:.2f}" if p.acres is not None else "—",
                f"{p.market_total_value:,}" if p.market_total_value is not None else "—",
            )
        console.print(table)
        console.print(f"\n[bold]{len(results)}[/] parcels owned by ~'{owner}'.")
        return

    if cited:
        target = Path(out_dir) if out_dir else settings.reference_dir / "allen-gis"
        ids = allen_gis.scan_parcel_ids(settings.extracted_dir)
        console.print(f"Found [bold]{len(ids)}[/] cited parcel ids in the corpus.")
        found: list[allen_gis.Parcel] = []
        for pid in ids:
            p = allen_gis.fetch_parcel(pid, settings=settings)
            if p is not None:
                found.append(p)
            else:
                console.print(
                    f"[dim]no GIS match for {pid} ({allen_gis.normalize_parcel_id(pid)})[/]"
                )
        path = allen_gis.write_parcels(found, target, scope="cited")
        console.print(f"[green]Wrote[/] {len(found)} parcels -> {path}")
        return

    if defense:
        from bosc.candidates import load_defense_contractors

        target = Path(out_dir) if out_dir else settings.reference_dir / "allen-gis"
        dcl = load_defense_contractors(settings.entities_dir)
        if dcl is None:
            console.print(
                "[yellow]No defense-contractor seed list[/] under data/entities/profiles."
            )
            raise typer.Exit(1)
        primes = [(d.name, d.patterns) for d in dcl.defense_contractors]
        n_pat = sum(len(d.patterns) for d in dcl.defense_contractors)
        prime_owned = allen_gis.defense_owner_scan(primes, settings=settings)
        army = allen_gis.army_controlled_defense_land(settings=settings)
        n_owned = sum(len(v) for v in prime_owned.values())
        console.print(
            f"Scanned [bold]{n_pat}[/] prime patterns -> [bold]{n_owned}[/] prime-owned "
            f"parcels, [bold]{len(army)}[/] Army-controlled (JSMC) parcels."
        )
        for name, parcels in sorted(prime_owned.items()):
            for p in parcels:
                console.print(f"  [cyan]{name}[/]: {p.parcel_no} {p.owner}")
        path = allen_gis.write_defense_scan(prime_owned, army, target, patterns_searched=n_pat)
        console.print(f"[green]Wrote[/] defense scan -> {path}")
        return

    console.print("Pass one of --parcel, --owner, --cited, or --defense.")
    raise typer.Exit(1)


@app.command(name="zoning")
def zoning(
    parcel: str | None = typer.Option(None, "--parcel", help="Zoning district for one parcel."),
    districts: bool = typer.Option(
        False, "--districts", help="Pull the Lima zoning-district catalog -> reference YAML."
    ),
    cited: bool = typer.Option(
        False, "--cited", help="Look up zoning for every parcel id cited in the corpus."
    ),
    write: bool = typer.Option(
        False, "--write", help="With --cited, persist the scan to parcels.zoning.yaml."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None,
        "--out",
        help="Output directory for --districts/--cited (default: data/reference/lima-gis).",
    ),
) -> None:
    """Query the City of Lima zoning layer (city limits only; joins by parcel number)."""
    from bosc.config import Settings
    from bosc.hydrology.connectors import allen_gis, lima_gis

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)

    if parcel:
        rec = lima_gis.zoning_for_parcel(parcel, settings=settings)
        if rec is None:
            console.print(
                f"[yellow]No Lima zoning[/] for {parcel} "
                f"({allen_gis.normalize_parcel_id(parcel)}) — outside city limits or unzoned."
            )
            raise typer.Exit(1)
        console.print(rec.model_dump())
        return

    if districts:
        target = Path(out_dir) if out_dir else settings.reference_dir / "lima-gis"
        cat = lima_gis.zoning_districts(settings=settings)
        table = Table("District", "Polygons")
        for d in cat:
            table.add_row(d.code, str(d.polygon_count))
        console.print(table)
        path = lima_gis.write_zoning_districts(cat, target)
        console.print(f"[green]Wrote[/] {len(cat)} districts -> {path}")
        return

    if cited:
        ids = allen_gis.scan_parcel_ids(settings.extracted_dir)
        console.print(f"Found [bold]{len(ids)}[/] cited parcel ids; looking up Lima zoning.")
        scan = lima_gis.scan_cited_zoning(ids, settings=settings)
        in_city = [s for s in scan if s.in_city]
        for s in in_city:
            console.print(f"  [cyan]{s.parcel_no}[/]: {s.zoning}")
        console.print(
            f"\n[bold]{len(in_city)}[/] of {len(scan)} cited parcels are within Lima city limits."
        )
        if write:
            target = Path(out_dir) if out_dir else settings.reference_dir / "lima-gis"
            path = lima_gis.write_cited_zoning(scan, target)
            console.print(f"[green]Wrote[/] {path}")
        return

    console.print("Pass one of --parcel, --districts, or --cited.")
    raise typer.Exit(1)


@app.command(name="floodzone")
def floodzone(
    catalog: bool = typer.Option(
        False, "--catalog", help="Pull the FEMA DFIRM flood-zone catalog -> reference YAML."
    ),
    footprint: str | None = typer.Option(
        None, "--footprint", help="GeoJSON footprint to test (default: the Bistrozzi parcels)."
    ),
    buffer_m: int = typer.Option(50, "--buffer", help="Proximity buffer (metres) for the check."),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory for --catalog (default: data/reference/lima-gis)."
    ),
) -> None:
    """Query the FEMA floodzone (DFIRM) layer: zone catalog, or a footprint's flood risk."""
    from bosc.config import Settings
    from bosc.hydrology.connectors import lima_gis
    from bosc.hydrology.floodplain import write_campus_floodzone

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)

    if catalog:
        target = Path(out_dir) if out_dir else settings.reference_dir / "lima-gis"
        classes = lima_gis.floodzone_catalog(settings=settings)
        table = Table("Zone", "Subtype", "SFHA", "Polygons")
        for c in classes:
            table.add_row(
                c.fld_zone, c.zone_subtype or "—", "✓" if c.sfha else "—", str(c.polygon_count)
            )
        console.print(table)
        path = lima_gis.write_floodzone_catalog(classes, target)
        console.print(f"[green]Wrote[/] {len(classes)} flood-zone classes -> {path}")
        return

    fp = (
        Path(footprint)
        if footprint
        else settings.reference_dir / "periplus" / "bosc-parcels.geojson"
    )
    if not fp.is_file():
        console.print(f"[yellow]No footprint GeoJSON[/] at {fp}.")
        raise typer.Exit(1)
    in_parcels = lima_gis.footprint_floodzones(fp, distance_m=0, settings=settings)
    nearby = lima_gis.footprint_floodzones(fp, distance_m=buffer_m, settings=settings)
    in_zones = sorted({f.fld_zone or "?" for f in in_parcels})
    near_zones = sorted(
        {f"{f.fld_zone}{' (' + f.zone_subtype + ')' if f.zone_subtype else ''}" for f in nearby}
    )
    if in_parcels:
        console.print(f"[red]In floodplain[/]: parcels intersect {', '.join(in_zones)}.")
    else:
        console.print(
            f"[green]Not in floodplain[/]: parcels intersect no SFHA; "
            f"within {buffer_m} m: {', '.join(near_zones) or 'none'}."
        )
    path = write_campus_floodzone(
        in_parcels, nearby, buffer_m=buffer_m, footprint=fp.name, settings=settings
    )
    console.print(f"[green]Wrote[/] campus floodzone finding -> {path}")


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
    from bosc.config import Settings
    from bosc.hydrology import lowflow_frequency as lf

    settings = get_settings()
    if offline:
        settings = Settings(
            data_dir=settings.data_dir,
            hydro_offline=True,
            hydro_fixtures_dir=settings.data_dir.parent / "tests" / "fixtures" / "hydrology",
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

    if write:
        path = lf.write_low_flow_frequency(lff, settings=get_settings())
        console.print(f"[green]Wrote[/] {path}")


@app.command(name="network")
def network_cmd(
    live: bool = typer.Option(
        False, "--live", help="Ground the abstraction reach with live NWIS flow (offline-aware)."
    ),
    theory: str = typer.Option(
        "",
        "--theory",
        help="Theory overlay id(s) to enable, comma-separated (see `bosc theories`).",
    ),
    all_theories: bool = typer.Option(
        False, "--all-theories", help="Enable every theory in the catalog."
    ),
) -> None:
    """Route the Lima loop at design low flow: natural vs effluent vs the cooling draw.

    Generalizes the per-stream assimilative screen into a routed mass balance over a
    cited confluence graph. The order-invariant system totals (natural low flow,
    effluent, net draw) are the headline; per-reach flows are screening-grade.

    Pass `--theory <id>` (repeatable) or `--all-theories` to overlay unproven
    interventions (the waterfall roundabout, the FM-3 Shawnee II diverter) on the
    buildout side; the overlay's isolated effect is reported below the table.
    """
    from bosc.hydrology import network as network_stage
    from bosc.pipeline import hydrology as hydro_stage

    settings = get_settings()
    requested = [t.strip() for t in theory.split(",") if t.strip()]
    theories: list[str] | None = requested or None
    if all_theories:
        theories = [t.id for t in network_stage.load_theories(settings=settings)]

    baseline, buildout, delta = hydro_stage.run_network(
        theories=theories, settings=settings, live=live
    )
    if not baseline.reaches:
        console.print("[yellow]No network topology[/] (data/reference/hydrology/network.yaml).")
        raise typer.Exit(1)

    bf = baseline.outlet_effluent_fraction
    frac = f" (outlet {bf:.0%} effluent)" if bf is not None else ""
    console.print(
        f"[bold]Lima loop at design low flow[/] — natural Σ[bold]{baseline.natural_total_cfs:g}[/] "
        f"cfs vs effluent Σ[bold]{baseline.effluent_total_cfs:g}[/] cfs{frac}"
    )
    if buildout.theories:
        console.print(f"[magenta]Theories enabled (buildout):[/] {', '.join(buildout.theories)}")
    table = Table("reach", "kind", "natural", "effluent", "routed", "deficit")
    for r in buildout.reaches:
        table.add_row(
            r.name,
            r.kind,
            f"{r.natural_cfs:g}",
            f"{r.effluent_cfs:g}",
            f"{r.routed_cfs:g}",
            f"{r.deficit_cfs:g}" if r.deficit_cfs else "—",
        )
    console.print(table)
    dry = "[red]runs dry[/]" if delta.mainstem_runs_dry else "holds"
    console.print(
        f"Buildout cooling draw [bold]{buildout.consumptive_cfs:g} cfs[/] = "
        f"[bold]{delta.multiple_of_natural:g}x[/] the loop's natural low flow; "
        f"Ottawa mainstem at the intake {dry}. "
        f"Conservation closes: {'✓' if buildout.closes else '✗'}."
    )
    for w in buildout.warnings:
        if "theory" in w.lower():
            console.print(f"[yellow]![/] {w}")

    if theories:
        _without, _with_theory, findings = hydro_stage.compare_theory(
            theories, settings=settings, live=live
        )
        console.print(
            "\n[bold magenta]Theory overlay (isolated, same buildout draw):[/] "
            "[dim]theorized — magnitudes are assumption knobs, not measurements[/]"
        )
        for f in findings:
            console.print(f"  • {f.detail}", markup=False)  # detail carries literal [..] brackets


@app.command(name="theories")
def theories_cmd() -> None:
    """List the toggleable network theories (unproven overlays held out of the baseline).

    Each is enabled per run with `bosc network --theory <id>`. Every theory is
    `theorized` and ships disabled; its injected magnitude is an assumption knob.
    """
    from bosc.hydrology import network as network_stage

    settings = get_settings()
    catalog = network_stage.load_theories(settings=settings)
    if not catalog:
        console.print("[yellow]No theories[/] (data/reference/hydrology/theories.yaml).")
        return
    table = Table("id", "name", "status", "default", "injects")
    for t in catalog:
        injects = "; ".join(
            f"{n.inject_cfs.value:g} {n.inject_cfs.unit} -> {n.downstream}"
            for n in t.add_nodes
            if n.inject_cfs is not None
        )
        table.add_row(
            t.id,
            t.name,
            t.status,
            "[green]on[/]" if t.enabled else "[dim]off[/]",
            injects or "—",
        )
    console.print(table)
    console.print(
        "[dim]Enable with[/] bosc network --theory <id> [dim](repeatable) or[/] --all-theories."
    )


@app.command(name="supply")
def supply_cmd() -> None:
    """Screen the campus draw against Lima's reservoir storage (the supply water-budget).

    The intake-side counterpart to `bosc network`. Lima's supply is five upground
    (off-stream) reservoirs (~15 BG) filled from the Auglaize + Ottawa at high flow, so
    the low-flow constraint is reservoir DRAWDOWN, not a 7Q10 intake. Reports the
    drought-reserve drawdown, the campus's share of plant production, and the net basin
    loss.
    """
    from bosc.pipeline import hydrology as hydro_stage

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

    The flow-side counterpart to `bosc supply`. Reports the normal-year supply surplus and
    the sequent-peak (Rippl) storage the worst gauged drought calls on, city-only vs +campus.
    `--write` re-pulls the Auglaize + Ottawa daily records and rewrites the committed artifact.
    """
    from bosc.hydrology import refill as refill_mod
    from bosc.pipeline import hydrology as hydro_stage

    settings = get_settings()
    if write:
        ra = refill_mod.compute_refill_adequacy(settings=settings)
        path = refill_mod.write_refill_adequacy(ra, settings=settings)
        console.print(f"[green]Wrote[/] {path}")
        findings = refill_mod.refill_findings(ra)
    else:
        loaded, findings = hydro_stage.run_refill(settings=settings)
        if loaded is None:
            console.print(
                "[yellow]No refill analysis[/] (data/reference/hydrology/refill-adequacy.yaml). "
                "Run [bold]bosc refill --write[/] to generate it."
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


@app.command(name="roundabout")
def roundabout_cmd() -> None:
    """Derive the Cole/Beery roundabout's directed flow into Pike Run (the waterfall theory).

    Grounds the `waterfall-roundabout-pike-run` network theory. The document-derived
    impervious catchment against the cited corridor rainfall shows the roundabout cannot
    sustainably augment Pike Run (mean-annual ~0.01 cfs, zero at the 7Q10); what it offers is
    transient storm surges — episodic flushing, not low-flow augmentation.
    """
    from bosc.pipeline import hydrology as hydro_stage

    settings = get_settings()
    rf, findings = hydro_stage.run_roundabout(settings=settings)
    console.print(
        f"[bold]{rf.roundabout} roundabout[/] -> Pike Run — "
        f"[bold]{rf.impervious_acres.value:g} impervious acres[/] "
        f"(CN {rf.curve_number.value:g}, Tc {rf.tc_hr.value:g} hr)\n"
        f"Sustained: mean-annual [bold]{rf.mean_annual_cfs.value:g} cfs[/]; "
        f"at design low flow [bold]{rf.drought_flow_cfs:g} cfs[/] (no rain)."
    )
    table = Table("design storm", "depth (in)", "peak (cfs)", "volume (ac-ft)", "runoff (in)")
    for p in rf.storm_peaks:
        table.add_row(
            f"{p.return_period_yr}-yr 24-hr",
            f"{p.depth_in:g}",
            f"{p.peak_cfs:g}",
            f"{p.volume_acft:g}",
            f"{p.runoff_depth_in:g}",
        )
    console.print(table)
    for f in findings:
        console.print(f"  {'·' if f.ok else '!'} {f.detail}", markup=False)
    for c in rf.caveats:
        console.print(f"  ~ {c}", markup=False)


@app.command(name="people")
def people() -> None:
    """List the curated individual profiles (the entity graph's detail store).

    Shows which individuals are tracked, which get expanded research (and so render
    on the site), and whether each resolves to a node in the entity graph.
    """
    from bosc.people import load_people
    from bosc.pipeline.corpus import load_corpus
    from bosc.pipeline.entities import build_entity_graph

    settings = get_settings()
    profiles = load_people(settings.people_dir)
    if not profiles:
        console.print(
            f"[yellow]No profiles[/] under {settings.people_dir}. "
            "Add `data/people/<slug>.md` files with a frontmatter header."
        )
        return

    egraph = build_entity_graph(
        load_corpus(settings),
        enrich_parcels=True,
        enrich_lei=True,
        enrich_rsei=True,
        enrich_federal=True,
        settings=settings,
    )

    table = Table("Individual", "Expanded", "In graph", "Roles", "Sources")
    for prof in profiles:
        in_graph = "✓" if egraph.get(prof.entity_key) is not None else "—"
        expanded = "[green]✓[/]" if prof.expanded else "[dim]—[/]"
        roles = ", ".join(prof.front.roles) or "—"
        table.add_row(prof.name, expanded, in_graph, roles, str(len(prof.front.sources)))
    console.print(table)

    n_expanded = sum(1 for p in profiles if p.expanded)
    console.print(
        f"\n[bold]{len(profiles)}[/] tracked individuals — "
        f"[green]{n_expanded}[/] with expanded research (published to the site), "
        f"{len(profiles) - n_expanded} tracked-only."
    )


site_app = typer.Typer(
    name="site",
    help="Generate / preview the GitHub Pages site from the corpus.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(site_app, name="site")


@site_app.command("build")
def site_build(
    notebooks: bool = typer.Option(
        False,
        "--notebooks/--no-notebooks",
        help="Also export the marimo methodology notebooks to WASM (needs `marimo`).",
    ),
) -> None:
    """Stage web/ from data/extracted + docs, then render the static HTML site/ (regenerable)."""
    from bosc.site import build_site, render_site

    result = build_site(notebooks=notebooks)
    rendered = render_site(result.web_dir, result.web_dir.parent / "site")
    console.print(
        f"[green]Built[/] {result.web_dir} — {result.n_records} records "
        f"({len(result.record_pages)} kind pages), {result.n_events} timeline events, "
        f"{result.n_entities} entities, {result.narrative_files} narrative/artifact files."
    )
    console.print(
        f"[green]Rendered[/] {rendered.site_dir} — {rendered.pages} HTML pages, "
        f"{rendered.assets} assets copied."
    )
    available = sum(1 for e in result.exhibits if e.available)
    if result.exhibits:
        console.print(
            f"[dim]exhibits: {available}/{len(result.exhibits)} available (rest need `git lfs pull`)[/]"
        )
    console.print(
        "[dim]Next:[/] bosc site serve   [dim](local preview at http://localhost:8000)[/]"
    )


@site_app.command("serve")
def site_serve(
    build: bool = typer.Option(True, "--build/--no-build", help="Rebuild the site before serving."),
    port: int = typer.Option(8000, "--port", help="Port for the local preview server."),
) -> None:
    """Build (unless --no-build) then serve the static site/ for a local preview."""
    import functools
    import http.server
    import socketserver

    from bosc.config import get_settings

    site_dir = get_settings().data_dir.parent / "site"
    if build:
        from bosc.site import build_site, render_site

        result = build_site()
        render_site(result.web_dir, site_dir)
    if not site_dir.is_dir():
        console.print("[red]No site/ to serve.[/] Run without --no-build first.")
        raise typer.Exit(1)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
    console.print(
        f"[green]Serving[/] {site_dir} at [bold]http://localhost:{port}[/] (Ctrl-C to stop)"
    )
    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[dim]stopped[/]")


subdivisions_app = typer.Typer(
    name="subdivisions",
    help="Allen County subdivisions — meeting-records registry + publishing discovery.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(subdivisions_app, name="subdivisions")


@subdivisions_app.command("list")
def subdivisions_list(
    undiscovered: bool = typer.Option(
        False, "--undiscovered", help="Only bodies still at platform: unknown."
    ),
) -> None:
    """List the committed subdivisions registry (grounded cadence + publishing)."""
    from bosc.civic import load_registry

    reg = load_registry()
    rows = reg.undiscovered() if undiscovered else reg.subdivisions
    table = Table("slug", "type", "name", "meeting schedule", "platform", "records url")
    for s in rows:
        table.add_row(
            s.slug,
            s.type,
            s.name,
            s.meeting_schedule or "—",
            s.publishing.platform.value,
            s.publishing.records_url or "—",
        )
    console.print(table)
    discovered = sum(1 for s in reg.subdivisions if s.publishing.records_url)
    console.print(
        f"[dim]{len(reg.subdivisions)} bodies — {discovered} with a discovered records URL, "
        f"{len(reg.undiscovered())} still unknown.[/]"
    )


@subdivisions_app.command("discover")
def subdivisions_discover(
    slug: str | None = typer.Argument(
        None, help="Body to probe (default: all with a homepage on record)."
    ),
    url: str | None = typer.Option(
        None, "--url", help="Homepage to probe (seeds an unknown body)."
    ),
    all_known: bool = typer.Option(
        False, "--all", help="Probe every body with a homepage on record."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture responses only; never touch the network."
    ),
    out: str | None = typer.Option(
        None, "--out", help="Write the discovery report to this YAML path."
    ),
) -> None:
    """Probe a body's website and classify how it publishes minutes/agendas.

    Read-only: prints (and optionally writes) findings for review — it does not
    rewrite the curated registry. Fold confirmed results into subdivisions.yaml by
    hand so the grounded/discovered split stays intact.
    """
    import yaml

    from bosc.civic import load_registry
    from bosc.civic.discovery import discover
    from bosc.config import Settings

    settings = Settings(hydro_offline=True) if offline else get_settings()
    reg = load_registry(settings)

    if all_known:
        targets = reg.with_website()
    elif slug:
        one = reg.get(slug)
        if one is None:
            console.print(f"[red]No such subdivision:[/] {slug}")
            raise typer.Exit(1)
        targets = [one]
    else:
        targets = reg.with_website()

    results = [discover(s, url=url if slug else None, settings=settings) for s in targets]

    table = Table("slug", "platform", "homepage", "records url", "candidates", "signals")
    for r in results:
        table.add_row(
            r.slug,
            r.platform.value,
            r.homepage or "—",
            r.records_url or "—",
            str(len(r.records_url_candidates)),
            ", ".join(r.signals) or "—",
        )
    console.print(table)

    if out:
        report = {"discovery": [r.model_dump(mode="json") for r in results]}
        Path(out).write_text(yaml.safe_dump(report, sort_keys=False, allow_unicode=True), "utf-8")
        console.print(f"[green]Wrote[/] {out}")


@subdivisions_app.command("fetch")
def subdivisions_fetch(
    slug: str = typer.Argument(..., help="Body to fetch meeting docs for (e.g. lima, lacrpc)."),
    url: str | None = typer.Option(None, "--url", help="Override the records/Agenda Center URL."),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture responses only; never touch the network."
    ),
    out: str | None = typer.Option(
        None, "--out", help="Write the meeting-doc inventory to this YAML path."
    ),
) -> None:
    """Fetch a body's online minutes/agendas into a MeetingDoc inventory.

    Dispatches on the body's discovered platform (CivicPlus Agenda Center is wired;
    others raise until their fetcher lands). Read-only inventory — it lists the
    documents and their URLs; downloading the binaries is a separate step.
    """
    import yaml

    from bosc.civic import load_registry
    from bosc.civic.fetchers import FetcherNotImplementedError, fetch_meetings
    from bosc.config import Settings

    settings = Settings(hydro_offline=True) if offline else get_settings()
    reg = load_registry(settings)
    body = reg.get(slug)
    if body is None:
        console.print(f"[red]No such subdivision:[/] {slug}")
        raise typer.Exit(1)

    try:
        docs = fetch_meetings(body, url=url, settings=settings)
    except FetcherNotImplementedError as exc:
        console.print(f"[yellow]{exc}[/]")
        raise typer.Exit(1) from exc

    table = Table("date", "kind", "body", "title")
    for d in sorted(docs, key=lambda d: (d.date or "", d.kind), reverse=True):
        table.add_row(d.date or "—", d.kind, d.body or "—", (d.title or "")[:70])
    console.print(table)
    n_min = sum(1 for d in docs if d.kind == "minutes")
    n_ag = sum(1 for d in docs if d.kind == "agenda")
    console.print(
        f"[dim]{body.name}: {len(docs)} documents ({n_min} minutes, {n_ag} agendas) "
        f"across {len({d.body for d in docs})} bodies — Agenda Center index view "
        f"(full archive is a follow-on).[/]"
    )

    if out:
        report = {"slug": slug, "meetings": [d.model_dump(mode="json") for d in docs]}
        Path(out).write_text(yaml.safe_dump(report, sort_keys=False, allow_unicode=True), "utf-8")
        console.print(f"[green]Wrote[/] {out}")


@subdivisions_app.command("download")
def subdivisions_download(
    slug: str = typer.Argument(..., help="Body to download meeting documents for."),
    limit: int | None = typer.Option(
        None, "--limit", help="Cap how many documents to pull this run (resume later)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be downloaded; write nothing."
    ),
    url: str | None = typer.Option(None, "--url", help="Override the records/Agenda Center URL."),
) -> None:
    """Download a body's minutes/agendas into data/documents/<slug>/meetings/.

    Fetches the body's MeetingDoc inventory, then pulls each binary into the raw,
    LFS-tracked evidence tree under its as-received name, and writes a
    non-destructive download manifest under data/extracted/<slug>/meetings/.
    Idempotent: unchanged files are skipped, conflicting bytes are kept beside the
    original. Dates in the manifest are listing-derived (not yet content-verified).
    """
    from bosc.civic import load_registry
    from bosc.civic.downloader import download_meetings, write_manifest
    from bosc.civic.fetchers import FetcherNotImplementedError, fetch_meetings

    settings = get_settings()
    reg = load_registry(settings)
    body = reg.get(slug)
    if body is None:
        console.print(f"[red]No such subdivision:[/] {slug}")
        raise typer.Exit(1)

    try:
        docs = fetch_meetings(body, url=url, settings=settings)
    except FetcherNotImplementedError as exc:
        console.print(f"[yellow]{exc}[/]")
        raise typer.Exit(1) from exc

    selected = docs[:limit] if limit is not None else docs
    if dry_run:
        console.print(
            f"[bold]{body.name}[/] — would download [bold]{len(selected)}[/] of "
            f"{len(docs)} documents to {settings.documents_dir / slug / 'meetings'}:"
        )
        for d in selected[:30]:
            console.print(f"  [dim]{d.date or '—'}[/] {d.kind:7} {d.url}")
        if len(selected) > 30:
            console.print(f"  [dim]… and {len(selected) - 30} more[/]")
        return

    report = download_meetings(body, docs, settings=settings, limit=limit)
    manifest = write_manifest(
        report, settings.extracted_dir / slug / "meetings" / "download-manifest.yaml"
    )
    console.print(
        f"[green]{report.downloaded}[/] downloaded, {report.skipped} skipped, "
        f"[{'red' if report.conflicts else 'dim'}]{report.conflicts} conflicts[/], "
        f"{report.errors} errors → {report.dest_dir}"
    )
    console.print(f"[green]Manifest[/] {manifest}")
    if report.errors:
        console.print("[yellow]Some documents failed to fetch; see the manifest notes.[/]")


@subdivisions_app.command("index")
def subdivisions_index(
    slug: str = typer.Argument(..., help="Body to index downloaded meeting documents for."),
    ocr: bool = typer.Option(
        False, "--ocr", help="OCR image-only scanned PDFs (needs the tesseract binary)."
    ),
) -> None:
    """OCR/text-index a body's downloaded meetings: verify dates + scan corridor topics.

    Reads data/extracted/<slug>/meetings/download-manifest.yaml, extracts each file's
    text (PDF text layer / DOCX / HTML; --ocr also reads image-only scans), confirms
    the listing date against the file's own content, scans for corridor topics, and
    writes meeting-index.yaml. Meetings with a corridor hit then surface on the timeline.
    """
    from bosc.civic import load_registry
    from bosc.civic.indexer import OcrUnavailableError, index_meetings, write_index

    settings = get_settings()
    reg = load_registry(settings)
    body = reg.get(slug)
    if body is None:
        console.print(f"[red]No such subdivision:[/] {slug}")
        raise typer.Exit(1)

    try:
        report = index_meetings(body, settings=settings, ocr=ocr)
    except OcrUnavailableError as exc:
        console.print(f"[red]OCR unavailable:[/] {exc}. Install tesseract (see Brewfile).")
        raise typer.Exit(1) from exc
    if not report.docs:
        console.print(
            f"[yellow]No downloaded documents for {slug}[/] — run "
            f"[bold]bosc subdivisions download {slug}[/] first."
        )
        raise typer.Exit(1)

    out = write_index(report, settings.extracted_dir / slug / "meetings" / "meeting-index.yaml")
    scanned = report.text_extracted
    console.print(
        f"[green]{report.text_extracted}/{len(report.docs)}[/] text-extracted, "
        f"{report.date_verified} dates content-verified, "
        f"[bold]{report.with_hits}[/] with corridor topic hits → timeline."
    )
    if scanned < len(report.docs):
        console.print(
            f"[dim]{len(report.docs) - scanned} file(s) had no text layer "
            f"(image-only scans) — they need an OCR pass not wired here.[/]"
        )
    console.print(f"[green]Index[/] {out}")


@subdivisions_app.command("audit")
def subdivisions_audit(
    slug: str | None = typer.Argument(None, help="Body to audit (default: all ingested)."),
) -> None:
    """Audit ingested minutes against the standing cadence → missing-meeting worklist.

    For each body with a meeting index, compares the dates we have against the dates
    its grounded meeting schedule should have produced over the ingested span, and
    writes completeness-audit.yaml (the `missing:` list is a records-request worklist).
    """
    from bosc.civic import load_registry
    from bosc.civic.audit import audit_body, write_audit

    settings = get_settings()
    reg = load_registry(settings)
    bodies = [reg.get(slug)] if slug else reg.subdivisions
    if slug and bodies[0] is None:
        console.print(f"[red]No such subdivision:[/] {slug}")
        raise typer.Exit(1)

    table = Table("slug", "schedule", "span", "expected", "present", "coverage", "missing")
    audited = 0
    for body in bodies:
        if body is None:
            continue
        report = audit_body(body, settings=settings)
        if report is None:  # not ingested
            continue
        audited += 1
        write_audit(
            report, settings.extracted_dir / body.slug / "meetings" / "completeness-audit.yaml"
        )
        cov = "—" if not report.parsed else f"{report.coverage:.0%}"
        span = f"{report.span_start}..{report.span_end}" if report.span_start else "—"
        table.add_row(
            body.slug,
            (report.schedule or "—")[:24],
            span,
            str(report.expected) if report.parsed else "—",
            str(report.present) if report.parsed else "—",
            cov,
            str(len(report.missing)),
        )
    if not audited:
        console.print("[yellow]No ingested bodies to audit[/] — download + index one first.")
        raise typer.Exit(1)
    console.print(table)
    console.print(
        "[dim]missing = scheduled dates not ingested (records-request candidates; "
        "verify — cadences change and meetings get cancelled).[/]"
    )


@subdivisions_app.command("summarize")
def subdivisions_summarize(
    slug: str = typer.Argument(..., help="Body to summarize corridor-relevant meetings for."),
    limit: int | None = typer.Option(None, "--limit", help="Cap how many meetings to summarize."),
    ocr: bool = typer.Option(True, "--ocr/--no-ocr", help="OCR scanned PDFs while reading text."),
) -> None:
    """Summarize a body's corridor meetings: extract what was decided (LLM analyze stage).

    For each indexed meeting that names the project (datacenter/bosc/bistrozzi/google),
    reads the file's text and extracts a grounded structured summary (motions, parties,
    parcels, dollar figures), writing meeting-summaries.yaml. Requires ANTHROPIC_API_KEY.
    """
    from bosc.civic import load_registry
    from bosc.civic.summarize import summarize_corridor_meetings, write_summaries

    settings = get_settings()
    reg = load_registry(settings)
    body = reg.get(slug)
    if body is None:
        console.print(f"[red]No such subdivision:[/] {slug}")
        raise typer.Exit(1)

    report = summarize_corridor_meetings(body, settings=settings, limit=limit, ocr=ocr)
    if not report.entries and not report.skipped:
        console.print(
            f"[yellow]No corridor-relevant meetings indexed for {slug}[/] — run "
            f"[bold]bosc subdivisions index {slug}[/] first."
        )
        raise typer.Exit(1)

    table = Table("date", "kind", "corridor relevance")
    for e in sorted(report.entries, key=lambda e: e.date or ""):
        table.add_row(e.date or "—", e.kind, e.summary.corridor_relevance[:70])
    console.print(table)
    out = write_summaries(
        report, settings.extracted_dir / slug / "meetings" / "meeting-summaries.yaml"
    )
    console.print(f"[green]{len(report.entries)}[/] meetings summarized → {out}")
    if report.skipped:
        console.print(f"[dim]{len(report.skipped)} skipped (no extractable text).[/]")


imagery_app = typer.Typer(
    name="imagery",
    help="Satellite imagery for tracking sites (AOIs from the GIS findings).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(imagery_app, name="imagery")


def _gis_offline_settings() -> Settings:
    """Settings that serve committed GIS fixtures only (never touch the network)."""
    base = get_settings()
    return Settings(
        gis_offline=True,
        gis_fixtures_dir=base.data_dir.parent / "tests" / "fixtures" / "gis",
    )


@imagery_app.command("sites")
def imagery_sites() -> None:
    """List the tracking sites (named AOIs grouped from the committed GIS findings)."""
    from bosc.gis import load_tracking_sites

    sites = load_tracking_sites()
    if not sites:
        console.print(
            "[yellow]No tracking sites[/] — check settings.gis_tracking_layers against "
            "the layers in data/site/gis-findings.geojson."
        )
        raise typer.Exit(1)
    table = Table("id", "name", "features", "acres", "bbox (W,S,E,N)")
    for s in sites:
        acres = f"{s.acreage:,.1f}" if s.acreage is not None else "—"
        bbox = ", ".join(f"{c:.4f}" for c in s.bbox)
        table.add_row(s.id, s.name, str(s.n_features), acres, bbox)
    console.print(table)


@imagery_app.command("search")
def imagery_search(
    site: str = typer.Argument(..., help="Tracking-site id (see `bosc imagery sites`)."),
    collection: str | None = typer.Option(
        None, "--collection", help="STAC collection (default: settings.gis_default_collection)."
    ),
    date_from: str | None = typer.Option(None, "--from", help="Start date, e.g. 2023-01-01."),
    date_to: str | None = typer.Option(None, "--to", help="End date, e.g. 2024-12-31."),
    max_cloud: float | None = typer.Option(
        None, "--max-cloud", help="Max eo:cloud_cover percent (Sentinel-2/Landsat)."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Max scenes to return."),
    pad: float = typer.Option(0.0, "--pad", help="Grow the site bbox by N degrees."),
    offline: bool = typer.Option(
        False, "--offline", help="Use the committed fixture only; never touch the network."
    ),
) -> None:
    """Search a public STAC catalog for scenes covering a tracking site, newest first.

    Lists the matching scenes (acquisition date, cloud, platform, native CRS) and their
    asset count — the search step; materializing AOI-clipped GeoTIFFs is a later stage.
    """
    from bosc.gis import imagery

    dt_range = f"{date_from or '..'}/{date_to or '..'}" if (date_from or date_to) else None
    settings = _gis_offline_settings() if offline else get_settings()
    try:
        site_obj, scenes = imagery.search_site(
            site,
            collection=collection,
            datetime_range=dt_range,
            max_cloud=max_cloud,
            limit=limit,
            pad_deg=pad,
            settings=settings,
        )
    except KeyError as exc:
        console.print(f"[red]{exc}[/] — see [bold]bosc imagery sites[/].")
        raise typer.Exit(1) from exc

    coll = collection or get_settings().gis_default_collection
    span = dt_range or "all dates"
    console.print(
        f"[bold]{site_obj.name}[/] [{coll}] {span} — [bold]{len(scenes)}[/] scenes "
        f"(bbox {', '.join(f'{c:.4f}' for c in site_obj.padded_bbox(pad))})"
    )
    table = Table("acquired", "platform", "cloud %", "EPSG", "assets", "scene id")
    for sc in scenes:
        table.add_row(
            (sc.acquired or "—")[:19],
            sc.platform or "—",
            f"{sc.cloud_cover:.1f}" if sc.cloud_cover is not None else "—",
            str(sc.epsg) if sc.epsg is not None else "—",
            str(len(sc.assets)),
            sc.scene_id,
        )
    console.print(table)


@imagery_app.command("pull")
def imagery_pull(
    site: str = typer.Argument(..., help="Tracking-site id (see `bosc imagery sites`)."),
    collection: str | None = typer.Option(
        None, "--collection", help="STAC collection (default: settings.gis_default_collection)."
    ),
    asset: str | None = typer.Option(
        None, "--asset", help="Asset/band key (default per collection, e.g. sentinel-2 'visual')."
    ),
    date_from: str | None = typer.Option(None, "--from", help="Start date, e.g. 2024-06-01."),
    date_to: str | None = typer.Option(None, "--to", help="End date, e.g. 2024-09-30."),
    max_cloud: float | None = typer.Option(None, "--max-cloud", help="Max eo:cloud_cover percent."),
    limit: int = typer.Option(1, "--limit", help="How many scenes (newest first) to pull."),
    out: str | None = typer.Option(
        None, "--out", help="Output root (default: data/reference/imagery)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use committed fixtures only; never touch the network."
    ),
) -> None:
    """Clip scenes covering a tracking site to AOI GeoTIFFs (dated, with provenance sidecars).

    Searches the catalog, then for each of the newest ``--limit`` scenes reads just the
    AOI window of the chosen asset and writes
    data/reference/imagery/<site>/<collection>/<date>.<asset>.tif plus a `.yaml`
    chain-of-custody sidecar (sensing vs. retrieval date, scene id, sha256). Pixels are
    verbatim — a windowed clip in the scene's native CRS, no resampling.
    """
    from bosc.gis import imagery, raster

    dt_range = f"{date_from or '..'}/{date_to or '..'}" if (date_from or date_to) else None
    settings = _gis_offline_settings() if offline else get_settings()
    out_dir = Path(out) if out else None
    try:
        site_obj, scenes = imagery.search_site(
            site,
            collection=collection,
            datetime_range=dt_range,
            max_cloud=max_cloud,
            limit=limit,
            settings=settings,
        )
    except KeyError as exc:
        console.print(f"[red]{exc}[/] — see [bold]bosc imagery sites[/].")
        raise typer.Exit(1) from exc
    if not scenes:
        console.print("[yellow]No scenes matched[/] — widen --from/--to or raise --max-cloud.")
        raise typer.Exit(1)

    table = Table("acquired", "asset", "EPSG", "size", "sha256", "path")
    for sc in scenes[:limit]:
        try:
            cap = raster.pull_capture(sc, site_obj, asset=asset, out_dir=out_dir, settings=settings)
        except raster.ImageryOfflineError as exc:
            console.print(f"[red]offline:[/] {exc}")
            raise typer.Exit(1) from exc
        table.add_row(
            (cap.acquired or "—")[:10],
            cap.asset,
            str(cap.epsg) if cap.epsg else "—",
            f"{cap.width}x{cap.height}",
            cap.sha256[:12],
            cap.path,
        )
    n = min(limit, len(scenes))
    console.print(f"[bold]{site_obj.name}[/] — pulled [bold]{n}[/] capture(s):")
    console.print(table)


poi_app = typer.Typer(
    name="poi",
    help="Points of interest (places) — the curated, depth-marked place store.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(poi_app, name="poi")


@poi_app.command("list")
def poi_list(
    tracked: bool = typer.Option(False, "--tracked", help="Only POIs that feed imagery tracking."),
) -> None:
    """List the curated POI store (place, kind, research depth, tracking)."""
    from bosc.poi import load_pois

    pois = load_pois()
    if tracked:
        pois = [p for p in pois if p.tracked]
    if not pois:
        console.print("[yellow]No POIs[/] — the store at data/poi/ is empty.")
        raise typer.Exit(1)
    table = Table("slug", "kind", "depth", "tracked", "parcels", "located")
    for p in pois:
        table.add_row(
            p.slug,
            p.kind,
            p.depth,
            "✓" if p.tracked else "",
            str(len(p.front.parcels)),
            "✓" if p.bbox else "",
        )
    console.print(table)
    console.print(
        f"[dim]{len(pois)} POIs — {sum(1 for p in pois if p.tracked)} watched/tracked.[/]"
    )


@poi_app.command("show")
def poi_show(slug: str = typer.Argument(..., help="POI slug (see `bosc poi list`).")) -> None:
    """Show one POI: its frontmatter (identity, location, tracking) and body."""
    from bosc.poi import load_poi

    poi = load_poi(slug)
    if poi is None:
        console.print(f"[red]No such POI:[/] {slug}")
        raise typer.Exit(1)
    f = poi.front
    console.print(f"[bold]{f.name}[/] [dim]({poi.slug})[/] — {f.kind}, depth=[bold]{f.depth}[/]")
    if f.parcels:
        console.print(f"  parcels: {', '.join(f.parcels)}")
    if f.members:
        console.print(f"  members: {', '.join(f.members)}")
    if f.location:
        loc = f.location
        bbox = ", ".join(f"{c:.4f}" for c in loc.bbox) if loc.bbox else "—"
        console.print(
            f"  location: method={loc.method or '—'} confidence={loc.confidence or '—'} "
            f"asof={loc.asof or '—'} bbox=[{bbox}]"
        )
    if f.track and f.track.enabled:
        console.print(
            f"  [green]tracked[/]: collections={', '.join(f.track.collections) or '—'} "
            f"since={f.track.since or '—'}"
        )
    if f.citations:
        console.print("  citations:")
        for c in f.citations:
            console.print(f"    - {c}")
    if poi.body:
        console.print(f"\n{poi.body}")


if __name__ == "__main__":
    app()
