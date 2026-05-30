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
def ask(question: str) -> None:
    """Ask the Project BOSC research agent a question."""
    answer = asyncio.run(analyze.research_question(question))
    console.print(answer)


@app.command()
def extract(
    doc_id: str = typer.Argument(..., help="A doc_id from `bosc ingest`."),
    page: int | None = typer.Option(None, "--page", help="0-based PDF page index."),
    pdf_page: int | None = typer.Option(
        None, "--pdf-page", help="1-based printed sheet number (= page index + 1)."
    ),
    dpi: int = typer.Option(DEFAULT_DPI, "--dpi", help="Render resolution for the vision read."),
    detail: bool = typer.Option(
        False, "--detail", "-d", help="Extract full line items, not just section subtotals."
    ),
    write: bool = typer.Option(False, "--write", "-w", help="Save the YAML under data/extracted."),
) -> None:
    """Extract one cost-estimate page (hybrid OCR-text + 300 DPI vision read)."""
    from bosc.models import DetailExtraction, DetailPageExtraction, PageExtraction
    from bosc.pipeline import analyze
    from bosc.pipeline import extract as extract_stage

    if (page is None) == (pdf_page is None):
        console.print("[red]Provide exactly one of --page (0-based) or --pdf-page (1-based).[/]")
        raise typer.Exit(code=2)
    page_index = page if page is not None else pdf_page - 1  # type: ignore[operator]

    docs = {d.doc_id: d for d in ingest.discover()}
    doc = docs.get(doc_id)
    if doc is None:
        console.print(f"[red]Unknown doc_id:[/] {doc_id}. Run `bosc ingest` to list ids.")
        raise typer.Exit(code=1)

    extraction: PageExtraction | DetailPageExtraction
    if detail:
        extraction = extract_stage.extract_detail_page(doc, page_index, dpi=dpi)
    else:
        extraction = extract_stage.extract_estimate_page(doc, page_index, dpi=dpi)

    est = extraction.estimate
    color = "green" if est.reconciles() else "yellow"
    console.print(
        f"[bold]{est.name}[/] — confidence [{color}]{est.confidence}[/], "
        f"reconciles={est.reconciles()}, warnings={len(est.warnings)}"
    )
    for warning in est.warnings:
        console.print(f"  [yellow]![/] {warning}")

    # For detail extractions, show the line-item -> section-subtotal rollup.
    if isinstance(est, DetailExtraction):
        findings = analyze.reconcile_detail(est)
        for f in findings:
            console.print(f"[{'green' if f.ok else 'red'}]{f}[/]")

    if write:
        path = extract_stage.save_extraction(extraction)
        console.print(f"[green]Saved[/] {path}")
    else:
        console.print(extraction.to_yaml())


if __name__ == "__main__":
    app()
