"""``watermark text-sidecars`` — the committed text sidecars for legacy binary formats (#1757).

``.doc`` / ``.dot`` / ``.xls`` / ``.rtf`` have no in-process reader, so a directory of them is
invisible to retrieval until each file is converted once, out of band, and the text committed
beside the corpus. This is that step: it rewrites the ``-text`` sibling tree of a directory under
``data/documents/`` and the manifest that pins each sidecar to its source's sha256.

It needs LibreOffice on PATH (``brew install --cask libreoffice``) and the real source bytes
(``git lfs pull``) — which is exactly why the output is committed rather than derived at index
time. ``--check`` needs neither converter nor write access: it re-hashes the sources and reports
drift, so CI or a reviewer can tell a current tree from a stale one.
"""

from __future__ import annotations

from typing import Annotated

import typer

from watermark.cli._base import app, console, get_settings


@app.command("text-sidecars")
def text_sidecars_cmd(
    source_dir: Annotated[
        str,
        typer.Argument(
            help="Directory under data/documents/ to convert, e.g. "
            "'legal/prr-mandamus/prr-production-2026-07-24-sanitary'.",
        ),
    ],
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Verify the committed tree against the source bytes instead of rewriting it.",
        ),
    ] = False,
) -> None:
    """Generate (or verify) the committed ``-text`` sidecars for a source directory."""
    from watermark.text_sidecars import ConverterUnavailableError, generate
    from watermark.text_sidecars import check as check_tree

    settings = get_settings()
    rel = source_dir.strip("/").removeprefix("data/documents/")

    if check:
        findings = check_tree(settings.documents_dir, rel)
        if not findings:
            console.print(f"[green]Sidecars current[/] for {rel}")
            return
        for finding in findings:
            console.print(f"[red]{finding.kind}[/] {finding.path} — {finding.detail}")
        console.print(f"\n[red]{len(findings)} finding(s)[/] — run `watermark text-sidecars {rel}`")
        raise typer.Exit(1)

    try:
        report = generate(settings.documents_dir, rel)
    except ConverterUnavailableError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    console.print(
        f"[green]Wrote[/] {report.written} sidecars → data/documents/{report.sidecar_dir}"
    )
    if report.empty:
        console.print(f"[dim]{report.empty} document(s) yielded no text (empty or image-only)[/]")
    if report.failed:
        console.print(f"[yellow]{report.failed} conversion(s) failed[/] — see the manifest notes")
    if report.skipped_pointers:
        console.print(
            f"[yellow]{report.skipped_pointers} unresolved Git-LFS pointer(s) skipped[/] — "
            "run `git lfs pull` and re-run"
        )
    if report.pruned:
        console.print(f"[dim]pruned {len(report.pruned)} stale sidecar(s)[/]")
