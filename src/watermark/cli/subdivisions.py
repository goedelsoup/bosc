from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import (
    console,
    get_settings,
    offline_settings,
    subdivisions_app,
)


@subdivisions_app.command("list")
def subdivisions_list(
    undiscovered: bool = typer.Option(
        False, "--undiscovered", help="Only bodies still at platform: unknown."
    ),
) -> None:
    """List the committed subdivisions registry (grounded cadence + publishing)."""
    from watermark.civic import load_registry

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

    from watermark.civic import load_registry
    from watermark.civic.discovery import discover

    settings = offline_settings("civic", offline)
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

    from watermark.civic import load_registry
    from watermark.civic.fetchers import FetcherNotImplementedError, fetch_meetings

    settings = offline_settings("civic", offline)
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
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only download docs dated on/after this ISO date (yyyy-mm-dd); "
        "undated docs are skipped. Use to ingest just the new meetings.",
    ),
) -> None:
    """Download a body's minutes/agendas into data/documents/<slug>/meetings/.

    Fetches the body's MeetingDoc inventory, then pulls each binary into the raw,
    LFS-tracked evidence tree under its as-received name, and writes a
    non-destructive download manifest under data/extracted/<slug>/meetings/.
    Idempotent: unchanged files are skipped, conflicting bytes are kept beside the
    original. Dates in the manifest are listing-derived (not yet content-verified).
    """
    from watermark.civic import load_registry
    from watermark.civic.downloader import download_meetings, write_manifest
    from watermark.civic.fetchers import FetcherNotImplementedError, fetch_meetings

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

    if since is not None:
        before = len(docs)
        docs = [d for d in docs if d.date and d.date >= since]
        console.print(
            f"[dim]--since {since}: {len(docs)} of {before} documents dated on/after "
            f"that date ({before - len(docs)} earlier/undated skipped).[/]"
        )

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

    report = download_meetings(
        body, docs, settings=settings, limit=limit, source_page=url or body.publishing.records_url
    )
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
    from watermark.civic import load_registry
    from watermark.civic.indexer import OcrUnavailableError, index_meetings, write_index

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
            f"[bold]watermark subdivisions download {slug}[/] first."
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
    from watermark.civic import load_registry
    from watermark.civic.audit import audit_body, write_audit

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
    from watermark.civic import load_registry
    from watermark.civic.summarize import summarize_corridor_meetings, write_summaries

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
            f"[bold]watermark subdivisions index {slug}[/] first."
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
