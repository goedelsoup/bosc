"""``watermark candidates`` — assemble the international data-center candidates register
(#1393 track A, epic #1387).

A thin wrapper over :mod:`watermark.international.register`: parse args → ``get_settings()`` →
sweep the AOIs → write the structured YAML and its generated prose peer → render a summary.
"""

from __future__ import annotations

import typer
from rich.table import Table

from watermark.cli._base import app, console, offline_settings, wrote
from watermark.international.aois import AOIS
from watermark.international.model import CORROBORATION_RADIUS_M
from watermark.international.register import (
    DEFAULT_SCOPE,
    build_register,
    register_path,
    render_register,
    save_register,
)


@app.command(name="candidates")
def candidates(
    # Comma-separated rather than repeatable: a `list[str]` parameter with a `typer.Option`
    # default trips ruff B008, the same wart the root CLAUDE.md documents for `Path`, and the
    # sanctioned fix is to type the option `str` and convert in the body.
    aoi: str = typer.Option(
        "",
        "--aoi",
        help="Comma-separated AOI slugs to sweep. Default: every registered AOI.",
    ),
    scope: str = typer.Option(
        DEFAULT_SCOPE,
        "--scope",
        help="Register scope — names which slice of the funnel produced it.",
    ),
    asof: str = typer.Option(
        "",
        "--asof",
        help="ISO date stamped as generated_at. Default: today (UTC).",
    ),
    radius_m: float = typer.Option(
        CORROBORATION_RADIUS_M,
        "--radius-m",
        help="Corroboration radius in metres — the stated screening parameter.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Serve committed priors fixtures only; never fetch."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Sweep and summarize without writing the register."
    ),
) -> None:
    """Sweep the open discovery priors (PeeringDB + OSM) across the international AOIs and write
    the seeded candidates register.

    Every entry is [reference] — this relays what published registers say and reports where two
    independent ones agree. Nothing here is [verified], and operator attribution is cited or
    [open]. Negative AOIs are recorded as results, not omitted.
    """
    from datetime import UTC, datetime

    slugs = [s.strip() for s in aoi.split(",") if s.strip()]
    unknown = [slug for slug in slugs if slug not in AOIS]
    if unknown:
        raise typer.BadParameter(
            f"unknown AOI(s) {unknown}; registered: {sorted(AOIS)}", param_hint="--aoi"
        )

    settings = offline_settings("priors", offline)
    generated_at = asof or datetime.now(UTC).date().isoformat()
    record = build_register(
        generated_at=generated_at,
        scope=scope,
        aoi_slugs=slugs or None,
        radius_m=radius_m,
        settings=settings,
    )

    table = Table(title=f"International data-center candidates — {scope} ({generated_at})")
    table.add_column("AOI")
    table.add_column("PeeringDB", justify="right")
    table.add_column("OSM", justify="right")
    table.add_column("Candidates", justify="right")
    table.add_column("Corroborated", justify="right")
    for result in record.aois:
        counts = result.observations_by_source
        table.add_row(
            result.label,
            str(counts.get("peeringdb", 0)),
            str(counts.get("osm", 0)),
            str(result.candidate_count),
            f"[bold]{result.corroborated_count}[/]" if result.corroborated_count else "[dim]0[/]",
        )
    console.print(table)

    attributed = sum(1 for c in record.corroborated if c.attribution.operator is not None)
    console.print(
        f"{len(record.corroborated)} corroborated of {len(record.candidates)} clusters; "
        f"{attributed} carry a cited operator, "
        # `\[` escapes Rich's markup parser — an unescaped `[open]` reads as a style tag and the
        # tag vocabulary disappears from the one line that reports it.
        rf"{len(record.corroborated) - attributed} are \[open]."
    )
    for result in record.negative_aois:
        console.print(f"[yellow]negative[/] {result.label} — swept, no corroborated candidate.")

    if dry_run:
        console.print("[dim]--dry-run: nothing written.[/]")
        return

    yaml_path = register_path(settings, scope)
    save_register(record, yaml_path)
    wrote(yaml_path)

    prose_path = register_path(settings, scope, suffix="md")
    prose_path.write_text(render_register(record), encoding="utf-8")
    wrote(prose_path)


@app.command(name="candidate-aois")
def candidate_aois() -> None:
    """List the registered international AOIs and the stated basis for sweeping each."""
    for slug, area in AOIS.items():
        console.print(f"[bold]{slug}[/] — {area.label} ({area.country})")
        console.print(f"  bbox: {area.bbox}")
        console.print(f"  [dim]{area.selection_basis}[/]\n")


__all__ = ["candidate_aois", "candidates"]
