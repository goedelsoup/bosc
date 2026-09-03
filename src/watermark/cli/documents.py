"""``watermark documents manifest`` — the committed record of the corpus' vaulted bytes (#2143).

`data/documents/**` is moving out of Git-LFS and into a yidam artifact vault (epic #2141). A vault
stores bytes; git stores the record of them, and this writes that record: one `vault.yaml` per
collection, pinning every file to the content address the vault holds it under.

It needs **neither the real bytes nor the network**. A Git-LFS oid is the SHA-256 of the file's
content — the same value a vault addresses by — so an unresolved pointer already carries its own
address, and this produces identical output on a `git lfs pull`ed tree and on the `lfs: false`
checkout CI uses. `--check` is therefore gateable in CI, which is the whole reason the record can
be trusted. See `docs/artifact-vault.md`.
"""

from __future__ import annotations

from typing import Annotated

import typer

from watermark.cli._base import console, documents_app, get_settings


@documents_app.command("manifest")
def documents_manifest_cmd(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Report drift between the committed manifests and the tree; write nothing.",
        ),
    ] = False,
    collection: Annotated[
        str,
        typer.Option(
            "--collection",
            help="Limit to one collection, e.g. 'documents/aedg' or 'reference/usgs'.",
        ),
    ] = "",
) -> None:
    """Write (or verify) the committed `vault.yaml` record for every vaulted collection."""
    from watermark.documents.vault import (
        UnaddressableError,
        build,
        collection_of,
        tracked_rels,
        write,
    )
    from watermark.documents.vault import (
        check as check_manifests,
    )

    settings = get_settings()
    data_dir = settings.data_dir
    repo_root = data_dir.parent

    rels: list[str] | None = None
    if collection:
        wanted = collection.strip("/")
        rels = [r for r in tracked_rels(repo_root, data_dir.name) if collection_of(r) == wanted]
        if not rels:
            console.print(f"[red]No Git-LFS-tracked file under[/] {wanted}")
            raise typer.Exit(2)

    if check:
        findings = check_manifests(data_dir, repo_root, rels=rels)
        if not findings:
            console.print("[green]Vault manifests current[/]")
            return
        for finding in findings[:50]:
            console.print(f"[red]{finding.kind}[/] {finding.rel} — {finding.detail}")
        if len(findings) > 50:
            console.print(f"[dim]… and {len(findings) - 50} more[/]")
        console.print(f"\n[red]{len(findings)} finding(s)[/] — run `watermark documents manifest`")
        raise typer.Exit(1)

    try:
        manifests = build(data_dir, repo_root, rels=rels)
    except UnaddressableError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    written = write(data_dir, manifests)
    artifacts = sum(len(m.artifacts) for m in manifests)
    total = sum(m.meta.counts["bytes"] for m in manifests)
    distinct = len({a.sha256 for m in manifests for a in m.artifacts})
    # `write` leaves an unchanged collection alone, so report both halves: "0 rewritten" over a
    # current corpus is the good outcome, and reading it as "nothing found" would be alarming.
    unchanged = len(manifests) - len(written)
    console.print(
        f"[green]{len(written)} manifest(s) rewritten[/], {unchanged} already current · "
        f"{artifacts} artifact(s) · {distinct} distinct address(es) · {total / 1_048_576:.0f} MiB"
    )
