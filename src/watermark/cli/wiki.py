"""``watermark`` wiki / knowledge-layer commands (epic #1560).

Root verbs backing the wiki glossary and its supporting corpus-hygiene passes. Today:
``term-backlog`` (A1, #1565) — harvest undefined domain terms from the prose into a per-site,
density-ranked backlog under ``data/concepts/backlog/`` that drives batch concept authoring (A2).
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
    from watermark.site import term_backlog as tb

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
