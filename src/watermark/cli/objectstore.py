from __future__ import annotations

import typer

from watermark.cli._base import (
    console,
    get_settings,
    objectstore_app,
)


@objectstore_app.command("sync")
def objectstore_sync_cmd(
    target: str = typer.Option(
        "local", "--target", help="'local' (dev bucket) or 'remote' (prod bucket)."
    ),
    collection: str = typer.Option(
        "", "--collection", help="Limit to one data/documents/<slug> (default: full corpus)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="List planned uploads; upload nothing."),
) -> None:
    """Upload data/documents/** into R2 — incremental, LFS-aware (epic #274 / #279).

    Skips objects already current (size + ETag) and unresolved Git-LFS pointers. Stamps
    each object's media_type/render_class so /api/doc serves the right type. Credentials
    come from WATERMARK_DOCUMENTS_OBJECT_STORE_* (never committed). See docs/object-store.md.
    """
    from watermark.site.objectstore import (
        ObjectStore,
        ObjectStoreUnconfiguredError,
        RemoteHead,
        corpus_items,
        run_sync,
        store_from_settings,
    )

    if target not in ("local", "remote"):
        console.print("[red]--target must be 'local' or 'remote'.[/]")
        raise typer.Exit(2)

    settings = get_settings()
    items = corpus_items(settings.documents_dir, collection=collection or None)
    if not items:
        scope = f" under collection '{collection}'" if collection else ""
        console.print(f"[yellow]No documents found{scope}.[/]")
        raise typer.Exit(0)

    class _EmptyStore:
        """Stand-in for an offline dry-run: treats the bucket as empty (head → None)."""

        def head(self, key: str) -> RemoteHead | None:
            return None

        def put(
            self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]
        ) -> None:
            raise NotImplementedError  # never reached in dry-run

    store: ObjectStore
    try:
        store = store_from_settings(settings, target=target)
    except ObjectStoreUnconfiguredError as exc:
        if not dry_run:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1) from None
        console.print(
            f"[yellow]Object store not configured — dry-run assumes an empty bucket.[/]\n[dim]{exc}[/]"
        )
        store = _EmptyStore()

    def _human(n: int) -> str:
        size = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    plan, result = run_sync(
        items,
        store,
        dry_run=dry_run,
        on_upload=lambda it: console.print(f"  [green]↑[/] {it.rel} [dim]({_human(it.size)})[/]"),
    )

    if dry_run:
        for it in plan.upload:
            console.print(f"  [dim]would upload[/] {it.rel} [dim]({_human(it.size)})[/]")
    if plan.lfs_skipped:
        console.print(
            f"[yellow]⚠ {len(plan.lfs_skipped)} unresolved Git-LFS pointer(s) skipped — "
            "run `git lfs pull` to upload them.[/]"
        )
        for it in plan.lfs_skipped[:10]:
            console.print(f"    [dim]{it.rel}[/]")

    verb = "Would upload" if dry_run else "Uploaded"
    n = len(plan.upload) if dry_run else result.uploaded
    nbytes = plan.upload_bytes if dry_run else result.uploaded_bytes
    console.print(
        f"\n[bold]{verb}:[/] {n} file(s), {_human(nbytes)} · "
        f"unchanged {len(plan.unchanged)} · lfs-skipped {len(plan.lfs_skipped)} "
        f"→ {target} bucket"
    )


@objectstore_app.command("audit")
def objectstore_audit_cmd(
    base_url: str = typer.Option(
        "", "--base", help="Origin to probe (default: WATERMARK_PUBLIC_SITE_BASE_URL)."
    ),
    via: str = typer.Option(
        "api",
        "--via",
        help="'api' (probe /api/doc), 'store' (also HEAD the bucket — needs credentials).",
    ),
    limit: int = typer.Option(
        20, "--limit", min=0, help="How many findings of each kind to print."
    ),
    concurrency: int = typer.Option(8, "--concurrency", help="Parallel HEAD requests."),
) -> None:
    """Check that production serves every document the site publishes (#2149).

    Compares three sets — what this commit's bundles offer, what the deployed allowlist admits,
    what /api/doc actually returns — and names which one broke. Exits 1 when production offers a
    download it cannot serve, or (with --via store) when an offered object is not in the bucket.
    Deploy lag is REPORTED, never failed. See docs/object-store.md.
    """
    from watermark.site.doc_serving import GateUnavailableError, audit
    from watermark.site.objectstore import (
        ObjectStoreUnconfiguredError,
        store_from_settings,
    )

    if via not in ("api", "store"):
        console.print("[red]--via must be 'api' or 'store'.[/]")
        raise typer.Exit(2)

    settings = get_settings()
    base = (base_url or settings.public_site_base_url).rstrip("/")

    store_head = None
    if via == "store":
        try:
            store_head = store_from_settings(settings, target="remote").head
        except ObjectStoreUnconfiguredError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1) from None

    try:
        result = audit(base_url=base, store_head=store_head, concurrency=concurrency)
    except GateUnavailableError as exc:
        console.print(f"[red]Publish gate unreadable — nothing could be compared:[/] {exc}")
        raise typer.Exit(1) from None

    console.print(
        f"[bold]{base}[/] · offered {result.offered} · gate admits {result.gate_size} · "
        f"served {result.served}"
    )
    for label, items, colour in (
        ("unserved (production offers it and 404s)", result.unserved, "red"),
        ("absent from the store (no deploy fixes this)", result.store_absent, "red"),
        ("not yet in the deployed gate (deploy lag)", result.ungated, "yellow"),
    ):
        if not items:
            continue
        console.print(f"\n[{colour}]{len(items)} {label}:[/]")
        for f in items[:limit]:
            console.print(f"  [dim]{f.rel}[/] — {f.detail}")
        if len(items) > limit:
            console.print(f"  [dim]… {len(items) - limit} more[/]")

    if result.gate_only:
        console.print(
            f"\n[dim]{len(result.gate_only)} rel(s) the gate admits that this commit does not "
            "publish — the deploy is ahead of this checkout, or a clearance was reverted.[/]"
        )

    if result.ok:
        console.print("\n[green]✓ every document production offers, production serves.[/]")
        return
    console.print(
        "\n[red]✗ production cannot serve what it offers.[/] "
        "Absent objects → `watermark objectstore sync --target remote`; "
        "gate-admitted 404s → check the bucket and DOCS_ENABLED."
    )
    raise typer.Exit(1)
