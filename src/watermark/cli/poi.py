from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import (
    Settings,
    console,
    get_settings,
    poi_app,
    repo_fixtures_dir,
)


@poi_app.command("list")
def poi_list(
    tracked: bool = typer.Option(False, "--tracked", help="Only POIs that feed imagery tracking."),
) -> None:
    """List the curated POI store (place, kind, research depth, tracking)."""
    from watermark.poi import load_pois

    pois = load_pois()
    if tracked:
        pois = [p for p in pois if p.tracked]
    if not pois:
        console.print("[yellow]No POIs[/] — the store at data/entities/poi/ is empty.")
        raise typer.Exit(1)
    table = Table("slug", "kind", "depth", "tracked", "parcels", "located")
    for p in pois:
        table.add_row(
            p.slug,
            p.kind,
            p.depth,
            "✓" if p.tracked else "",
            str(len(p.front.parcels)),
            "✓" if p.bbox else "",
        )
    console.print(table)
    console.print(
        f"[dim]{len(pois)} POIs — {sum(1 for p in pois if p.tracked)} watched/tracked.[/]"
    )


@poi_app.command("show")
def poi_show(slug: str = typer.Argument(..., help="POI slug (see `watermark poi list`).")) -> None:
    """Show one POI: its frontmatter (identity, location, tracking) and body."""
    from watermark.poi import load_poi

    poi = load_poi(slug)
    if poi is None:
        console.print(f"[red]No such POI:[/] {slug}")
        raise typer.Exit(1)
    f = poi.front
    console.print(f"[bold]{f.name}[/] [dim]({poi.slug})[/] — {f.kind}, depth=[bold]{f.depth}[/]")
    if f.parcels:
        console.print(f"  parcels: {', '.join(f.parcels)}")
    if f.members:
        console.print(f"  members: {', '.join(f.members)}")
    if f.location:
        loc = f.location
        bbox = ", ".join(f"{c:.4f}" for c in loc.bbox) if loc.bbox else "—"
        console.print(
            f"  location: method={loc.method or '—'} confidence={loc.confidence or '—'} "
            f"asof={loc.asof or '—'} bbox=[{bbox}]"
        )
    if f.track and f.track.enabled:
        console.print(
            f"  [green]tracked[/]: collections={', '.join(f.track.collections) or '—'} "
            f"since={f.track.since or '—'}"
        )
    if f.citations:
        console.print("  citations:")
        for c in f.citations:
            console.print(f"    - {c}")
    if poi.body:
        console.print(f"\n{poi.body}")


@poi_app.command("discover")
def poi_discover(
    kind: str | None = typer.Option(None, "--kind", help="Filter: parcel-id | address | feature."),
    uncovered: bool = typer.Option(
        False, "--uncovered", help="Only references the POI store doesn't cover yet."
    ),
    no_names: bool = typer.Option(
        False, "--no-names", help="Skip the entity-graph facility/business-name pass."
    ),
    limit: int = typer.Option(40, "--limit", help="Max rows to show."),
    out: str | None = typer.Option(
        None, "--out", help="Write the full candidate list to this YAML path."
    ),
) -> None:
    """Scan the corpus for place references → POI candidates.

    Read-only worklist: the *uncovered* parcel-id candidates are places cited in the
    corpus that are not yet POIs. Promoting a candidate to a curated POI is a manual step.
    Addresses and facility/business names (entity-graph verified, emitted as ``feature``
    for the GNIS funnel) are leads to verify, not precise extractions.
    """
    import yaml

    from watermark.poi import discover_candidates

    cands = discover_candidates(names=not no_names)
    if kind:
        cands = [c for c in cands if c.kind == kind]
    if uncovered:
        cands = [c for c in cands if not c.covered]
    if not cands:
        console.print("[yellow]No candidates.[/]")
        raise typer.Exit(1)

    n_parcel = sum(1 for c in cands if c.kind == "parcel-id")
    n_addr = sum(1 for c in cands if c.kind == "address")
    n_feat = sum(1 for c in cands if c.kind == "feature")
    n_unc = sum(1 for c in cands if c.kind == "parcel-id" and not c.covered)
    table = Table("kind", "value", "occ", "sources", "covered")
    for c in cands[:limit]:
        table.add_row(
            c.kind, c.value, str(c.occurrences), str(len(c.citations)), "✓" if c.covered else ""
        )
    console.print(table)
    if len(cands) > limit:
        console.print(f"[dim]… {len(cands) - limit} more (raise --limit or use --out).[/]")
    console.print(
        f"[dim]{len(cands)} candidates — {n_parcel} parcel-id ({n_unc} uncovered), "
        f"{n_addr} address, {n_feat} feature.[/]"
    )

    if out:
        doc = {"candidates": [c.model_dump() for c in cands]}
        Path(out).write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), "utf-8")
        console.print(f"[green]Wrote[/] {out}")


def _poi_offline_settings() -> Settings:
    """Settings that serve committed POI + parcel fixtures only (never touch the network)."""
    return Settings(
        poi_offline=True,
        poi_fixtures_dir=repo_fixtures_dir("poi"),
        hydro_offline=True,
        hydro_fixtures_dir=repo_fixtures_dir("hydrology"),
    )


