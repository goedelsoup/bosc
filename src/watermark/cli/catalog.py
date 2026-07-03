from __future__ import annotations

import typer
from rich.table import Table

from watermark.cli._base import (
    SITES,
    catalog_app,
    console,
    get_settings,
)


@catalog_app.command("list")
def catalog_list(
    scope: str = typer.Option("", "--scope", help="Filter to one scope (e.g. reference)."),
    site: str = typer.Option("", "--site", help="View per-site existence/freshness for a slug."),
    stale: bool = typer.Option(False, "--stale", help="Only datasets past their refresh TTL."),
    missing: bool = typer.Option(False, "--missing", help="Only datasets absent (for the site)."),
) -> None:
    """List the committed catalog entries (data/catalog/<scope>/<id>.yaml).

    With ``--site <slug>`` the per-site axis is resolved: each dataset's ``site_scope`` is joined
    against that site (basin-shared + the site's slug-scoped copy) and printed with per-site
    existence + freshness — so "what does findlay still need?" is ``--site findlay --missing``.
    """
    if site:
        _catalog_list_site(site, scope=scope, stale=stale, missing=missing)
        return

    from watermark.catalog import load_entries

    entries = [e for e in load_entries() if not scope or e.scope == scope]
    obs = {}
    if stale or missing:
        from watermark.catalog.reconcile import reconcile

        obs = reconcile().entries
    if stale:
        entries = [e for e in entries if obs.get(e.id) and obs[e.id].stale]
    if missing:
        entries = [e for e in entries if obs.get(e.id) and not obs[e.id].exists]
    if not entries:
        console.print(f"[dim](no catalog entries{f' for scope {scope!r}' if scope else ''})[/]")
        return
    table = Table("id", "scope", "status", "tier", "site", "producer", "files")
    for e in sorted(entries, key=lambda x: (x.scope, x.id)):
        table.add_row(
            e.id,
            e.scope,
            e.status,
            e.access_tier,
            e.site_scope,
            e.producer.kind,
            str(len(e.storage)),
        )
    console.print(table)


def _catalog_list_site(site: str, *, scope: str, stale: bool, missing: bool) -> None:
    """The ``--site`` view of ``catalog list`` — per-site existence + freshness + readiness."""
    from watermark.catalog.sites import readiness, site_view

    if site not in SITES:
        raise typer.BadParameter(
            f"unknown site {site!r}; known: {sorted(SITES)}", param_hint="--site"
        )
    rows = [s for s in site_view(site) if not scope or s.scope == scope]
    if stale:
        rows = [s for s in rows if s.stale]
    if missing:
        rows = [s for s in rows if not s.present]
    table = Table("dataset", "scope", "site_scope", "present", "stale")
    for s in rows:
        present = "[green]yes[/]" if s.present else "[red]no[/]"
        is_stale = "[yellow]stale[/]" if s.stale else "—"
        table.add_row(s.id, s.scope, s.site_scope, present, is_stale)
    console.print(table)
    r = readiness(site)
    ready = "[green]ready[/]" if r.ready else f"[yellow]{len(r.missing)} missing[/]"
    console.print(
        f"\n[bold]{site}[/]: {r.present}/{r.total} datasets present · {ready}"
        f"{f' · {len(r.stale)} stale' if r.stale else ''}"
    )


