"""``watermark corpus-mirror`` — project the BOSC corpus into yidam node format (#1561).

A thin wrapper over :mod:`watermark.site.corpus_mirror`: load the active site's corpus, project
it into ``.yidam/corpus/`` as yidam nodes, and (by default) run the yidam ``graph-check`` rules
over the result so a broken mirror fails loudly. Per-site via the global ``--site`` flag.
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
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Run the yidam graph-check rules after writing and fail on any issue.",
    ),
) -> None:
    """Project the corpus (entities, relationships, concepts, people, leads, hypotheses,
    [open] claims) into yidam corpus nodes under .yidam/corpus/ for the active site.

    The mirror is the bridge that lets ``yidam corpus-index`` / ``graph-check`` / ``serve --mcp``
    and the vector index read BOSC's corpus (Epic #1560, E1). It's a git-ignored, regenerable
    artifact — re-run any time (`watermark --site <slug> corpus-mirror`); the committed corpus
    stays the source of truth. Every node is site-tagged and emits ≥1 outgoing link (the yidam
    graph rule); claim tags ([verified]/[inference]/[reference]/[open]) are preserved.
    """
    from watermark.site.corpus_mirror import (
        build_mirror,
        default_corpus_dir,
        render_corpus_index,
        validate_mirror,
        write_mirror,
    )

    settings = get_settings()
    corpus_dir = Path(out) if out else default_corpus_dir(settings)

    mirror = build_mirror(settings)
    write_mirror(mirror, corpus_dir)

    by_class = ", ".join(f"{cls} {n}" for cls, n in mirror.counts_by_class().items())
    console.print(
        f"[green]Mirrored[/] {settings.site} → {corpus_dir} — "
        f"{len(mirror.nodes)} nodes across {len(mirror.classes)} classes ([dim]{by_class}[/])."
    )

    if check:
        issues = validate_mirror(corpus_dir)
        if issues:
            console.print(f"[red]graph-check: {len(issues)} node(s) with issues[/]")
            for issue in issues:
                console.print(f"  [yellow]{issue.node}[/]")
                for problem in issue.problems:
                    console.print(f"    - {problem}")
            raise typer.Exit(code=1)
        console.print(f"[green]graph-check clean[/] — {len(mirror.nodes)} instances.")
        # Populate the corpus README's regen block (the yidam corpus-index target).
        _write_index_readme(corpus_dir, render_corpus_index(corpus_dir))


def _write_index_readme(corpus_dir: Path, index_md: str) -> None:
    """Drop the rendered corpus-index into the README's REGEN block (best-effort)."""
    readme = corpus_dir / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    start = text.find("<!-- REGEN: yidam corpus-index -->")
    end = text.find("<!-- /REGEN -->")
    if start == -1 or end == -1 or end < start:
        return
    head = text[: start + len("<!-- REGEN: yidam corpus-index -->")]
    tail = text[end:]
    readme.write_text(f"{head}\n{index_md}\n{tail}", encoding="utf-8")
