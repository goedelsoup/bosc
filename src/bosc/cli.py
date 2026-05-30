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
    kind: str = typer.Option("opc", "--kind", help="Document kind to extract."),
    profile: str = typer.Option(
        "auto", "--profile", help="Format profile id, or 'auto' to detect from the page."
    ),
    dpi: int = typer.Option(DEFAULT_DPI, "--dpi", help="Render resolution for the vision read."),
    detail: bool = typer.Option(
        False, "--detail", "-d", help="Extract full line items, not just section subtotals."
    ),
    write: bool = typer.Option(False, "--write", "-w", help="Save the YAML under data/extracted."),
) -> None:
    """Extract one cost-estimate page (hybrid OCR-text + 300 DPI vision read)."""
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

    extraction = extract_stage.extract_page(
        doc, page_index, kind=kind, profile=profile, detail=detail, dpi=dpi
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