@catalog_app.command("show")
def catalog_show(
    entry_id: str = typer.Argument(..., help="Catalog entry id to display."),
) -> None:
    """Print a single catalog entry's resolved record."""
    from watermark.catalog import get_entry

    entry = get_entry(entry_id)
    if entry is None:
        raise typer.BadParameter(f"unknown catalog entry {entry_id!r}", param_hint="entry_id")
    console.print(f"[bold]{entry.id}[/]  [dim]({entry.scope} · {entry.status})[/]")
    console.print(f"  {entry.title}")
    console.print(f"  [dim]producer:[/] {entry.producer.kind} · {entry.producer.source}")
    if entry.producer.command:
        console.print(f"  [dim]regen:[/] watermark {entry.producer.command}")
    console.print(
        f"  [dim]license:[/] {entry.license or '—'}  "
        f"[dim]access:[/] {entry.access_tier}  [dim]site:[/] {entry.site_scope}"
    )
    console.print(
        f"  [dim]refresh:[/] {entry.refresh.cadence}"
        f"{f' · ttl {entry.refresh.ttl_days}d' if entry.refresh.ttl_days else ''}"
        f"{f' · last {entry.refresh.last_refreshed}' if entry.refresh.last_refreshed else ''}"
    )
    if entry.storage:
        table = Table("relpath", "media_type", "lfs")
        for s in entry.storage:
            table.add_row(s.relpath, s.media_type, "yes" if s.lfs else "no")
        console.print(table)


@catalog_app.command("run")
def catalog_run_cmd(
    entry_id: str = typer.Argument(..., help="Catalog entry id to (re)produce."),
    site: str = typer.Option(
        "", "--site", help="Expand {site} in producer commands (default: the active site)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the resolved run plan without executing."
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignore refresh TTLs; re-run every node in the subgraph."
    ),
) -> None:
    """Run an entry's producer plus its prerequisites, in dependency order (#1021).

    Resolves the ``depends_on`` subgraph rooted at ENTRY_ID (upstream-first), skips nodes
    still within their refresh TTL (unless --force), expands ``{site}``, and invokes each
    ``producer.command`` as a ``watermark`` subprocess — aborting on the first failure. The
    machine-readable ordering that used to live only in the onboarding prose (epic #1019).
    """
    from watermark.catalog import get_entry
    from watermark.catalog.runner import execute_plan, plan

    if site and site not in SITES:
        raise typer.BadParameter(
            f"unknown site {site!r}; known: {sorted(SITES)}", param_hint="--site"
        )
    resolved_site = site or get_settings().site
    try:
        steps = plan(entry_id, site=resolved_site, force=force)
    except KeyError as exc:
        # subgraph_order raises KeyError for both an unknown root and an unresolved depends_on
        # target. Only the former is a bad user argument; the latter is a broken catalog graph.
        if get_entry(entry_id) is None:
            raise typer.BadParameter(
                f"unknown catalog entry {entry_id!r}", param_hint="entry_id"
            ) from exc
        console.print(
            f"[red]{exc.args[0]}[/] — broken dependency graph (`watermark catalog check`)."
        )
        raise typer.Exit(1) from exc
    except ValueError as exc:  # a dependency cycle — a `catalog check` failure
        console.print(f"[red]{exc}[/] — fix the graph (`watermark catalog check`).")
        raise typer.Exit(1) from exc

    action_colors = {"run": "green", "skip-fresh": "dim", "virtual": "dim"}
    console.print(f"Plan ({len(steps)} entries, topological order, site={resolved_site}):")
    for i, step in enumerate(steps, 1):
        cmd = f"watermark {step.command}" if step.command else "—"
        color = action_colors[step.action]
        console.print(f"  {i}. [{color}]{step.entry_id}[/]  {cmd}  [dim]({step.reason})[/]")
    if dry_run:
        console.print("[dim]dry-run — nothing executed.[/]")
        return

    report = execute_plan(steps, site=resolved_site)
    console.print(
        f"\nran {report.count('ran')} · fresh-skipped {report.count('fresh')} · "
        f"virtual {report.count('virtual')} · failed {report.count('failed')} · "
        f"aborted {report.count('aborted')}"
    )
    failed = report.failed
    if failed is not None:
        exit_note = (
            f"exited {failed.exit_code}"
            if failed.exit_code is not None
            else "did not run to completion (timeout/spawn error)"
        )
        console.print(
            f"[red]failed:[/] {failed.step.entry_id} "
            f"(`watermark {failed.step.command}` {exit_note})"
        )
        raise typer.Exit(1)


