"""``watermark corpus-mirror`` — project the BOSC corpus into yidam node format + reports (#1561/#1562).

A thin wrapper over :func:`watermark.site.corpus_mirror.regenerate_mirror`: load the active
site's corpus, project it into ``.yidam/corpus/`` as yidam nodes, regenerate the yidam reports
(``corpus-index`` / ``open-questions`` / ``graph-check`` / ``lint``) under ``.yidam/reports/``,
and (by default) fail loudly if the ``graph-check`` gate is dirty. Per-site via ``--site``.
"""

from __future__ import annotations

from pathlib import Path

import typer

from watermark.cli._base import app, console, get_settings


@app.command("corpus-mirror")
def corpus_mirror(
    out: str | None = typer.Option(
        None,
        "--out",
        help="Corpus dir to write (default: <repo-root>/.yidam/corpus, what the yidam CLI reads).",
    ),
    reports: str | None = typer.Option(
        None,
        "--reports",
        help="Reports dir to write (default: <repo-root>/.yidam/reports).",
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Run the yidam graph-check rules after writing and fail on any issue.",
    ),
    index: bool = typer.Option(
        False,
        "--index/--no-index",
        help="Also build the LanceDB vector index over the mirror (.yidam/index; yidam "
        "embed + index-build). Off by default — downloads the ~80 MB embedding model on "
        "first run and is rebuilt lazily by `yidam serve --mcp` regardless.",
    ),
) -> None:
    """Project the corpus (entities, relationships, concepts, people, leads, hypotheses,
    [open] claims) into yidam corpus nodes under .yidam/corpus/ for the active site, and
    regenerate the yidam reports under .yidam/reports/.

    The mirror is the bridge that lets ``yidam corpus-index`` / ``graph-check`` / ``serve --mcp``
    and the vector index read BOSC's corpus (Epic #1560). It's a git-ignored, regenerable
    artifact — re-run any time (`watermark --site <slug> corpus-mirror`), and every
    ``watermark export`` refreshes it; the committed corpus stays the source of truth. Every
    node is site-tagged and emits ≥1 outgoing link (the yidam graph rule); claim tags
    ([verified]/[inference]/[reference]/[open]) are preserved.
    """
    from watermark.site.corpus_mirror import (
        default_corpus_dir,
        default_reports_dir,
        regenerate_mirror,
    )

    settings = get_settings()
    corpus_dir = Path(out) if out else default_corpus_dir(settings)
    reports_dir = Path(reports) if reports else default_reports_dir(settings)

    regen = regenerate_mirror(settings, corpus_dir=corpus_dir, reports_dir=reports_dir)
    mirror = regen.mirror

    by_class = ", ".join(f"{cls} {n}" for cls, n in mirror.counts_by_class().items())
    console.print(
        f"[green]Mirrored[/] {settings.site} → {corpus_dir} — "
        f"{len(mirror.nodes)} nodes across {len(mirror.classes)} classes ([dim]{by_class}[/])."
    )
    console.print(
        f"[dim]  reports → {reports_dir} "
        f"(open-questions · graph-check · lint; corpus-index in corpus/README.md)[/]"
    )
    if regen.lint_issues:
        console.print(
            f"[yellow]lint: {len(regen.lint_issues)} advisory finding(s)[/] "
            f"[dim](see {reports_dir.name}/lint.txt)[/]"
        )

    if check:
        if regen.graph_issues:
            console.print(f"[red]graph-check: {len(regen.graph_issues)} node(s) with issues[/]")
            for issue in regen.graph_issues:
                console.print(f"  [yellow]{issue.node}[/]")
                for problem in issue.problems:
                    console.print(f"    - {problem}")
            raise typer.Exit(code=1)
        console.print(f"[green]graph-check clean[/] — {len(mirror.nodes)} instances.")

    if index:
        from watermark.site.yidam_index import build_yidam_index

        console.print("[dim]  embedding nodes → LanceDB vector index (all-MiniLM-L6-v2)…[/]")
        built = build_yidam_index(settings, mirror=mirror)
        console.print(
            f"[green]Indexed[/] {built.nodes} nodes ({built.dimension}-dim) → {built.index_dir} "
            f"[dim](reconciled with the /ask embeddings; queryable via yidam serve --mcp)[/]"
        )
