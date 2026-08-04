"""``watermark oepa`` — OEPA/DAM document discovery and fetch.

Sub-commands:

    watermark oepa discover <slug>        # DDG site-search; writes discovery manifest
    watermark oepa fetch [manifest] ...   # Download permits from manifest or bare IDs
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.table import Table

from watermark.cli._base import console, get_settings, oepa_app, wrote
from watermark.sites import SITES


@oepa_app.command(name="discover")
def discover(
    slug: str = typer.Argument(..., help="Site slug (e.g. 'lima', 'van-wert')."),
    extra_terms: Annotated[
        list[str] | None,
        typer.Option(
            "--term", help="Additional search keyword appended to the place query (repeatable)."
        ),
    ] = None,
    out: str | None = typer.Option(
        None,
        "--out",
        help="Output directory for the manifest (default: data/research/oepa-discovery-<slug>-<date>).",
    ),
    offline: bool = typer.Option(False, "--offline", help="Skip network; return empty results."),
) -> None:
    """Search for OEPA/DAM documents for a site and write a discovery manifest.

    Queries Google (via Serper) with the site's place name and county, filtered
    to ``dam.assets.ohio.gov`` PDF results.  Results are annotated ``known`` (in
    the site's ``npdes_permits`` list), ``committed`` (already on disk under
    ``data/documents/oepa/<slug>/``), or ``new``.  The manifest is written to
    ``data/research/oepa-discovery-<slug>-<date>/`` for human review — no files
    are downloaded.
    """
    from datetime import UTC, datetime

    from watermark.config import Settings
    from watermark.oepa.discovery import discover_dam_documents

    if slug not in SITES:
        raise typer.BadParameter(
            f"unknown site {slug!r}; known: {sorted(SITES)}", param_hint="slug"
        )

    prof = SITES[slug]
    settings = get_settings()
    if offline:
        settings = Settings(civic_offline=True)

    # county_name may include state suffix ("Allen County, OH") — strip it for search
    county_raw = prof.county_name
    county = county_raw.split(",")[0].strip()

    docs = discover_dam_documents(
        prof.place,
        county,
        basin=prof.basin,
        extra_terms=extra_terms or None,
        settings=settings,
    )

    # Annotate results
    known_ids = set(prof.npdes_permits)
    doc_dir = settings.documents_dir / "oepa" / slug
    committed_files = {p.name for p in doc_dir.glob("*.pdf")} if doc_dir.exists() else set()

    results = []
    for d in docs:
        committed = (
            d.filename_on_disk(slug) in committed_files
            if hasattr(d, "filename_on_disk")
            else Path(d.url).name in committed_files
        )
        status = "committed" if committed else ("known" if d.permit_id in known_ids else "new")
        results.append({**d.model_dump(), "status": status})

    # Summary table
    table = Table("permit_id", "doc_type", "status", "url")
    for r in results:
        color = {"new": "green", "known": "dim", "committed": "blue"}.get(r["status"], "")
        table.add_row(
            f"[{color}]{r['permit_id']}[/]" if color else r["permit_id"],
            r["doc_type"],
            r["status"],
            r["url"][:72],
        )
    console.print(table)

    new_count = sum(1 for r in results if r["status"] == "new")
    console.print(
        f"\n[bold]{len(results)}[/] result(s) — "
        f"[green]{new_count} new[/], "
        f"{sum(1 for r in results if r['status'] == 'known')} known, "
        f"{sum(1 for r in results if r['status'] == 'committed')} committed."
    )

    if not results:
        console.print(
            "[dim]No DAM documents found. Try --term with a permit ID or check online mode.[/]"
        )
        return

    # Write manifest
    today = datetime.now(UTC).date().isoformat()
    if out:
        out_dir = Path(out)
    else:
        out_dir = settings.data_dir / "research" / f"oepa-discovery-{slug}-{today}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.yaml"

    manifest = {
        "meta": {
            "subject": f"OEPA/DAM document discovery — {slug}",
            "site": slug,
            "place": prof.place,
            "county": county,
            "generated_at": today,
            "counts": {
                "total": len(results),
                "new": new_count,
                "known": sum(1 for r in results if r["status"] == "known"),
                "committed": sum(1 for r in results if r["status"] == "committed"),
            },
        },
        "results": results,
    }
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    wrote(manifest_path)


@oepa_app.command(name="fetch")
def fetch(
    manifest: str | None = typer.Argument(
        None,
        help="Path to a discovery manifest written by 'watermark oepa discover'.",
    ),
    permit_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--permit-id",
            help="Bare NPDES permit ID to fetch from the DAM (repeatable; constructs URL automatically).",
        ),
    ] = None,
    slug: str | None = typer.Option(
        None,
        "--site",
        help="Site slug for the destination directory (default: inherits from --site on the root app).",
    ),
    all_statuses: bool = typer.Option(
        False,
        "--all",
        help="Also fetch 'known' and 'committed' results (default: new-only).",
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help="Destination directory (default: data/documents/oepa/<site-slug>/).",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Dry-run: skip network fetch and report what would be downloaded."
    ),
) -> None:
    """Download OEPA/DAM permit PDFs from a discovery manifest or bare permit IDs.

    Reads ``new`` results from a manifest (use ``--all`` to include known/committed),
    or constructs DAM URLs from ``--permit-id`` arguments.  Files land in
    ``data/documents/oepa/<site>/`` with as-received names; provenance is recorded in
    ``filename-map.yaml``.  Run ``watermark ingest`` + ``watermark extract`` afterward.
    """
    from watermark.oepa.fetch import dam_url, fetch_one, update_filename_map

    settings = get_settings()

    ids = permit_ids or []
    if not manifest and not ids:
        raise typer.BadParameter("Provide a manifest path or at least one --permit-id.")

    # Collect URLs to fetch
    urls: list[tuple[str, str | None]] = []  # (url, permit_id)

    if manifest:
        mp = Path(manifest)
        if not mp.exists():
            raise typer.BadParameter(f"manifest not found: {mp}", param_hint="manifest")
        data = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
        site_slug: str = slug or str(data.get("meta", {}).get("site", settings.site))
        for r in data.get("results", []):
            if all_statuses or r.get("status") == "new":
                urls.append((r["url"], r.get("permit_id")))
    else:
        site_slug = slug or settings.site

    for bare_id in ids:
        urls.append((dam_url(bare_id), bare_id))

    if not urls:
        console.print(
            "[yellow]Nothing to fetch (no 'new' results in manifest; use --all to override).[/]"
        )
        return

    dest = Path(out) if out else (settings.documents_dir / "oepa" / site_slug)
    dest.mkdir(parents=True, exist_ok=True)
    map_path = dest / "filename-map.yaml"

    if offline:
        console.print(f"[dim]--offline: would fetch {len(urls)} file(s) to {dest}[/]")
        for doc_url, doc_id in urls:
            console.print(f"  {doc_id or '?'}: {doc_url}")
        return

    table = Table("permit_id", "filename", "status", "bytes")
    fetched: list[object] = []
    for doc_url, doc_id in urls:
        r = fetch_one(doc_url, dest, permit_id=doc_id, settings=settings)
        fetched.append(r)
        color = {
            "downloaded": "green",
            "skipped_existing": "dim",
            "conflict": "yellow",
            "error": "red",
        }.get(r.status, "")
        table.add_row(
            r.permit_id or "?",
            r.filename or "—",
            f"[{color}]{r.status}[/]" if color else r.status,
            str(r.bytes) if r.bytes is not None else "—",
        )
    console.print(table)

    update_filename_map(fetched, map_path)  # type: ignore[arg-type]
    wrote(map_path)
    console.print(
        "\n[dim]Run 'watermark ingest' then 'watermark extract' to process the new files.[/]"
    )


@oepa_app.command(name="coverage")
def coverage(
    write: bool = typer.Option(
        False,
        "--write",
        help="Persist to data/reference/oepa/ohd000001-coverage.yaml (else print only).",
    ),
    out: str | None = typer.Option(
        None, "--out", help="Write the coverage artifact to this path instead of the default."
    ),
) -> None:
    """Resolve OHD000001 general-permit coverage for the closed-loop cohort (#1678).

    For each registered facility disclosing a recirculating/closed cooling archetype, reports
    whether it can hold coverage under Ohio EPA's data-center general permit OHD000001 and whether
    a facility-own discharge permit is on record. OHD000001 was WITHDRAWN on 2026-07-21 (it never
    left draft), so every candidate resolves to ``not_available`` — a [verified] cited absence,
    itself the finding, and a *permanent* one rather than a pending one: no coverage list will ever
    exist, so the replacement watch is an INDIVIDUAL NPDES permit (or, for a campus on a POTW
    sanitary sewer, the City's industrial-user/pretreatment permit, which is not an NPDES record at
    all). Same gate as the draft branch, categorically different finding.
    """
    from watermark.hydrology import blowdown

    settings = get_settings()
    gp, coverages = blowdown.resolve_cohort(settings=settings)

    console.print(
        f"[bold]{gp.permit_id}[/] — {gp.title}: state [yellow]{gp.state.value}[/] "
        f"(effective: {gp.effective}), asof {gp.asof}"
    )
    table = Table("site", "facility", "cooling claim", "OHD000001", "facility-own", "tag")
    for c in coverages:
        table.add_row(
            c.site,
            c.facility,
            c.cooling_claim,
            c.ohd000001_status.value,
            c.facility_own_discharge.value,
            c.tag,
        )
    console.print(table)
    console.print(f"[dim]{len(coverages)} candidate facilit(y/ies) in the closed-loop cohort.[/]")

    if write or out:
        document = blowdown.coverage_document(gp, coverages)
        path = blowdown.write_coverage(document, settings=settings, out=Path(out) if out else None)
        wrote(path)
