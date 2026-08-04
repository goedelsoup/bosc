from __future__ import annotations

import typer
from rich.table import Table

from watermark.cli._base import (
    console,
    hypotheses_app,
)


@hypotheses_app.command("list")
def hypotheses_list() -> None:
    """List the registered boom-origin hypotheses (watermark.hypotheses.HYPOTHESES)."""
    from watermark.hypotheses import HYPOTHESES, load_assessments

    cells = load_assessments()
    table = Table("id", "n", "name", "status", "cells")
    for hid, hyp in HYPOTHESES.items():
        n = sum(1 for c in cells if c.hypothesis == hid)
        table.add_row(hid, hyp.number, hyp.name, hyp.status, str(n))
    console.print(table)


@hypotheses_app.command("show")
def hypotheses_show(
    hid: str = typer.Argument(..., help="Hypothesis id (water | defense | surveillance)."),
) -> None:
    """Print a hypothesis and its committed evidence cells."""
    from watermark.hypotheses import HYPOTHESES, assessments_for

    if hid not in HYPOTHESES:
        raise typer.BadParameter(
            f"unknown hypothesis {hid!r}; known: {sorted(HYPOTHESES)}", param_hint="hid"
        )
    hyp = HYPOTHESES[hid]
    console.print(f"[bold]{hyp.number} · {hyp.name}[/]  [dim]({hyp.status})[/]")
    # Question first, then the candidate answer under test, then the thesis behind it (#1917).
    console.print(f"  [bold]{hyp.question}[/]")
    console.print(f"  {hyp.claim}\n  [dim]{hyp.thesis}[/]\n")
    cells = assessments_for(hid)
    if not cells:
        console.print("[dim](no assessment cells — rendered from the site registry)[/]")
        return
    table = Table("site", "signal", "tag", "group", *hyp.fields, "cites")
    for c in sorted(cells, key=lambda x: x.site):
        row = [c.site, c.signal or "—", c.tag, c.group or "—"]
        row += [c.fields.get(f, "—") for f in hyp.fields]
        row.append(str(len(c.citations)))
        table.add_row(*row)
    console.print(table)


@hypotheses_app.command("check")
def hypotheses_check() -> None:
    """Lint the registry and its committed evidence cells.

    Two passes. The REGISTRY pass (#1917) asks whether each hypothesis states the question
    it exists to answer — required content, not optional prose, because every surface now
    leads with it. The CELL pass covers unknown hypothesis, bad group/field, and missing
    citation. Both are hard and exit non-zero; 'untracked-site' is an informational note
    (a cell for a not-yet-registered candidate).
    """
    from watermark.hypotheses import lint_assessments, lint_hypotheses

    registry = lint_hypotheses()
    if registry:
        table = Table("hypothesis", "issue", "detail")
        for reg in registry:
            table.add_row(reg.hypothesis, f"[red]{reg.kind}[/]", reg.detail)
        console.print(table)
        raise typer.Exit(1)

    findings = lint_assessments()
    if not findings:
        console.print(
            "[green]hypotheses: every hypothesis states its question, and all cells are valid[/]"
            " — no lint findings."
        )
        return
    hard = [f for f in findings if f.kind != "untracked-site"]
    table = Table("hypothesis/site", "issue", "detail")
    for f in findings:
        color = "yellow" if f.kind == "untracked-site" else "red"
        table.add_row(f"{f.hypothesis}/{f.site}", f"[{color}]{f.kind}[/]", f.detail)
    console.print(table)
    console.print(
        f"\n[dim]{len(hard)} hard, {len(findings) - len(hard)} informational "
        "(untracked-site = a cell for a tracking candidate with no SiteProfile yet).[/]"
    )
    if hard:
        raise typer.Exit(1)
