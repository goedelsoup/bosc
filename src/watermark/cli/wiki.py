"""``watermark`` wiki / knowledge-layer commands (epic #1560).

Root verbs backing the wiki glossary and its supporting corpus-hygiene passes:

* ``term-backlog`` (A1, #1565) — harvest undefined domain terms from the prose into a per-site,
  density-ranked backlog under ``data/concepts/backlog/`` that drives batch concept authoring (A2).
* ``wiki-lint`` (C, #1571) — audit the wiki cross-reference graph: flag unresolved ``[[wiki links]]``
  (the hard gate), orphan concepts, and under-linked concepts, with optional ``--suggest`` hints.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import app, console, get_settings, wrote


@app.command(name="term-backlog")
def term_backlog(
    site: str | None = typer.Option(
        None, "--site", help="Harvest one site (registry slug); default harvests every site."
    ),
    no_network: bool = typer.Option(
        False, "--no-network", help="Skip the shared docs/skills 'network' scope."
    ),
    no_discovery: bool = typer.Option(
        False, "--no-discovery", help="Lexicon pass only; skip the acronym-discovery candidates."
    ),
    min_count: int = typer.Option(
        1, "--min-count", help="Minimum occurrences for a term to enter the backlog."
    ),
    max_candidates: int = typer.Option(
        40, "--max-candidates", help="Cap on discovery candidates per scope (0 = uncapped)."
    ),
    out: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/concepts/backlog)."
    ),
    write: bool = typer.Option(
        True, "--write/--no-write", help="Write the per-scope YAML files (off = summary only)."
    ),
) -> None:
    """Harvest undefined glossary terms from investigative prose → a per-site backlog.

    Mines each site's extracted ``.md`` record (plus the shared ``docs/`` + ``.claude/skills/``
    layer, scope ``network``) for domain terms the wiki doesn't yet define — a curated-lexicon
    pass (``terms``) plus a mechanical acronym-discovery pass (``candidates``) — and writes one
    ``<scope>.yaml`` per scope with any hits under ``data/concepts/backlog/`` (#1565). Regenerable;
    the committed backlog drives A2 (batch-author concepts, #1566).
    """
    from watermark.cli._base import SITES
    from watermark.site import term_backlog as tb

    if site is not None and site not in SITES:
        raise typer.BadParameter(
            f"unknown site {site!r}; known: {sorted(SITES)}", param_hint="--site"
        )
    settings = get_settings()
    sites = [site] if site else None
    backlogs = tb.harvest_backlog(
        settings,
        sites=sites,
        include_network=not no_network,
        min_count=min_count,
        discover=not no_discovery,
        max_candidates=max_candidates,
    )

    out_dir = Path(out) if out else settings.concepts_dir / tb.BACKLOG_DIRNAME
    repo_root = settings.data_dir.parent

    def _display(path: Path) -> str:
        try:
            return str(path.relative_to(repo_root))
        except ValueError:
            return str(path)

    table = Table("scope", "sources", "terms", "candidates", "file")
    written = 0
    for scope in sorted(backlogs):
        bl = backlogs[scope]
        path = tb.write_backlog(bl, out_dir) if write else None
        if path is not None:
            written += 1
        table.add_row(
            scope,
            str(bl.sources_scanned),
            str(len(bl.terms)),
            str(len(bl.candidates)),
            _display(path) if path else "—",
        )
    console.print(table)
    if write and written:
        wrote(f"{written} backlog file(s) under {out_dir}")
    elif write:
        console.print("[yellow]No undefined terms harvested — nothing written.[/]")


@app.command(name="wiki-lint")
def wiki_lint(
    min_degree: int = typer.Option(
        2,
        "--min-degree",
        help="Under-linked threshold: flag concepts with in+out cross-links below this.",
    ),
    suggest: bool = typer.Option(
        False,
        "--suggest",
        help="Emit link suggestions — nodes a weak concept names in prose but never links.",
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Exit non-zero on any unresolved [[wiki link]] (the corpus-hygiene CI gate).",
    ),
    out: str | None = typer.Option(
        None, "--out", help="Also write the plain-text report to this file."
    ),
) -> None:
    """Audit the wiki cross-link graph for the active site — orphan / link-coverage audit (#1571).

    Rebuilds the ``[[wiki link]]`` cross-reference graph the frontend renders (resolved concept /
    person body links + ``related:`` slugs, over the same site-scoped concepts / entities / people)
    and reports three gaps: **unresolved [[wiki links]]** (the hard gate — they ship as broken
    ``wikilink-missing`` spans), **orphan concepts** (nothing links to them), and **under-linked
    concepts** (fewer than ``--min-degree`` cross-links). ``--suggest`` proposes links a weak
    concept already names in prose. Offline, read-only; per-site via the global ``--site`` flag.

    Complements ``watermark corpus-mirror``'s graph-check/lint, which audit the yidam *node* graph's
    structured links; this pass audits the inline prose cross-links that graph is blind to.
    """
    from watermark.site.wiki_lint import lint_wiki, render_report

    settings = get_settings()
    report = lint_wiki(settings, min_degree=min_degree, suggest=suggest)

    console.print(
        f"[bold]wiki-lint · {report.site}[/] — {report.concepts} concept(s), "
        f"{report.links_scanned} cross-link(s) scanned."
    )
    if report.unresolved:
        console.print(f"[red]unresolved [[wiki links]]: {len(report.unresolved)}[/]")
        for u in report.unresolved:
            where = f"{u.source_id}" + (f":{u.line}" if u.line else " (related:)")
            console.print(f"  [yellow]{where}[/] → [red][[{u.target}]][/]")
    if report.orphans:
        console.print(
            f"[yellow]orphan concepts: {len(report.orphans)}[/] [dim](nothing links to them)[/]"
        )
        for o in report.orphans:
            console.print(f"  [dim]{o.id} (out {o.out_degree})[/]")
    if report.underlinked:
        console.print(
            f"[yellow]under-linked concepts: {len(report.underlinked)}[/] "
            f"[dim](degree < {report.min_degree})[/]"
        )
        for ul in report.underlinked:
            console.print(f"  [dim]{ul.id} (in {ul.in_degree}, out {ul.out_degree})[/]")
    if suggest and report.suggestions:
        console.print(
            f"[cyan]suggested links: {len(report.suggestions)}[/] [dim](named, not linked)[/]"
        )
        for s in report.suggestions:
            why = "→ orphan" if s.helps == "orphan-target" else "(under-linked)"
            console.print(f"  [dim]{s.source_id} could link [[{s.target.label}]] {why}[/]")

    if out:
        Path(out).write_text(
            render_report(report, suggest=suggest).rstrip() + "\n", encoding="utf-8"
        )
        wrote(out)

    if report.ok:
        advisory = len(report.orphans) + len(report.underlinked)
        tail = f" [dim]({advisory} advisory finding(s))[/]" if advisory else ""
        console.print(f"[green]wiki-lint clean[/] — every cross-link resolves.{tail}")
    elif check:
        console.print(
            f"[red]wiki-lint: {len(report.unresolved)} unresolved [[wiki link(s)]] — "
            f"fix or unlink them.[/]"
        )
        raise typer.Exit(code=1)
