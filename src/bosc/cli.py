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
from bosc.config import get_settings
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

    graph = entities_stage.build_entity_graph(enrich_parcels=True)
    if not graph.entities:
        console.print("[yellow]No entities found. Run some extractions first.[/]")
        raise typer.Exit()

    ent_table = Table("entity", "kind", "classification", "roles", "signals")
    for ent in sorted(graph.entities.values(), key=lambda e: (e.kind, e.key)):
        roles = ", ".join(f"{r} x{n}" for r, n in ent.roles.most_common())
        signals = ", ".join(sorted(ent.signals))
        klass = ent.classification + (f" [yellow]({signals})[/]" if signals else "")
        ent_table.add_row(ent.display, ent.kind, klass, roles, signals or "—")
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
    console.print(
        "\n[dim]Cooling basis derived from the air permit + FM-2 discharge (see provenance "
        "tags); the Ottawa 7Q10 is document-cited (Ohio EPA 2IG00001). Tier-0 screening.[/]"
    )
    if write:
        for r in (base, build):
            path = scenario_stage.write_scenario(r, settings=settings)
            console.print(f"[green]Wrote[/] {path}")


@app.command(name="tier1")
def tier1(
    return_period: int = typer.Option(
        25, "--return-period", help="Design storm return period (yr)."
    ),
    offline: bool = typer.Option(False, "--offline", help="Use cached/fixture rainfall only."),
) -> None:
    """Tier-1 EPA SWMM: detention sizing + sanitary wet-weather surcharge."""
    from bosc.config import Settings
    from bosc.hydrology.tier1 import run_tier1, tier1_findings

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
) -> None:
    """Reduce the EPA RSEI Public Data Set to one county's toxic-release inventory.

    Joins elements -> release -> submission -> facility (+ chemical, media) and rolls
    up each facility's population-weighted RSEI Score (cancer/non-cancer split),
    Hazard, and pounds released. Bulk tables cache under data/cache/rsei (~340 MB on
    first run); the committed artifact is a small per-county YAML.
    """
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
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory for --districts (default: data/reference/lima-gis)."
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
        in_city = 0
        for pid in ids:
            rec = lima_gis.zoning_for_parcel(pid, settings=settings)
            if rec is not None:
                in_city += 1
                console.print(f"  [cyan]{pid}[/]: {rec.zoning}")
        console.print(
            f"\n[bold]{in_city}[/] of {len(ids)} cited parcels are within Lima city limits."
        )
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

    egraph = build_entity_graph(load_corpus(settings), enrich_parcels=True, settings=settings)

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
def site_build() -> None:
    """Stage web/ from data/extracted + docs, then render the static HTML site/ (regenerable)."""
    from bosc.site import build_site, render_site

    result = build_site()
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


if __name__ == "__main__":
    app()
