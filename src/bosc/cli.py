"""``bosc`` command-line interface.

Commands:
    bosc version
    bosc ingest                 # inventory source documents
    bosc reconcile <file>       # arithmetic checks over a summary extraction
    bosc ask "<question>"       # ask the research agent
    bosc extract <doc-id> ...   # run an agentic extraction (seam for your data)
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

    graph = entities_stage.build_entity_graph()
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


if __name__ == "__main__":
    app()