@poi_app.command("resolve")
def poi_resolve(
    value: str = typer.Argument(..., help="A parcel id, or an address (qualify with city/state)."),
    kind: str | None = typer.Option(
        None, "--kind", help="parcel-id | address | coord (default: inferred from the value)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use committed fixtures only; never touch the network."
    ),
) -> None:
    """Resolve a place reference to a canonical Allen County parcel (the resolve funnel).

    A parcel id resolves exactly (auto-mergeable); an address is geocoded (US Census) then
    snapped to the containing parcel — a *proposal* (confirm before merging), because
    geocoding an under-qualified address can match the wrong place.
    """
    import re

    from watermark.poi import resolve_value

    settings = _poi_offline_settings() if offline else get_settings()
    inferred = (
        "parcel-id" if re.fullmatch(r"\d{2}-\d{4}-\d{2}-\d{3}\.\d{3}", value.strip()) else "address"
    )
    r = resolve_value(kind or inferred, value, settings=settings)

    badge = {"high": "green", "medium": "yellow", "low": "yellow", "none": "red"}[r.confidence]
    console.print(
        f"[bold]{value}[/] → method=[bold]{r.method}[/] confidence=[{badge}]{r.confidence}[/] "
        f"auto_mergeable={r.auto_mergeable}"
    )
    if r.matched_address:
        console.print(f"  match: {r.matched_address}  {r.point}")
    if r.parcel:
        p = r.parcel
        console.print(
            f"  parcel: [bold]{r.parcel_no}[/]  owner={p.owner!r}  "
            f"situs={p.situs_address!r}  acres={p.acres}"
        )
    elif r.fallback_key:
        console.print(f"  key: [bold]{r.fallback_key}[/]  (non-parcel identity)")
    if r.note:
        console.print(f"  [dim]{r.note}[/]")


@poi_app.command("merge")
def poi_merge(
    addresses: bool = typer.Option(
        False, "--addresses", help="Also resolve address candidates (slower; geocoded)."
    ),
    status: str | None = typer.Option(
        None, "--status", help="Filter: auto | review | covered | unresolved."
    ),
    limit: int = typer.Option(40, "--limit", help="Max groups to show."),
    out: str | None = typer.Option(
        None, "--out", help="Write the full merge plan to this YAML path."
    ),
) -> None:
    """Resolve + block discovered candidates into deduplicated place groups (the dedup plan).

    Each group is one canonical parcel with the surface forms that resolve to it.
    ``auto`` = identity fixed by an exact parcel-id (promotable); ``review`` = rests on a
    geocode (confirm); ``covered`` = already a POI. Hits the network to resolve (cached).
    """
    import yaml

    from watermark.poi import merge_corpus

    groups = merge_corpus(parcel_ids_only=not addresses)
    if status:
        groups = [g for g in groups if g.status == status]
    if not groups:
        console.print("[yellow]No groups.[/]")
        raise typer.Exit(1)

    counts: dict[str, int] = {}
    for g in groups:
        counts[g.status] = counts.get(g.status, 0) + 1
    table = Table("status", "parcel", "owner", "members", "citations")
    for g in groups[:limit]:
        owner = g.parcel.owner if g.parcel else None
        cites = sum(len(m.citations) for m in g.members)
        table.add_row(
            g.status, g.parcel_no or "—", (owner or "—")[:28], str(len(g.members)), str(cites)
        )
    console.print(table)
    if len(groups) > limit:
        console.print(f"[dim]… {len(groups) - limit} more (raise --limit or use --out).[/]")
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    console.print(f"[dim]{len(groups)} groups — {summary}.[/]")

    if out:
        doc = {"groups": [g.model_dump() for g in groups]}
        Path(out).write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), "utf-8")
        console.print(f"[green]Wrote[/] {out}")


@poi_app.command("curate")
def poi_curate(
    parcel_no: str = typer.Argument(..., help="A parcel number cited in the corpus."),
    write: bool = typer.Option(
        False,
        "--write",
        help="Write the scaffold to data/entities/poi/ (default: dry-run preview).",
    ),
    force: bool = typer.Option(False, "--force", help="Re-scaffold even if a POI exists."),
) -> None:
    """Scaffold a POI profile for a parcel from its corpus surface forms (the promotion step).

    Resolves the parcel + gathers its cited surface forms, then scaffolds a `data/entities/poi/`
    profile at depth `located`. Promotion is a human step: review the dry-run, `--write`
    it, then hand-edit `depth`/relationships and add a tracking `bbox` to make it `watched`.
    """
    from datetime import date

    from watermark.hydrology.connectors.allen_gis import normalize_parcel_id
    from watermark.poi import discover_candidates, merge_candidates
    from watermark.poi.curate import CurateError, profile_text, scaffold_from_group, write_profile

    settings = get_settings()
    target = normalize_parcel_id(parcel_no)
    cands = [
        c
        for c in discover_candidates(settings=settings)
        if c.kind == "parcel-id" and c.normalized == target
    ]
    if not cands:
        console.print(f"[red]Parcel {parcel_no} is not cited in the corpus[/] (no parcel-id).")
        raise typer.Exit(1)

    group = next(
        (g for g in merge_candidates(cands, settings=settings) if g.parcel_no == target), None
    )
    if group is None or group.parcel is None:
        console.print(f"[red]Could not resolve parcel {parcel_no} in CAMA.[/]")
        raise typer.Exit(1)
    if group.covered and not force:
        console.print(
            f"[yellow]Parcel {parcel_no} is already a POI[/] — pass --force to re-scaffold."
        )
        raise typer.Exit(1)

    front, body = scaffold_from_group(group, asof=date.today().isoformat())
    if not write:
        console.print(profile_text(front, body))
        console.print("[dim](dry run — pass --write to commit to data/entities/poi/)[/]")
        return
    try:
        path = write_profile(front, body, settings=settings, force=force)
    except CurateError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Wrote[/] {path}  [dim](review + promote depth before publishing)[/]")
