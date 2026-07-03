from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.table import Table

from watermark import __version__
from watermark.cli._base import (
    DEFAULT_DPI,
    SITES,
    OPCSummary,
    Settings,
    app,
    console,
    get_settings,
    offline_settings,
)
from watermark.pipeline import analyze, ingest


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"watermark {__version__}")


@app.command(name="onboard")
def onboard_cmd(
    slug: str = typer.Argument(..., help="Site slug; must be registered in watermark.sites.SITES."),
    offline: bool = typer.Option(False, "--offline", help="Use cached/committed fixtures only."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the plan (steps + target paths); write nothing."
    ),
    check: bool = typer.Option(
        False, "--check", help="Lint the profile (unfilled / copied-from-Lima fields) and exit."
    ),
    research: bool = typer.Option(
        False,
        "--research",
        help="Also run the discipline-bound self-research first pass (paid/online LLM call).",
    ),
) -> None:
    """Onboard a watershed-point site: scaffold per-site data + run the reach connectors.

    Builds its own Settings for SLUG (the global --site is not needed). Proposes; never
    promotes — flipping the site live in web/src/lib/sites.ts stays a manual,
    parity-gated edit. See docs/onboarding.md.
    """
    from watermark.onboard import onboard_site
    from watermark.sites import profile_readiness

    if slug not in SITES:
        raise typer.BadParameter(
            f"unknown site {slug!r}; known: {sorted(SITES)}", param_hint="slug"
        )

    if check:
        findings = profile_readiness(slug)
        if not findings:
            console.print(
                f"[green]{slug}: profile looks ready[/] — no unfilled or copied-from-Lima fields."
            )
            return
        placeholders = [f for f in findings if f.kind == "placeholder"]
        table = Table("field", "issue", "detail")
        for f in findings:
            color = "red" if f.kind == "placeholder" else "yellow"
            table.add_row(f.field, f"[{color}]{f.kind}[/]", f.detail)
        console.print(table)
        console.print(
            f"\n[dim]{len(placeholders)} unfilled, {len(findings) - len(placeholders)} match Lima "
            "(verify each). 'matches-lima' can be legitimate (e.g. an Ohio site's eia_state).[/]"
        )
        if placeholders:
            raise typer.Exit(1)
        return

    settings = Settings(site=slug, hydro_offline=offline)
    try:
        report = onboard_site(settings=settings, dry_run=dry_run, research=research)
    except ValueError as exc:  # e.g. per-site output paths collide with another site
        console.print(f"[red]Cannot onboard {slug}:[/] {exc}")
        raise typer.Exit(1) from exc

    banner = " [dim](dry run — nothing written)[/]" if dry_run else ""
    console.print(f"[bold]Onboarding {report.place}[/] ({report.slug} · {report.basin}){banner}\n")
    table = Table("step", "status", "output")
    colors = {"ok": "green", "dry-run": "yellow", "skipped": "yellow", "error": "red"}
    for s in report.steps:
        color = colors.get(s.status, "white")
        table.add_row(s.name, f"[{color}]{s.status}[/]", s.output_path or f"[dim]{s.detail}[/]")
    console.print(table)

    console.print("\n[bold]Review gate[/] — blocking; complete before promotion:")
    for i, item in enumerate(report.review_checklist, 1):
        console.print(f"  {i}. {item}")

    from watermark.catalog.sites import readiness

    r = readiness(report.slug)
    ready = "[green]ready[/]" if r.ready else f"[yellow]{len(r.missing)} missing[/]"
    console.print(
        f"\n[bold]Catalog readiness[/] — {r.present}/{r.total} datasets present · {ready}"
    )
    if r.missing:
        console.print(f"  [dim]still needed (catalog per-site axis):[/] {', '.join(r.missing)}")
    console.print(
        "\n[dim]onboard never promotes. When parity is reached, flip status/selectable in "
        "web/src/lib/sites.ts by hand (one reviewed edit).[/]"
    )


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
    from watermark.pipeline import timeline as timeline_stage

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
    from watermark.pipeline import entities as entities_stage

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
    from watermark import ledger as ledger_mod

    settings = offline_settings("hydro", offline)
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
def ask(
    question: str,
    no_tools: bool = typer.Option(
        False, "--no-tools", help="Disable the BOSC data tools (answer from the prompt alone)."
    ),
) -> None:
    """Ask the Project BOSC research agent a question (streams the answer)."""
    from watermark.agent.client import AgentResult, ResearchAgent

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
    doc_id: str = typer.Argument(..., help="A doc_id from `watermark ingest`."),
    page: int | None = typer.Option(None, "--page", help="0-based PDF page index."),
    pdf_page: int | None = typer.Option(
        None, "--pdf-page", help="1-based printed sheet number (= page index + 1)."
    ),
    kind: str = typer.Option(
        "opc",
        "--kind",
        help="Document kind: opc | deed | npdes | sos | epa | wetland | plan | engineering | sanitary.",
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
    from watermark.models import (
        DeedExtraction,
        EngineeringExtraction,
        EpaExtraction,
        NpdesExtraction,
        PlanExtraction,
        SosExtraction,
        WetlandExtraction,
    )
    from watermark.pipeline import analyze
    from watermark.pipeline import extract as extract_stage

    docs = {d.doc_id: d for d in ingest.discover()}
    doc = docs.get(doc_id)
    if doc is None:
        console.print(f"[red]Unknown doc_id:[/] {doc_id}. Run `watermark ingest` to list ids.")
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
        elif isinstance(doc_extraction, WetlandExtraction):
            w = doc_extraction.determination
            console.print(
                f"[bold]Wetland[/] {w.sampling_point or '?'} @ {w.city_county or '?'} — "
                f"wetland={w.is_wetland} "
                f"(veg={w.hydrophytic_vegetation_present} soil={w.hydric_soil_present} "
                f"hydro={w.wetland_hydrology_present}) applicant={w.applicant or '?'} "
                f"[dim](confidence {w.confidence})[/]"
            )
            warns = w.warnings
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
        elif isinstance(doc_extraction, EngineeringExtraction):
            r = doc_extraction.record
            comps = ", ".join(c.name for c in r.components[:8])
            design = ", ".join(
                f"{p.parameter}={p.value or '?'}{(' ' + p.unit) if p.unit else ''}"
                for p in r.design_parameters[:6]
            )
            firms = ", ".join(fm.name for fm in r.prepared_by)
            console.print(
                f"[bold]Engineering[/] {r.facility_name or r.project_name or '?'} — "
                f"{r.record_type or '?'} ({r.discipline or '?'}) "
                f"[dim](confidence {r.confidence})[/]\n"
                f"  components: {comps}\n"
                f"  design: {design}\n"
                f"  sheets: {len(r.sheets)}  prepared by: {firms}"
            )
            warns = r.warnings
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


@app.command(name="extract-sweep")
def extract_sweep(
    doc_id: str = typer.Argument(..., help="A doc_id from `watermark ingest` (the OPC bundle)."),
    pages: str = typer.Option(
        "318-327", "--pages", help="0-based inclusive PDF page range, e.g. 318-327."
    ),
    profile: str = typer.Option("auto", "--profile", help="OPC format profile id, or 'auto'."),
    detail: bool = typer.Option(
        True, "--detail/--no-detail", help="Extract full line items (default on)."
    ),
    dpi: int = typer.Option(0, "--dpi", help="Render DPI; 0 uses the default."),
    out: str | None = typer.Option(
        None, "--out", help="Write the assembled summary YAML here (default: print only)."
    ),
) -> None:
    """OPC sweep (#39): extract a page range, assemble the sub-estimates, reconcile the summary."""
    import yaml

    from watermark.pipeline import analyze
    from watermark.pipeline import extract as extract_stage

    docs = {d.doc_id: d for d in ingest.discover()}
    doc = docs.get(doc_id)
    if doc is None:
        console.print(f"[red]Unknown doc_id:[/] {doc_id}. Run `watermark ingest` to list ids.")
        raise typer.Exit(code=1)
    try:
        lo_s, hi_s = pages.split("-", 1)
        lo, hi = int(lo_s), int(hi_s)
    except ValueError:
        console.print(f"[red]--pages must be 'LO-HI' (0-based inclusive); got {pages!r}.[/]")
        raise typer.Exit(code=2) from None
    indices = list(range(lo, hi + 1))

    console.print(f"[dim]Sweeping {len(indices)} pages ({lo}-{hi}) of {doc_id} (live vision)...[/]")
    extractions = extract_stage.sweep_opc_pages(
        doc, indices, profile=profile, detail=detail, dpi=dpi or DEFAULT_DPI
    )
    if not extractions:
        console.print(
            "[yellow]No pages extracted.[/] The sweep runs live Claude-vision extraction — "
            "it needs WATERMARK_ANTHROPIC_API_KEY / ANTHROPIC_API_KEY."
        )
        raise typer.Exit(code=1)

    for pe in extractions:
        est = pe.estimate
        bad = [f for f in analyze.reconcile_estimate(est) if not f.ok]
        mark = "green" if not bad else "yellow"
        console.print(
            f"  p{pe.pdf_page} [bold]{est.name}[/] — {len(est.sections)} sections, "
            f"[{mark}]reconciles={not bad}[/]"
        )
    summary = extract_stage.assemble_opc_summary(
        [pe.estimate for pe in extractions], pdf_pages=[pe.pdf_page for pe in extractions]
    )
    findings = analyze.reconcile(summary)
    fails = [f for f in findings if not f.ok]
    console.print(
        f"\n[bold]Assembled summary[/]: {len(summary.sub_estimates)} sub-estimates, "
        f"grand total [bold]{summary.grand_total():,}[/]; "
        f"reconcile {len(findings) - len(fails)}/{len(findings)} pass"
    )
    for f in fails:
        console.print(f"  [red]{f}[/]", markup=False)
    if out:
        Path(out).write_text(
            yaml.safe_dump(summary.model_dump(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        console.print(f"[green]Wrote[/] {out}")
    else:
        console.print("[dim]Pass --out PATH to write the assembled summary YAML.[/]")


@app.command(name="reconcile-repair")
def reconcile_repair_cmd(
    filename: str = typer.Argument(
        "aedg/roundabouts.detail.opc.yaml",
        help="A committed detail/estimate YAML under data/extracted.",
    ),
) -> None:
    """OPC reconcile-repair (#40): reconcile an estimate and characterize the failing rollups.

    Runs the self-correcting loop with NO re-extractor, so it characterizes the known
    ROADWAY/PAVEMENT gaps without rewriting the reviewed artifact. The live `reextract`
    path (a higher-fidelity second pass) is wired in `analyze.reconcile_with_repair`.
    """
    from watermark.pipeline import analyze
    from watermark.pipeline import corpus as corpus_mod

    settings = get_settings()
    corpus = corpus_mod.load_corpus(settings)
    matches = [
        (rel, pe) for rel, pe in corpus.estimates if rel == filename or rel.endswith(filename)
    ]
    if not matches:
        console.print(f"[red]No estimates found for[/] {filename}. (Looked in data/extracted.)")
        raise typer.Exit(code=1)

    for rel, pe in matches:
        est = pe.estimate
        result = analyze.reconcile_with_repair(est)  # no reextractor -> characterize, don't rewrite
        fails = result.failures
        ok = len(result.findings) - len(fails)
        console.print(
            f"[bold]{est.name}[/] [dim]({rel})[/] — {len(result.findings)} checks, "
            f"[green]{ok} pass[/], [{'red' if fails else 'green'}]{len(fails)} fail[/]"
        )
        for f in result.findings:
            console.print(f"  {'ok' if f.ok else 'XX'} [{f.check}] {f.detail}", markup=False)
        if fails:
            keys = analyze.failing_section_keys(fails)
            console.print(
                f"  [yellow]re-extract targets:[/] "
                f"{', '.join(keys) if keys else '(estimate-level subtotal gap)'}"
            )
    console.print(
        "\n[dim]No re-extractor supplied, so the gaps are characterized, not rewritten "
        "(the committed reviewed artifact is left intact). Supply a re-extractor to "
        "analyze.reconcile_with_repair for the live higher-fidelity repair pass (#40).[/]"
    )


@app.command(name="network")
def network_cmd(
    live: bool = typer.Option(
        False, "--live", help="Ground the abstraction reach with live NWIS flow (offline-aware)."
    ),
    theory: str = typer.Option(
        "",
        "--theory",
        help="Theory overlay id(s) to enable, comma-separated (see `watermark theories`).",
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
    from watermark.hydrology import network as network_stage
    from watermark.pipeline import hydrology as hydro_stage

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

    Each is enabled per run with `watermark network --theory <id>`. Every theory is
    `theorized` and ships disabled; its injected magnitude is an assumption knob.
    """
    from watermark.hydrology import network as network_stage

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
        "[dim]Enable with[/] watermark network --theory <id> [dim](repeatable) or[/] --all-theories."
    )


@app.command(name="roundabout")
def roundabout_cmd() -> None:
    """Derive the Cole/Beery roundabout's directed flow into Pike Run (the waterfall theory).

    Grounds the `waterfall-roundabout-pike-run` network theory. The document-derived
    impervious catchment against the cited corridor rainfall shows the roundabout cannot
    sustainably augment Pike Run (mean-annual ~0.01 cfs, zero at the 7Q10); what it offers is
    transient storm surges — episodic flushing, not low-flow augmentation.
    """
    from watermark.pipeline import hydrology as hydro_stage

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
    from watermark.people import load_people
    from watermark.pipeline.corpus import load_corpus
    from watermark.pipeline.entities import build_entity_graph

    settings = get_settings()
    profiles = load_people(settings.people_dir)
    if not profiles:
        console.print(
            f"[yellow]No profiles[/] under {settings.people_dir}. "
            "Add `data/entities/people/<slug>.md` files with a frontmatter header."
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


@app.command("export")
def export(
    out: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/site/bundles/<active-site>)."
    ),
    no_embeddings: bool = typer.Option(
        False,
        "--no-embeddings",
        help="Skip the ask-embeddings feed (avoids the ~80 MB model download; hybrid retrieval degrades to BM25-only).",
    ),
) -> None:
    """Export the corpus as the typed JSON content bundle (regenerable).

    Writes versioned, schema-validated JSON feeds (records, timeline, entities, geo, …) +
    a manifest read by the frontend at build time. The bundle is per network site — it lands
    under data/site/bundles/<slug>/ for the active site (pick one with `watermark --site <slug>
    export`; default is the WATERMARK_SITE site).

    By default also generates ``ask-embeddings.json`` (all-MiniLM-L6-v2 vectors for hybrid
    BM25 + vector retrieval, #329). Use --no-embeddings to skip if you don't need it or
    want a faster export.
    """
    from watermark.site import export_bundle

    _export_preflight()
    result = export_bundle(out_dir=Path(out) if out else None, skip_embeddings=no_embeddings)
    console.print(
        f"[green]Exported[/] {result.out_dir} — {result.feed_count} feeds, {result.row_total} rows."
    )
    for ref in result.feeds:
        console.print(f"[dim]  {ref.name:<22} {ref.count:>6}  {ref.path}[/]")


def _export_preflight() -> None:
    """Warn (never abort) when the bundle's declared upstream chain is downstream-stale (#1024).

    The catalog's ``bundle-records`` entry declares the reference datasets the export reads;
    this surfaces any upstream refreshed more recently than its dependent at export time, with
    the ``watermark catalog run`` fix — the operator/agent decides whether to re-run upstreams
    or export with current data.
    """
    from watermark.catalog.check import upstream_preflight

    findings = upstream_preflight("bundle-records")
    for f in findings:
        console.print(f"[yellow]stale upstream:[/] {f.subject} — {f.detail}")
    if findings:
        console.print(
            "[yellow]exporting with current data[/] — re-run the stale producers first "
            "(`watermark catalog run bundle-records`) if the bundle must reflect them.\n"
        )