@catalog_app.command("validate")
def catalog_validate() -> None:
    """Structurally validate the catalog (schema + scope/id path match + unique ids).

    The model-layer half of the gate; the fuller missing/orphan/staleness checks land with
    ``watermark catalog check`` (issue #626) once ``reconcile`` supplies the observed snapshot.
    """
    from watermark.catalog import validate_entries

    findings = validate_entries()
    if not findings:
        from watermark.catalog import load_entries

        console.print(f"[green]catalog: valid[/] — {len(load_entries())} entries, no findings.")
        return
    table = Table("entry", "issue", "detail")
    for f in findings:
        table.add_row(f.entry_id, f"[red]{f.kind}[/]", f.detail)
    console.print(table)
    raise typer.Exit(1)


@catalog_app.command("backfill")
def catalog_backfill_cmd(
    scope: str = typer.Option("", "--scope", help="Restrict to one scope (reference | extracted)."),
    only: str = typer.Option("", "--only", help="Restrict to entry ids with this prefix."),
    apply: bool = typer.Option(
        False, "--apply", help="Write the stubs (default: dry-run, show what would change)."
    ),
) -> None:
    """Idempotently scaffold catalog entries from committed data/reference + data/extracted.

    Groups files into logical datasets (per-site files collapse onto a {site} template),
    enriches each with a producer hint + embedded meta.source, and writes needs-review stubs.
    Reviewed entries are never touched; needs-review entries are refreshed with prose preserved.
    """
    from watermark.catalog.backfill import BACKFILL_SCOPES, backfill

    scopes = tuple(s for s in BACKFILL_SCOPES if s == scope) if scope else BACKFILL_SCOPES
    if scope and not scopes:
        raise typer.BadParameter(f"scope must be one of {BACKFILL_SCOPES}", param_hint="--scope")
    actions = backfill(scopes=scopes, only=only or None, apply=apply)
    colors = {
        "create": "green",
        "refresh": "yellow",
        "skip-reviewed": "dim",
        "skip-unchanged": "dim",
    }
    table = Table("action", "id", "scope", "detail")
    for a in actions:
        table.add_row(f"[{colors[a.action]}]{a.action}[/]", a.id, a.scope, a.detail)
    console.print(table)
    counts: dict[str, int] = {}
    for a in actions:
        counts[a.action] = counts.get(a.action, 0) + 1
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    mode = "[green]applied[/]" if apply else "[dim]dry-run (use --apply to write)[/]"
    console.print(f"\n{summary}  —  {mode}")


@catalog_app.command("reconcile")
def catalog_reconcile_cmd(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Compute the snapshot but don't write _observed.yaml."
    ),
) -> None:
    """Observe the catalog's storage on disk → data/catalog/_observed.yaml (offline).

    The declared-vs-observed split's observed half: stat + sha256 + LFS-materialization +
    freshness for every entry. Reconcile observes; `watermark catalog check` (#626) gates on it.
    """
    from watermark.catalog.reconcile import reconcile, write_observed

    snapshot = reconcile()
    n = len(snapshot.entries)
    missing = [e for e in snapshot.entries.values() if not e.exists]
    unmaterialized = [e for e in snapshot.entries.values() if not e.lfs_materialized]
    stale = [e for e in snapshot.entries.values() if e.stale]
    console.print(
        f"reconciled {n} entries — "
        f"[red]{len(missing)} missing[/] · "
        f"[yellow]{len(unmaterialized)} lfs-unmaterialized[/] · "
        f"[yellow]{len(stale)} stale[/]"
    )
    if dry_run:
        console.print("[dim]dry-run — _observed.yaml not written.[/]")
        return
    path = write_observed(snapshot)
    console.print(f"[green]wrote[/] {path.relative_to(get_settings().data_dir.parent)}")


