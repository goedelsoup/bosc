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
    instructions: str = typer.Option(
        "Extract the cost estimate summary as structured YAML.",
        "--instructions",
        "-i",
        help="What to extract from the document.",
    ),
) -> None:
    """Run an agentic extraction over an ingested document."""
    from bosc.pipeline import extract as extract_stage

    docs = {d.doc_id: d for d in ingest.discover()}
    doc = docs.get(doc_id)
    if doc is None:
        console.print(f"[red]Unknown doc_id:[/] {doc_id}. Run `bosc ingest` to list ids.")
        raise typer.Exit(code=1)
    text = asyncio.run(extract_stage.extract_document(doc, instructions))
    console.print(text)


if __name__ == "__main__":
    app()
