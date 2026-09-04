"""``watermark documents`` — the corpus' vaulted bytes: their record, and their restoration.

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


@documents_app.command("hydrate")
def documents_hydrate_cmd(
    check: Annotated[
        bool,
        typer.Option("--check", help="Report what hydration would do; write nothing."),
    ] = False,
    collection: Annotated[
        str,
        typer.Option("--collection", help="Limit to one collection, e.g. 'documents/aedg'."),
    ] = "",
    paths_from: Annotated[
        str,
        typer.Option(
            "--paths-from",
            help="File of data/-relative paths (one per line) to hydrate — the selective-pull set.",
        ),
    ] = "",
) -> None:
    """Restore vaulted bytes into the working tree under their as-received names.

    Hardlinks from the yidam vault cache to ``data/<rel>``, so the bytes are on disk once rather
    than twice; copies where the cache is on another device. **Never overwrites a file whose bytes
    differ from the record** — that is reported as a conflict and left alone, because a tool that
    resolved a divergence by overwriting it would destroy the evidence that there was one.

    Not ``yidam vault materialize``: that names its output ``<slug>-<hash8>.<ext>`` and this corpus'
    filenames are evidence. See docs/artifact-vault.md.
    """
    from pathlib import Path

    from watermark.documents.vault import collection_of, hydrate, recorded_rels

    settings = get_settings()
    data_dir = settings.data_dir

    rels: list[str] | None = None
    if paths_from:
        raw = Path(paths_from).read_text(encoding="utf-8").splitlines()
        rels = [line.strip().lstrip("./").removeprefix("data/") for line in raw if line.strip()]
    elif collection:
        wanted = collection.strip("/")
        rels = [r for r in recorded_rels(data_dir) if collection_of(r) == wanted]
        if not rels:
            console.print(f"[red]No recorded artifact under[/] {wanted}")
            raise typer.Exit(2)

    outcomes = hydrate(data_dir, rels=rels, settings=settings, check=check)
    counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.action] = counts.get(outcome.action, 0) + 1

    for outcome in outcomes:
        if outcome.action in ("conflict", "absent-from-cache", "pointer"):
            colour = "yellow" if outcome.action == "absent-from-cache" else "red"
            console.print(f"[{colour}]{outcome.action}[/] {outcome.rel} — {outcome.detail}")

    summary = " · ".join(f"{n} {action}" for action, n in sorted(counts.items()))
    verb = "would hydrate" if check else "hydrated"
    console.print(f"[green]{verb}[/] {len(outcomes)} artifact(s): {summary or 'nothing'}")

    # A conflict is a source byte that disagrees with the committed record — the one outcome that
    # must not pass silently. An uncached artifact is merely absent from THIS machine.
    # A conflict is a source byte disagreeing with the record; a pointer is a stub nothing can
    # read. Both must fail a gate. An uncached artifact is merely absent from THIS machine.
    if counts.get("conflict") or counts.get("pointer"):
        raise typer.Exit(1)