def _fmt_value(field: str, value: object) -> str:
    """Compact one FieldChange side for the git-status-style summary."""
    if value is None:
        return "—"
    if field in ("sha256",) and isinstance(value, str) and len(value) > 8:
        return f"{value[:7]}…"
    return str(value)


_CHANGE_LABELS = {"file_count": "files"}


def _fmt_change(field: str, before: object, after: object) -> str:
    label = _CHANGE_LABELS.get(field, field)
    return f"{label} {_fmt_value(field, before)} → {_fmt_value(field, after)}"


@catalog_app.command("diff")
def catalog_diff_cmd(
    site: str = typer.Option(
        "", "--site", help="Scope to entries relevant to a site slug (slug-scoped + basin-shared)."
    ),
    as_json: bool = typer.Option(False, "--json", help="Dump the DiffEntry list for scripting."),
) -> None:
    """Diff the committed _observed.yaml snapshot against a fresh live reconcile (observes only).

    The `git diff` analogue to reconcile's `git add`: after a producer/connector run, see which
    entries' content, membership, or freshness moved before committing the new snapshot. Distinct
    from `watermark catalog check` (the declared-vs-disk gate) — this compares snapshot-vs-disk,
    never gates, and always exits 0. A clean tree prints "in sync."
    """
    from watermark.catalog.diff import diff
    from watermark.catalog.reconcile import load_observed

    if site and site not in SITES:
        raise typer.BadParameter(
            f"unknown site {site!r}; known: {sorted(SITES)}", param_hint="--site"
        )
    diffs = diff(site=site or None)

    if as_json:
        console.print_json(data=[d.model_dump() for d in diffs])
        return

    no_snapshot = load_observed() is None
    if no_snapshot:
        console.print(
            "[yellow]no snapshot[/] — every entry shows as added; "
            "run `watermark catalog reconcile` to record a baseline."
        )

    if not diffs:
        # "in sync" only means something against a real baseline — with no snapshot (and no
        # entries) the hint above already stands, so don't also claim parity.
        if not no_snapshot:
            console.print("[green]in sync[/] — snapshot matches live disk.")
        return

    sigils = {"added": "[green]+[/]", "removed": "[red]-[/]", "changed": "[yellow]~[/]"}
    width = max(len(d.id) for d in diffs)
    for d in diffs:
        summary = ", ".join(_fmt_change(c.field, c.before, c.after) for c in d.changes)
        console.print(f"  {sigils[d.status]} {d.id:<{width}}  [dim]{summary}[/]")
    counts: dict[str, int] = {}
    for d in diffs:
        counts[d.status] = counts.get(d.status, 0) + 1
    console.print("\n" + " · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


@catalog_app.command("render")
def catalog_render_cmd(
    only: str = typer.Option("", "--only", help="Restrict to one reference collection."),
    apply: bool = typer.Option(
        False, "--apply", help="Write the READMEs (default: dry-run, show what would change)."
    ),
) -> None:
    """Generate the data/reference/<collection>/README.md facts block from the catalog.

    Additive + prose-preserving: injects a marker-delimited generated block (files, regen
    command, source, license, access tier, refresh) and leaves all other prose untouched. A
    collection opts in the first time it is rendered; `watermark catalog check` then gates its drift.
    """
    from watermark.catalog.render import render

    actions = render(only=only or None, apply=apply)
    colors = {"added": "green", "updated": "yellow", "unchanged": "dim", "no-readme": "red"}
    table = Table("action", "collection", "readme")
    for a in actions:
        table.add_row(f"[{colors[a.action]}]{a.action}[/]", a.collection, a.relpath)
    console.print(table)
    counts: dict[str, int] = {}
    for a in actions:
        counts[a.action] = counts.get(a.action, 0) + 1
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    mode = "[green]applied[/]" if apply else "[dim]dry-run (use --apply to write)[/]"
    console.print(f"\n{summary}  —  {mode}")


@catalog_app.command("check")
def catalog_check_cmd(
    strict: bool = typer.Option(
        False, "--strict", help="Promote staleness from a warning to a failure."
    ),
) -> None:
    """Validate the catalog + gate on drift (schema · missing · orphan · stale · checksum).

    The CI-enforced successor to the manual corpus-completeness audit. Exits non-zero on any
    error finding; warnings (unmaterialized LFS, staleness without --strict) print but pass.
    """
    from watermark.catalog.check import check, errors

    findings = check(strict=strict)
    if not findings:
        console.print("[green]catalog: clean[/] — no findings.")
        return
    table = Table("severity", "kind", "subject", "detail")
    for f in findings:
        color = "red" if f.severity == "error" else "yellow"
        table.add_row(f"[{color}]{f.severity}[/]", f.kind, f.subject, f.detail)
    console.print(table)
    errs = errors(findings)
    n_err, n_warn = len(errs), len(findings) - len(errs)
    console.print(f"\n[red]{n_err} error(s)[/] · [yellow]{n_warn} warning(s)[/]")
    if errs:
        raise typer.Exit(1)


@catalog_app.command("producer-check")
def catalog_producer_check_cmd(
    base: str = typer.Option("origin/main", "--base", help="Diff base ref (default: origin/main)."),
) -> None:
    """Fail if a producer changed without its catalog entry (the producer→entry drift gate).

    Maps a changed connector module (producer.connector_ref) to its catalog entries; if the
    producer changed in the diff vs --base but none of its entries did, that's drift. Bypass
    with a `[catalog-waiver: <reason>]` token in a commit message. Skips cleanly (passes) when
    the base ref isn't available (e.g. a shallow checkout), so it never false-fails.
    """
    from watermark.catalog.producer import run_producer_check

    result = run_producer_check(base=base)
    if result.status == "skipped":
        console.print(f"[dim]producer-check skipped — {result.detail}[/]")
        return
    if result.status == "clean":
        console.print("[green]producer-check: clean[/] — no producer changed without its entry.")
        return
    table = Table("connector_ref", "changed source", "expected entry touched")
    for f in result.findings:
        table.add_row(f.connector_ref, f.source, ", ".join(f.expected_entries))
    console.print(table)
    if result.status == "waived":
        console.print(f"\n[yellow]waived[/] — [catalog-waiver: {result.detail}] (logged for audit)")
        return
    console.print(
        f"\n[red]{len(result.findings)} producer(s) changed without a catalog update.[/] "
        "Update the entry (`watermark catalog backfill --apply` then review) or add "
        "`[catalog-waiver: <reason>]` to a commit message."
    )
    raise typer.Exit(1)


@catalog_app.command("audit")
def catalog_audit_cmd(
    apply: bool = typer.Option(
        False, "--apply", help="Write data/catalog/COMPLETENESS.md (default: dry-run summary)."
    ),
) -> None:
    """Generate the corpus completeness integrity audit from the catalog + reconcile snapshot.

    The automated half of the corpus-completeness audit: existence + freshness for every
    catalogued dataset, rendered to data/catalog/COMPLETENESS.md (the substantive "what was
    withheld" half stays human-authored). Reads the committed snapshot, so it's content-stable;
    `watermark catalog check` gates the committed report's drift.
    """
    from watermark.catalog.audit import build_audit, write_audit

    report = build_audit()
    console.print(
        f"[bold]{report.total}[/] datasets — [green]{report.present}[/] fresh · "
        f"[yellow]{report.stale}[/] stale · [red]{report.missing}[/] missing · "
        f"{report.unmaterialized} LFS-pointer · {report.unobserved} unobserved "
        f"(snapshot {report.reconciled_at or 'none'})"
    )
    if apply:
        relpath, changed = write_audit()
        state = "[green]written[/]" if changed else "[dim]unchanged[/]"
        console.print(f"{state}  data/{relpath}")
    else:
        console.print("[dim]dry-run — use --apply to write data/catalog/COMPLETENESS.md[/]")
